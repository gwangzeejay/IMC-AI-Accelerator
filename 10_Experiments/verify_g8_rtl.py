"""Execute Icarus RTL and independently decode every reset image in Python."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'09_Simulation'))
from g4_reference import encode,decode
from g4_tools import prepare,execute

def run(args):
    out=ROOT/'10_Experiments/g8'/args.run_id
    if out.exists():raise FileExistsError('Choose a new --run-id; existing RTL evidence is immutable')
    out.mkdir(parents=True)
    identity=tuple(hashlib.sha256(x).digest() for x in (b'g8_model',b'g8_input',b'g8_descriptor'))
    payload=bytes(range(16));header,_=encode(identity,1,64,output=payload)
    source=out/'record.hex';source.write_text(''.join(f'{v:02x}\n' for v in header+payload))
    tc=prepare(ROOT);build=out/'output_log.vvp'
    files=[ROOT/'04_RTL/g8/recap_output_log_commit.sv',ROOT/'09_Simulation/g8/tb_output_log.sv',Path(__file__)]
    execute(ROOT,tc,[tc['iverilog'],'-B'+str(tc['ivl']),'-g2012','-Wall','-s','tb_output_log','-o',build.relative_to(ROOT),*[p.relative_to(ROOT) for p in files[:2]]],out/'compile.log')
    result=execute(ROOT,tc,[tc['vvp'],build.relative_to(ROOT),'+SOURCE='+source.relative_to(ROOT).as_posix()],out/'simulation.log')
    cases=[]
    for line in result.splitlines():
        if not line.startswith('CUT '):continue
        _,stall,cut,raw=line.split();cut=int(cut)
        memory=bytes.fromhex(raw)[32:172]
        record=decode(memory,0,140,identity,64,64,16,channels=64)
        if (record is not None)!=(cut==141):raise AssertionError('torn/committed visibility: '+line[:20])
        if record is not None and record['output']!=payload:raise AssertionError('output mismatch')
        cases.append(dict(stall_mode=int(stall),cut=cut,visible=record is not None))
    if len(cases)!=284 or 'PASS_OUTPUT_LOG' not in result:raise AssertionError('incomplete RTL campaign')
    netlist=out/'publisher_generic.json'
    script='read_verilog -sv 04_RTL/g8/recap_output_log_commit.sv; hierarchy -check -top recap_output_log_commit; proc; opt; check -assert; stat; write_json '+netlist.relative_to(ROOT).as_posix()
    execute(ROOT,tc,[tc['yosys'],'-p',script],out/'generic_synthesis.log',timeout=60)
    cells=len(json.loads(netlist.read_text())['modules']['recap_output_log_commit']['cells'])
    report=dict(status='PASS_G8_OUTPUT_LOG_RTL',reset_cut_cases=len(cases),invalid_commands=2,
        stall_modes=2,source_payload_bytes=16,record_bytes=140,write_acknowledgments_per_commit=141,
        scope='One standalone publisher, 16-byte payload and 32-bit base; every ACK cut plus deterministic stalls. Not complete accelerator/physical NVM.',
        generic_synthesis=dict(status='PASS_GENERIC_PROC_CHECK',cells=cells,technology_mapped=False,area_mm2=None,power_w=None,fmax_hz=None),
        tool_sha256={name:hashlib.sha256(tc[name].read_bytes()).hexdigest() for name in ('iverilog','vvp','yosys')},
        artifact_sha256={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (source,out/'compile.log',out/'simulation.log',out/'generic_synthesis.log',netlist)},
        source_sha256={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in files},cases=cases)
    (out/'rtl_report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('cases','source_sha256')},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run-id',default='rtl-20261023-v3');run(p.parse_args())
