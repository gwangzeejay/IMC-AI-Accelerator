"""Exploratory matched recovery episodes, separate from held-out source runs.

Post-hoc diagnostic: main source runs with CI16 did not finish any workload.
No policy is refitted here. One descriptor, same committed PW prefix=16,
then either no outage or one controlled cold loss after that checkpoint.
This is a state-aligned intervention, not identical wall-clock outages and
not a substitute for the coupled-source held-out benchmark.
"""
from dataclasses import replace
import json
from recap.g3_workload import Mapping
from recap.g3_simulator import G3Simulator
from g3_experiments import cost_model


def episodes(root,output):
    protocol=json.loads((root/'09_Simulation/configs/g3_protocol.json').read_text())
    frozen=json.loads((output/'frozen_mapper.json').read_text())
    mapping=replace(Mapping(**frozen['mapping']),ci=protocol['diagnostic_ci_chunk'],keep_ps=True)
    catalog=json.loads((output/'descriptors/catalog.json').read_text())
    plan=catalog['catalog'][f'h{mapping.h}w{mapping.w}_co{mapping.co}']
    job=plan['jobs'][0]
    def simulate(save,dw,write,loss):
        m=replace(mapping,save_z=save)
        cost=cost_model(root,protocol,dw,write)
        def make(faults=None):
            return G3Simulator(output/'descriptors'/job['path'],m.policy,cost,
                slot_bytes=job['slot_bytes'],bank_bytes=protocol['bank_bytes'],sram_bytes=protocol['sram_bytes'],
                frontier=bytearray(len(plan['jobs'])),job_index=0,faults=faults)
        sim=make()
        result=sim.run()
        if loss:
            publish=next(i for i,e in enumerate(sim.ledger.events) if e['action']=='COMMIT_CHECKPOINT' and e['phase']=='publish')
            sim=make({publish:1})
            result=sim.run()
        r=result
        if not r['completed'] or r['mismatches']!=0 or sim.unexpected_losses!=loss:
            raise AssertionError('episode recovery incorrect')
        return dict(save_z=save,keep_ps=True,ci=m.ci,dw_scale=dw,write_scale=write,
                    controlled_cold_losses=loss,committed_prefix_at_intervention=16 if loss else None,
                    energy_j=r['ledger']['total_energy_j'],breakdown=r['ledger']['breakdown'],mismatches=r['mismatches'])
    rows=[];cells=[]
    for dw in protocol['sensitivity_dw_scales']:
        for write in protocol['sensitivity_write_scales']:
            for loss in (0,1):
                replay=simulate(False,dw,write,loss);save=simulate(True,dw,write,loss)
                rows.extend((replay,save))
                reduction=1-save['energy_j']/replay['energy_j']
                cells.append(dict(dw_scale=dw,write_scale=write,controlled_cold_losses=loss,
                                  save_energy_j=save['energy_j'],replay_energy_j=replay['energy_j'],
                                  save_relative_energy_reduction=reduction))
    report=dict(status='PASS_EXPLORATORY_EPISODES',post_hoc_diagnostic=True,used_to_refit_mapper=False,
                scope='one descriptor to committed output; intervention after same durable PW prefix; not full workload or stochastic/source evidence',
                mapping=mapping.name,descriptor=job['descriptor'],model_calibrated=False,
                ready_for_paper_energy_results=False,cells=cells,rows=rows,mismatches=0)
    report.update(evaluated_episodes=len(rows),boundary_probe_executions=18)
    (output/'recovery_episodes.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Exploratory matched recovery episodes: 36 executions, no mismatch',flush=True)
    return report
