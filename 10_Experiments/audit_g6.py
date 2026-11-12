"""Post-run integrity and coverage audit. Never tune or rerun held-out inference."""
from collections import Counter
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'09_Simulation'))
from g5_experiments import sha,dump
from g6_experiments import summarize,canonical


def run():
    out=ROOT/'10_Experiments/g6';dest=ROOT/'10_Experiments/g6_audit';dest.mkdir(exist_ok=True)
    provenance={}
    for milestone in ('g2','g3','g4','g5','g6'):
        path=ROOT/f'10_Experiments/manifests/{milestone}_run.json';m=json.loads(path.read_text())
        for name,digest in m['sha256'].items():
            if sha(ROOT/name)!=digest:raise AssertionError('provenance mismatch: '+name)
        provenance[milestone]=dict(files=len(m['sha256']),manifest_sha256=sha(path))
    frozen=json.loads((out/'frozen_protocol.json').read_text())
    for field in ('source_sha256','input_sha256'):
        for name,digest in frozen[field].items():
            if sha(ROOT/name)!=digest:raise AssertionError('freeze mismatch '+name)
    p=json.loads((out/'protocol_snapshot.json').read_text());scenarios=json.loads((out/'scenarios.json').read_text())
    smap={a['id']:a for a in scenarios}
    rows={name:[json.loads(line) for line in (out/f'raw/{name}.jsonl').read_text().splitlines()] for name in ('main','ablations','sensitivity','backend_factorial')}
    records=[r for part in rows.values() for r in part]
    for row in records:
        s=smap[row['scenario_id']]
        if abs(sum(row['breakdown_j'].values())-row['energy_j'])>1e-9 or abs(row['energy_balance_error_j'])>1e-9:raise AssertionError('energy balance')
        if row['admitted_unit_depletions']:raise AssertionError('admitted depletion')
        if row['max_sram_algorithm_bytes']>p['sram_bytes'] or row['max_nvm_reserved_bytes']>p['nvm_bytes']:raise AssertionError('memory')
        if row['completed']!=len(row['outputs']) or row['total_inputs']!=len(s['arrivals_s']):raise AssertionError('count')
        if [a['arrival_s'] for a in row['statuses']]!=s['arrivals_s']:raise AssertionError('arrivals')
        if [a['input_id'] for a in row['outputs']]!=s['input_ids'][row['workload']][:row['completed']]:raise AssertionError('FIFO output IDs')
        if row['completed']==0 and row['energy_per_completed_j'] is not None:raise AssertionError('zero denominator')
        if row['incomplete']+row['failed'] and row['total_inputs']<20 and not row['p95_is_infinite']:raise AssertionError('p95 unfinished')
    for name in p['workloads']:
        for method in ('B1_layer','B2_fixed','B3_adaptive','RECAP'):
            part=[r for r in rows['main'] if r['workload']==name and r['method']==method]
            if len(part)!=len(scenarios) or {r['scenario_id'] for r in part}!=set(smap):raise AssertionError('main pairing')
        for variant in p['ablations']:
            if not any(r['variant']==variant and r['workload']==name for r in rows['ablations']):raise AssertionError('ablation missing')
        for knob,values in p['sensitivity'].items():
            for value in values:
                for method in ('B3_adaptive','RECAP'):
                    if not any(r['workload']==name and r['knob']==knob and r['value']==value and r['method']==method for r in rows['sensitivity']):raise AssertionError('sensitivity cell missing')
    result=json.loads((out/'results.json').read_text());again=summarize(rows['main'],rows['ablations'],rows['sensitivity'],rows['backend_factorial'],scenarios,p)
    for key,value in again.items():
        if result[key]!=value:raise AssertionError('summary changed: '+key)
    # Verify model/source hashes against the pinned download manifest too.
    base=ROOT/'05_Model_Training/reference_vww';source=json.loads((base/'source_manifest.json').read_text())
    for name,info in source['files'].items():
        if sha(base/name)!=info['sha256']:raise AssertionError('VWW original source checksum')
    pools=json.loads((out/'input_pools.json').read_text())
    prior=json.loads((ROOT/'10_Experiments/g5/scenarios.json').read_text());old_ids={i for group in prior.values() for s in group for i in s['input_ids']}
    old_ids|={a['input_id'] for a in json.loads((ROOT/'10_Experiments/g5/accuracy.json').read_text())['checks']}
    old_hashes=set()
    for part in json.loads((ROOT/'10_Experiments/g5/input_splits.json').read_text()).values():
        old_hashes|={a['sha256'] for a in part if a['id'] in old_ids}
    if old_hashes & {a['sha256'] for a in pools['kws']}:raise AssertionError('G5 runtime input hash leakage')
    old_seeds={s['seed'] for group in prior.values() for s in group}
    seeds=[s['seed'] for s in scenarios]
    if len(seeds)!=len(set(seeds)) or set(seeds)&old_seeds:raise AssertionError('power-seed reuse')
    faults=json.loads((out/'faults.json').read_text())
    if faults['mismatches'] or faults['random_large_slot_schedules']!=1000 or faults['full_network_cases']!=8:raise AssertionError('fault evidence')
    case_contents={canonical(json.loads(f.read_text())) for f in (out/'cases').glob('*.json')}
    for row in records:
        clean={k:v for k,v in row.items() if k not in ('experiment','ablation','knob','value')}
        if canonical(clean) not in case_contents:raise AssertionError('raw row missing source-bound case artifact')
    domain_counts=Counter(s['source_kind'] for s in scenarios)
    report=dict(status='PASS_G6_POST_RUN_AUDIT',provenance=provenance,
        logical_rows=len(records),case_files=len(list((out/'cases').glob('*.json'))),
        main_scenarios_per_workload_method=len(scenarios),source_domains=dict(domain_counts),
        completed_outputs_in_main=sum(r['completed'] for r in rows['main']),
        max_sram_algorithm_bytes=result['max_sram_algorithm_bytes'],max_nvm_reserved_bytes=result['max_nvm_reserved_bytes'],
        source_seed_reuse_with_g5=0,input_hash_reuse_with_g5_runtime=0,
        ablations_per_workload=len(p['ablations']),sensitivity_axes=len(p['sensitivity']),
        losing_trace_comparisons=len(result['losing_trace_comparisons']),
        frozen_protocol_sha256=sha(out/'frozen_protocol.json'),
        scope='artifact/coverage/paired-statistic audit only; no new inference, fitting, calibration or physical validation')
    parallel={}
    for name in p['workloads']:
        path=ROOT/f'10_Experiments/g6_parallel/{name}.json'
        if not path.exists():continue
        worker=json.loads(path.read_text())
        if worker['driver_sha256']!=sha(ROOT/'10_Experiments/prefill_g6_cases.py') or worker['freeze_id']!=result['freeze_id']:
            raise AssertionError('parallel driver/source binding')
        for file,digest in worker['case_sha256'].items():
            if sha(ROOT/file)!=digest:raise AssertionError('worker case provenance')
        parallel[name]=dict(published=worker['written'],worker_manifest_sha256=sha(path))
    report['parallel_workers']=parallel
    dump(dest/'audit.json',report)
    dump(dest/'manifest.json',dict(command='python 10_Experiments/audit_g6.py',
        sha256={'10_Experiments/audit_g6.py':sha(Path(__file__)),'10_Experiments/g6_audit/audit.json':sha(dest/'audit.json')},
        g6_run_manifest_sha256=sha(ROOT/'10_Experiments/manifests/g6_run.json')))
    print(json.dumps({k:report[k] for k in ('status','logical_rows','case_files','completed_outputs_in_main','losing_trace_comparisons')}))


if __name__=='__main__':run()
