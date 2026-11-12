"""G8 recovery experiments; G2-G6 sources and evidence remain immutable.

All costs and the Poisson planning hazard are assumptions. Expected redo is
used ONLY for ranking; the execution ledger charges actual operations only.
"""
from collections import Counter
import bisect
import math
import numpy as np
from g6_runtime import Runtime as G6Runtime, Capacity
from g6_storage import geometry
from g5_runtime import Interrupted, Horizon
from recap.power import Reservoir


def expected_remaining(costs, probabilities, recovery_costs, keep_ps):
    """Finite boundary-loss model, solved as E_i=A_i+B_i*E_0.

    A failure AFTER an acknowledged intermediate checkpoint returns to i+1
    when PS was saved, otherwise to zero. The final durable output has no
    subsequent loss window. Recovery costs include reloading missing DW.
    This is a ranking approximation, not a calibrated prediction of runtime.
    """
    if not costs or len(probabilities) != len(costs)-1 or len(recovery_costs) != len(probabilities):
        raise ValueError('invalid renewal dimensions')
    if any(not math.isfinite(v) or v < 0 for v in costs+recovery_costs):
        raise ValueError('invalid renewal cost')
    if any(not math.isfinite(q) or not 0 <= q < 1 for q in probabilities):
        raise ValueError('invalid loss probability')
    a, b = costs[-1], 0.
    for i in range(len(costs)-2, -1, -1):
        q = probabilities[i]
        if keep_ps:
            a, b = costs[i]+a+q*recovery_costs[i], b
        else:
            a, b = costs[i]+(1-q)*a+q*recovery_costs[i], (1-q)*b+q
    if 1-b <= 1e-14:
        return math.inf
    return a/(1-b)


class OutageReservoir(Reservoir):
    """Exogenous supply disconnects at fixed absolute times, shared by policies.

    Discarded capacitor charge is counted as spilled, not inference energy.
    A reset can tear an operation even if its energy admission was valid.
    Idle/boot integration continues to the requested time after a reset.
    """
    def __init__(self, *args, reset_times=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.reset_times = list(reset_times)
        if any(not math.isfinite(t) or not 0 < t < self.horizon for t in self.reset_times):
            raise ValueError('reset outside horizon')
        if any(a >= b for a,b in zip(self.reset_times,self.reset_times[1:])):
            raise ValueError('reset schedule must be ordered and unique')
        self.reset_index = self.external_resets = 0
        self.discarded_j = 0.
        self.last_external = False

    def advance(self, seconds, load_w, stop_at_empty=True):
        # Let Reservoir validate negative/nonfinite inputs even at a reset.
        if not math.isfinite(seconds) or seconds < 0 or not math.isfinite(load_w) or load_w < 0:
            raise ValueError('invalid time/load')
        start = self.time; end = min(start+seconds,self.horizon)
        self.last_external = False
        while self.reset_index < len(self.reset_times):
            when = self.reset_times[self.reset_index]
            if when > end+1e-15: break
            if when < self.time-1e-12:
                raise AssertionError('unconsumed reset schedule')
            _, brown = super().advance(max(0.,when-self.time),load_w,stop_at_empty)
            if brown: return self.time-start,True
            dumped = self.energy
            self.spilled += dumped; self.discarded_j += dumped; self.energy = 0.
            self.reset_index += 1; self.external_resets += 1; self.last_external = True
            if stop_at_empty: return self.time-start,True
        _,brown = super().advance(max(0.,end-self.time),load_w,stop_at_empty)
        return self.time-start,brown


class Runtime(G6Runtime):
    def __init__(self, root, model, p, scenario, method='RECAP_redo', fault=None):
        super().__init__(root,model,p,scenario,method=method,fault=fault)
        cap=scenario['capacity_j']
        self.power=OutageReservoir(2*cap/(3.3**2-2**2),3.3,2,scenario['trace'],
            cap*p['initial_energy_fraction'],scenario['horizon_s'],reset_times=scenario.get('reset_times_s',[]))
        self.direct_publication=p.get('direct_publication',True)
        self.planning_rate=p['planning_outage_rate_hz']
        if not math.isfinite(self.planning_rate) or self.planning_rate < 0:
            raise ValueError('invalid planning hazard')
        self.ranking=Counter()

    def spend(self,energy,seconds,name,units=0,mutation=None):
        if energy<0 or seconds<0:raise ValueError('negative event')
        if seconds==0:
            if energy:raise ValueError('positive energy requires duration')
            if mutation:mutation(1.)
            return
        dt,brown=self.power.advance(seconds,energy/seconds)
        fraction=min(1.,max(0.,dt/seconds))
        if not brown and abs(dt-seconds)<1e-12:fraction=1.
        self.energy[name]+=energy*fraction;self.units[name]+=units*fraction;self.durations[name]+=seconds*fraction
        if mutation:mutation(fraction)
        if brown:
            self.losses+=1
            if self.power.last_external:raise Interrupted()
            self.depletions+=1
            raise AssertionError('energy-admitted unit depleted without external reset')
        if fraction<1:raise Horizon()

    def dw_phase(self,stage,a,execute=False):
        d=self.model.stages[stage];blob=self.weights(stage,a,0,True)[0][0]
        hit=len(blob)<=self.p['bank_bytes'] and blob==self.bank
        actions=[] if hit else [('read_byte',len(blob),'weight_load'),('bank_byte',len(blob),'weight_bank_load')]
        actions += [('bank_byte',a['n']*9*d['ci'],'activation_load'),
            ('dw_mac',a['n']*9*d['ci'],'dw_compute'),('requant',a['n']*d['ci'],'dw_requant')]
        if execute:
            bound=sum(self.cost(k,u)[0] for k,u,_ in actions);self.observe(bound)
            self.admitted+=1;self.max_bound=max(self.max_bound,bound)
            for k,u,label in actions:
                e,t=self.cost(k,u);self.spend(e,t,label,u)
            self.bank=blob if len(blob)<=self.p['bank_bytes'] else blob[-self.p['bank_bytes']:]
            self.bank_hits+=int(hit);self.bank_misses+=int(not hit)
        return actions

    def plans(self,stage,f):
        d=self.model.stages[stage];kind=d['kind']
        key=(stage,f%d['co'],min(8,d['pixels']-f//d['co']),self.bank)
        if key in self.plan_cache:return self.plan_cache[key]
        result=[]
        for n,co in geometry(self.p,d,f):
            chunks=sorted({min(v,d['ci']) for v in self.p['ci_chunks']}) if kind in ('fused','pw') else [d['ci']]
            for chunk in chunks:
                flags=[(False,False)] if chunk==d['ci'] else [(z,ps) for z in ([False,True] if kind=='fused' else [False]) for ps in (False,True)]
                for z,ps in flags:
                    a=dict(n=n,co=co,c=f%d['co'],chunk=chunk,z=z,ps=ps)
                    sram=self.footprint(stage,a)
                    if sram>self.p['sram_bytes']:continue
                    if 124+(n*d['ci'] if z else 0)+(4*n*co if ps else 0)>self.p['scratch_slot_bytes']:continue
                    costs=[];times=[];bounds=[];dw_e=dw_t=prologue_e=prologue_t=0.
                    if kind=='fused':
                        dw=self.dw_phase(stage,a)
                        dw_e=sum(self.cost(k,u)[0] for k,u,_ in dw);dw_t=sum(self.cost(k,u)[1] for k,u,_ in dw)
                        bounds.append(dw_e)
                        if z:
                            prologue_e,prologue_t,_,_=self.write_cost(n*d['ci']);bounds.append(prologue_e)
                    prefixes=list(range(0,d['ci'],chunk)) if kind in ('fused','pw') else [0]
                    for prefix in prefixes:
                        acts=self.compute(stage,a,prefix,need_dw=False)
                        ce=sum(self.cost(k,u)[0] for k,u,_ in acts);ct=sum(self.cost(k,u)[1] for k,u,_ in acts)
                        bounds.append(ce)
                        if prefix+chunk<d['ci'] and ps:
                            we,wt,_,_=self.write_cost((n*d['ci'] if z else 0)+4*n*co)
                            ce+=we;ct+=wt;bounds.append(we)
                        costs.append(ce);times.append(ct)
                    # All policies use the same durable log primitive. Optional
                    # scratch output is a predeclared publication ablation.
                    for output in ([True,False] if not self.direct_publication else [False]):
                        we,wt,_,_=self.write_cost(n*co,output)
                        costs[-1]+=we;times[-1]+=wt;bounds.append(we)
                    largest=max(bounds)
                    if largest*(1+self.p['admission_margin_fraction'])+1e-12>self.power.capacity:continue
                    # Hazard is fixed from protocol/development; neither future
                    # trace nor actual test reset times enter this calculation.
                    qs=[min(1-1e-12,-math.expm1(-self.planning_rate*t)) for t in times[:-1]]
                    recovery=[]
                    for i in range(len(qs)):
                        payload=(n*d['ci'] if z else 0)+(4*n*co if ps else 0)
                        read_e,_=self.cost('read_byte',124+payload if (z or ps) else 0)
                        boot_e,_=self.cost('boot',1)
                        # DW bank is volatile; DW reexecution/load on cold
                        # restart is approximated conservatively by dw_e.
                        recovery.append(boot_e+read_e+(0 if z else dw_e))
                    nominal=dw_e+prologue_e+sum(costs)
                    expected=dw_e+prologue_e+expected_remaining(costs,qs,recovery,ps)
                    a.update(bound=largest,score_energy=nominal/(n*co),score_time=(dw_t+prologue_t+sum(times))/(n*co),
                        score_expected=expected/(n*co),sram=sram)
                    result.append(a)
        if len(self.plan_cache)>4000:self.plan_cache.clear()
        self.plan_cache[key]=result
        return result

    def choose(self,stage,f):
        d=self.model.stages[stage];plans=self.plans(stage,f)
        if not plans:raise Capacity('no memory/energy-feasible mapping')
        if self.control:self.action('decision',1,'runtime_decision_assumed')
        self.decisions+=1
        if self.method=='B1_layer':
            # NHWC channel tiles narrower than a full pixel cannot span pixels.
            # VWW has CO128/256 stages; the fixed contract must respect geometry.
            fixed_co=min(64,d['co'])
            fixed_n=min(8,d['pixels']-f//d['co']) if fixed_co==d['co'] else 1
            subset=[a for a in plans if a['n']==fixed_n and a['co']==fixed_co and a['chunk']==min(64,d['ci']) and not a['z'] and not a['ps']]
        elif self.method=='B4_periodic':
            interval=min(self.p['periodic_ci'],d['ci'])
            subset=[a for a in plans if a['chunk']==interval and not a['z'] and a['ps']==(interval<d['ci'])]
        else:subset=plans
        # Safety fallback stays within the baseline's recovery contract.
        if not subset:raise Capacity('baseline contract has no feasible mapping')
        feasible=[a for a in subset if a['bound']<=self.power.energy-self.p['reserve_fraction']*self.power.capacity]
        subset=feasible or subset
        field='score_time' if self.method in ('B1_layer','B3_adaptive') else 'score_expected' if self.method=='RECAP_redo' else 'score_energy'
        chosen=min(subset,key=lambda a:(a[field],a['score_energy'],-a['n']*a['co'],-a['chunk']))
        self.max_sram=max(self.max_sram,chosen['sram']);self.ranking[field]+=1
        self.choices[f"p{chosen['n']}_co{chosen['co']}_ci{chosen['chunk']}_z{int(chosen['z'])}ps{int(chosen['ps'])}"]+=1
        return dict(chosen)

    def tile(self,store,stage,source,f,a):
        d=self.model.stages[stage];kind=d['kind'];n,co=a['n'],a['co'];p,c=divmod(f,d['co']);a['c']=c
        self.max_sram=max(self.max_sram,self.footprint(stage,a))
        old=None if self.method=='B1_layer' else store.scratch(stage,f,n,co)
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
            if z is None:
                self.dw_phase(stage,a,execute=True);z=self.model.dw(stage,source,p,n)
                if a['z']:
                    ops,length=store.scratch_ops(stage,f,n,co,prefix,z.tobytes(),old['ps'] if old else None)
                    self.write(store,ops,length,'checkpoint_partial');old=store.scratch(stage,f,n,co)
            while prefix<d['ci']:
                stop=min(d['ci'],prefix+a['chunk']);key=(store.ids[1],stage,f,n,co,prefix,stop)
                actions=self.compute(stage,a,prefix,need_dw=False,execute=True)
                if key in self.seen:self.repeated_range_macs+=sum(u for k,u,_ in actions if k in ('dw_mac','pw_mac'))
                self.seen.add(key)
                ps=self.model.pw(stage,z,ps,prefix,stop,c,co);prefix=stop
                if prefix<d['ci'] and a['ps']:
                    ops,length=store.scratch_ops(stage,f,n,co,prefix,z.tobytes() if a['z'] else None,ps.astype('<i4').tobytes())
                    self.write(store,ops,length,'checkpoint_partial');old=store.scratch(stage,f,n,co)
            out=self.model.finish(stage,ps,c,co).tobytes()
        if not self.direct_publication:
            ops,length=store.scratch_ops(stage,f,n,co,d['ci'],out=out)
            self.write(store,ops,length,'checkpoint_output',True)
        return out

    def run(self,inputs):
        row=super().run(inputs)
        row.update(protocol='G8',direct_publication=self.direct_publication,
            planning_outage_rate_hz=self.planning_rate,ranking_fields=dict(self.ranking),
            external_resets=self.power.external_resets,discarded_capacitor_energy_j=self.power.discarded_j,
            discard_scope='rail disconnect dump counted in reservoir spilled, excluded from load energy')
        return row
