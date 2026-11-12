"""Reproduce G4 actual RTL simulation, arithmetic, faults and wire/cycle checks."""
import argparse
from datetime import datetime,timezone
import hashlib
import io
import json
from pathlib import Path
import re
import sys
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'09_Simulation'))
from g4_reference import export_vectors
from g4_vectors import arithmetic_vectors
from g4_tools import prepare,execute
from g4_campaign import campaign
from g4_synthesis import check
from g4_whole_unit import check as whole_unit_check


def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def run(collect_existing=False,full_controller=False):
    start=time.perf_counter();out=ROOT/'10_Experiments/g4';out.mkdir(parents=True,exist_ok=True)
    for name in ('build','logs','cases','raw'):(out/name).mkdir(exist_ok=True)
    # Reuse and checksum prior golden sources. Do not refit G3 or rewrite its runs.
    for milestone in ('g2','g3'):
        prior=json.loads((ROOT/f'10_Experiments/manifests/{milestone}_run.json').read_text())
        for name,digest in prior['sha256'].items():
            if sha(ROOT/name)!=digest:raise ValueError(f'{milestone} provenance mismatch: {name}')
    if collect_existing:
        bound=json.loads((out/'rtl_source_hashes.json').read_text())
        for name,digest in bound.items():
            if sha(ROOT/name)!=digest:raise ValueError('existing RTL source changed: '+name)
        configs={p.parent.name:json.loads(p.read_text()) for p in (out/'vectors').glob('*/config.json')}
    else:
        configs=export_vectors(ROOT)
        files=list((ROOT/'04_RTL/g4').glob('*.sv'))+list((ROOT/'09_Simulation/g4').glob('*.sv'))
        files += [ROOT/'09_Simulation'/n for n in ('g4_reference.py','g4_trace_check.py','g4_vectors.py','g4_campaign.py')]
        (out/'rtl_source_hashes.json').write_text(json.dumps({p.relative_to(ROOT).as_posix():sha(p) for p in files},indent=2)+'\n')
    toolchain=prepare(ROOT)
    stream=io.StringIO()
    suite=unittest.defaultTestLoader.discover(str(ROOT/'09_Simulation/tests_g4'))
    tests=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    (out/'unit_tests.txt').write_text(stream.getvalue(),encoding='utf-8')
    if not tests.wasSuccessful():raise RuntimeError('G4 Python codec checks failed')
    unit_report=dict(status='PASS',tests=tests.testsRun,failures=len(tests.failures),errors=len(tests.errors),skipped=len(tests.skipped))
    (out/'unit_tests.json').write_text(json.dumps(unit_report,indent=2)+'\n')
    if not collect_existing:
        arithmetic=arithmetic_vectors(ROOT,configs)
        execute(ROOT,toolchain,[toolchain['iverilog'],'-B'+str(toolchain['ivl']),'-g2012','-s','tb_arithmetic','-o',
            '10_Experiments/g4/build/arithmetic.vvp','04_RTL/g4/recap_int8_mac.sv','04_RTL/g4/recap_requantize.sv','09_Simulation/g4/tb_arithmetic.sv'],out/'logs/compile_arithmetic.log')
        execute(ROOT,toolchain,[toolchain['vvp'],'-M',toolchain['ivl'],'10_Experiments/g4/build/arithmetic.vvp',
            '+MAC=10_Experiments/g4/vectors/mac.txt','+QUANT=10_Experiments/g4/vectors/requant.txt'],out/'logs/arithmetic.log')
        rtl=campaign(ROOT,toolchain,configs)
        whole=whole_unit_check(ROOT,toolchain,configs)
        synth=check(ROOT,toolchain,full_controller)
    else:
        arithmetic=json.loads((out/'vectors/arithmetic_manifest.json').read_text())
        rtl=json.loads((out/'rtl_summary.json').read_text())
        synth=json.loads((out/'synthesis_summary.json').read_text())
        whole=json.loads((out/'whole_unit_summary.json').read_text())
    match=re.search(r'PASS arithmetic mac_cases=(\d+) quant_cases=(\d+)',(out/'logs/arithmetic.log').read_text())
    if not match or tuple(map(int,match.groups()))!=(arithmetic['mac_cases'],arithmetic['requant_cases']):
        raise AssertionError('missing arithmetic execution evidence')
    if rtl['mismatches'] or rtl['status']!='PASS_RTL_TRANSACTION_REFINEMENT':raise AssertionError('RTL results failed')
    versions={}
    for name,cmd in [('iverilog',[toolchain['iverilog'],'-B'+str(toolchain['ivl']),'-V']),('vvp',[toolchain['vvp'],'-V']),('yosys',[toolchain['yosys'],'-V'])]:
        text=execute(ROOT,toolchain,cmd,out/f'logs/{name}_version.log')
        versions[name]=next((line for line in text.splitlines() if 'version' in line.lower() or line.startswith('Yosys ')),text[:200])
    report=dict(status='G4_RTL_SIMULATION_VALIDATED',scope='microtile checkpoint controller plus independent scalar arithmetic cores; not full accelerator integration',
        rtl=rtl,whole_unit=whole,arithmetic=arithmetic,python_tests=unit_report,synthesis=synth,
        total_rtl_cases=rtl['total_cases']+whole['total_cases'],total_fault_cases=rtl['fault_cases']+whole['fault_cases'],
        total_executed_losses=rtl['executed_losses']+whole['executed_losses'],
        total_cycle_checks=rtl['cycle_checks']+whole['cycle_checks'],
        total_checked_transactions=rtl['checked_transactions']+whole['transactions'],
        physical_macro_validated=False,ready_for_paper_energy_results=False,formal_proof_performed=False,
        g3_energy_improvements_revalidated=False,codec='binary_v1 CRC32 and full 256-bit identities; semantic refinement, not JSON byte equivalence')
    (out/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    selected=list(out.rglob('*'))+[ROOT/'10_Experiments/run_g4.py',ROOT/'10_Experiments/setup_g4_tools.py']
    selected+=list((ROOT/'04_RTL/g4').glob('*.sv'))+list((ROOT/'09_Simulation/g4').glob('*.sv'))
    selected+=list((ROOT/'09_Simulation').glob('g4_*.py'))+list((ROOT/'09_Simulation/tests_g4').glob('*.py'))
    selected += [ROOT/'tmp/g4_tools/source_manifest.json']
    files={p.relative_to(ROOT).as_posix():sha(p) for p in sorted(set(selected)) if p.is_file()}
    manifest=dict(status=report['status'],command='python 10_Experiments/run_g4.py'+(' --collect-existing' if collect_existing else '')+(' --full-controller' if full_controller else ''),
        recorded_at_utc=datetime.now(timezone.utc).isoformat(),collection_mode=collect_existing,
        collection_mode_note='Collect mode verifies source bindings and stored execution evidence; does not rerun the completed RTL campaigns or Yosys passes',
        python=sys.version,tools=versions,elapsed_s=time.perf_counter()-start,sha256=files,
        tool_binary_sha256={name:sha(toolchain[name]) for name in ('iverilog','vvp','yosys')},
        ready_for_paper_energy_results=False)
    (ROOT/'10_Experiments/manifests/g4_run.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(status=report['status'],rtl_cases=report['total_rtl_cases'],fault_cases=report['total_fault_cases'],
        mismatches=rtl['mismatches']+whole['mismatches'],cycle_checks=report['total_cycle_checks'],collection_mode=collect_existing)),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collect-existing',action='store_true',help='collect already executed, source-bound RTL runs without repeating them')
    parser.add_argument('--full-controller',action='store_true',help='also attempt full-size generic controller check (180 s limit; no PPA claim)')
    args=parser.parse_args();run(args.collect_existing,args.full_controller)
