"""Frozen multi-workload evaluation, complete planned ablation axes and failures."""
from collections import defaultdict
import copy
from datetime import datetime,timezone
import hashlib
import json
import math
from pathlib import Path
import random
import time
import numpy as np
from g5_experiments import aggregate,comparison,bootstrap,dump,sha
from g6_model import Model
from g6_runtime import Runtime
from g6_storage import Store
from g6_inputs import inputs,synthetic,measured,assign_inputs
from g6_faults import campaign


def canonical(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def diagnostics(root):
    import csv
    path=root/'05_Model_Training/reference_eembc';name,_,label=next(csv.reader((path/'y_labels.csv').open()))
    kws=dict(id=name,label=int(label),x=np.frombuffer((path/name).read_bytes(),dtype=np.int8).reshape(1,49,10,1).copy())
    path=root/'05_Model_Training/reference_vww/coco_subset';meta=json.loads((path/'manifest.json').read_text())
    with np.load(path/'inputs.npz') as a:vww=dict(id=meta['images'][0]['id'],label=meta['images'][0]['label'],x=a['x'][:1].copy())
    return dict(kws=kws,vww=vww)


def accuracy(root,models,pools,out):
    base=root/'05_Model_Training/reference_vww/coco_subset';meta=json.loads((base/'manifest.json').read_text())
    checks=[];predictions=[]
    with np.load(base/'inputs.npz') as f:
        for i,a in enumerate(meta['images']):
            x=f['x'][i:i+1];ref=models['vww'].reference(x);pred=int(np.argmax(ref[-1]))
            predictions.append(dict(id=a['id'],label=a['label'],prediction=pred,correct=pred==a['label']))
            if i in (0,1,20,21):
                own=models['vww'].uninterrupted(x)
                mismatches=sum(int(np.count_nonzero(u!=v)) for u,v in zip(own,ref))
                checks.append(dict(workload='vww',id=a['id'],operators=len(ref),elements=sum(u.size for u in ref),mismatches=mismatches))
    for label in range(12):
        a=next(x for x in pools['kws'] if x['label']==label);m=models['kws']
        own=m.uninterrupted(a['x']);ref=m.reference(a['x'])
        checks.append(dict(workload='kws',id=a['id'],operators=len(ref),elements=sum(u.size for u in ref),mismatches=sum(int(np.count_nonzero(u!=v)) for u,v in zip(own,ref))))
    if any(a['mismatches'] for a in checks):raise AssertionError('G6 arithmetic equivalence')
    result=dict(status='PASS_MODEL_EQUIVALENCE',vww_reference_inputs=len(predictions),
        vww_reference_correct=sum(a['correct'] for a in predictions),vww_reference_accuracy=sum(a['correct'] for a in predictions)/len(predictions),
        scope='40-image balanced research-preprocessed COCO/VWW subset, not full-dataset or official MLPerf accuracy',
        own_checked_inputs=len(checks),own_checked_operator_outputs=sum(a['operators'] for a in checks),
        own_checked_elements=sum(a['elements'] for a in checks),mismatches=0,checks=checks,predictions=predictions)
    dump(out/'accuracy.json',result);return result


def measured_bootstrap(a,b,scenario_map,p):
    da={r['scenario_id']:r for r in a};db={r['scenario_id']:r for r in b}
    if da.keys()!=db.keys():raise ValueError('measured trace pairing')
    groups=defaultdict(list)
    for key in da:groups[scenario_map[key]['cluster_id']].append(key)
    ids=list(groups);rng=random.Random(p['bootstrap_seed']);reductions=[];completion=[];ontime=[];undefined=0
    for _ in range(p['bootstrap_replicates']):
        keys=[k for _ in ids for k in groups[rng.choice(ids)]]
        c=comparison([da[k] for k in keys],[db[k] for k in keys],p);r=c['relative_energy_reduction']
        if r is None:undefined+=1
        else:reductions.append(r)
        completion.append(c['a']['completion_rate']-c['b']['completion_rate']);ontime.append(c['a']['on_time_rate']-c['b']['on_time_rate'])
    interval=lambda x:[float(v) for v in np.percentile(x,[2.5,97.5])]
    return dict(unit='paired measurement-day blocks; both capacitor configurations and all arrivals kept together; one measured location only',
        independent_day_blocks=len(ids),replicates=p['bootstrap_replicates'],undefined_replicates=undefined,
        energy_reduction_ci95=None if undefined or not reductions else interval(reductions),
        completion_difference_ci95=interval(completion),on_time_difference_ci95=interval(ontime))


def experiment(root,out,p,models,pools,diagnostic):
    scenarios=assign_inputs(synthetic(p)+measured(root,p,out),pools);lookup={n:{a['id']:a for a in pool} for n,pool in pools.items()}
    dump(out/'scenarios.json',scenarios)
    dump(out/'input_pools.json',{n:[dict(id=a['id'],sha256=a['sha256']) for a in pool] for n,pool in pools.items()})
    # Preflight each actual ablation and backend on a separate diagnostic input
    # and strong constant source, before touching the main source scenarios.
    preflight=[]
    for name in p['workloads']:
        for variant in ['full']+p['ablations']:
            model=Model(root,name,False) if variant=='unfused' else models[name]
            s=dict(id='preflight_'+name,seed=0,family='preflight',capacity_j=100e-6,trace=[[0,.1]],horizon_s=8)
            r=Runtime(root,model,p,s,variant=variant).run([dict(diagnostic[name],arrival_s=0,deadline_s=8)])
            if r['completed']!=1:raise AssertionError(f'preflight {name}/{variant}: {r["blocked_reason"]}')
            preflight.append(dict(workload=name,variant=variant,completed=1,energy_j=r['energy_j']))
        print('G6 all-variant diagnostic preflight PASS:',name,flush=True)
    dump(out/'preflight.json',preflight)
    files=list((root/'09_Simulation').glob('g6_*.py'))+[root/'10_Experiments/run_g6.py',root/'10_Experiments/setup_g6_sources.py',
        root/'09_Simulation/configs/g6_protocol.json']+list((root/'09_Simulation/tests_g6').glob('*.py'))
    datafiles=[root/'05_Model_Training/reference_vww/source_manifest.json',root/'05_Model_Training/reference_vww/coco_subset/manifest.json',
        root/'05_Model_Training/reference_eembc/source_manifest.json',root/'09_Simulation/traces/g6_eth/source_manifest.json',out/'scenarios.json',out/'input_pools.json']
    frozen=dict(frozen_at_utc=datetime.now(timezone.utc).isoformat(),source_sha256={f.relative_to(root).as_posix():sha(f) for f in files},
        input_sha256={f.relative_to(root).as_posix():sha(f) for f in datafiles},model_sha256={n:m.model_hash for n,m in models.items()},
        reserve_fraction=p['reserve_fraction'],no_g6_tuning=True,design='G5 policy transfer, extended common memory, fresh synthetic seeds and six deterministic native solar windows')
    dump(out/'frozen_protocol.json',frozen);freeze_id=canonical(frozen['source_sha256']|frozen['input_sha256'])
    print('G6 sources, scenarios and all policies FROZEN before main evaluation.',flush=True)
    cases=out/'cases';cases.mkdir(exist_ok=True);executed=0;hits=0
    unfused={n:Model(root,n,False) for n in p['workloads']}
    def evaluate(name,s,method='RECAP',variant='full',backend='cim',config=None):
        nonlocal executed,hits
        config=p if config is None else config
        key=canonical(dict(freeze=freeze_id,workload=name,scenario=s,method=method,variant=variant,backend=backend,config=config))
        path=cases/(key+'.json')
        if path.exists():hits+=1;return json.loads(path.read_text())
        items=[dict(lookup[name][name_id],arrival_s=arrival,deadline_s=min(s['horizon_s'],arrival+s['deadline_interval_s'])) for name_id,arrival in zip(s['input_ids'][name],s['arrivals_s'])]
        r=Runtime(root,unfused[name] if variant=='unfused' else models[name],config,s,method,variant,backend).run(items)
        dump(path,r);executed+=1;return r
    raw=out/'raw';raw.mkdir(exist_ok=True)
    def save(name,rows):(raw/name).write_text(''.join(json.dumps(r,allow_nan=False)+'\n' for r in rows))
    main=[]
    for name in p['workloads']:
        for method in ('B1_layer','B2_fixed','B3_adaptive','RECAP'):
            group=[evaluate(name,s,method) for s in scenarios];main+=group
            print('G6 main',name,method,'completed',sum(a['completed'] for a in group),'/',sum(a['total_inputs'] for a in group),flush=True)
        save('main.jsonl',main)
    subset=[s for s in scenarios if s['source_kind'] in ('steady','zero') or (s['source_kind'] in ('mild','severe') and s['seed']%100<2)]
    sensitivity_subset=[s for s in subset if s['source_kind'] in ('mild','severe')]
    ablations=[]
    for name in p['workloads']:
        for variant in p['ablations']:
            rows=[dict(evaluate(name,s,variant=variant),experiment='ablation',ablation=variant) for s in subset]
            ablations+=rows;print('G6 ablation',name,variant,'completed',sum(r['completed'] for r in rows),flush=True)
        save('ablations.jsonl',ablations)
    sensitivity=[]
    for knob,values in p['sensitivity'].items():
        for value in values:
            config=dict(p,**{knob:value})
            for name in p['workloads']:
                for method in ('B3_adaptive','RECAP'):
                    sensitivity += [dict(evaluate(name,s,method,config=config),experiment='sensitivity',knob=knob,value=value) for s in sensitivity_subset]
        print('G6 sensitivity complete:',knob,flush=True);save('sensitivity.jsonl',sensitivity)
    factorial=[]
    for name in p['workloads']:
        for backend in ('cim','digital'):
            for method in ('B3_adaptive','RECAP'):
                factorial += [evaluate(name,s,method,backend=backend) for s in subset]
    save('backend_factorial.jsonl',factorial)
    for name,digest in frozen['source_sha256'].items():
        if sha(root/name)!=digest:raise AssertionError('post-freeze source mutation')
    result=summarize(main,ablations,sensitivity,factorial,scenarios,p)
    result.update(unique_executions=executed,cache_hits=hits,freeze_id=freeze_id,raw_rows=dict(main=len(main),ablations=len(ablations),sensitivity=len(sensitivity),backend_factorial=len(factorial)))
    dump(out/'results.json',result);return result


def summarize(main,ablations,sensitivity,factorial,scenarios,p):
    smap={s['id']:s for s in scenarios};workloads={};loss_cases=[]
    for name in p['workloads']:
        groups={}
        for domain in ('synthetic_stochastic','steady','zero','eth_measured_derived_rail'):
            allowed={s['id'] for s in scenarios if (s['source_kind'] in ('mild','severe') if domain=='synthetic_stochastic' else s['source_kind']==domain)}
            part=[r for r in main if r['workload']==name and r['scenario_id'] in allowed]
            methods={m:[r for r in part if r['method']==m] for m in ('B1_layer','B2_fixed','B3_adaptive','RECAP')}
            a,b=methods['RECAP'],methods['B3_adaptive'];c=comparison(a,b,p)
            ci=bootstrap(a,b,p) if domain=='synthetic_stochastic' else measured_bootstrap(a,b,smap,p) if domain.startswith('eth') else None
            groups[domain]=dict(methods={m:aggregate(rows) for m,rows in methods.items()},comparison_vs_adaptive=c,
                comparison_vs_layer=comparison(a,methods['B1_layer'],p),paired_bootstrap=ci,
                meets_20pct_with_ci=bool(ci and ci['energy_reduction_ci95'] and ci['energy_reduction_ci95'][0]>=p['energy_reduction_goal'] and ci['completion_difference_ci95'][0]>=-p['completion_tolerance_absolute'] and ci['on_time_difference_ci95'][0]>=-p['on_time_tolerance_absolute']))
        workloads[name]=groups
        aa={r['scenario_id']:r for r in main if r['workload']==name and r['method']=='RECAP'}
        for comparator in ('B1_layer','B3_adaptive'):
            for b in (r for r in main if r['workload']==name and r['method']==comparator):
                a=aa[b['scenario_id']];c=comparison([a],[b],p)
                if not c['noninferior_point_estimate'] or (c['relative_energy_reduction'] is not None and c['relative_energy_reduction']<0):
                    loss_cases.append(dict(workload=name,scenario_id=b['scenario_id'],source_kind=smap[b['scenario_id']]['source_kind'],
                        comparator=comparator,completion_difference=a['completed']-b['completed'],
                        relative_energy_reduction=c['relative_energy_reduction'],a_energy_j=a['energy_j'],b_energy_j=b['energy_j'],
                        a_breakdown_j=a['breakdown_j'],b_breakdown_j=b['breakdown_j'],a_losses=a['losses'],b_losses=b['losses']))
    ablation_results=[]
    for name in p['workloads']:
        for variant in p['ablations']:
            part=[r for r in ablations if r['workload']==name and r['variant']==variant];ids={r['scenario_id'] for r in part}
            full=[r for r in main if r['workload']==name and r['method']=='RECAP' and r['scenario_id'] in ids]
            ablation_results.append(dict(workload=name,variant=variant,comparison_ablation_vs_full=comparison(part,full,p),
                blocked_cases=sum(r['blocked_reason'] is not None for r in part),bank_hits=sum(r['bank_hits'] for r in part)))
    sensitivity_results=[]
    for name in p['workloads']:
        for knob,values in p['sensitivity'].items():
            for value in values:
                part=[r for r in sensitivity if r['workload']==name and r['knob']==knob and r['value']==value]
                a=[r for r in part if r['method']=='RECAP'];b=[r for r in part if r['method']=='B3_adaptive']
                sensitivity_results.append(dict(workload=name,knob=knob,value=value,comparison_vs_adaptive=comparison(a,b,p)))
    backend_results=[]
    for name in p['workloads']:
        for backend in ('cim','digital'):
            part=[r for r in factorial if r['workload']==name and r['backend']==backend]
            backend_results.append(dict(workload=name,backend=backend,comparison_vs_adaptive=comparison(
                [r for r in part if r['method']=='RECAP'],[r for r in part if r['method']=='B3_adaptive'],p)))
    return dict(status='G6_MULTIPLE_WORKLOAD_SIMULATION_EXECUTED',calibrated=False,ready_for_paper_energy_results=False,
        workloads=workloads,ablations=ablation_results,sensitivity=sensitivity_results,backend_factorial=backend_results,
        losing_trace_comparisons=loss_cases,
        max_sram_algorithm_bytes=max(r['max_sram_algorithm_bytes'] for r in main+ablations+sensitivity+factorial),
        max_nvm_reserved_bytes=max(r['max_nvm_reserved_bytes'] for r in main+ablations+sensitivity+factorial),
        admitted_unit_depletions=sum(r['admitted_unit_depletions'] for r in main+ablations+sensitivity+factorial),
        completed_outputs_in_main=sum(r['completed'] for r in main),
        limitations=['All backend/control/NVM/CPU cost coefficients are assumed; no physical energy or CIM-specific superiority claim.',
            'B4 literature reproduction remains unresolved at G1; these ablations are explicit implementations, not named prior-art reproductions.',
            'VWW cannot run in original 16 KiB/256 KiB configuration; both workloads evaluated with common 64 KiB SRAM/2 MiB NVM.',
            'Measured ETH panel power uses assumed 70% transfer, native time, one location and six windows; no validated harvester I-V/voltage adaptation.',
            'Logical buffers only; no compiled CPU arena/full accelerator RTL; sensing/preprocessing and external input queue excluded.',
            '1000 random faults apply to large model-backed tiles, not 1000 complete graph runs.',
            'Do not select cost parameters/policies using these held-out sensitivity/ablation outcomes.'])
