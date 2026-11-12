"""G3 finite crash campaign across small/large descriptors and four flags."""
import json
from pathlib import Path
import random
import time
from recap.g3_simulator import G3Simulator
from recap.simulator import Policy


def campaign(root,output,random_cases=1000,seed=81000):
    catalog=json.loads((output/'descriptors/catalog.json').read_text())
    protocol=json.loads((root/'09_Simulation/configs/g3_protocol.json').read_text())
    cases=[]
    for key in ('h1w1_co4','h4w2_co16'):
        job=catalog['catalog'][key]['jobs'][0]
        for z in (False,True):
            for ps in (False,True): cases.append((key,job,Policy(z,ps,16)))
    def make(case,faults=None):
        key,job,policy=case
        return G3Simulator(output/'descriptors'/job['path'],policy,
            slot_bytes=job['slot_bytes'],bank_bytes=protocol['bank_bytes'],sram_bytes=protocol['sram_bytes'],
            frontier=bytearray(len(catalog['catalog'][key]['jobs'])),job_index=0,faults=faults)
    counts=dict(boundary=0,interior_write=0,random_multi=0)
    coverage={};losses=0;lengths=[];rng=random.Random(seed);start=time.perf_counter()
    dest=output/'faults';dest.mkdir(exist_ok=True)
    with (dest/'cases.jsonl').open('w',encoding='utf-8') as log:
        def check(case,faults,kind):
            nonlocal losses
            sim=make(case,faults)
            r=sim.run(max_events=20000)
            if not r['completed'] or r['mismatches']!=0 or sim.frontier[0]!=1:
                raise AssertionError('G3 crash recovery failed')
            counts[kind]+=1;losses+=sim.unexpected_losses
            for fault in sim.executed_faults:
                key=fault['action']+'/'+fault['phase']
                coverage[key]=coverage.get(key,0)+1
            log.write(json.dumps(dict(descriptor_group=case[0],policy=case[2].name,kind=kind,
                faults=faults,executed_faults=sim.executed_faults,mismatches=r['mismatches'],frontier=sim.frontier[0]))+'\n')
        for case in cases:
            base=make(case);base.run();events=base.ledger.events
            lengths.append(len(events))
            for index,event in enumerate(events):
                check(case,{index:1},'boundary')
                if event['unit_kind']=='write_byte': check(case,{index:.5},'interior_write')
        for n in range(random_cases):
            index=n%len(cases);length=lengths[index]
            points={rng.randrange(length):rng.choice([0,.5,1])}
            for _ in range(rng.randint(1,5)):
                points[rng.randrange(length*3)]=rng.choice([0,.5,1])
            check(cases[index],points,'random_multi')
    report=dict(status='PASS',scope='two descriptor sizes, four flag combinations, finite boundaries and seeded multi-faults; not universal proof',
                counts=counts,total_cases=sum(counts.values()),executed_losses=losses,mismatches=0,
                coverage=coverage,seed=seed,elapsed_s=time.perf_counter()-start)
    (dest/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('status','total_cases','executed_losses','mismatches')}),flush=True)
    return report
