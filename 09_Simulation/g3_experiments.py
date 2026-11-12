"""G3 model-only experiment: splits, freeze, held-out evaluation and sensitivity."""
from dataclasses import asdict,replace
from datetime import datetime,timezone
import hashlib
import itertools
import json
from pathlib import Path
import random
import time
import tracemalloc
import numpy as np
from recap.cost import CostModel
from recap.g3_workload import Mapping,mappings,build_descriptors
from recap.g3_simulator import run_workload


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def scenarios(protocol,split):
    base=protocol[{'train':'train_seed_base','validation':'validation_seed_base','test':'test_seed_base'}[split]]
    replicas=protocol['test_replicates_per_family'] if split=='test' else 1
    result=[]
    for family,(capacity,mean) in enumerate(itertools.product(protocol['capacities_j'],protocol['harvest_means_w'])):
        for replicate in range(replicas):
            seed=base+family*100+replicate
            rng=random.Random(seed)
            horizon=protocol['horizon_s']
            trace=[]
            for step in range(20):
                p=0.0 if rng.random()<.2 else mean*rng.uniform(.2,1.8)
                trace.append([step*horizon/20,p])
            result.append(dict(id=f'{split}_{seed}',split=split,seed=seed,family=f'cap{family//2}_harvest{family%2}',
                               capacity_j=capacity,trace=trace,horizon_s=horizon))
    return result


def aggregate(rows):
    if not rows: raise ValueError('empty evaluation')
    energy=sum(r['energy_j'] for r in rows)
    completed=sum(r['completed'] for r in rows)
    total=sum(r['total_inputs'] for r in rows)
    latencies=sorted(float('inf') if r['completion_s'] is None else r['completion_s'] for r in rows)
    p95=latencies[int(np.ceil(.95*len(latencies)))-1]
    return dict(energy_j=energy,completed=completed,total_inputs=total,completion_rate=completed/total,
                on_time_rate=sum(r['on_time'] for r in rows)/total,
                energy_per_completed_j=energy/completed if completed else None,
                p95_latency_s=None if np.isinf(p95) else p95,p95_is_infinite=bool(np.isinf(p95)))


def rank_policies(rows,reference,tolerance=.05):
    scenarios_by_policy={}
    for row in rows:
        scenarios_by_policy.setdefault(row['method'],set()).add(row['scenario_id'])
    if len({tuple(sorted(v)) for v in scenarios_by_policy.values()})!=1:
        raise ValueError('policies did not see identical training/validation scenarios')
    ref=aggregate(reference)
    rankings=[]
    for method in scenarios_by_policy:
        part=[r for r in rows if r['method']==method]
        if len(part)!=len(scenarios_by_policy[method]): raise ValueError('duplicate scenario')
        a=aggregate(part)
        if a['energy_per_completed_j'] is None: continue
        if a['completion_rate']+1e-12<ref['completion_rate']-tolerance or a['on_time_rate']+1e-12<ref['on_time_rate']-tolerance:
            continue
        rankings.append(dict(method=method,**a))
    return sorted(rankings,key=lambda r:(r['energy_per_completed_j'],r['method']))


def compare(rows_a,rows_b,tolerance=.05,goal=.2):
    a,b=aggregate(rows_a),aggregate(rows_b)
    ea,eb=a['energy_per_completed_j'],b['energy_per_completed_j']
    reduction=None if ea is None or eb is None or eb<=0 else 1-ea/eb
    comparable=a['completion_rate']>=b['completion_rate']-tolerance-1e-12 and a['on_time_rate']>=b['on_time_rate']-tolerance-1e-12
    return dict(a=a,b=b,relative_energy_reduction=reduction,noninferior_point_estimate=comparable,
                meets_goal_point_estimate=bool(comparable and reduction is not None and reduction>=goal),
                latency_nonregression_finite_only=bool(not a['p95_is_infinite'] and not b['p95_is_infinite'] and a['p95_latency_s']<=b['p95_latency_s']))


def paired_bootstrap(rows_a,rows_b,repeats,seed):
    a={r['scenario_id']:r for r in rows_a};b={r['scenario_id']:r for r in rows_b}
    if len(a)!=len(rows_a) or len(b)!=len(rows_b) or a.keys()!=b.keys():
        raise ValueError('bootstrap requires unique paired trace IDs')
    groups={}
    for key in a:
        if a[key]['family']!=b[key]['family']: raise ValueError('family mismatch')
        groups.setdefault(a[key]['family'],[]).append(key)
    rng=random.Random(seed)
    reductions=[];completion_diffs=[];undefined=0
    for _ in range(repeats):
        keys=[rng.choice(ids) for ids in groups.values() for _ in ids]
        aa,bb=[a[k] for k in keys],[b[k] for k in keys]
        comp=compare(aa,bb)
        reduction=comp['relative_energy_reduction']
        if reduction is None: undefined+=1
        else: reductions.append(reduction)
        completion_diffs.append(comp['a']['completion_rate']-comp['b']['completion_rate'])
    # Do not silently delete undefined resamples to report an unconditional CI.
    ci=None if undefined or not reductions else [float(x) for x in np.percentile(reductions,[2.5,97.5])]
    return dict(unit='independent trace seed, paired and stratified by capacitor/harvest family',
                replicates=repeats,seed=seed,undefined_replicates=undefined,
                energy_reduction_ci95=ci,completion_difference_ci95=[float(x) for x in np.percentile(completion_diffs,[2.5,97.5])])


def cost_model(root,protocol,dw_scale=None,write_scale=1):
    cfg=json.loads((root/'09_Simulation/configs/g2_assumed_debug.json').read_text())
    scale=protocol['base_dw_compute_scale'] if dw_scale is None else dw_scale
    cfg['energy_j_per_unit']['dw_mac']*=scale
    cfg['energy_j_per_unit']['write_byte']*=write_scale
    cfg['provenance']=f'ASSUMED_G3_ONLY; G2 debug coefficients; DW energy x{scale}; NVM write energy x{write_scale}; no calibration'
    return CostModel(**cfg)


def experiment(root,output):
    output.mkdir(parents=True,exist_ok=True)
    protocol=json.loads((root/'09_Simulation/configs/g3_protocol.json').read_text())
    (output/'protocol_snapshot.json').write_text(json.dumps(protocol,indent=2)+'\n')
    descriptor_dir=output/'descriptors'
    catalog=build_descriptors(root,descriptor_dir,protocol)
    splits={s:scenarios(protocol,s) for s in ('train','validation','test')}
    seeds=[r['seed'] for group in splits.values() for r in group]
    if len(seeds)!=len(set(seeds)): raise ValueError('split seed leakage')
    (output/'scenarios.json').write_text(json.dumps(splits,indent=2)+'\n')
    choices=mappings(protocol);lookup={m.name:m for m in choices}
    cost=cost_model(root,protocol)
    raw=output/'raw';raw.mkdir(exist_ok=True)
    evaluations=0
    def evaluate(mapping,scenario,method,**kwargs):
        nonlocal evaluations
        result=run_workload(descriptor_dir,catalog,mapping,cost,scenario,protocol,**kwargs)
        result['method']=method
        evaluations+=1
        return result
    def write_rows(name,rows):
        with (raw/name).open('w',encoding='utf-8') as f:
            for row in rows: f.write(json.dumps(row)+'\n')
    baseline=Mapping(2,2,4,16,True,True)
    start=time.perf_counter();tracemalloc.start()
    train=[]
    for i,m in enumerate(choices):
        train.extend(evaluate(m,s,m.name) for s in splits['train'])
        if (i+1)%16==0: print(f'Train policies {i+1}/{len(choices)}',flush=True)
    write_rows('train.jsonl',train)
    # Feasibility must use the adaptive baseline, not the weaker fixed B2.
    # This reference is fitted on TRAIN/VALIDATION ONLY, like the candidates.
    reftrain=[evaluate(baseline,s,'B3_micro',adaptive=True) for s in splits['train']]
    write_rows('train_reference_B3.jsonl',reftrain)
    ranked=rank_policies(train,reftrain,protocol['completion_tolerance_absolute'])
    if not ranked: raise ValueError('no feasible training policies')
    finalists=[];behaviors=set()
    for row in ranked:
        m=lookup[row['method']]
        behavior=(m.h,m.w,m.co,m.ci,None if m.ci==64 else m.save_z,None if m.ci==64 else m.keep_ps)
        if behavior in behaviors: continue
        behaviors.add(behavior);finalists.append(m.name)
        if len(finalists)>=protocol['validation_top_k']: break
    # Fixed-mapping ablation is fitted using train/validation only as well.
    fixed_names=[m.name for m in choices if (m.h,m.w,m.co,m.ci)==(2,2,4,16)]
    validation_names=sorted(set(finalists+fixed_names+[baseline.name]))
    validation=[evaluate(lookup[name],s,name) for name in validation_names for s in splits['validation']]
    write_rows('validation.jsonl',validation)
    refval=[evaluate(baseline,s,'B3_micro',adaptive=True) for s in splits['validation']]
    write_rows('validation_reference_B3.jsonl',refval)
    validated=rank_policies([r for r in validation if r['method'] in finalists],refval,protocol['completion_tolerance_absolute'])
    if not validated: raise ValueError('training finalists fail validation feasibility')
    chosen=lookup[validated[0]['method']]
    fixed_rank=rank_policies([r for r in validation if r['method'] in fixed_names],refval,protocol['completion_tolerance_absolute'])
    fixed_chosen=lookup[fixed_rank[0]['method']] if fixed_rank else baseline
    fit_seconds=time.perf_counter()-start;_,peak=tracemalloc.get_traced_memory();tracemalloc.stop()
    frozen=dict(protocol_hash=canonical_hash(protocol),mapping=asdict(chosen),mapping_name=chosen.name,
                fixed_mapping_ablation=asdict(fixed_chosen),fit_ids=[s['id'] for split in ('train','validation') for s in splits[split]],
                finalists=finalists,validation_ranking=validated,training_ranking=ranked,
                feasibility_reference='B3_micro',fixed_mapping_feasible=bool(fixed_rank),
                frozen_at_utc=datetime.now(timezone.utc).isoformat(),
                fit_seconds=fit_seconds,python_tracemalloc_peak_bytes=peak,used_test_for_selection=False)
    frozen_path=output/'frozen_mapper.json'
    frozen_path.write_text(json.dumps(frozen,indent=2)+'\n')
    frozen_hash=hashlib.sha256(frozen_path.read_bytes()).hexdigest()
    print(f'Frozen mapper {chosen.name}; starting held-out evaluation',flush=True)
    diagnostic=replace(chosen,ci=protocol['diagnostic_ci_chunk'],keep_ps=True)
    methods={
        'B1_micro':(Mapping(4,2,16,64,False,False),{}),
        'B2_micro':(baseline,{}),
        'B3_micro':(baseline,dict(adaptive=True)),
        'RECAP_proto':(chosen,{}),
        'fixed_mapping_joint_recovery':(fixed_chosen,{}),
        'no_weight_reuse':(chosen,dict(reuse_weights=False)),
        'matched_SAVE':(replace(diagnostic,save_z=True),{}),
        'matched_REPLAY':(replace(diagnostic,save_z=False),{})}
    test=[evaluate(m,s,name,**opts) for name,(m,opts) in methods.items() for s in splits['test']]
    write_rows('test.jsonl',test)
    if hashlib.sha256(frozen_path.read_bytes()).hexdigest()!=frozen_hash:
        raise AssertionError('frozen policy changed during test')
    grouped={name:[r for r in test if r['method']==name] for name in methods}
    primary=compare(grouped['RECAP_proto'],grouped['B3_micro'],protocol['completion_tolerance_absolute'],protocol['energy_reduction_goal'])
    primary['bootstrap']=paired_bootstrap(grouped['RECAP_proto'],grouped['B3_micro'],protocol['bootstrap_replicates'],protocol['bootstrap_seed'])
    sensitivities=[]
    for dw,write in itertools.product(protocol['sensitivity_dw_scales'],protocol['sensitivity_write_scales']):
        profile=cost_model(root,protocol,dw,write)
        rows=[]
        for save in (False,True):
            for s in splits['test']:
                r=run_workload(descriptor_dir,catalog,replace(diagnostic,save_z=save),profile,s,protocol)
                r.update(method='SAVE' if save else 'REPLAY',dw_scale=dw,write_scale=write)
                rows.append(r);evaluations+=1
        write_rows(f'sensitivity_dw{dw:g}_write{write:g}.jsonl',rows)
        sensitivities.append(dict(dw_scale=dw,write_scale=write,
            comparison=compare([r for r in rows if r['method']=='SAVE'],[r for r in rows if r['method']=='REPLAY'],protocol['completion_tolerance_absolute'],protocol['energy_reduction_goal'])))
    # Example event traces are diagnostic artifacts, not used to refit policies.
    witness=evaluate(replace(diagnostic,save_z=True),splits['test'][0],'matched_SAVE',keep_events=True)
    events=witness.pop('events')
    with (raw/'witness_events.jsonl').open('w',encoding='utf-8') as f:
        for e in events: f.write(json.dumps(e)+'\n')
    write_rows('witness_summary.jsonl',[witness])
    status='CONTINUE_MODEL_VALIDATION_ONLY' if primary['meets_goal_point_estimate'] else 'REVISE_SCOPE_BEFORE_RTL'
    report=dict(status='MODEL_ONLY_G3_COMPLETED',decision=status,protocol_hash=canonical_hash(protocol),
                frozen_mapper_sha256=frozen_hash,ready_for_paper_energy_results=False,
                model_calibrated=False,cim_specific_benefit_established=False,held_out_test_used_for_tuning=False,
                policy_count=len(choices),descriptor_count=catalog['descriptor_count'],
                split_sizes={k:len(v) for k,v in splits.items()},evaluations=evaluations,selected_mapping=asdict(chosen),
                fit_seconds=fit_seconds,fit_python_tracemalloc_peak_bytes=peak,
                methods={k:aggregate(v) for k,v in grouped.items()},primary_comparison=primary,
                save_replay_comparison=compare(grouped['matched_SAVE'],grouped['matched_REPLAY']),
                sensitivities=sensitivities,completed_mismatches=sum(r['mismatches'] or 0 for r in test),
                unexpected_source_losses=sum(r['unexpected_losses'] for r in test),
                max_ledger_residual_j=max(abs(r['source_ledger_error_j']) for r in test),
                max_source_residual_j=max(abs(r['source_balance_error_j']) for r in test),
                coverage_scope='one real-model DW-PW interior workload (8 pixels x 16 outputs); no full KWS accuracy or calibrated macro; B1/B2/B3 are project prototypes')
    (output/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('status','decision','evaluations','completed_mismatches','selected_mapping')}),flush=True)
    return report


if __name__=='__main__':
    root=Path(__file__).resolve().parents[1]
    experiment(root,root/'10_Experiments/g3')
