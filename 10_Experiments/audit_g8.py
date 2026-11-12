"""Read-only independent audit of G8 hashes, pairing and raw-row aggregates."""
import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def close(a,b):
    if a is None or b is None:
        if a is not b:raise AssertionError((a,b))
    elif not math.isclose(a,b,rel_tol=1e-10,abs_tol=1e-13):raise AssertionError((a,b))

def audit(run_id):
    out=ROOT/'10_Experiments/g8'/run_id
    if not (out/'manifest.json').exists():raise ValueError('Incomplete/aborted run has no final manifest')
    manifest=json.loads((out/'manifest.json').read_text());count=0
    frozen=json.loads((out/'freeze.json').read_text())
    for hashes in (manifest['sha256'],frozen['source_sha256'],frozen['input_sha256'],frozen['legacy']['manifest_sha256']):
        for name,digest in hashes.items():
            if sha(ROOT/name)!=digest:raise AssertionError('Hash mismatch: '+name)
            count+=1
    p=json.loads((out/'protocol.json').read_text());result=json.loads((out/'results.json').read_text())
    scenarios=json.loads((out/'scenarios.json').read_text());lookup={s['id']:s for s in scenarios}
    if len(lookup)!=len(scenarios):raise AssertionError('duplicate source IDs')
    seeds=[s['seed'] for s in scenarios]
    if len(set(seeds))!=len(seeds):raise AssertionError('duplicate independent seed')
    legacy={s['seed'] for s in json.loads((ROOT/'10_Experiments/g6/scenarios.json').read_text())}
    if legacy&set(seeds):raise AssertionError('G6/G8 seed leakage')
    pools=json.loads((out/'input_splits.json').read_text())
    for work in p['workloads']:
        dev={r['sha256'] for r in pools['development'][work]};test={r['sha256'] for r in pools['holdout'][work]}
        if dev&test:raise AssertionError('development/holdout feature leakage')
    rows=[json.loads(line) for line in (out/'main.jsonl').read_text().splitlines()]
    expected={(w,m,s) for w in p['workloads'] for m in p['methods'] for s in lookup}
    actual={(r['workload'],r['method'],r['scenario_id']) for r in rows}
    if actual!=expected or len(rows)!=len(actual):raise AssertionError('incomplete/duplicated main grid')
    secondary=[json.loads(line) for line in (out/'secondary.jsonl').read_text().splitlines()]
    interventions={'scratch_output','hazard_zero','hazard_high','nvm_quarter','nvm_four'}
    selected={s['id'] for s in scenarios if s['source_kind']=='steady' or (s['source_kind']=='external_reset' and s['seed']%100==0)}
    expected_secondary={(w,m,s,k) for w in p['workloads'] for m in ('B3_adaptive','RECAP_redo') for s in selected for k in interventions}
    actual_secondary={(r['workload'],r['method'],r['scenario_id'],r['intervention']) for r in secondary}
    if expected_secondary!=actual_secondary or len(secondary)!=len(actual_secondary):raise AssertionError('incomplete/duplicated secondary grid')
    if result['secondary_rows']!=len(secondary):raise AssertionError('secondary count')
    for r in secondary:
        close(sum(r['breakdown_j'].values()),r['energy_j']);close(r['energy_balance_error_j'],0.)
        if r['calibrated'] or r['admitted_unit_depletions']!=0:raise AssertionError('secondary scope/admission')
        if r['max_sram_algorithm_bytes']>p['sram_bytes'] or r['max_nvm_reserved_bytes']>p['nvm_bytes']:raise AssertionError('secondary memory')
        if r['direct_publication']!=(r['intervention']!='scratch_output'):raise AssertionError('publication intervention')
        if r['planning_outage_rate_hz']!={'hazard_zero':0.,'hazard_high':20.}.get(r['intervention'],p['planning_outage_rate_hz']):raise AssertionError('hazard intervention')
        if r['completed']!=len(r['outputs']):raise AssertionError('secondary completion ledger')
    for r in rows:
        close(sum(r['breakdown_j'].values()),r['energy_j']);close(r['energy_balance_error_j'],0.)
        if r['calibrated'] or not r['direct_publication']:raise AssertionError('wrong evidence scope')
        if r['units'].get('checkpoint_output',0)!=0:raise AssertionError('duplicate output scratch publication')
        if r['admitted_unit_depletions']!=0:raise AssertionError('energy admission violated')
        if r['max_sram_algorithm_bytes']>p['sram_bytes'] or r['max_nvm_reserved_bytes']>p['nvm_bytes']:raise AssertionError('memory bound')
        if r['completed']!=sum('committed_s' in s for s in r['statuses']) or r['completed']!=len(r['outputs']):raise AssertionError('completion ledger')
        if r['total_inputs']!=len(r['statuses']):raise AssertionError('input denominator')
        if not math.isfinite(r['energy_j']) or r['energy_j']<0:raise AssertionError('invalid load energy')
    cells=0
    for work,domains in result['workloads'].items():
        for domain,item in domains.items():
            kinds={'stochastic':{'mild','severe'},'external_reset':{'external_reset'},'steady':{'steady'},'zero':{'zero'}}[domain]
            for method,value in item['methods'].items():
                part=[r for r in rows if r['workload']==work and r['method']==method and r['source_kind'] in kinds]
                energy=sum(r['energy_j'] for r in part);done=sum(r['completed'] for r in part);total=sum(r['total_inputs'] for r in part)
                if value['completed']!=done or value['total_inputs']!=total:raise AssertionError('aggregate count')
                close(value['energy_j'],energy);close(value['completion_rate'],done/total)
                close(value['energy_per_completed_j'],energy/done if done else None)
                latencies=sorted(s['committed_s']-s['arrival_s'] if 'committed_s' in s else math.inf for r in part for s in r['statuses'])
                p95=latencies[math.ceil(.95*total)-1]
                if value['p95_is_infinite']!=math.isinf(p95):raise AssertionError('p95 censoring')
                close(value['p95_latency_s'],None if math.isinf(p95) else p95)
                cells+=1
            ea=item['methods']['RECAP_redo']['energy_per_completed_j']
            for baseline,comparison in item['comparisons'].items():
                eb=item['methods'][baseline]['energy_per_completed_j']
                close(comparison['comparison']['relative_energy_reduction'],None if ea is None or eb is None else 1-ea/eb)
    if result['calibrated'] or result['submission_ready']:raise AssertionError('unsupported claim')
    return dict(status='PASS_G8_INDEPENDENT_AUDIT',run_id=run_id,hash_entries_checked=count,main_rows=len(rows),secondary_rows=len(secondary),aggregate_cells=cells,
        auditor_sha256=sha(Path(__file__)),
        scope='Read-only hashes, independent raw aggregation, full pairing, ledger/memory/censoring checks; not a fresh inference replay or physical calibration')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run-id',default='20261023-v2')
    print(json.dumps(audit(parser.parse_args().run_id),indent=2))
