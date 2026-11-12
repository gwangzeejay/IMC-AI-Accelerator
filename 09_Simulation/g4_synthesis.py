"""Generic Yosys process/memory checks, with no technology or PPA claims."""
import json
import subprocess
from g4_tools import execute


def check(root,toolchain,full_controller=False):
    results=[]
    cases=[('recap_int8_mac','04_RTL/g4/recap_int8_mac.sv','default',''),
           ('recap_requantize','04_RTL/g4/recap_requantize.sv','default',''),
           ('recap_checkpoint_ctrl','04_RTL/g4/recap_checkpoint_ctrl.sv','reduced Z4/PS4/OUT1/C4/SLOT160',
            'chparam -set Z_BYTES 4 -set PS_BYTES 4 -set OUT_BYTES 1 -set CHANNELS 4 -set SLOT_BYTES 160 recap_checkpoint_ctrl; ')]
    if full_controller:
        cases.append(('recap_checkpoint_ctrl','04_RTL/g4/recap_checkpoint_ctrl.sv','full Z128/PS128/OUT32/SLOT512',
            'chparam -set Z_BYTES 128 -set PS_BYTES 128 -set OUT_BYTES 32 recap_checkpoint_ctrl; '))
    for top,source,parameters,extra in cases:
        label=top+('_full' if parameters.startswith('full') else '')
        command=f'read_verilog -sv {source}; {extra}hierarchy -check -top {top}; proc; opt; memory_collect; check -assert; tee -o 10_Experiments/g4/{label}_generic.json stat -json'
        try:
            execute(root,toolchain,[toolchain['yosys'],'-Q','-l',f'10_Experiments/g4/logs/yosys_live_{label}.log','-p',command],
                    root/f'10_Experiments/g4/logs/yosys_{label}.log',timeout=180 if parameters.startswith('full') else 90)
            status='PASS_GENERIC_PROC_CHECK'
        except subprocess.TimeoutExpired:status='TIMEOUT_NOT_PASSED'
        results.append(dict(top=top,status=status,parameters=parameters,technology_mapped=False))
    report=dict(results=results,full_controller_attempt='REQUESTED' if full_controller else 'NOT_RUN_IN_DEFAULT_PIPELINE',
                area_mm2=None,power_w=None,frequency_hz=None,
                scope='generic proc/opt/memory_collect/check; no technology mapping, place-route, timing or physical power')
    (root/'10_Experiments/g4/synthesis_summary.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
