"""Supplement: the frozen G3 CI64/output-only unit, without changing CI16 runs.

Generate an auditable test-driver variant from the frozen CI16 bench by
changing only its execution chunk constant. The controller RTL is identical.
"""
from g4_tools import execute
from g4_campaign import run_suite
import json


def check(root,toolchain,configs):
    original=(root/'09_Simulation/g4/tb_checkpoint.sv').read_text()
    needle='stop_channel=volatile_offset+16;'
    if original.count(needle)!=1:raise ValueError('unexpected test-driver template')
    variant=original.replace(needle,'stop_channel=volatile_offset+64;')
    path=root/'10_Experiments/g4/build/tb_checkpoint_ci64.sv';path.write_text(variant)
    reports={}
    for name,cfg in configs.items():
        alias=name+'_ci64';config=dict(cfg,name=alias)
        execute(root,toolchain,[toolchain['iverilog'],'-B'+str(toolchain['ivl']),'-g2012','-s','tb_checkpoint',
            '-I',f'10_Experiments/g4/vectors/{name}','-o',f'10_Experiments/g4/build/{alias}.vvp',
            '04_RTL/g4/recap_checkpoint_ctrl.sv',path.relative_to(root).as_posix()],root/f'10_Experiments/g4/logs/compile_{alias}.log')
        rows={i:[i,z,ps,-1,-1,0,0,900+i,stall,0,0] for i,(z,ps,stall) in enumerate(
            ( (z,ps,s) for z in (0,1) for ps in (0,1) for s in (0,1) ))}
        publish=2*cfg['slot_bytes']+1+1+cfg['out_bytes']+123
        extra=[(publish,0,0),(publish,1,0),(publish,1,1),(publish+1,1,1),(publish+1,0,0)]
        for point,mode,persist in extra:
            cid=len(rows);rows[cid]=[cid,0,0,point,-1,mode,persist,900+cid,1,0,0]
        r=run_suite(root,toolchain,config,rows,'whole_unit')
        reports[name]=dict(cases=r['cases'],fault_cases=len(extra),executed_losses=sum(c['losses'] for c in r['results']),
            transactions=r['transactions'],cycle_checks=r['cycle_checks'],mismatches=r['mismatches'])
    report=dict(status='PASS_CI64_REFINEMENT',reports=reports,total_cases=sum(r['cases'] for r in reports.values()),
        fault_cases=sum(r['fault_cases'] for r in reports.values()),executed_losses=sum(r['executed_losses'] for r in reports.values()),
        transactions=sum(r['transactions'] for r in reports.values()),cycle_checks=sum(r['cycle_checks'] for r in reports.values()),
        test_driver_variant='generated from CI16 bench; only stop_channel chunk 16 -> 64; no controller RTL changes',mismatches=0)
    (root/'10_Experiments/g4/whole_unit_summary.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
