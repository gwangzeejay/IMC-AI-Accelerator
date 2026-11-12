"""Causal mapper/runtime with actual durable INT8/INT32 bytes and finite power.

All joules/times below are architectural assumptions, not hardware estimates.
Future harvest is used only by the source integrator, never by the policy.
"""
from collections import Counter
import json
import math
import numpy as np
from recap.power import Reservoir
from recap.metrics import summarize_inputs
from g5_storage import Store


class Interrupted(Exception):pass
class Horizon(Exception):pass


def coefficients(root,p):
    cfg=json.loads((root/'09_Simulation/configs/g2_assumed_debug.json').read_text())
    e=cfg['energy_j_per_unit'];t=cfg['seconds_per_unit']
    e['dw_mac']*=p['base_dw_compute_scale']
    e.update(controller=p['controller_cycle_j'],decision=p['decision_j'],cpu_op=1e-10)
    t.update(controller=p['controller_cycle_s'],decision=p['decision_s'],cpu_op=1e-7)
    return e,t


def geometry(p,f,size=8000):
    if size==12:return [(1,12)]
    choices=[]
    for n,co in p['tiles']:
        if f%64 and (n!=1 or co>64-f%64):continue
        n=min(n,125-f//64)
        if (n,co) not in choices:choices.append((n,co))
    return choices


class Runtime:
    def __init__(self,root,model,p,scenario,method,reserve=0.0,overhead=True,fault=None):
        self.model,self.p,self.scenario,self.method=model,p,scenario,method
        self.reserve=reserve;self.overhead=overhead;self.fault=fault;self.fault_done=False
        self.e,self.t=coefficients(root,p)
        cap=scenario['capacity_j']
        self.power=Reservoir(2*cap/(3.3**2-2.0**2),3.3,2.0,scenario['trace'],
            cap*p['initial_energy_fraction'],scenario['horizon_s'])
        self.energy=Counter();self.units=Counter();self.duration=Counter()
        self.losses=0;self.wait_s=0;self.commits=0;self.decisions=0;self.admitted_units=0
        self.max_bound=0.0;self.max_sram=0;self.max_nvm=0;self.write_ordinal=0
        self.replayed_macs=0;self.seen_compute=set();self.chosen=Counter();self.events=[]
        self.forced_plan=None;self.write_occurrences=Counter()
        self.admitted_depletions=0;self.inside_unit=False

    def charge(self,kind,units,action=None,mutation=None):
        if units<=0:return
        joules=self.e[kind]*units;seconds=self.t[kind]*units
        dt,brownout=self.power.advance(seconds,joules/seconds if seconds else 0)
        fraction=min(1.0,dt/seconds) if seconds else 1.0
        if abs(dt-seconds)<1e-12:fraction=1.0
        name=action or kind
        self.energy[name]+=joules*fraction;self.units[name]+=units*fraction
        self.duration[name]+=seconds*fraction
        if mutation is not None:mutation(fraction)
        if brownout:
            self.losses+=1
            if self.inside_unit:
                self.admitted_depletions+=1
                raise AssertionError('admitted unit depleted despite conservative reserve')
            raise Interrupted()
        if fraction<1.0:raise Horizon()

    def wait(self,bound):
        if not math.isfinite(bound) or bound<0:raise ValueError('invalid admission bound')
        if bound>self.power.capacity+1e-14:return False
        while not self.power.admit(bound,1e-12):
            dt,brown=self.power.advance(min(self.p['wait_step_s'],self.power.horizon-self.power.time),self.p['retention_w'])
            self.wait_s+=dt;self.energy['retention_wait']+=dt*self.p['retention_w'];self.duration['retention_wait']+=dt
            if brown:self.losses+=1;raise Interrupted()
            if self.power.time>=self.power.horizon-1e-12:raise Horizon()
        return True

    def bound(self,actions):return sum(self.e[k]*u for k,u,_ in actions)

    def actions(self,actions):
        bound=self.bound(actions)
        if not self.wait(bound):raise ValueError('unit exceeds reservoir capacity')
        self.admitted_units+=1;self.max_bound=max(self.max_bound,bound)
        self.inside_unit=True
        try:
            for kind,count,name in actions:self.charge(kind,count,name)
        finally:self.inside_unit=False

    def read(self,count,name):
        # Bounded streaming reads may retain already loaded SRAM while recharging.
        for start in range(0,count,512):self.actions([('read_byte',min(512,count-start),name)])

    def write(self,store,ops,payload,name,frontier=False):
        cycles=2*payload+246+int(frontier)
        nonbus=max(0,cycles-len(ops))
        # Bus service is in write_byte; only nonbus cycles extend wall time.
        # Controller dissipates during bus waits too, with separately charged energy.
        controller_cycles=nonbus+len(ops)*self.t['write_byte']/self.t['controller']
        ectrl=self.e['controller']*controller_cycles if self.overhead else 0
        bound=self.e['write_byte']*len(ops)+ectrl
        if not self.wait(bound):raise ValueError('commit cannot fit capacitor')
        self.admitted_units+=1;self.max_bound=max(self.max_bound,bound)
        if self.overhead:
            self.inside_unit=True
            try:self.charge('controller',nonbus,name+'_controller')
            finally:self.inside_unit=False
            # Zero-duration energy is avoided; bus-wait controller power is folded
            # into the write coefficient for this call, then restored.
        olde=self.e['write_byte']
        if self.overhead:self.e['write_byte']+=self.e['controller']*(controller_cycles-nonbus)/len(ops)
        count=len(ops)
        inject=False
        occurrence=self.write_occurrences[name];self.write_occurrences[name]+=1
        if self.fault is not None and not self.fault_done:
            target=self.fault.get('action')
            if (target is None or target==name) and occurrence>=self.fault.get('occurrence',0):
                cut=self.fault.get('cut',count//2)
                count=min(count,max(0,cut));inject=True
        def mutate(fraction):store.apply(ops,int(math.floor(count*fraction+1e-10)))
        before=self.energy[name]
        self.inside_unit=True
        try:self.charge('write_byte',count,name,mutate)
        finally:
            self.inside_unit=False
            self.e['write_byte']=olde
            if self.overhead:
                charged=self.energy[name]-before
                ctrl=charged*(self.e['controller']*(controller_cycles-nonbus)/len(ops))/(olde+self.e['controller']*(controller_cycles-nonbus)/len(ops))
                self.energy[name]-=ctrl;self.energy[name+'_controller_wait']+=ctrl
        self.write_ordinal+=count
        if inject:
            self.fault_done=True;self.losses+=1
            # Fault-injection energy loss is external; preserve capacitor balance.
            self.power.consumed+=self.power.energy;self.energy['injected_discharge']+=self.power.energy;self.power.energy=0
            raise Interrupted()
        self.commits+=1

    def boot(self,store):
        # Cold charging is powered off. In particular zero harvest must advance
        # time rather than causing an infinite zero-time reboot loop.
        threshold=min(self.power.capacity*.2,5e-6)
        while self.power.energy<threshold:
            self.power.advance(min(self.p['wait_step_s'],self.power.horizon-self.power.time),0,stop_at_empty=False)
            if self.power.time>=self.power.horizon-1e-12:raise Horizon()
        self.actions([('boot',1,'boot')])
        self.read(2*self.p['root_slot_bytes']+1,'boot_root')
        done,source,current=store.restore()
        if done>=0:self.read(store.scan(done)['read_bytes'],'restore_source')
        else:self.read(490,'load_feature')
        if current is not None:self.read(current['read_bytes'],'scan_destination')
        self.read(2*self.p['scratch_slot_bytes']+1,'boot_scratch')
        # CRC/parser/control cost is modeled (not a cycle proof of the graph runtime).
        if self.overhead:self.actions([('controller',256,'boot_parser')])
        return done,source,current

    def plans(self,stage,f):
        result=[]
        for n,co in geometry(self.p,f,12 if stage==5 else 8000):
            for ci in ([64] if stage in (0,5) else self.p['ci_chunks']):
                for z,ps in ([(False,False)] if ci==64 else [(a,b) for a in self.p['save_z'] for b in self.p['keep_ps']]):
                    plan=dict(n=n,co=co,ci=ci,z=z,ps=ps)
                    actions=self.compute_actions(stage,f,plan,0,need_dw=stage in (1,2,3,4))
                    out=n*co;payload=max(out,(n*64 if z else 0)+(4*out if ps else 0))
                    write_count=payload+126
                    ctrl=(2*payload+247-write_count)*self.t['controller']+write_count*self.t['write_byte']
                    bound=self.bound(actions)+write_count*self.e['write_byte']+(ctrl/self.t['controller']*self.e['controller'] if self.overhead else 0)
                    # Two separate commits (scratch then append log) need not be
                    # admitted together. This bound deliberately covers first chunk
                    # plus its possible durable record, without future harvest.
                    full=[]
                    for prefix in (range(0,64,ci) if stage in range(1,5) else [0]):
                        full+=self.compute_actions(stage,f,plan,prefix,need_dw=prefix==0)
                    ee=self.bound(full);tt=sum(self.t[k]*u for k,u,_ in full)
                    payloads=[(out,True),(out,False)]
                    if ci<64 and stage in range(1,5):
                        if ps:payloads += [((n*64 if z else 0)+4*out,False)]*(64//ci-1)
                        elif z:payloads += [(n*64,False)]
                    for payload,final in payloads:
                        writes=payload+125+int(final);cyc=2*payload+246+int(final)
                        ee+=writes*self.e['write_byte'];tt+=writes*self.t['write_byte']
                        if self.overhead:
                            tt+=(cyc-writes)*self.t['controller']
                            ee+=(cyc-writes+writes*self.t['write_byte']/self.t['controller'])*self.e['controller']
                    plan.update(bound=bound,score_energy=ee/out,score_time=tt/out)
                    # 8000-byte resident source; bounded streamed bank and tile PS.
                    sram=(8000 if stage else 490)+2048+n*64+4*out+out+384+512
                    plan['sram']=sram
                    if sram<=self.p['sram_bytes'] and bound<=self.power.capacity+1e-14:result.append(plan)
        return result

    def choose(self,stage,f):
        plans=self.plans(stage,f)
        if not plans:return None
        if self.overhead:self.actions([('decision',1,'runtime_decision')])
        self.decisions+=1
        if self.forced_plan is not None:
            n,co,ci,z,ps=self.forced_plan
            if stage in (0,5):ci,z,ps=64,False,False
            n=min(n,125-f//64) if stage!=5 else 1
            if stage==5:co=12
            chosen=next(a for a in plans if (a['n'],a['co'],a['ci'],a['z'],a['ps'])==(n,co,ci,z,ps))
        elif self.method=='B1_layer':
            # Whole layer durability is implemented by suppression of tile-log
            # publication below, using the same bounded compute tile primitive.
            eligible=plans
            chosen=min([a for a in eligible if a['ci']==64],key=lambda a:(a['score_time'],-a['n']*a['co']))
        elif self.method=='B2_fixed':
            eligible=[a for a in plans if a['n']==1 and a['co']==min(16,12 if stage==5 else 64) and a['ci']==64]
            chosen=eligible[0] if eligible else min(plans,key=lambda a:a['bound'])
        else:
            feasible=[a for a in plans if a['bound']<=self.power.energy-self.reserve*self.power.capacity+1e-14]
            if self.method=='B3_adaptive':
                # Causal spatial/CO/CI adaptation over the SAME candidate set.
                chosen=min(feasible or plans,key=lambda a:(a['score_time'],a['score_energy'],-a['ci']))
            else:
                chosen=min(feasible or plans,key=lambda a:(a['score_energy'],a['score_time'],-a['ci']))
        self.max_sram=max(self.max_sram,chosen['sram'])
        self.chosen[f"p{chosen['n']}_co{chosen['co']}_ci{chosen['ci']}_z{int(chosen['z'])}ps{int(chosen['ps'])}"]+=1
        return chosen

    def compute_actions(self,stage,f,a,prefix,need_dw=True):
        n,co,ci=a['n'],a['co'],min(a['ci'],64-prefix)
        if stage==0:return [('read_byte',co*40+co*4,'weight_load'),('bank_byte',n*40,'activation_load'),
            ('pw_mac',n*co*40,'first_conv'),('requant',n*co,'requant')]
        if stage==5:return [('read_byte',12*64+48,'weight_load'),('cpu_op',8000+64*12+12*32,'cpu_tail')]
        units=[]
        if need_dw:units += [('read_byte',576+256,'weight_load'),('bank_byte',n*9*64,'activation_load'),
            ('dw_mac',n*9*64,'dw_compute'),('requant',n*64,'dw_requant')]
        units += [('read_byte',ci*co+(co*4 if prefix==0 else 0),'weight_load'),
            ('pw_mac',n*ci*co,'pw_compute')]
        if prefix+ci==64:units += [('requant',n*co,'pw_requant')]
        return units

    def tile(self,store,stage,source,f,plan):
        n,co=plan['n'],plan['co'];p,c=divmod(f,64)
        footprint=(8000 if stage else 490)+2048+n*64+4*n*co+n*co+384+512
        self.max_sram=max(self.max_sram,footprint)
        old=store.scratch(stage,f,n,co)
        if old and old['output'] is not None:return old['output']
        if stage==0:
            self.actions(self.compute_actions(stage,f,plan,0))
            out=self.model.first(source,p,n,c,co).tobytes()
        elif stage==5:
            self.actions(self.compute_actions(stage,f,plan,0))
            out=self.model.tail(source).tobytes()
        else:
            z=None if old is None or old['z'] is None else np.frombuffer(old['z'],dtype=np.int8).reshape(n,64).copy()
            ps=self.model.bias(stage,n,c,co) if old is None or old['ps'] is None else np.frombuffer(old['ps'],dtype='<i4').reshape(n,co).copy()
            prefix=0 if old is None else old['offset']
            while prefix<64:
                end=min(64,prefix+plan['ci'])
                acts=self.compute_actions(stage,f,plan,prefix,z is None)
                key=(store.ids[1],stage,f,n,co,prefix,end)
                if key in self.seen_compute:self.replayed_macs+=sum(u for k,u,_ in acts if k in ('dw_mac','pw_mac'))
                self.seen_compute.add(key)
                self.actions(acts)
                if z is None:z=self.model.dw(stage,source,p,n)
                ps=self.model.pw(stage,z,ps,prefix,end,c,co);prefix=end
                if prefix<64 and (plan['ps'] or (plan['z'] and (old is None or old['z'] is None))):
                    keep_z=z.tobytes() if plan['z'] else old['z'] if old else None
                    keep_ps=ps.astype('<i4').tobytes() if plan['ps'] else old['ps'] if old else None
                    durable_prefix=prefix if plan['ps'] else old['offset'] if old else 0
                    ops,length=store.scratch_ops(stage,f,n,co,durable_prefix,keep_z,keep_ps)
                    self.write(store,ops,length,'checkpoint_partial')
                    old=store.scratch(stage,f,n,co)
            out=self.model.finish(stage,ps,c,co).tobytes()
        if self.method!='B1_layer':
            ops,length=store.scratch_ops(stage,f,n,co,64,out=out)
            self.write(store,ops,length,'checkpoint_output',True)
        return out

    def inference(self,store):
        while self.power.time<self.power.horizon-1e-12:
            try:
                done,source,current=self.boot(store)
                if done==5:return source.reshape(1,12)
                for stage in range(done+1,6):
                    if current is None:current=store.scan(stage)
                    f=current['frontier'];offset=current['offset'];size=len(current['array'])
                    # B1 does write outputs to NVM, but publishes durability only
                    # at layer root. A loss restarts the whole unfinished layer.
                    if self.method=='B1_layer':f=offset=0
                    while f<size:
                        plan=None
                        for n,co in geometry(self.p,f,size):
                            if self.method=='B1_layer':break
                            r=store.scratch(stage,f,n,co)
                            if r is not None:
                                # Resume durable job before choosing a new geometry.
                                plan=dict(n=n,co=co,ci=64,z=r['z'] is not None,ps=r['ps'] is not None,sram=0);break
                        if plan is None:plan=self.choose(stage,f)
                        if plan is None:return None
                        out=self.tile(store,stage,source,f,plan)
                        ops,length=store.log_ops(stage,f,plan['n'],plan['co'],offset,out)
                        self.write(store,ops,length,'layer_log')
                        f+=len(out);offset+=124+len(out)
                    # Old anchor is dead before loading the next 8000-byte anchor.
                    # Host scan arrays are semantic views, not a second resident
                    # embedded output arena. CRC is computed streaming from NVM.
                    source=None
                    scan=store.scan(stage)
                    if scan['frontier']!=size:raise AssertionError('incomplete layer publication')
                    self.read(scan['read_bytes'],'load_next_anchor')
                    flat=scan['array']
                    ops,length=store.root_ops(stage,flat.tobytes())
                    self.write(store,ops,length,'graph_root',True)
                    source=flat.reshape(1,12) if stage==5 else flat.reshape(1,25,5,64)
                    current=None
                return source
            except Interrupted:
                # All volatile arrays/plan/prefix are discarded and reconstructed.
                continue
        return None

    def run(self,inputs):
        statuses=[];outputs=[];memory=None
        for item in inputs:
            statuses.append(dict(arrival_s=item['arrival_s'],deadline_s=item['deadline_s']))
        try:
            for i,item in enumerate(inputs):
                arrival=item['arrival_s']
                if self.power.time<arrival:
                    # No active request: power off, zero modeled peripheral leakage.
                    self.power.advance(arrival-self.power.time,0,stop_at_empty=False)
                store=Store(self.model.model_hash,item['x'],self.p,invocation=f'{self.scenario["id"]}:{i}:{arrival}')
                if memory is not None:store.memory=memory
                memory=store.memory;self.max_nvm=max(self.max_nvm,store.reserved_bytes)
                out=self.inference(store)
                if out is None:break
                statuses[i]['committed_s']=self.power.time
                # Golden is queried AFTER completion, and never used in execution.
                expected=self.model.reference(item['x'])[-1]
                if not np.array_equal(out,expected):raise AssertionError('full KWS durable output mismatch')
                outputs.append(dict(input_id=item['id'],label=item['label'],prediction=int(np.argmax(out)),
                    correct=int(np.argmax(out))==item['label'],output_sha256=__import__('hashlib').sha256(out.tobytes()).hexdigest(),
                    output=out.reshape(-1).astype(int).tolist()))
        except Horizon:pass
        if self.power.time<self.power.horizon:self.power.advance(self.power.horizon-self.power.time,0,stop_at_empty=False)
        total=sum(self.energy.values())
        if abs(total-self.power.consumed)>1e-10 or abs(self.power.balance_error())>1e-10:
            raise AssertionError('energy ledger/capacitor conservation')
        metrics=summarize_inputs(statuses,self.power.horizon,total)
        return dict(method=self.method,reserve=self.reserve,scenario_id=self.scenario['id'],family=self.scenario['family'],
            seed=self.scenario['seed'],total_inputs=len(inputs),energy_j=total,**metrics,
            statuses=statuses,outputs=outputs,breakdown_j=dict(self.energy),duration_s=dict(self.duration),units=dict(self.units),
            losses=self.losses,wait_s=self.wait_s,commits=self.commits,decisions=self.decisions,
            max_admitted_bound_j=self.max_bound,admitted_units=self.admitted_units,admitted_unit_depletions=self.admitted_depletions,
            max_sram_algorithm_bytes=self.max_sram,max_nvm_reserved_bytes=self.max_nvm,
            replayed_macs=self.replayed_macs,chosen=dict(self.chosen),energy_balance_error_j=self.power.balance_error(),
            fault_executed=self.fault_done,overhead_included=self.overhead,calibrated=False)
