"""Reproduce G3 descriptors, regression tests, frozen mapper and held-out study."""
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
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'09_Simulation'))
from recap.g3_workload import build_descriptors
from g3_experiments import experiment
from g3_faults import campaign
from g3_recovery_episodes import episodes
from plot_g3 import plot,plot_episodes


def reproduce():
    start=time.perf_counter();out=ROOT/'10_Experiments/g3';out.mkdir(parents=True,exist_ok=True)
    process=subprocess.run([sys.executable,str(ROOT/'05_Model_Training/export_g3_quantization.py')],
        cwd=ROOT,env=dict(os.environ,PYTHONUTF8='1'),capture_output=True,text=True,encoding='utf-8')
    (out/'quantization_export.log').write_text(process.stdout+process.stderr,encoding='utf-8')
    if process.returncode: raise RuntimeError('quantization export failed')
    protocol=json.loads((ROOT/'09_Simulation/configs/g3_protocol.json').read_text())
    build_descriptors(ROOT,out/'descriptors',protocol)
    stream=io.StringIO();reports=[]
    for directory in ('tests','tests_g3'):
        suite=unittest.defaultTestLoader.discover(str(ROOT/'09_Simulation'/directory))
        r=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
        reports.append(dict(suite=directory,tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),skipped=len(r.skipped)))
        if not r.wasSuccessful():
            (out/'unit_tests.txt').write_text(stream.getvalue(),encoding='utf-8')
            raise RuntimeError('G3 regression failure')
    (out/'unit_tests.txt').write_text(stream.getvalue(),encoding='utf-8')
    (out/'unit_tests.json').write_text(json.dumps(dict(status='PASS',suites=reports,total=sum(r['tests'] for r in reports)),indent=2)+'\n')
    report=experiment(ROOT,out)
    episode_report=episodes(ROOT,out)
    faults=campaign(ROOT,out)
    plot(out)
    plot_episodes(out)
    paths=[p for p in out.rglob('*') if p.is_file() and '_diagnostics' not in p.parts]
    paths+=list((ROOT/'09_Simulation/recap').glob('*.py'))+list((ROOT/'09_Simulation/tests_g3').glob('*.py'))
    paths+=[ROOT/p for p in ['09_Simulation/g3_experiments.py','09_Simulation/g3_faults.py','09_Simulation/g3_recovery_episodes.py','10_Experiments/plot_g3.py',
        '10_Experiments/run_g3.py','05_Model_Training/export_g3_quantization.py','09_Simulation/configs/g3_protocol.json',
        '09_Simulation/configs/g2_assumed_debug.json','10_Experiments/g2/reference/artifact_hashes.json']]
    manifest=dict(status='MODEL_ONLY_G3_COMPLETED',decision=report['decision'],ready_for_paper_energy_results=False,
        recorded_at_utc=datetime.now(timezone.utc).isoformat(),command='python 10_Experiments/run_g3.py',
        python=sys.version,versions={p:importlib.metadata.version(p) for p in ('numpy','tensorflow','matplotlib')},
        unit_tests=reports,fault_cases=faults['total_cases'],fault_mismatches=faults['mismatches'],
        evaluations=report['evaluations'],elapsed_s=time.perf_counter()-start,
        exploratory_episode_executions=episode_report['evaluated_episodes'],
        exploratory_boundary_probes=episode_report['boundary_probe_executions'],
        retired_diagnostic_sha256={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((out/'_diagnostics').rglob('*')) if p.is_file()},
        sha256={str(p.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths))})
    path=ROOT/'10_Experiments/manifests/g3_run.json';path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({k:manifest[k] for k in ('status','decision','fault_cases','evaluations','elapsed_s')}),flush=True)


if __name__=='__main__': reproduce()
