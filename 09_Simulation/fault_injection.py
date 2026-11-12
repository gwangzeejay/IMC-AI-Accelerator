"""Exhaustive single-cut boundaries plus seeded multi-cut G2 campaign.

Exhaustiveness is ONLY over the no-fault microtile's emitted operation
boundaries, four fixed policies, and selected interior-write cuts. It is not
an exhaustive proof for arbitrary networks, crash sequences or byte positions.
"""
import argparse
import json
from pathlib import Path
import random
import time
from recap.simulator import Simulator, Policy

ROOT=Path(__file__).resolve().parents[1]


def campaign(output, random_cases=1000, seed=20261015):
    if random_cases<0:
        raise ValueError('negative case count')
    fixture=ROOT/'10_Experiments/g2/reference/microtile.npz'
    output.mkdir(parents=True,exist_ok=True)
    rng=random.Random(seed)
    start=time.perf_counter()
    policies=[Policy(z,p) for z in (False,True) for p in (False,True)]
    counts={'single_boundary':0,'interior':0,'restore_interruption':0,'random_multi':0}
    coverage=set()
    fault_coverage={}
    baseline_lengths=[]
    actual_losses=0
    with (output/'cases.jsonl').open('w',encoding='utf-8') as log:
        def check(policy,faults,kind,label):
            nonlocal actual_losses
            sim=Simulator(fixture,policy,faults=faults)
            result=sim.run(max_events=20000)
            if not result['completed'] or result['mismatches']!=0:
                raise AssertionError(dict(label=label,faults=faults,result=result))
            counts[kind]+=1
            actual_losses+=result['unexpected_losses']
            for event in sim.executed_faults:
                key=(event['action'],event['phase'])
                fault_coverage[key]=fault_coverage.get(key,0)+1
            log.write(json.dumps(dict(case=label,policy=policy.name,kind=kind,faults=faults,
                                      losses=result['unexpected_losses'],mismatches=result['mismatches'],
                                      executed_faults=sim.executed_faults))+'\n')
        for policy in policies:
            base=Simulator(fixture,policy)
            assert base.run()['completed']
            events=base.ledger.events
            baseline_lengths.append(len(events))
            for index,event in enumerate(events):
                coverage.add((event['action'],event['phase']))
                check(policy,{index:1.0},'single_boundary',f'{policy.name}_after_{index}')
                if event['unit_kind']=='write_byte':
                    # Atomic marker torn case keeps old marker; byte writes keep prefix.
                    check(policy,{index:0.5},'interior',f'{policy.name}_inside_{index}')
            if policy.save_z or policy.keep_ps:
                publish=next(i for i,e in enumerate(events) if e['phase']=='publish')
                probe=Simulator(fixture,policy,faults={publish:1.0})
                probe.run()
                # Reconstruct primitive indices: POWER_LOSS is a ledger event,
                # not an executed primitive in the fault-index namespace.
                primitive=0
                for event in probe.ledger.events:
                    if event['action']=='POWER_LOSS':
                        continue
                    if event['action']=='RESTORE_PAYLOAD':
                        check(policy,{publish:1.0,primitive:0.5},'restore_interruption',f'{policy.name}_restore_again')
                        break
                    primitive+=1
        for n in range(random_cases):
            policy=policies[n%len(policies)]
            length=baseline_lengths[n%len(policies)]
            points={rng.randrange(length):rng.choice([0.0,0.5,1.0])}
            for _ in range(rng.randint(1,5)):
                points[rng.randrange(length*3)]=rng.choice([0.0,0.5,1.0])
            check(policy,points,'random_multi',f'seed{seed}_{n}')
    report=dict(status='PASS',scope='one pinned official-model microtile; finite campaign, not universal proof',
                counts=counts,total_cases=sum(counts.values()),injected_losses_executed=actual_losses,
                mismatches=0,seed=seed,baseline_event_counts=baseline_lengths,
                boundary_coverage=[dict(action=a,phase=p) for a,p in sorted(coverage)],
                actual_fault_coverage=[dict(action=a,phase=p,cuts=n) for (a,p),n in sorted(fault_coverage.items())],
                elapsed_s=time.perf_counter()-start,energy_calibrated=False)
    (output/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['status','total_cases','injected_losses_executed','mismatches','elapsed_s']}))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=ROOT/'10_Experiments/g2/faults')
    p.add_argument('--random-cases',type=int,default=1000)
    p.add_argument('--seed',type=int,default=20261015)
    args=p.parse_args()
    campaign(args.output,args.random_cases,args.seed)
