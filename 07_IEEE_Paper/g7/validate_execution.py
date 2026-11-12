"""Fresh same-host diagnostic executions, not independent-host validation."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib
import json
import sys
import time
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'09_Simulation'))
from g6_model import Model
from g6_inputs import inputs
from g6_runtime import Runtime

def read(p):return json.loads((ROOT/p).read_text())

def main():
    start=time.perf_counter();p=read('10_Experiments/g6/protocol_snapshot.json')
    frozen=read('10_Experiments/g6/frozen_protocol.json')
    for field in ['source_sha256','input_sha256']:
        for name,digest in frozen[field].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
    pools=inputs(ROOT);checks=[]
    for work in ['kws','vww']:
        model=Model(ROOT,work);a=pools[work][0];t=time.perf_counter()
        own=model.uninterrupted(a['x']);gold=model.reference(a['x'])
        mismatches=sum(int(np.count_nonzero(u!=v)) for u,v in zip(own,gold));assert not mismatches
        checks.append({'workload':work,'input_id':a['id'],'operator_outputs':len(own),
                       'elements':sum(x.size for x in own),'mismatches':mismatches,
                       'host_elapsed_s':time.perf_counter()-t})
    scenarios=read('10_Experiments/g6/scenarios.json');s=next(a for a in scenarios if a['source_kind']=='steady')
    model=Model(ROOT,'kws');lookup={a['id']:a for a in pools['kws']}
    items=[dict(lookup[name],arrival_s=t,deadline_s=min(s['horizon_s'],t+s['deadline_interval_s']))
           for name,t in zip(s['input_ids']['kws'],s['arrivals_s'])]
    original=next(json.loads(line) for line in (ROOT/'10_Experiments/g6/raw/main.jsonl').read_text().splitlines()
                  if json.loads(line)['scenario_id']==s['id'] and json.loads(line)['method']=='RECAP' and json.loads(line)['workload']=='kws')
    runs=[]
    for index in range(2):
        t=time.perf_counter();row=Runtime(ROOT,model,p,s,'RECAP').run(items)
        assert row==original,'Fresh runtime differs from frozen case'
        runs.append({'repeat':index+1,'energy_j':row['energy_j'],'completed':row['completed'],
                     'host_elapsed_s':time.perf_counter()-t,'matches_frozen_full_case':True})
    report={'status':'PASS_SAME_HOST_DIAGNOSTICS','recorded_at_utc':datetime.now(timezone.utc).isoformat(),
            'new_arithmetic_checks':checks,'fresh_runtime_case':s['id'],'runtime_repeats':runs,
            'energy_repeat_spread_j':max(a['energy_j'] for a in runs)-min(a['energy_j'] for a in runs),
            'cross_host_validation':'NOT_RUN','hardware_timing_validation':'NOT_RUN',
            'scope':'Two fresh uninterrupted inputs and two repeats of one existing steady KWS source case. '
                    'Same host and frozen code; no new holdout claim, policy tuning, or target energy/timing validation.',
            'elapsed_s':time.perf_counter()-start,'submission_ready':False}
    dest=ROOT/'10_Experiments/g7/cv_report.json';dest.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
    return 0

if __name__=='__main__':raise SystemExit(main())
