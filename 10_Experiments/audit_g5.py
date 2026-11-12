"""Post-run G5 provenance/metric audit; does not refit or rerun test policies."""
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import platform
import statistics
import sys
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'09_Simulation'))
from g5_experiments import aggregate,sha,dump
from g5_runtime import Runtime
from g5_storage import Store
import numpy as np


def run():
    out=ROOT/'10_Experiments/g5';dest=ROOT/'10_Experiments/g5_audit';dest.mkdir(exist_ok=True)
    provenance={}
    for milestone in ('g2','g3','g4','g5'):
        path=ROOT/f'10_Experiments/manifests/{milestone}_run.json'
        manifest=json.loads(path.read_text())
        for name,digest in manifest['sha256'].items():
            if sha(ROOT/name)!=digest:raise AssertionError('manifest mismatch: '+name)
        provenance[milestone]=dict(files=len(manifest['sha256']),manifest_sha256=sha(path))
    frozen=json.loads((out/'frozen_policy.json').read_text())
    for name,digest in frozen['source_sha256'].items():
        if sha(ROOT/name)!=digest:raise AssertionError('frozen source changed')
    splits=json.loads((out/'input_splits.json').read_text());sets={s:{a['sha256'] for a in part} for s,part in splits.items()}
    for i,s in enumerate(sets):
        for t in list(sets)[i+1:]:
            if sets[s]&sets[t]:raise AssertionError('identical-feature leakage')
    scenarios=json.loads((out/'scenarios.json').read_text());seeds=[a['seed'] for part in scenarios.values() for a in part]
    if len(seeds)!=len(set(seeds)):raise AssertionError('power-seed leakage')
    rows={s:[json.loads(line) for line in (out/f'raw/{s}.jsonl').read_text().splitlines()] for s in scenarios}
    p=json.loads((out/'protocol_snapshot.json').read_text());result=json.loads((out/'results.json').read_text())
    for split,part in rows.items():
        allowed={a['id'] for a in splits[split]}
        for s in scenarios[split]:
            if not set(s['input_ids'])<=allowed:raise AssertionError('input split mismatch')
        for row in part:
            if abs(sum(row['breakdown_j'].values())-row['energy_j'])>1e-10:raise AssertionError('energy ledger')
            if abs(row['energy_balance_error_j'])>1e-10:raise AssertionError('capacitor conservation')
            if row['admitted_unit_depletions']:raise AssertionError('admission failure')
            if row['max_sram_algorithm_bytes']>p['sram_bytes'] or row['max_nvm_reserved_bytes']>p['nvm_bytes']:
                raise AssertionError('memory bound')
            if row['completed']!=len(row['outputs']):raise AssertionError('output count')
    test=rows['test'];methods={}
    for method,expected in result['methods'].items():
        part=[r for r in test if r['method']==method]
        if aggregate(part)!=expected:raise AssertionError('aggregate mismatch '+method)
        if {r['scenario_id'] for r in part}!={s['id'] for s in scenarios['test']}:raise AssertionError('test pairing')
        choices=Counter()
        for r in part:choices.update(r['chosen'])
        methods[method]=dict(chosen=dict(choices),completed=expected['completed'],losses=expected['losses'],
            selected_save_z_jobs=sum(v for k,v in choices.items() if '_z1' in k),
            selected_keep_ps_jobs=sum(v for k,v in choices.items() if k.endswith('ps1')))
    a={r['scenario_id']:r for r in test if r['method']=='RECAP'}
    b={r['scenario_id']:r for r in test if r['method']=='B3_adaptive'}
    identical=sum(a[k]['energy_j']==b[k]['energy_j'] and a[k]['statuses']==b[k]['statuses'] and a[k]['chosen']==b[k]['chosen'] for k in a)
    # Host-only planning microprofile. No joules or target clock is inferred.
    class Dummy:pass
    scenario=dict(id='host_profile',seed=0,family='profile',capacity_j=100e-6,trace=[[0,.002]],horizon_s=4)
    runtime=Runtime(ROOT,Dummy(),p,scenario,'RECAP',reserve=frozen['mapper_reserve'])
    samples=[]
    for repeat in range(110):
        start=time.perf_counter_ns();runtime.plans(1,0);elapsed=time.perf_counter_ns()-start
        if repeat>=10:samples.append(elapsed/1000)
    # Derive enumerated persistence boundary count from the actual ops, not a
    # hand-maintained count in the report.
    store=Store('11'*32,np.zeros((1,49,10,1),dtype=np.int8),p)
    ops,_=store.scratch_ops(1,0,4,64,16,z=bytes(256),ps=bytes(1024));store.apply(ops)
    tests=[store.scratch_ops(1,0,4,64,32,z=bytes([1])*256,ps=bytes([2])*1024)[0],
        Store('11'*32,store.x,p).scratch_ops(1,0,4,64,64,out=bytes(256))[0],
        store.log_ops(0,0,4,64,0,bytes(256))[0],store.root_ops(1,b'new')[0]]
    profile=dict(scope='host Python candidate enumeration only; not embedded CPU timing/energy or TFLite arena',
        measured_at_utc=datetime.now(timezone.utc).isoformat(),platform=platform.platform(),python=sys.version,
        samples=len(samples),warmup=10,median_us=statistics.median(samples),p95_us=float(np.percentile(samples,95)))
    report=dict(status='PASS_G5_POST_RUN_AUDIT',provenance=provenance,
        independent_power_seeds=len(seeds),input_split_counts={s:len(part) for s,part in splits.items()},
        input_unique_hashes={s:len(h) for s,h in sets.items()},identical_feature_cross_split=0,
        total_evaluations=sum(len(part) for part in rows.values()),
        completed_runtime_outputs_checked=sum(r['completed'] for part in rows.values() for r in part),
        enumerated_ack_boundary_cases=sum(len(ops)+1 for ops in tests),
        recap_adaptive_identical_test_traces=identical,methods=methods,host_profile=profile,
        frozen_policy_sha256=sha(out/'frozen_policy.json'),
        analysis_scope='post-run integrity/summary/profile only; no policy refitting, no new held-out inference claim')
    dump(dest/'audit.json',report)
    dump(dest/'manifest.json',dict(command='python 10_Experiments/audit_g5.py',
        sha256={'10_Experiments/audit_g5.py':sha(Path(__file__)),'10_Experiments/g5_audit/audit.json':sha(dest/'audit.json')},
        g5_run_manifest_sha256=sha(ROOT/'10_Experiments/manifests/g5_run.json')))
    print(json.dumps({k:report[k] for k in ('status','total_evaluations','completed_runtime_outputs_checked','enumerated_ack_boundary_cases','recap_adaptive_identical_test_traces')}))


if __name__=='__main__':run()
