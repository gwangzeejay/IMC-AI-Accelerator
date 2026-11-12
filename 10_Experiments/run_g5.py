"""Reproduce G5 hybrid KWS runtime, labeled accuracy, faults and held-out traces."""
from datetime import datetime,timezone
import io
import json
import os
from pathlib import Path
import sys
import time
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'09_Simulation'))
from g5_experiments import sha,dump,data,accuracy,experiment
from g5_model import KWS
from g5_faults import campaign


def run():
    start=time.perf_counter();out=ROOT/'10_Experiments/g5';out.mkdir(exist_ok=True)
    # Keep previous milestone evidence immutable.
    for milestone in ('g2','g3','g4'):
        prior=json.loads((ROOT/f'10_Experiments/manifests/{milestone}_run.json').read_text())
        for name,digest in prior['sha256'].items():
            if sha(ROOT/name)!=digest:raise ValueError('prior provenance changed: '+name)
    p=json.loads((ROOT/'09_Simulation/configs/g5_protocol.json').read_text())
    dump(out/'protocol_snapshot.json',p)
    stream=io.StringIO();suite=unittest.defaultTestLoader.discover(str(ROOT/'09_Simulation/tests_g5'))
    tests=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    (out/'unit_tests.txt').write_text(stream.getvalue(),encoding='utf-8')
    if not tests.wasSuccessful():raise RuntimeError('G5 unit tests failed; see unit_tests.txt')
    print(f'G5 unit tests PASS ({tests.testsRun})',flush=True)
    items,splits=data(ROOT,p);model=KWS(ROOT)
    acc=accuracy(model,items,splits,out)
    faults=campaign(ROOT,model,p,splits['train'][0],out)
    results=experiment(ROOT,out,model,p,items,splits)
    summary=dict(results,accuracy={k:v for k,v in acc.items() if k not in ('confusion_matrix','checks')},
        fault_cases=faults['cases'],executed_diagnostic_losses=faults['executed_losses'],
        python_tests=tests.testsRun,elapsed_s=time.perf_counter()-start)
    dump(out/'summary.json',summary)
    from g5_plot import plot
    plot(out)
    selected=list(out.rglob('*'))+list((ROOT/'09_Simulation').glob('g5_*.py'))
    selected+=list((ROOT/'09_Simulation/tests_g5').glob('*.py'))
    selected += [ROOT/'09_Simulation/configs/g5_protocol.json',ROOT/'10_Experiments/run_g5.py',ROOT/'10_Experiments/setup_g5_data.py']
    selected+=list((ROOT/'05_Model_Training/reference_eembc').glob('*'))
    files={path.relative_to(ROOT).as_posix():sha(path) for path in sorted(set(selected)) if path.is_file()}
    dump(ROOT/'10_Experiments/manifests/g5_run.json',dict(status=summary['status'],command='python 10_Experiments/run_g5.py',
        recorded_at_utc=datetime.now(timezone.utc).isoformat(),python=sys.version,tensorflow=model.tf_version,
        elapsed_s=time.perf_counter()-start,sha256=files,calibrated=False,ready_for_paper_energy_results=False))
    print(json.dumps({k:summary[k] for k in ('status','evaluations','fault_cases','python_tests','meets_20pct_with_ci')}),flush=True)


if __name__=='__main__':run()
