"""Small-space mapper profiling on ASSUMED training costs, never paper results."""
import json
from pathlib import Path
import sys
import time
import tracemalloc
from recap.cost import CostModel
from recap.power import Reservoir
from recap.simulator import Simulator, Policy
from recap.metrics import summarize_inputs
from mapper import candidates,choose_policy

ROOT=Path(__file__).resolve().parents[1]


def profile(output):
    fixture=ROOT/'10_Experiments/g2/reference/microtile.npz'
    cost=CostModel(**json.loads((ROOT/'09_Simulation/configs/g2_assumed_debug.json').read_text()))
    base=json.loads((ROOT/'09_Simulation/traces/g2_debug_harvest.json').read_text())
    rows=[]
    policies=candidates((8,16,32,64))
    tracemalloc.start()
    start=time.perf_counter()
    for scenario,scale in enumerate((.8,1.,1.2)):
        cfg={k:v for k,v in base.items() if k not in ('label','domain')}
        cfg['trace']=[[t,p*scale] for t,p in cfg['trace']]
        for policy in policies:
            reservoir=Reservoir(**cfg)
            sim=Simulator(fixture,policy,cost,reservoir)
            result=sim.run()
            if abs(reservoir.consumed-result['ledger']['total_energy_j'])>1e-12 or abs(reservoir.balance_error())>1e-12:
                raise AssertionError('source/ledger imbalance')
            # Powered off after completion: zero assumed load to fixed horizon.
            reservoir.advance(reservoir.horizon-reservoir.time,0,stop_at_empty=False)
            rows.append(dict(policy=policy.name,scenario_id=f'train{scenario}',weight=1,
                             energy_j=result['ledger']['total_energy_j'],completed=int(result['completed']),
                             total_inputs=1,on_time=int(result['completed']),
                             mismatches=result['mismatches'],power_losses=result['power_losses']))
    selected=choose_policy(rows,minimum_completion=1,minimum_on_time=1)
    elapsed=time.perf_counter()-start
    _,peak=tracemalloc.get_traced_memory()
    tracemalloc.stop()
    # Baseline prototypes: same arithmetic/storage backend, microtile scope only.
    baselines=[]
    for label,policy in [('B1_microtile_prototype',Policy(False,False,64)),('B2_microtile_prototype',Policy(True,True,16))]:
        sim=Simulator(fixture,policy)
        r=sim.run()
        baselines.append(dict(baseline=label,scope='one microtile; not full-network reproduced baseline',result=r))
    report=dict(status='PASS_DEBUG_PROFILE',mode='ASSUMED_DEBUG_ONLY',selected=selected,
                policy_count=len(policies),scenario_count=3,evaluations=len(rows),
                distinct_behaviors=13,distinct_behaviors_note='Four ci64 save flags are equivalent because there is no intermediate checkpoint',
                elapsed_s=elapsed,peak_python_traced_bytes=peak,
                memory_scope='tracemalloc Python allocations; NOT process peak RSS or target-device SRAM',
                python=sys.version,training_only=True,held_out_test_performed=False,
                ready_for_paper_energy_results=False,rows=rows,baselines=baselines)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['status','policy_count','evaluations','elapsed_s','peak_python_traced_bytes','selected']}))
    return report


if __name__=='__main__':
    profile(ROOT/'10_Experiments/g2/mapper_profile.json')
