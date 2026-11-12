"""G5 preregistered tuning, source-bound freeze and paired held-out evaluation."""
import csv
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path
import random
import time
import numpy as np
from g5_model import KWS
from g5_runtime import Runtime,coefficients


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def dump(path,data):path.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def data(root,p):
    base=root/'05_Model_Training/reference_eembc'
    manifest=json.loads((base/'source_manifest.json').read_text())
    for name,digest in manifest['sha256'].items():
        if sha(base/name)!=digest:raise ValueError('input provenance mismatch: '+name)
    rows=list(csv.reader((base/'y_labels.csv').open()))
    items=[]
    for i,(name,classes,label) in enumerate(rows):
        if int(classes)!=12:raise ValueError('classes')
        value=np.frombuffer((base/name).read_bytes(),dtype=np.int8).reshape(1,49,10,1).copy()
        items.append(dict(id=name,index=i,label=int(label),x=value,sha256=hashlib.sha256(value.tobytes()).hexdigest()))
    # Group identical feature bytes by their FIRST index. No identical feature
    # crosses power-policy tuning/test even if source filenames differ.
    first={}
    for item in items:first.setdefault(item['sha256'],item['index'])
    splits={s:[a for a in items if lo<=first[a['sha256']]<hi] for s,(lo,hi) in p['input_split'].items()}
    hashes=[{a['sha256'] for a in split} for split in splits.values()]
    if any(a&b for i,a in enumerate(hashes) for b in hashes[i+1:]):raise AssertionError('input leakage')
    return items,splits


def scenarios(p,split,inputs):
    result=[];base=p[split+'_seed_base'];family=0
    for capacity in p['capacities_j']:
        for mean in p['harvest_means_w']:
            for rep in range(p['replicates'][split]):
                seed=base+family*100+rep;rng=random.Random(seed)
                trace=[[step*p['horizon_s']/40,0.0 if rng.random()<.2 else mean*rng.uniform(.2,1.8)] for step in range(40)]
                names=[rng.choice(inputs)['id'] for _ in p['arrivals_s']]
                result.append(dict(id=f'{split}_{seed}',seed=seed,family=f'cap{capacity:g}_harvest{mean:g}',
                    split=split,capacity_j=capacity,trace=trace,horizon_s=p['horizon_s'],input_ids=names))
            family+=1
    return result


def aggregate(rows):
    energy=sum(a['energy_j'] for a in rows);completed=sum(a['completed'] for a in rows)
    total=sum(a['total_inputs'] for a in rows);ontime=sum(round(a['on_time_rate']*a['total_inputs']) for a in rows)
    latencies=sorted(math.inf if x.get('committed_s') is None else x['committed_s']-x['arrival_s'] for a in rows for x in a['statuses'])
    p95=latencies[math.ceil(.95*len(latencies))-1]
    outputs=[x for a in rows for x in a['outputs']]
    return dict(energy_j=energy,completed=completed,total_inputs=total,completion_rate=completed/total,
        on_time_rate=ontime/total,energy_per_completed_j=energy/completed if completed else None,
        p95_latency_s=None if math.isinf(p95) else p95,p95_is_infinite=math.isinf(p95),
        correct_completed=sum(x['correct'] for x in outputs),
        correct_committed_per_arrival=sum(x['correct'] for x in outputs)/total,
        conditional_accuracy=None if not outputs else sum(x['correct'] for x in outputs)/len(outputs),
        losses=sum(a['losses'] for a in rows))


def comparison(a,b,p):
    aa,bb=aggregate(a),aggregate(b);ea,eb=aa['energy_per_completed_j'],bb['energy_per_completed_j']
    reduction=None if ea is None or eb is None or eb<=0 else 1-ea/eb
    feasible=aa['completion_rate']>=bb['completion_rate']-p['completion_tolerance_absolute']-1e-12 and aa['on_time_rate']>=bb['on_time_rate']-p['on_time_tolerance_absolute']-1e-12
    return dict(a=aa,b=bb,relative_energy_reduction=reduction,noninferior_point_estimate=feasible,
        meets_goal_point_estimate=bool(feasible and reduction is not None and reduction>=p['energy_reduction_goal']),
        latency_nonregression_finite_only=not aa['p95_is_infinite'] and not bb['p95_is_infinite'] and aa['p95_latency_s']<=bb['p95_latency_s'])


def bootstrap(a,b,p):
    da={x['scenario_id']:x for x in a};db={x['scenario_id']:x for x in b}
    if da.keys()!=db.keys() or len(da)!=len(a) or len(db)!=len(b):raise ValueError('paired unique traces required')
    groups={}
    for key,x in da.items():groups.setdefault(x['family'],[]).append(key)
    rng=random.Random(p['bootstrap_seed']);red=[];diff=[];ot=[];undefined=0
    for _ in range(p['bootstrap_replicates']):
        keys=[rng.choice(ids) for ids in groups.values() for _ in ids]
        c=comparison([da[k] for k in keys],[db[k] for k in keys],p)
        if c['relative_energy_reduction'] is None:undefined+=1
        else:red.append(c['relative_energy_reduction'])
        diff.append(c['a']['completion_rate']-c['b']['completion_rate'])
        ot.append(c['a']['on_time_rate']-c['b']['on_time_rate'])
    interval=lambda x:[float(v) for v in np.percentile(x,[2.5,97.5])]
    return dict(unit='paired independent trace seed, stratified by source/capacitor family; all arrivals in a trace remain together',
        replicates=p['bootstrap_replicates'],undefined_replicates=undefined,
        energy_reduction_ci95=None if undefined or not red else interval(red),
        completion_difference_ci95=interval(diff),on_time_difference_ci95=interval(ot))


def accuracy(model,items,splits,out):
    predictions=[];conf=np.zeros((12,12),dtype=int)
    for i,a in enumerate(items):
        ref=model.reference(a['x']);y=ref[-1];pred=int(np.argmax(y));conf[a['label'],pred]+=1
        head=model.tail(ref[8],True)
        if any(not np.array_equal(u,v) for u,v in zip(head,ref[9:])):
            raise AssertionError('CPU reference head mismatch '+a['id'])
        predictions.append(dict(input_id=a['id'],label=a['label'],prediction=pred,correct=pred==a['label'],
            output_sha256=hashlib.sha256(y.tobytes()).hexdigest()))
        if (i+1)%250==0:print(f'KWS reference accuracy {i+1}/{len(items)}',flush=True)
    checks=[]
    chosen=[]
    for split,part in splits.items():
        for label in range(12):chosen.append((split,next(a for a in part if a['label']==label)))
    for split,a in chosen:
        own=model.uninterrupted(a['x']);ref=model.reference(a['x'])
        mismatch=sum(int(np.count_nonzero(x!=y)) for x,y in zip(own,ref))
        if mismatch:raise AssertionError('hybrid arithmetic mismatch '+a['id'])
        checks.append(dict(split=split,input_id=a['id'],operator_outputs=13,
            elements=sum(x.size for x in own),mismatches=mismatch))
    for name in ('unit_min','unit_max','unit_seed20261015'):
        with np.load(out.parents[1]/f'10_Experiments/g2/reference/{name}.npz') as a:x=a['input'].copy()
        own=model.uninterrupted(x);ref=model.reference(x)
        mismatch=sum(int(np.count_nonzero(u!=v)) for u,v in zip(own,ref))
        if mismatch:raise AssertionError('stress arithmetic mismatch')
        checks.append(dict(split='arithmetic_stress_only',input_id=name,operator_outputs=13,
            elements=sum(u.size for u in own),mismatches=mismatch))
    dump(out/'reference_predictions.json',predictions)
    result=dict(reference_inputs=len(items),reference_correct=sum(a['correct'] for a in predictions),
        reference_accuracy=sum(a['correct'] for a in predictions)/len(items),confusion_matrix=conf.tolist(),
        own_arithmetic_inputs=len(checks),own_operator_outputs=sum(a['operator_outputs'] for a in checks),
        own_verified_elements=sum(a['elements'] for a in checks),own_mismatches=0,checks=checks,
        scope='1000-input reference accuracy; own arithmetic checked on 36 labeled class/split examples + 3 stress fixtures and every completed runtime inference',
        input_scope='490 precomputed INT8 MFCC values; excludes audio/preprocessing',
        cpu_head_verified_inputs=len(items),fc_requantization='float64 scale and ties-away rounding matching TF 2.21 BUILTIN_REF; not an integer accelerator kernel',
        softmax='isolated TFLite BUILTIN_REF CPU op fed computed logits')
    dump(out/'accuracy.json',result);return result


def experiment(root,out,model,p,items,splits):
    raw=out/'raw';raw.mkdir(exist_ok=True)
    scenario_sets={s:scenarios(p,s,splits[s]) for s in ('train','validation','test')}
    dump(out/'scenarios.json',scenario_sets)
    dump(out/'input_splits.json',{s:[dict(id=a['id'],sha256=a['sha256']) for a in part] for s,part in splits.items()})
    lookup={a['id']:a for a in items}
    evaluated=0
    def evaluate(s,method,reserve=0,overhead=True):
        nonlocal evaluated
        inputs=[dict(lookup[name],arrival_s=arrival,deadline_s=min(p['horizon_s'],arrival+p['deadline_interval_s']))
            for name,arrival in zip(s['input_ids'],p['arrivals_s'])]
        r=Runtime(root,model,p,s,method,reserve,overhead).run(inputs);evaluated+=1
        return r
    def rowsfile(name,rows):
        (raw/name).write_text(''.join(json.dumps(r,allow_nan=False)+'\n' for r in rows),encoding='utf-8')
    results={}
    for split in ('train','validation'):
        rows=[]
        for method in ('B3_adaptive','RECAP'):
            for reserve in p['mapper_reserve_fractions']:
                group=[evaluate(s,method,reserve) for s in scenario_sets[split]]
                rows.extend(group);results[split,method,reserve]=group
                print(f'{split}: {method} reserve={reserve} completed={aggregate(group)["completed"]}',flush=True)
        rowsfile(split+'.jsonl',rows)
    def choose(method,refmethod,refreserve):
        candidates=[]
        for reserve in p['mapper_reserve_fractions']:
            feasible=all(comparison(results[split,method,reserve],results[split,refmethod,refreserve],p)['noninferior_point_estimate'] for split in ('train','validation'))
            both=aggregate(results['train',method,reserve]+results['validation',method,reserve])
            if feasible and both['energy_per_completed_j'] is not None:candidates.append((both['energy_per_completed_j'],reserve))
        if candidates:return min(candidates)[1],True
        # No success claim if no policy satisfies predeclared feasibility.
        choices=[(aggregate(results['train',method,r]+results['validation',method,r]),r) for r in p['mapper_reserve_fractions']]
        best=min(choices,key=lambda ar:(-ar[0]['completion_rate'],ar[0]['energy_per_completed_j'] or math.inf,ar[1]))
        return best[1],False
    breserve,bvalid=choose('B3_adaptive','B3_adaptive',0.0)
    reserve,valid=choose('RECAP','B3_adaptive',breserve)
    files=list((root/'09_Simulation').glob('g5_*.py'))+[root/'09_Simulation/configs/g5_protocol.json',
        root/'10_Experiments/run_g5.py',root/'09_Simulation/recap/integer.py',root/'09_Simulation/recap/power.py',root/'09_Simulation/g4_reference.py']
    frozen=dict(frozen_at_utc=datetime.now(timezone.utc).isoformat(),mapper_reserve=reserve,
        mapper_feasible_train_validation=valid,baseline_reserve=breserve,baseline_feasible_train_validation=bvalid,
        protocol_sha256=sha(root/'09_Simulation/configs/g5_protocol.json'),
        source_sha256={f.relative_to(root).as_posix():sha(f) for f in files},
        model_sha256=model.model_hash,softmax_subgraph_sha256=hashlib.sha256(model.softmax_blob).hexdigest(),
        data_manifest_sha256=sha(root/'05_Model_Training/reference_eembc/source_manifest.json'),
        scenarios_sha256=sha(out/'scenarios.json'),input_splits_sha256=sha(out/'input_splits.json'))
    dump(out/'frozen_policy.json',frozen)
    print('Policy and source hashes frozen. Starting untouched G5 test traces.',flush=True)
    test=[]
    for method,r,overhead in [('B1_layer',0,True),('B2_fixed',0,True),('B3_adaptive',breserve,True),('RECAP',reserve,True),('RECAP_no_control',reserve,False)]:
        group=[evaluate(s,'RECAP' if method=='RECAP_no_control' else method,r,overhead) for s in scenario_sets['test']]
        for a in group:a['method']=method
        test.extend(group);print(f'test: {method} completed={aggregate(group)["completed"]}',flush=True)
    rowsfile('test.jsonl',test)
    for name,digest in frozen['source_sha256'].items():
        if sha(root/name)!=digest:raise AssertionError('source changed after freeze')
    group=lambda method:[a for a in test if a['method']==method]
    cmp=comparison(group('RECAP'),group('B3_adaptive'),p);boot=bootstrap(group('RECAP'),group('B3_adaptive'),p)
    summaries={method:aggregate(group(method)) for method in sorted({a['method'] for a in test})}
    energy=sum(a['energy_j'] for a in group('RECAP'))
    control=sum(v for a in group('RECAP') for k,v in a['breakdown_j'].items() if 'controller' in k or k in ('runtime_decision','boot_parser'))
    checkpoint=sum(v for a in group('RECAP') for k,v in a['breakdown_j'].items() if k.startswith(('checkpoint','layer_log','graph_root','scan_destination','boot_root','boot_scratch')))
    result=dict(status='G5_HYBRID_SIMULATION_EXECUTED',calibrated=False,ready_for_paper_energy_results=False,
        evaluations=evaluated,test_traces=len(scenario_sets['test']),arrivals_per_method=sum(a['total_inputs'] for a in group('RECAP')),
        frozen_mapper_reserve=reserve,frozen_adaptive_baseline_reserve=breserve,
        mapper_feasible_train_validation=valid,methods=summaries,comparison_vs_adaptive=cmp,paired_bootstrap=boot,
        meets_20pct_with_ci=bool(valid and boot['energy_reduction_ci95'] and boot['energy_reduction_ci95'][0]>=p['energy_reduction_goal'] and
            boot['completion_difference_ci95'][0]>=-p['completion_tolerance_absolute'] and boot['on_time_difference_ci95'][0]>=-p['on_time_tolerance_absolute']),
        assumed_control_energy_fraction=control/energy,checkpoint_path_energy_fraction=checkpoint/energy,
        no_control_ablation=comparison(group('RECAP_no_control'),group('RECAP'),p),
        max_sram_algorithm_bytes=max(a['max_sram_algorithm_bytes'] for a in test),
        max_nvm_reserved_bytes=max(a['max_nvm_reserved_bytes'] for a in test),
        full_embedded_runtime_arena_verified=False,physical_macro_validated=False,
        admitted_unit_depletions=sum(a['admitted_unit_depletions'] for a in test),
        notes=['Binary G4 codec reused; graph log/root protocol is new software simulation, not full-network RTL verification.',
            'Control ablation preserves metadata/traffic and frozen policies; changes both assumed control energy and time, and therefore may alter causal schedules.',
            'Finite horizon includes all partial/replayed/unfinished consumption; undefined energy denominators and infinite p95 retained.',
            'Capacitor source couples to policy load; loss during retention wait is separate from admitted work. No future harvest credited.',
            'All cost coefficients remain explicitly assumed. Host mathematical memoization never reduces simulated cost.'])
    dump(out/'results.json',result)
    return result
