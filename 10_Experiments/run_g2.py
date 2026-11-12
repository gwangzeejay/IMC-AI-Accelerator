"""Reproduce G2 artifacts offline after the pinned model has been fetched."""
import argparse
import hashlib
import importlib.metadata
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'09_Simulation'))
from recap_simulator import run
from fault_injection import campaign
from profile_g2_mapper import profile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reproduce(skip_reference=False):
    start=time.perf_counter()
    out=ROOT/'10_Experiments/g2'
    out.mkdir(parents=True,exist_ok=True)
    if not skip_reference:
        env=dict(os.environ,PYTHONUTF8='1')
        p=subprocess.run([sys.executable,str(ROOT/'05_Model_Training/export_reference_int8.py')],
                         cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8')
        (out/'reference_export.log').write_text(p.stdout+p.stderr,encoding='utf-8')
        if p.returncode:
            raise RuntimeError('reference export failed; see reference_export.log')
    artifact_hashes=json.loads((out/'reference/artifact_hashes.json').read_text())
    for name,expected in artifact_hashes.items():
        if sha(out/'reference'/name)!=expected:
            raise ValueError('golden artifact checksum mismatch: '+name)
    stream=io.StringIO()
    suite=unittest.defaultTestLoader.discover(str(ROOT/'09_Simulation/tests'))
    test_start=time.perf_counter()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    (out/'unit_tests.txt').write_text(stream.getvalue(),encoding='utf-8')
    test_report=dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),
                     skipped=len(result.skipped),elapsed_s=time.perf_counter()-test_start,
                     status='PASS' if result.wasSuccessful() else 'FAIL')
    (out/'unit_tests.json').write_text(json.dumps(test_report,indent=2)+'\n')
    if not result.wasSuccessful():
        raise RuntimeError('G2 unit checks failed; see unit_tests.txt')
    functional=run(out/'functional')
    source=run(out/'source_debug',True)
    mapper=profile(out/'mapper_profile.json')
    faults=campaign(out/'faults')
    if functional['status']!='PASS_MICROTILE' or source['status']!='PASS_SOURCE_INVARIANTS':
        raise AssertionError('G2 invariants failed')
    paths=list(out.rglob('*'))
    paths += list((ROOT/'09_Simulation/recap').glob('*.py'))
    paths += list((ROOT/'09_Simulation/tests').glob('*.py'))
    paths += list((ROOT/'09_Simulation/configs').glob('g2_*.json'))
    paths += list((ROOT/'09_Simulation/traces').glob('g2_*.json'))
    paths += [ROOT/p for p in ['05_Model_Training/export_reference_int8.py','09_Simulation/recap_simulator.py',
              '09_Simulation/fault_injection.py','09_Simulation/mapper.py','09_Simulation/profile_g2_mapper.py',
              '10_Experiments/run_g2.py','02_Research/hardware_selection/research_parameters.json',
              '05_Model_Training/reference_mlperf/source_manifest.json']]
    files={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in sorted(set(paths)) if p.is_file() and '__pycache__' not in p.parts}
    manifest=dict(schema_version='1.0',date='2026-10-15',g2_status='PARTIAL_CORE_VALIDATED',
                  ready_for_paper_energy_results=False,
                  command='python 10_Experiments/run_g2.py'+(' --skip-reference' if skip_reference else ''),
                  versions=dict(python=sys.version,numpy=importlib.metadata.version('numpy'),tensorflow=importlib.metadata.version('tensorflow')),
                  tests=test_report,fault_cases=faults['total_cases'],fault_mismatches=faults['mismatches'],
                  debug_source_completed_policies=source['workload_completed_policies'],
                  mapper_policy_count=mapper['policy_count'],elapsed_s=time.perf_counter()-start,sha256=files)
    dest=ROOT/'10_Experiments/manifests/g2_run.json'
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({k:manifest[k] for k in ['g2_status','fault_cases','fault_mismatches','elapsed_s']}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-reference',action='store_true',help='reuse checksummed golden files; still rerun tests/simulations')
    reproduce(parser.parse_args().skip_reference)
