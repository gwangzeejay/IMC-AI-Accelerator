"""Optional CPU worker for source-frozen G6 cases; no policy or test fitting.

Equivalent to the sequential runner's sensitivity/digital cases. Atomic cache
publication lets independent processes help without exposing partial JSON.
"""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'09_Simulation'))
from g5_experiments import sha,dump
from g6_experiments import canonical
from g6_model import Model
from g6_inputs import inputs
from g6_runtime import Runtime


def run(name):
    start=time.perf_counter();out=ROOT/'10_Experiments/g6'
    frozen=json.loads((out/'frozen_protocol.json').read_text())
    for field in ('source_sha256','input_sha256'):
        for file,digest in frozen[field].items():
            if sha(ROOT/file)!=digest:raise AssertionError('frozen input/source changed')
    freeze=canonical(frozen['source_sha256']|frozen['input_sha256'])
    p=json.loads((out/'protocol_snapshot.json').read_text());model=Model(ROOT,name)
    pool={a['id']:a for a in inputs(ROOT)[name]};scenarios=json.loads((out/'scenarios.json').read_text())
    subset=[s for s in scenarios if s['source_kind'] in ('steady','zero') or (s['source_kind'] in ('mild','severe') and s['seed']%100<2)]
    sens=[s for s in subset if s['source_kind'] in ('mild','severe')]
    tasks=[]
    for knob,values in p['sensitivity'].items():
        for value in values:
            config=dict(p,**{knob:value})
            for method in ('B3_adaptive','RECAP'):
                tasks += [(s,method,'cim',config) for s in sens]
    for method in ('B3_adaptive','RECAP'):tasks += [(s,method,'digital',p) for s in subset]
    written={};skipped=0;stage=ROOT/'tmp/g6_worker_staging';stage.mkdir(exist_ok=True)
    for index,(s,method,backend,config) in enumerate(tasks):
        key=canonical(dict(freeze=freeze,workload=name,scenario=s,method=method,variant='full',backend=backend,config=config))
        path=out/'cases'/(key+'.json')
        if path.exists():skipped+=1;continue
        items=[dict(pool[input_id],arrival_s=t,deadline_s=min(s['horizon_s'],t+s['deadline_interval_s'])) for input_id,t in zip(s['input_ids'][name],s['arrivals_s'])]
        row=Runtime(ROOT,model,config,s,method,'full',backend).run(items)
        temp=stage/(key+f'.{os.getpid()}.tmp');dump(temp,row)
        # Recheck before atomic publication; another process may have finished it.
        if path.exists():
            if json.loads(path.read_text())!=row:raise AssertionError('parallel deterministic case mismatch')
            temp.unlink();skipped+=1
        else:temp.replace(path);written[path.relative_to(ROOT).as_posix()]=sha(path)
        if (index+1)%32==0:print('G6 CPU worker',name,index+1,'/',len(tasks),flush=True)
    for field in ('source_sha256','input_sha256'):
        for file,digest in frozen[field].items():
            if sha(ROOT/file)!=digest:raise AssertionError('frozen source changed during worker')
    dest=ROOT/'10_Experiments/g6_parallel';dest.mkdir(exist_ok=True)
    dump(dest/(name+'.json'),dict(workload=name,recorded_at_utc=datetime.now(timezone.utc).isoformat(),
        command=f'python 10_Experiments/prefill_g6_cases.py --workload {name}',driver_sha256=sha(Path(__file__)),
        frozen_protocol_sha256=sha(out/'frozen_protocol.json'),freeze_id=freeze,source_frozen=True,
        tasks=len(tasks),written=len(written),skipped=skipped,elapsed_s=time.perf_counter()-start,case_sha256=written))
    print('G6 CPU worker complete:',name,'published',len(written),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--workload',choices=['kws','vww'],required=True)
    run(parser.parse_args().workload)
