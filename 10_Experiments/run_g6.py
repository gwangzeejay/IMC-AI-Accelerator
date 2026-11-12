"""Reproduce G6: two workloads, real solar windows, sensitivity and ablations."""
from datetime import datetime,timezone
import io
import json
from pathlib import Path
import sys
import time
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'09_Simulation'))
from g5_experiments import sha,dump
from g6_model import Model
from g6_storage import Store
from g6_inputs import inputs
from g6_experiments import diagnostics,accuracy,experiment
from g6_faults import campaign


def run():
    start=time.perf_counter();out=ROOT/'10_Experiments/g6';out.mkdir(exist_ok=True)
    for milestone in ('g2','g3','g4','g5'):
        manifest=json.loads((ROOT/f'10_Experiments/manifests/{milestone}_run.json').read_text())
        for name,digest in manifest['sha256'].items():
            if sha(ROOT/name)!=digest:raise ValueError('prior provenance changed: '+name)
    p=json.loads((ROOT/'09_Simulation/configs/g6_protocol.json').read_text());dump(out/'protocol_snapshot.json',p)
    stream=io.StringIO();suite=unittest.defaultTestLoader.discover(str(ROOT/'09_Simulation/tests_g6'))
    tests=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    (out/'unit_tests.txt').write_text(stream.getvalue())
    if not tests.wasSuccessful():raise RuntimeError('G6 tests failed; see unit_tests.txt')
    print('G6 unit tests PASS:',tests.testsRun,flush=True)
    models={n:Model(ROOT,n) for n in p['workloads']};pools=inputs(ROOT);diag=diagnostics(ROOT)
    feasibility=[]
    for name,m in models.items():
        for regime,sram,nvm in [('original',p['original_sram_bytes'],p['original_nvm_bytes']),('extended',p['sram_bytes'],p['nvm_bytes'])]:
            try:s=Store(m,diag[name]['x'],dict(p,nvm_bytes=nvm));reserve=s.reserved_bytes;nvm_ok=True
            except ValueError:reserve=None;nvm_ok=False
            largest=max(d['input_bytes'] for d in m.stages)
            feasibility.append(dict(workload=name,regime=regime,model_bytes=len(m.blob),largest_anchor_bytes=largest,
                sram_bytes=sram,nvm_bytes=nvm,nvm_reserved_bytes=reserve,model_fits_nvm=len(m.blob)<=nvm,
                resident_anchor_fits_sram=largest<=sram,nvm_layout_fits=nvm_ok,
                note='anchor check is necessary, not sufficient; actual algorithm-buffer highwater checked in runtime'))
    dump(out/'memory_feasibility.json',feasibility)
    acc=accuracy(ROOT,models,pools,out);faults=campaign(ROOT,models,p,diag,out)
    results=experiment(ROOT,out,p,models,pools,diag)
    summary=dict(results,python_tests=tests.testsRun,accuracy={k:v for k,v in acc.items() if k not in ('checks','predictions')},
        full_network_fault_cases=faults['full_network_cases'],random_large_slot_schedules=faults['random_large_slot_schedules'],
        random_executed_losses=faults['random_executed_losses'],elapsed_s=time.perf_counter()-start)
    dump(out/'summary.json',summary)
    from g6_plot import plot
    plot(out)
    files=list(out.rglob('*'))+list((ROOT/'09_Simulation').glob('g6_*.py'))+list((ROOT/'09_Simulation/tests_g6').glob('*.py'))
    files += [ROOT/'09_Simulation/configs/g6_protocol.json',Path(__file__),ROOT/'10_Experiments/setup_g6_sources.py']
    files += list((ROOT/'05_Model_Training/reference_vww').rglob('*'))+list((ROOT/'09_Simulation/traces/g6_eth').rglob('*'))
    files += [ROOT/'tmp/g6_sources/pos16_power_relative.h5']
    pinned={f.relative_to(ROOT).as_posix():sha(f) for f in sorted(set(files)) if f.is_file() and '__pycache__' not in str(f)}
    import tensorflow as tf
    import numpy as np
    import h5py,PIL
    dump(ROOT/'10_Experiments/manifests/g6_run.json',dict(status=summary['status'],command='python 10_Experiments/run_g6.py',
        recorded_at_utc=datetime.now(timezone.utc).isoformat(),sha256=pinned,python=sys.version,
        versions=dict(tensorflow=tf.__version__,numpy=np.__version__,h5py=h5py.__version__,pillow=PIL.__version__),
        elapsed_s=time.perf_counter()-start,calibrated=False,ready_for_paper_energy_results=False))
    print(json.dumps({k:summary[k] for k in ('status','unique_executions','completed_outputs_in_main','full_network_fault_cases','random_large_slot_schedules')}),flush=True)


if __name__=='__main__':run()
