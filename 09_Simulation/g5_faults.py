"""Finite full-network crash campaign, beyond binary codec boundary tests."""
import json
from g5_runtime import Runtime
from g5_experiments import dump


def campaign(root,model,p,item,out):
    # Diagnostic only: not tuning, not a held-out energy result.
    scenario=dict(id='fault_diagnostic',seed=231000,family='diagnostic',capacity_j=100e-6,
        trace=[[0,.01]],horizon_s=4.0)
    inp=dict(item,arrival_s=0.0,deadline_s=4.0)
    cases=[]
    sizes={'checkpoint_partial':1280+125,'checkpoint_output':256+126,
           'layer_log':256+125,'graph_root':48+126}
    for action,total in sizes.items():
        for cut in (0,total//2,total-1,total):
            fault=dict(action=action,cut=cut)
            runtime=Runtime(root,model,p,scenario,'RECAP',fault=fault)
            runtime.forced_plan=(4,64,16,True,True)
            r=runtime.run([inp])
            if not r['fault_executed'] or r['completed']!=1 or r['losses']!=1:
                raise AssertionError(f'full-network recovery failed {fault}: {r["completed"]}, losses={r["losses"]}')
            cases.append(dict(fault=fault,completed=r['completed'],losses=r['losses'],
                replayed_macs=r['replayed_macs'],output=r['outputs'][0]['output'],energy_j=r['energy_j'],
                energy_balance_error_j=r['energy_balance_error_j']))
        print('Full KWS fault campaign:',action,'PASS',flush=True)
    report=dict(status='PASS_FINITE_FULL_NETWORK_FAULT_CAMPAIGN',cases=len(cases),
        executed_losses=sum(c['losses'] for c in cases),mismatches=0,details=cases,
        assumptions='atomic byte persistence ACK; external diagnostic discharge counted; CRC32 not adversarial integrity',
        scope='one labeled input; CI16 SAVE_DW+KEEP_PS; four publication paths, before/mid/before-final-ACK/after-ACK; not exhaustive graph fault sequences')
    dump(out/'faults.json',report);return report
