"""CLI for G2 functional or explicitly assumed coupled-source microbenchmark."""
import argparse
import json
from pathlib import Path
from recap.cost import CostModel
from recap.power import Reservoir
from recap.simulator import Policy, Simulator
from recap.metrics import summarize_inputs

ROOT=Path(__file__).resolve().parents[1]


def run(output, source_debug=False):
    fixture=ROOT/'10_Experiments/g2/reference/microtile.npz'
    mode='g2_assumed_debug.json' if source_debug else 'g2_functional.json'
    cost=CostModel(**json.loads((ROOT/'09_Simulation/configs'/mode).read_text()))
    trace=json.loads((ROOT/'09_Simulation/traces/g2_debug_harvest.json').read_text())
    results=[]
    output.mkdir(parents=True,exist_ok=True)
    for save_z in (False,True):
        for keep_ps in (False,True):
            policy=Policy(save_z,keep_ps)
            reservoir=Reservoir(**{k:v for k,v in trace.items() if k not in ('label','domain')}) if source_debug else None
            sim=Simulator(fixture,policy,cost,reservoir)
            result=sim.run()
            completion_time=result['source_time_s'] if result['completed'] else None
            # Observe the entire fixed horizon, with explicitly assumed powered-off zero load after completion.
            if reservoir and reservoir.time<reservoir.horizon:
                dt,_=reservoir.advance(reservoir.horizon-reservoir.time,0,stop_at_empty=False)
                sim.ledger.record('IDLE_OFF','after_completion','wait_s',dt,start_s=reservoir.time-dt)
                result['ledger']=sim.ledger.summary()
                result['source_balance_error_j']=reservoir.balance_error()
            if reservoir:
                consumed=reservoir.consumed
                ledger=result['ledger']['total_energy_j']
                if ledger is None or abs(consumed-ledger)>1e-12:
                    raise AssertionError('ledger/source load energy mismatch')
                result.update(horizon_s=reservoir.horizon,source_consumed_j=consumed,
                              source_ledger_error_j=consumed-ledger,admission_bound_j=sim.unit_bound())
                result['metrics']=summarize_inputs([dict(arrival_s=0,deadline_s=reservoir.horizon,
                    committed_s=completion_time)],reservoir.horizon,ledger)
            results.append(result)
            with (output/(policy.name+'.jsonl')).open('w',encoding='utf-8') as f:
                for event in sim.ledger.events:
                    f.write(json.dumps(event)+'\n')
    invariant_pass=all(r['mismatches'] in (None,0) for r in results)
    report=dict(status=('PASS_SOURCE_INVARIANTS' if invariant_pass else 'FAIL') if source_debug else
                ('PASS_MICROTILE' if all(r['completed'] and r['mismatches']==0 for r in results) else 'INCOMPLETE'),
                mode='ASSUMED_DEBUG_ONLY' if source_debug else 'FUNCTIONAL_UNKNOWN_ENERGY',
                workload_completed_policies=sum(r['completed'] for r in results),
                ready_for_paper_energy_results=False,results=results)
    (output/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],mode=report['mode'],policies=len(results))))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-debug',action='store_true')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    destination=args.output or ROOT/'10_Experiments/g2'/('source_debug' if args.source_debug else 'functional')
    run(destination,args.source_debug)
