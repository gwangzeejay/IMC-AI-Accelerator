"""Two-workload causal event model. No calibration or physical PPA is implied."""
from collections import Counter
import bisect
import hashlib
import math
import numpy as np
from recap.power import Reservoir
from recap.metrics import summarize_inputs
from g5_runtime import coefficients,Horizon,Interrupted
from g6_storage import Store,geometry


class Capacity(Exception):pass


class Runtime:
    def __init__(self,root,model,p,scenario,method='RECAP',variant='full',backend='cim',fault=None):
        self.model,self.p,self.scenario,self.method,self.variant=model,p,scenario,method,variant
        self.backend=backend;self.fault=fault;self.fault_done=False
        self.e,self.t=coefficients(root,p)
        for k in ('read_byte','write_byte'):self.e[k]*=p.get('nvm_energy_scale',1)
        for k in ('read_byte','write_byte','bank_byte'):self.t[k]/=p.get('bandwidth_scale',1)
        for k in ('dw_mac','pw_mac','requant','cpu_op'):self.e[k]*=p.get('compute_energy_scale',1)
        if backend=='digital':
            self.e['pw_mac']*=p['digital_pw_energy_scale'];self.t['pw_mac']*=p['digital_pw_time_scale']
        self.control=variant!='no_control';self.leak=p.get('active_leakage_w',0)
        cap=scenario['capacity_j'];self.power=Reservoir(2*cap/(3.3**2-2**2),3.3,2,scenario['trace'],cap*p['initial_energy_fraction'],scenario['horizon_s'])
        self.boundaries=[t for t,_ in self.power.trace]
        self.energy=Counter();self.units=Counter();self.durations=Counter();self.choices=Counter()
        self.losses=self.admitted=self.depletions=self.commits=self.decisions=0;self.max_bound=0
        self.max_sram=self.max_nvm=0;self.wait_seconds=0;self.bank=b'';self.bank_hits=0;self.bank_misses=0
        self.active=False;self.plan_cache={};self.seen=set();self.repeated_range_macs=0
        self.aux_gen=0;self.write_occurrences=Counter();self.blocked_reason=None

    def cost(self,kind,units):return self.e[kind]*units+self.leak*self.t[kind]*units,self.t[kind]*units
    def observe(self,bound):
        if not math.isfinite(bound) or bound<0:raise ValueError('invalid bound')
        reserve=bound*(1+self.p['admission_margin_fraction'])+1e-12
        if reserve>self.power.capacity:raise Capacity('bounded work/commit exceeds capacitor')
        while self.power.energy<reserve:
            # Environment integration to a physical threshold/source boundary.
            # The policy receives ONLY current energy, never the future source.
            i=bisect.bisect_right(self.boundaries,self.power.time)-1
            current=self.power.trace[i][1];retention=self.p['retention_w']
            nexttime=self.boundaries[i+1] if i+1<len(self.boundaries) else self.power.horizon
            net=current-retention
            crossing=(reserve-self.power.energy)/net if net>0 else math.inf
            seconds=min(nexttime-self.power.time,self.power.horizon-self.power.time,crossing)
            seconds=max(min(seconds,self.power.horizon-self.power.time),1e-12)
            dt,brown=self.power.advance(seconds,retention)
            self.wait_seconds+=dt;self.energy['retention_wait']+=dt*retention;self.durations['retention_wait']+=dt
            if brown:self.losses+=1;raise Interrupted()
            if self.power.time>=self.power.horizon-1e-12:raise Horizon()

    def spend(self,energy,seconds,name,units=0,mutation=None):
        if energy<0 or seconds<0:raise ValueError('negative event')
        if seconds==0:
            if energy:raise ValueError('positive energy requires duration')
            if mutation:mutation(1.)
            return
        dt,brown=self.power.advance(seconds,energy/seconds)
        fraction=min(1.,dt/seconds)
        if abs(dt-seconds)<1e-12:fraction=1.
        self.energy[name]+=energy*fraction;self.units[name]+=units*fraction;self.durations[name]+=seconds*fraction
        if mutation:mutation(fraction)
        if brown:
            self.losses+=1;self.depletions+=1
            raise AssertionError('admitted unit depleted')
        if fraction<1:raise Horizon()

    def action(self,kind,units,name,mutation=None):
        e,t=self.cost(kind,units);self.observe(e);self.admitted+=1;self.max_bound=max(self.max_bound,e)
        self.spend(e,t,name,units,mutation)

    def read(self,count,name):
        for offset in range(0,count,512):self.action('read_byte',min(512,count-offset),name)

    def write_cost(self,length,output=False):
        writes=length+125+int(output);cycles=2*length+246+int(output);nonbus=cycles-writes
        ee,tt=self.cost('write_byte',writes)
        ctrl=(nonbus+writes*self.t['write_byte']/self.t['controller'])*self.e['controller'] if self.control else 0
        extra=nonbus*self.t['controller'] if self.control else 0
        return ee+ctrl+self.leak*extra,tt+extra,ctrl,writes

    def write(self,store,ops,length,name,output=False):
        e,t,ctrl,writes=self.write_cost(length,output)
        if len(ops)!=writes:raise AssertionError('wire length')
        self.observe(e);self.admitted+=1;self.max_bound=max(self.max_bound,e)
        count=len(ops);occurrence=self.write_occurrences[name];self.write_occurrences[name]+=1
        inject=self.fault is not None and not self.fault_done and self.fault['action']==name and occurrence>=self.fault.get('occurrence',0)
        if inject:count=min(len(ops),max(0,self.fault.get('cut',len(ops)//2)))
        # Aggregate FSM service, preserving actual byte ordering for crash images.
        fraction=count/len(ops)
        before=self.energy[name]
        try:self.spend(e*fraction,t*fraction,name,count,lambda f:store.apply(ops,math.floor(count*f+1e-9)))
        finally:
            charged=self.energy[name]-before;realized_control=ctrl*charged/e if e else 0
            self.energy[name]-=realized_control;self.energy[name+'_controller']+=realized_control
        if inject:
            self.fault_done=True;self.losses+=1
            self.energy['injected_discharge']+=self.power.energy;self.power.consumed+=self.power.energy;self.power.energy=0
            raise Interrupted()
        self.commits+=1

    def boot(self,store):
        self.bank=b''
        threshold=min(self.power.capacity*.2,5e-6)
        while self.power.energy<threshold:
            i=bisect.bisect_right(self.boundaries,self.power.time)-1;p=self.power.trace[i][1]
            boundary=self.boundaries[i+1] if i+1<len(self.boundaries) else self.power.horizon
            needed=(threshold-self.power.energy)/p if p>0 else math.inf
            dt=min(boundary-self.power.time,needed,self.power.horizon-self.power.time)
            self.power.advance(max(dt,1e-12),0,stop_at_empty=False)
            if self.power.time>=self.power.horizon-1e-12:raise Horizon()
        self.action('boot',1,'boot');self.read(2*store.root_bytes+1,'boot_root')
        done,source,current=store.restore()
        self.read(source.nbytes if done<0 else store.scan(done)['read_bytes'],'load_feature' if done<0 else 'restore_source')
        if current is not None:self.read(current['read_bytes'],'scan_destination')
        self.read(2*store.scratch_bytes+1,'boot_scratch')
        if self.variant=='all_live':self.read(2*store.aux_slot,'restore_redundant_live')
        if self.control:self.action('controller',256,'boot_parser_assumed')
        return done,source,current

    def weights(self,stage,plan,prefix,dw):
        d=self.model.stages[stage];n,co=plan['n'],plan['co'];c=plan['c'];kind=d['kind']
        result=[]
        if kind=='conv':
            w,b=self.model.weights(d['ops'][0]);return [(w[c:c+co].tobytes()+b[c:c+co].tobytes(),'weight_load')]
        if kind=='head':
            return [(b''.join(self.model.constants[int(t)].tobytes() for i in d['ops'] for t in self.model.ops[i]['inputs'][1:] if t>=0),'weight_load')]
        if kind=='dw' or (kind=='fused' and dw):
            w,b=self.model.weights(d['ops'][0]);cc=c if kind=='dw' else 0;count=co if kind=='dw' else d['ci']
            result.append((w[0,:,:,cc:cc+count].tobytes()+b[cc:cc+count].tobytes(),'weight_load'))
        if kind in ('fused','pw'):
            w,b=self.model.weights(d['ops'][-1]);stop=min(d['ci'],prefix+plan['chunk'])
            result.append((w[c:c+co,0,0,prefix:stop].tobytes()+(b[c:c+co].tobytes() if prefix==0 else b''),'weight_load'))
        return result

    def compute(self,stage,plan,prefix=0,need_dw=True,execute=False):
        d=self.model.stages[stage];kind=d['kind'];n,co=plan['n'],plan['co'];ci=min(plan['chunk'],d['ci']-prefix)
        actions=[];bank=self.bank
        for blob,name in self.weights(stage,plan,prefix,need_dw):
            hit=self.variant!='no_weight_reuse' and len(blob)<=self.p['bank_bytes'] and blob==bank
            if not hit:actions += [('read_byte',len(blob),name),('bank_byte',len(blob),'weight_bank_load')]
            if execute:
                if hit:self.bank_hits+=1
                else:self.bank_misses+=1
            bank=blob if len(blob)<=self.p['bank_bytes'] else blob[-self.p['bank_bytes']:]
        if kind=='conv':
            w,_=self.model.weights(d['ops'][0]);terms=int(np.prod(w.shape[1:]))
            actions += [('bank_byte',n*terms,'activation_load'),('pw_mac',n*co*terms,'first_conv'),('requant',n*co,'requant')]
        elif kind=='head':actions += [('cpu_op',d['input_bytes']+d['co']*d['inshape'][-1]+d['co']*32,'cpu_head_assumed')]
        else:
            if kind=='dw' or (kind=='fused' and need_dw):
                wc=co if kind=='dw' else d['ci'];actions += [('bank_byte',n*9*wc,'activation_load'),('dw_mac',n*9*wc,'dw_compute'),('requant',n*wc,'dw_requant')]
            if kind in ('fused','pw'):
                actions += [('pw_mac',n*ci*co,'pw_compute')]
                if prefix+ci==d['ci']:actions += [('requant',n*co,'pw_requant')]
        if execute:
            total=sum(self.cost(k,u)[0] for k,u,_ in actions);self.observe(total);self.admitted+=1;self.max_bound=max(self.max_bound,total)
            for k,u,name in actions:
                e,t=self.cost(k,u);self.spend(e,t,name,u)
            self.bank=bank
        return actions

    def footprint(self,stage,plan):
        d=self.model.stages[stage];n,co=plan['n'],plan['co']
        return d['input_bytes']+self.p['bank_bytes']+n*d['ci']+4*n*co+n*co+384+512

    def plans(self,stage,f):
        d=self.model.stages[stage];kind=d['kind'];key=(stage,f%d['co'],min(8,d['pixels']-f//d['co']),self.bank)
        if key in self.plan_cache:return self.plan_cache[key]
        plans=[]
        for n,co in geometry(self.p,d,f):
            chunks=sorted({min(v,d['ci']) for v in self.p['ci_chunks']}) if kind in ('fused','pw') else [d['ci']]
            for chunk in chunks:
                flags=[(False,False)] if chunk==d['ci'] else [(z,ps) for z in ([False,True] if kind=='fused' else [False]) for ps in (False,True)]
                for z,ps in flags:
                    if self.variant=='always_save_dw' and kind=='fused':z=True
                    if self.variant=='always_replay_dw':z=False
                    if self.variant in ('adaptive_mapping_fixed_recovery','continuous_fusion'):z=ps=False
                    if self.variant=='always_save_dw' and chunk==d['ci'] and kind=='fused':z=True
                    if self.method=='B2_fixed':
                        if chunk!=min(16,d['ci']):continue
                        z=kind=='fused';ps=kind in ('fused','pw') and chunk<d['ci']
                    a=dict(n=n,co=co,c=f%d['co'],chunk=chunk,z=z,ps=ps)
                    sram=self.footprint(stage,a)
                    if sram>self.p['sram_bytes']:continue
                    e=t=0.;largest=0
                    for prefix in range(0,d['ci'],chunk):
                        actions=self.compute(stage,a,prefix,need_dw=prefix==0)
                        ee=sum(self.cost(k,u)[0] for k,u,_ in actions);largest=max(largest,ee)
                        for k,u,label in actions:
                            ce,ct=self.cost(k,u)
                            # Only the decision ignores reload. Execution retains it.
                            if self.variant=='ignore_reload_decision' and label in ('weight_load','weight_bank_load'):ce=ct=0
                            e+=ce;t+=ct
                        if prefix+chunk<d['ci'] and (ps or (z and prefix==0)):
                            length=(n*d['ci'] if z else 0)+(4*n*co if ps else 0)
                            we,wt,_,_=self.write_cost(length);e+=we;t+=wt;largest=max(largest,we)
                    # Save-DW at CI==all is still executed as a separate checkpoint
                    # before PW for the always-save mechanism ablation below.
                    if z and kind=='fused' and (chunk==d['ci'] or ps) and (self.variant=='always_save_dw' or self.method=='B2_fixed'):
                        we,wt,_,_=self.write_cost(n*d['ci']);e+=we;t+=wt;largest=max(largest,we)
                    for output in (True,False):
                        we,wt,_,_=self.write_cost(n*co,output);e+=we;t+=wt;largest=max(largest,we)
                    if largest*(1+self.p['admission_margin_fraction'])+1e-12>self.power.capacity:continue
                    a.update(bound=largest,score_energy=e/(n*co),score_time=t/(n*co),sram=sram)
                    if a not in plans:plans.append(a)
        if len(self.plan_cache)>4000:self.plan_cache.clear()
        self.plan_cache[key]=plans;return plans

    def choose(self,stage,f):
        d=self.model.stages[stage];plans=self.plans(stage,f)
        if not plans:raise Capacity('no memory/energy-feasible mapping')
        if self.control:self.action('decision',1,'runtime_decision_assumed')
        self.decisions+=1
        if self.method=='B2_fixed' or self.variant=='fixed_mapping_recovery':
            subset=[a for a in plans if a['n']==1 and a['co']==min(16,d['co'])]
        elif self.method=='B1_layer' or self.variant=='continuous_fusion':
            subset=[a for a in plans if a['n']==min(8,d['pixels']-f//d['co']) and a['co']==min(64,d['co']) and a['chunk']==min(64,d['ci']) and not a['ps'] and not a['z']]
        else:
            subset=[a for a in plans if a['bound']<=self.power.energy-self.p['reserve_fraction']*self.power.capacity]
        subset=subset or plans
        if self.method=='B1_layer':key=lambda a:(a['score_time'],-a['n']*a['co'],-a['chunk'])
        elif self.method=='B3_adaptive':key=lambda a:(a['score_time'],a['score_energy'],-a['chunk'])
        else:key=lambda a:(a['score_energy'],a['score_time'],-a['chunk'])
        chosen=min(subset,key=key);self.max_sram=max(self.max_sram,chosen['sram'])
        self.choices[f"p{chosen['n']}_co{chosen['co']}_ci{chosen['chunk']}_z{int(chosen['z'])}ps{int(chosen['ps'])}"]+=1
        return dict(chosen)

    def live_copy(self,store,stage,f,prefix,source,z,ps,out):
        if self.variant!='all_live':return
        contents=source.tobytes()+(z.tobytes() if z is not None else b'')+(ps.astype('<i4').tobytes() if ps is not None else b'')+(out or b'')+self.bank
        self.aux_gen+=1;ops,length=store.aux_ops(stage,f,prefix,contents,self.aux_gen)
        self.write(store,ops,length,'redundant_live_buffers')

    def tile(self,store,stage,source,f,a):
        d=self.model.stages[stage];kind=d['kind'];n,co=a['n'],a['co'];p,c=divmod(f,d['co']);a['c']=c
        self.max_sram=max(self.max_sram,self.footprint(stage,a));old=None if self.method=='B1_layer' else store.scratch(stage,f,n,co)
        if old and old['output'] is not None:return old['output']
        z=ps=None
        if kind in ('conv','dw','head'):
            self.compute(stage,a,execute=True)
            result=self.model.conv(stage,source,p,n,c,co) if kind=='conv' else self.model.dw(stage,source,p,n,c,co) if kind=='dw' else self.model.cpu(source)
            out=result.tobytes()
        else:
            z=None if old is None or old['z'] is None else np.frombuffer(old['z'],dtype=np.int8).reshape(n,d['ci']).copy()
            ps=self.model.bias(stage,n,c,co) if old is None or old['ps'] is None else np.frombuffer(old['ps'],dtype='<i4').reshape(n,co).copy()
            prefix=old['offset'] if old else 0
            if kind=='pw':z=source.reshape(-1,d['ci'])[p:p+n].copy()
            # For always-save, checkpoint Z even when a whole PW fits one chunk.
            if (self.variant=='always_save_dw' or self.method=='B2_fixed') and kind=='fused' and z is None:
                # Load/DW only; PW is computed and charged below after the save.
                acts=self.compute(stage,a,prefix,True)
                dwacts=[x for x in acts if x[2] in ('activation_load','dw_compute','dw_requant')]
                blob=self.weights(stage,a,prefix,True)[0][0]
                self.read(len(blob),'weight_load');self.action('bank_byte',len(blob),'weight_bank_load')
                for k,u,label in dwacts:self.action(k,u,label)
                self.bank=blob[-self.p['bank_bytes']:];z=self.model.dw(stage,source,p,n)
                ops,length=store.scratch_ops(stage,f,n,co,prefix,z.tobytes(),old['ps'] if old else None)
                self.write(store,ops,length,'checkpoint_partial');old=store.scratch(stage,f,n,co)
            while prefix<d['ci']:
                stop=min(d['ci'],prefix+a['chunk']);key=(store.ids[1],stage,f,n,co,prefix,stop)
                actions=self.compute(stage,a,prefix,z is None,execute=True)
                if key in self.seen:self.repeated_range_macs+=sum(u for k,u,_ in actions if k in ('dw_mac','pw_mac'))
                self.seen.add(key)
                if z is None:z=self.model.dw(stage,source,p,n)
                ps=self.model.pw(stage,z,ps,prefix,stop,c,co);prefix=stop
                if prefix<d['ci'] and (a['ps'] or (a['z'] and (old is None or old['z'] is None))):
                    zz=z.tobytes() if a['z'] else old['z'] if old else None
                    pp=ps.astype('<i4').tobytes() if a['ps'] else old['ps'] if old else None
                    durable=prefix if a['ps'] else old['offset'] if old else 0
                    self.live_copy(store,stage,f,prefix,source,z,ps,None)
                    ops,length=store.scratch_ops(stage,f,n,co,durable,zz,pp)
                    self.write(store,ops,length,'checkpoint_partial');old=store.scratch(stage,f,n,co)
            out=self.model.finish(stage,ps,c,co).tobytes()
        if self.method!='B1_layer':
            self.live_copy(store,stage,f,d['ci'],source,z,ps,out)
            ops,length=store.scratch_ops(stage,f,n,co,d['ci'],out=out)
            self.write(store,ops,length,'checkpoint_output',True)
        return out

    def inference(self,store):
        while self.power.time<self.power.horizon-1e-12:
            try:
                done,source,current=self.boot(store)
                if done==len(self.model.stages)-1:return source
                for stage in range(done+1,len(self.model.stages)):
                    d=self.model.stages[stage];current=store.scan(stage) if current is None else current
                    f,offset=current['frontier'],current['offset']
                    if self.method=='B1_layer':f=offset=0
                    while f<d['size']:
                        a=None
                        if self.method!='B1_layer':
                            for n,co in geometry(self.p,d,f):
                                old=store.scratch(stage,f,n,co)
                                if old:
                                    a=dict(n=n,co=co,c=f%d['co'],chunk=min(64,d['ci']),z=old['z'] is not None,ps=old['ps'] is not None);break
                        a=self.choose(stage,f) if a is None else a
                        out=self.tile(store,stage,source,f,a)
                        ops,length=store.log_ops(stage,f,a['n'],a['co'],offset,out)
                        self.write(store,ops,length,'layer_log')
                        f+=len(out);offset+=124+len(out)
                    source=None;scan=store.scan(stage)
                    if scan['frontier']!=d['size']:raise AssertionError('layer coverage')
                    self.read(scan['read_bytes'],'load_next_anchor');flat=scan['array']
                    ops,length=store.root_ops(stage,flat.tobytes());self.write(store,ops,length,'graph_root',True)
                    source=flat.reshape(d['outshape']);current=None
                return source
            except Interrupted:self.bank=b'';continue
            except Capacity as exc:self.blocked_reason=str(exc);return None
        return None

    def run(self,inputs):
        statuses=[dict(arrival_s=a['arrival_s'],deadline_s=a['deadline_s']) for a in inputs];outputs=[];memory=None
        try:
            for index,a in enumerate(inputs):
                if self.power.time<a['arrival_s']:self.power.advance(a['arrival_s']-self.power.time,0,stop_at_empty=False)
                try:store=Store(self.model,a['x'],self.p,f'{self.scenario["id"]}:{index}',self.variant=='all_live')
                except ValueError as exc:self.blocked_reason=str(exc);break
                if memory is not None:store.memory=memory
                memory=store.memory;self.max_nvm=max(self.max_nvm,store.reserved_bytes)
                result=self.inference(store)
                if result is None:break
                expected=self.model.reference(a['x'])[-1]
                if not np.array_equal(result,expected):raise AssertionError('committed full-network output mismatch')
                statuses[index]['committed_s']=self.power.time
                outputs.append(dict(input_id=a['id'],label=a['label'],prediction=int(np.argmax(result)),correct=int(np.argmax(result))==a['label'],output=result.reshape(-1).astype(int).tolist()))
        except Horizon:pass
        if self.power.time<self.power.horizon:self.power.advance(self.power.horizon-self.power.time,0,stop_at_empty=False)
        total=sum(self.energy.values())
        if abs(total-self.power.consumed)>1e-9 or abs(self.power.balance_error())>1e-9:raise AssertionError('energy conservation')
        metrics=summarize_inputs(statuses,self.power.horizon,total)
        return dict(workload=self.model.name,method=self.method,variant=self.variant,backend=self.backend,scenario_id=self.scenario['id'],family=self.scenario['family'],seed=self.scenario['seed'],
            total_inputs=len(inputs),energy_j=total,**metrics,statuses=statuses,outputs=outputs,breakdown_j=dict(self.energy),units=dict(self.units),
            losses=self.losses,admitted_units=self.admitted,admitted_unit_depletions=self.depletions,max_admitted_bound_j=self.max_bound,
            max_sram_algorithm_bytes=self.max_sram,max_nvm_reserved_bytes=self.max_nvm,chosen=dict(self.choices),
            bank_hits=self.bank_hits,bank_misses=self.bank_misses,repeated_exact_range_macs=self.repeated_range_macs,
            energy_balance_error_j=self.power.balance_error(),fault_executed=self.fault_done,blocked_reason=self.blocked_reason,calibrated=False)
