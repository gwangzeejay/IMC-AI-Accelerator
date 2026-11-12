"""Read-only verification of G2-G6 hashes and independent paper aggregations."""
from pathlib import Path
import hashlib
import json
import math
import time

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def read(p):return json.loads((ROOT/p).read_text(encoding='utf-8'))

def close(a,b):
    if a is None or b is None:assert a is b,(a,b)
    else:assert math.isclose(a,b,rel_tol=1e-11,abs_tol=1e-14),(a,b)

def main():
    start=time.perf_counter();files=0;manifests={}
    for stage in ['g2','g3','g4','g5','g6']:
        path=ROOT/f'10_Experiments/manifests/{stage}_run.json';m=json.loads(path.read_text(encoding='utf-8'))
        for name,digest in m['sha256'].items():
            assert sha(ROOT/name)==digest,'Manifest mismatch: '+name;files+=1
        manifests[stage]={'files':len(m['sha256']),'manifest_sha256':sha(path)}
    f=read('10_Experiments/g6/frozen_protocol.json')
    for field in ['source_sha256','input_sha256']:
        for name,digest in f[field].items():assert sha(ROOT/name)==digest,'Freeze mismatch: '+name
    assert f['no_g6_tuning'] and f['reserve_fraction']==.3
    data=read('10_Experiments/g6/results.json');scenarios={a['id']:a for a in read('10_Experiments/g6/scenarios.json')}
    rows=[json.loads(line) for line in (ROOT/'10_Experiments/g6/raw/main.jsonl').read_text().splitlines()]
    assert len(rows)==448 and sum(a['completed'] for a in rows)==481
    comparisons=0
    for work,domains in data['workloads'].items():
        for domain,item in domains.items():
            kinds={'synthetic_stochastic':{'mild','severe'},'eth_measured_derived_rail':{'eth_measured_derived_rail'},
                   'steady':{'steady'},'zero':{'zero'}}[domain]
            for method,value in item['methods'].items():
                part=[r for r in rows if r['workload']==work and r['method']==method and scenarios[r['scenario_id']]['source_kind'] in kinds]
                assert part,(work,domain,method)
                energy=sum(a['energy_j'] for a in part);commits=sum(a['completed'] for a in part);total=sum(a['total_inputs'] for a in part)
                assert commits==value['completed'] and total==value['total_inputs']
                close(energy,value['energy_j']);close(None if commits==0 else energy/commits,value['energy_per_completed_j'])
                comparisons+=1
            a=item['methods']['RECAP']['energy_per_completed_j'];b=item['methods']['B3_adaptive']['energy_per_completed_j']
            close(None if a is None or b is None else 1-a/b,item['comparison_vs_adaptive']['relative_energy_reduction'])
            if domain=='eth_measured_derived_rail':
                assert item['paired_bootstrap']['undefined_replicates']>0
                assert item['paired_bootstrap']['energy_reduction_ci95'] is None
    assert not data['calibrated'] and not data['ready_for_paper_energy_results']
    for r in rows:
        close(sum(r['breakdown_j'].values()),r['energy_j'])
        assert r['admitted_unit_depletions']==0 and not r['calibrated']
    assets=HERE/'assets/sources.json'
    if assets.exists():
        for name,digest in json.loads(assets.read_text()).items():assert sha(ROOT/name)==digest,'Stale paper asset: '+name
    report={'status':'PASS_ARTIFACT_AUDIT','execution_scope':'Hash verification and independent raw-row aggregation; no inference rerun, fitting, physical calibration, or cross-host validation.',
            'files_checked':files,'manifests':manifests,'aggregate_cells_checked':comparisons,
            'main_rows':len(rows),'main_committed_outputs':481,'frozen_policy_preserved':True,
            'submission_ready':False,'elapsed_s':time.perf_counter()-start}
    (HERE/'evidence_audit.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='manifests'},indent=2))
    return 0

if __name__=='__main__':raise SystemExit(main())
