"""Fresh G8 evaluation. Default runs full declared grid; never rewrites G2-G6.

Requires existing G2-G6 inputs and setup_g8_data.py. Outputs to g8/<run-id>.
Existing runs are immutable: choose a new --run-id for an intentional rerun.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import io
import json
import math
from pathlib import Path
import random
import sys
import time
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'09_Simulation'))
from g6_model import Model
from g6_inputs import inputs as g6_inputs,synthetic,assign_inputs
from g8_runtime import Runtime
from g5_experiments import aggregate,comparison,bootstrap


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def dump(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def verify_legacy():
    count=0;manifests={}
    for g in range(2,7):
        path=ROOT/f'10_Experiments/manifests/g{g}_run.json'
        m=json.loads(path.read_text());manifests[path.relative_to(ROOT).as_posix()]=sha(path)
        for name,digest in m['sha256'].items():
            if sha(ROOT/name)!=digest:raise ValueError('Legacy provenance mismatch: '+name)
            count+=1
    return dict(entries_checked=count,manifest_sha256=manifests)

def load_inputs():
    pools=g6_inputs(ROOT)
    old_scenarios=json.loads((ROOT/'10_Experiments/g6/scenarios.json').read_text())
    used={i for s in old_scenarios for i in s['input_ids']['kws']}
    used|={c['id'] for c in json.loads((ROOT/'10_Experiments/g6/accuracy.json').read_text())['checks'] if c['workload']=='kws'}
    used_hashes={a['sha256'] for a in pools['kws'] if a['id'] in used}
    seen=set();available=[]
    for a in pools['kws']:
        if a['sha256'] not in used_hashes and a['sha256'] not in seen:
            available.append(a);seen.add(a['sha256'])
    development=[];holdout=[]
    for label in range(12):
        part=[a for a in available if a['label']==label]
        if len(part)<4:raise ValueError('Insufficient fresh KWS class '+str(label))
        development+=part[:1];holdout+=part[1:4]
    result=dict(development=dict(kws=development),holdout=dict(kws=holdout))
    dest=ROOT/'05_Model_Training/g8_vww';meta=json.loads((dest/'manifest.json').read_text())
    with np.load(dest/'inputs.npz') as data:x=data['x']
    if hashlib.sha256(x.tobytes()).hexdigest()!=meta['tensor_sha256']:raise ValueError('G8 VWW tensors')
    old=json.loads((ROOT/'05_Model_Training/reference_vww/coco_subset/manifest.json').read_text())
    if {m['id'] for m in meta['images']}&{m['id'] for m in old['images']}:raise ValueError('VWW ID overlap')
    for split in result:
        result[split]['vww']=[dict(id=m['id'],label=m['label'],sha256=m['feature_sha256'],x=x[i:i+1].copy())
            for i,m in enumerate(meta['images']) if m['split']==split]
    for work in ('kws','vww'):
        a={v['sha256'] for v in result['development'][work]};b={v['sha256'] for v in result['holdout'][work]}
        if a&b:raise ValueError('G8 development/holdout leakage')
    return result

def schedules(p):
    out=synthetic(p)
    for s in out:s['id']=s['id'].replace('g6_','g8_')
    for ci,cap in enumerate(p['capacities_j']):
        for ri,rate in enumerate(p['reset_rates_hz']):
            for rep in range(p['reset_replicates']):
                seed=p['reset_seed_base']+ci*10000+ri*100+rep;rng=random.Random(seed)
                t=0.;resets=[]
                while True:
                    t+=rng.expovariate(rate)
                    if t>=p['horizon_s']:break
                    resets.append(t)
                out.append(dict(id=f'g8_reset_{seed}',seed=seed,family=f'reset{rate:g}_cap{ci}',source_kind='external_reset',
                    capacity_j=cap,trace=[[0.,p['source_mean_w']]],reset_times_s=resets,actual_outage_rate_hz=rate,
                    horizon_s=p['horizon_s'],arrivals_s=p['arrivals_s'],deadline_interval_s=p['deadline_interval_s']))
    return out

def summarize(rows,p):
    result={}
    for work in p['workloads']:
        domains={}
        for domain,kinds in [('stochastic',{'mild','severe'}),('external_reset',{'external_reset'}),('steady',{'steady'}),('zero',{'zero'})]:
            part=[a for a in rows if a['workload']==work and a['source_kind'] in kinds]
            methods={m:[r for r in part if r['method']==m] for m in p['methods']}
            comparisons={}
            for m in p['methods']:
                if m=='RECAP_redo':continue
                a,b=methods['RECAP_redo'],methods[m]
                comparisons[m]=dict(comparison=comparison(a,b,p),
                    paired_bootstrap=bootstrap(a,b,p) if domain in ('stochastic','external_reset') else None)
            domains[domain]=dict(methods={m:aggregate(r) for m,r in methods.items()},comparisons=comparisons)
        result[work]=domains
    return result

def run(args):
    start=time.perf_counter()
    if not args.run_id.replace('-','').replace('_','').isalnum():raise ValueError('simple run-id required')
    out=ROOT/'10_Experiments/g8'/args.run_id
    if out.exists():raise FileExistsError('Run exists; choose a new --run-id. Never overwrite frozen results.')
    legacy=verify_legacy();print('G2-G6 legacy hashes verified:',legacy['entries_checked'],flush=True)
    p=json.loads((ROOT/'09_Simulation/configs/g6_protocol.json').read_text())
    p.update(json.loads((ROOT/'09_Simulation/configs/g8_protocol.json').read_text()))
    out.mkdir(parents=True);dump(out/'protocol.json',p)
    stream=io.StringIO();suite=unittest.defaultTestLoader.discover(str(ROOT/'09_Simulation/tests_g8'))
    tests=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    (out/'unit_tests.txt').write_text(stream.getvalue(),encoding='utf-8')
    if not tests.wasSuccessful():raise RuntimeError('G8 tests failed')
    pools=load_inputs();models={n:Model(ROOT,n) for n in p['workloads']}
    # Development and all diagnostic faults execute before holdout freeze.
    development=[];faults=[];equivalence=[]
    for work,model in models.items():
        item=pools['development'][work][0]
        own=model.uninterrupted(item['x']);gold=model.reference(item['x'])
        if len(own)!=len(gold) or any(not np.array_equal(a,b) for a,b in zip(own,gold)):raise AssertionError('G8 operator mismatch')
        equivalence.append(dict(workload=work,input_id=item['id'],elements=sum(a.size for a in own),mismatches=0))
        s=dict(id='development_'+work,seed=p['development_seed_base'],family='development',source_kind='development',
            capacity_j=100e-6,trace=[[0.,.02]],horizon_s=24.)
        for action in ('layer_log','graph_root','checkpoint_partial'):
            config=dict(p,ci_chunks=[16],tiles=[[1,64]],planning_outage_rate_hz=100000.) if action=='checkpoint_partial' else p
            r=Runtime(ROOT,model,config,s,fault=dict(action=action,cut=70)).run([dict(item,arrival_s=0.,deadline_s=24.)])
            if r['completed']!=1 or not r['fault_executed']:raise AssertionError('G8 graph fault not exercised: '+work+'/'+action)
            faults.append(dict(workload=work,action=action,completed=1,fault_executed=True,losses=r['losses']))
        for interval in p['periodic_ci_candidates']:
            config=dict(p,periodic_ci=interval)
            for reset in (False,True):
                case=dict(s,id=f'development_{work}_{reset}',trace=[[0.,.002]],reset_times_s=[.08,.3,.7] if reset else [])
                row=Runtime(ROOT,model,config,case,'B4_periodic').run([dict(item,arrival_s=0.,deadline_s=24.)])
                row['periodic_ci']=interval;development.append(row)
        print('G8 development/equivalence/faults PASS:',work,flush=True)
    ranked=[]
    for interval in p['periodic_ci_candidates']:
        score=0.;completion=0
        for work in p['workloads']:
            agg=aggregate([r for r in development if r['workload']==work and r['periodic_ci']==interval])
            completion+=agg['completed'];score+=agg['energy_per_completed_j'] if agg['energy_per_completed_j'] is not None else 1e9
        ranked.append((-completion,score,interval))
    p['periodic_ci']=min(ranked)[2]
    dump(out/'protocol.json',p);dump(out/'development.json',development)
    dump(out/'faults.json',dict(status='PASS_FINITE_GRAPH_FAULTS',cases=faults,scope='6 full-network directed faults; byte-cut tests separately in unit_tests.txt'))
    dump(out/'equivalence.json',equivalence)
    scenario=assign_inputs(schedules(p),pools['holdout'])
    old_seeds={s['seed'] for s in json.loads((ROOT/'10_Experiments/g6/scenarios.json').read_text())}
    if old_seeds&{s['seed'] for s in scenario}:raise AssertionError('trace seed overlap')
    dump(out/'scenarios.json',scenario)
    dump(out/'input_splits.json',{split:{w:[{k:v for k,v in a.items() if k!='x'} for a in items] for w,items in works.items()} for split,works in pools.items()})
    sources=list((ROOT/'09_Simulation').glob('*.py'))+list((ROOT/'09_Simulation/recap').glob('*.py'))
    sources+=list((ROOT/'09_Simulation/tests_g8').glob('*.py'))+[Path(__file__),ROOT/'09_Simulation/configs/g8_protocol.json',ROOT/'09_Simulation/configs/g6_protocol.json',ROOT/'09_Simulation/configs/g2_assumed_debug.json',ROOT/'10_Experiments/setup_g8_data.py']
    inputs=[out/n for n in ('protocol.json','scenarios.json','input_splits.json','development.json','faults.json','equivalence.json')]
    inputs += [ROOT/'05_Model_Training/reference_mlperf/kws_ref_model.tflite',ROOT/'05_Model_Training/reference_vww/vww_96_int8.tflite']
    inputs += list((ROOT/'05_Model_Training/g8_vww').glob('*'))
    inputs += [ROOT/'05_Model_Training/reference_eembc'/a['id'] for split in pools.values() for a in split['kws']]
    frozen=dict(version=p['version'],frozen_at_utc=datetime.now(timezone.utc).isoformat(),legacy=legacy,
        source_sha256={v.relative_to(ROOT).as_posix():sha(v) for v in sorted(set(sources))},
        input_sha256={v.relative_to(ROOT).as_posix():sha(v) for v in sorted(set(inputs)) if v.is_file()},
        python=sys.version,planning_hazard_fitted=False,periodic_ci_fitted_on='development only',
        fresh_scope='new runtime input hashes and source/reset seeds; same pretrained model and assumed cost family')
    dump(out/'freeze.json',frozen);print('G8 FROZEN before holdout; B4 periodic_ci:',p['periodic_ci'],flush=True)
    lookup={w:{a['id']:a for a in items} for w,items in pools['holdout'].items()}
    rows=[]
    raw=out/'main.jsonl'
    def evaluate(work,s,method,config=p):
        items=[dict(lookup[work][i],arrival_s=t,deadline_s=min(s['horizon_s'],t+s['deadline_interval_s'])) for i,t in zip(s['input_ids'][work],s['arrivals_s'])]
        r=Runtime(ROOT,models[work],config,s,method).run(items);r['source_kind']=s['source_kind']
        return r
    with raw.open('w',encoding='utf-8') as f:
        for work in p['workloads']:
            for method in p['methods']:
                group=[]
                for s in scenario:
                    row=evaluate(work,s,method);rows.append(row);group.append(row)
                    f.write(json.dumps(row,allow_nan=False)+'\n');f.flush()
                print('G8 main',work,method,aggregate(group)['completed'],'/',sum(r['total_inputs'] for r in group),flush=True)
    # Preset stress/ablation subset, kept out of the primary estimate.
    selected=[s for s in scenario if s['source_kind']=='steady' or (s['source_kind']=='external_reset' and s['seed']%100==0)]
    secondary=[]
    variants=[('scratch_output',dict(p,direct_publication=False)),('hazard_zero',dict(p,planning_outage_rate_hz=0.)),
        ('hazard_high',dict(p,planning_outage_rate_hz=20.)),('nvm_quarter',dict(p,nvm_energy_scale=.25)),('nvm_four',dict(p,nvm_energy_scale=4.))]
    for label,config in variants:
        for work in p['workloads']:
            for method in ('B3_adaptive','RECAP_redo'):
                for s in selected:
                    row=evaluate(work,s,method,config);row['intervention']=label;secondary.append(row)
        print('G8 secondary complete:',label,flush=True)
    with (out/'secondary.jsonl').open('w',encoding='utf-8') as f:
        for row in secondary:f.write(json.dumps(row,allow_nan=False)+'\n')
    result=dict(status='G8_ENGINEERING_EVALUATION_EXECUTED',calibrated=False,submission_ready=False,
        test_count=tests.testsRun,main_rows=len(rows),secondary_rows=len(secondary),scenarios=len(scenario),
        workloads=summarize(rows,p),direct_output_scratch_writes=sum(r['units'].get('checkpoint_output',0) for r in rows),
        selected_save_dw_jobs=sum(v for r in rows if r['method']=='RECAP_redo' for k,v in r['chosen'].items() if '_z1' in k),
        selected_keep_ps_jobs=sum(v for r in rows if r['method']=='RECAP_redo' for k,v in r['chosen'].items() if 'ps1' in k),
        main_completed=sum(r['completed'] for r in rows),elapsed_s=time.perf_counter()-start,
        limitations=['Assumed cost/hazard, not measured or calibrated; inherited DW x30 debug coefficient.',
            'Renewal ranking is approximate: boundary losses, nominal residency and simplified boot/read costs; actual execution uses absolute-time disconnects.',
            'B4_periodic is a local periodic-checkpoint adaptation inspired by checkpoint/recomputation literature, not Chime/CIM-Tuner reproduction.',
            'Horizon/deadlines differ from G6; no before/after percentage may mix protocols.',
            'Small VWW subset and same pretrained models; not a full benchmark accuracy claim.',
            'The reserved G8 feature pool was used in an aborted G8_1.0 integration run; G8_1.1 uses new source/reset seeds after a fixed B1 geometry bug, without policy tuning.',
            'No hardware, complete accelerator RTL, calibrated macro, formal proof or independent human novelty review.'])
    dump(out/'results.json',result)
    for field in ('source_sha256','input_sha256'):
        for name,digest in frozen[field].items():
            if sha(ROOT/name)!=digest:raise AssertionError('post-freeze mutation: '+name)
    for name,digest in legacy['manifest_sha256'].items():
        if sha(ROOT/name)!=digest:raise AssertionError('legacy manifest changed')
    files=[f for f in out.rglob('*') if f.is_file()]
    dump(out/'manifest.json',dict(status=result['status'],sha256={f.relative_to(ROOT).as_posix():sha(f) for f in sorted(files)},
        command=f'python 10_Experiments/run_g8.py --run-id {args.run_id}',calibrated=False))
    print(json.dumps({k:result[k] for k in ('status','main_rows','secondary_rows','main_completed','selected_save_dw_jobs','selected_keep_ps_jobs','elapsed_s')},indent=2),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id',default='20261023-v2')
    run(parser.parse_args())
