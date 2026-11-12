"""Pinned local tools, with an ASCII temporary runtime for Windows DLL loading."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def prepare(root):
    source=root/'tmp/g4_tools/oss-cad-suite'
    if not (source/'bin/iverilog.exe').exists():
        raise RuntimeError('Run python 10_Experiments/setup_g4_tools.py first')
    cache=Path(tempfile.gettempdir())/'recap_g4_oss_20261014'
    if not str(cache).isascii(): raise RuntimeError('An ASCII tool runtime directory is required on this Windows toolchain')
    selected=[]
    for group in ('bin','lib'):
        selected+=list((source/group).glob('*.dll'))
    selected+=list((source/'lib/ivl').rglob('*'))
    selected+=list((source/'share/yosys').rglob('*'))
    selected += [source/'bin'/n for n in ('iverilog.exe','vvp.exe','yosys.exe','yosys-abc.exe','abc.exe')]
    for p in selected:
        if not p.is_file(): continue
        target=cache/p.relative_to(source);target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists() or target.stat().st_size!=p.stat().st_size or hashlib.sha256(target.read_bytes()).digest()!=hashlib.sha256(p.read_bytes()).digest():
            shutil.copy2(p,target)
    env=os.environ.copy()
    env['PATH']=os.pathsep.join(str(cache/p) for p in ('bin','lib','lib/ivl'))+os.pathsep+env.get('PATH','')
    env['YOSYS_DATDIR']=(cache/'share/yosys').as_posix()
    return dict(cache=cache,env=env,iverilog=cache/'bin/iverilog.exe',vvp=cache/'bin/vvp.exe',yosys=cache/'bin/yosys.exe',ivl=cache/'lib/ivl')


def execute(root,toolchain,arguments,log=None,timeout=180):
    try:
        p=subprocess.run([str(a) for a in arguments],cwd=root,env=toolchain['env'],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=timeout)
    except subprocess.TimeoutExpired as error:
        if log:
            def decode(value):return value.decode('utf-8',errors='replace') if isinstance(value,bytes) else value or ''
            log.parent.mkdir(parents=True,exist_ok=True)
            log.write_text(decode(error.stdout)+decode(error.stderr)+'\nTIMEOUT: no pass claimed.\n',encoding='utf-8')
        raise
    if log:
        log.parent.mkdir(parents=True,exist_ok=True);log.write_text(p.stdout+p.stderr,encoding='utf-8')
    if p.returncode: raise RuntimeError(f'Tool failed ({p.returncode}): {arguments[0]}\n'+p.stdout[-1800:]+p.stderr[-1800:])
    return p.stdout+p.stderr


def compile_controller(root,toolchain,name):
    output=f'10_Experiments/g4/build/{name}.vvp'
    return execute(root,toolchain,[toolchain['iverilog'],'-B'+str(toolchain['ivl']),'-g2012','-Wall',
        '-I',f'10_Experiments/g4/vectors/{name}','-s','tb_checkpoint','-o',output,
        '04_RTL/g4/recap_checkpoint_ctrl.sv','09_Simulation/g4/tb_checkpoint.sv'],root/f'10_Experiments/g4/logs/compile_{name}.log')
