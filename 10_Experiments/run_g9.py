"""G9 crossover study. Stages: smoke (development inputs only), lock, main.

  python 10_Experiments/run_g9.py --stage smoke --run-id s1
  python 10_Experiments/run_g9.py --stage lock
  python 10_Experiments/run_g9.py --stage main --run-id m1

`lock` writes 10_Experiments/g9/protocol_lock.json (hashes of protocol, code,
inputs, scenarios). `main` verifies it and refuses to run while
grounded_nvm_scale_range is null or any hashed file changed. Runs are
immutable: use a new --run-id. Never reads holdout outcomes to choose anything.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import sys
import time
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '09_Simulation'))
sys.path.insert(0, str(ROOT / '10_Experiments'))
import run_g8
from g6_model import Model
from g6_inputs import inputs as g6_inputs, synthetic, assign_inputs
from g9_runtime import Runtime
import analyze_g9

OUT = ROOT / '10_Experiments/g9'
LOCK = OUT / 'protocol_lock.json'


def sha(path):
    return run_g8.sha(path)


def dump(path, data):
    run_g8.dump(path, data)


def load_protocol():
    p = {}
    for name in ('g6_protocol.json', 'g8_protocol.json', 'g9_protocol.json'):
        p.update(json.loads((ROOT / '09_Simulation/configs' / name).read_text()))
    return p


def kws_pool():
    """Same deduplicated 'available' pool as run_g8.load_inputs (before its split)."""
    pools = g6_inputs(ROOT)
    old = json.loads((ROOT / '10_Experiments/g6/scenarios.json').read_text())
    used = {i for s in old for i in s['input_ids']['kws']}
    used |= {c['id'] for c in json.loads((ROOT / '10_Experiments/g6/accuracy.json').read_text())['checks'] if c['workload'] == 'kws'}
    used_hashes = {a['sha256'] for a in pools['kws'] if a['id'] in used}
    seen, available = set(), []
    for a in pools['kws']:
        if a['sha256'] not in used_hashes and a['sha256'] not in seen:
            available.append(a)
            seen.add(a['sha256'])
    return available


def load_inputs():
    g8 = run_g8.load_inputs()
    available = kws_pool()
    g8_ids = {a['id'] for a in g8['development']['kws'] + g8['holdout']['kws']}
    holdout = []
    for label in range(12):
        part = [a for a in available if a['label'] == label]
        chosen = part[4:10]
        if len(chosen) < 6 or any(a['id'] in g8_ids for a in chosen):
            raise ValueError('G9 KWS split invalid for class ' + str(label))
        holdout += chosen
    return dict(development=g8['development'], holdout=dict(kws=holdout, vww=g8['holdout']['vww']))


def reset_schedules(p):
    out = []
    g = p['grid']
    for ci, cap in enumerate(g['capacities_j']):
        for ri, rate in enumerate(g['reset_rates_hz']):
            for rep in range(g['replicates_per_cell']):
                seed = p['seeds']['reset_seed_base'] + ci * 10000 + ri * 100 + rep
                rng = random.Random(seed)
                t, resets = 0., []
                while True:
                    t += rng.expovariate(rate)
                    if t >= p['source']['horizon_s']:
                        break
                    resets.append(t)
                out.append(dict(id=f'g9_reset_{seed}', seed=seed, family=f'reset{rate:g}_cap{ci}', source_kind='external_reset',
                                capacity_j=cap, trace=[[0., p['source']['source_mean_w']]], reset_times_s=resets,
                                actual_outage_rate_hz=rate, rate_index=ri, cap_index=ci, horizon_s=p['source']['horizon_s'],
                                arrivals_s=p['source']['arrivals_s'], deadline_interval_s=p['source']['deadline_interval_s']))
    return out


def stochastic_schedules(p):
    q = dict(p, test_seed_base=p['stochastic_secondary']['test_seed_base'],
             synthetic_replicates_per_family=p['stochastic_secondary']['synthetic_replicates_per_family'])
    out = synthetic(q)
    for s in out:
        s['id'] = s['id'].replace('g6_', 'g9_stoch_')
    return out


def check_seed_disjoint(scenarios):
    old = {s['seed'] for s in json.loads((ROOT / '10_Experiments/g6/scenarios.json').read_text())}
    old |= {s['seed'] for s in json.loads((ROOT / '10_Experiments/g8/20261023-v2/scenarios.json').read_text())}
    if old & {s['seed'] for s in scenarios}:
        raise AssertionError('scenario seed overlaps earlier protocols')


def frozen_files():
    files = list((ROOT / '09_Simulation').glob('*.py')) + list((ROOT / '09_Simulation/recap').glob('*.py'))
    files += list((ROOT / '09_Simulation/tests_g9').glob('*.py'))
    files += [ROOT / '09_Simulation/configs' / n for n in ('g2_assumed_debug.json', 'g6_protocol.json', 'g8_protocol.json', 'g9_protocol.json')]
    files += [ROOT / '10_Experiments' / n for n in ('run_g9.py', 'analyze_g9.py', 'run_g8.py', 'setup_g8_data.py')]
    files += [ROOT / '10_Experiments/g9/analysis_plan.md']
    files += [ROOT / '05_Model_Training/reference_mlperf/kws_ref_model.tflite', ROOT / '05_Model_Training/reference_vww/vww_96_int8.tflite']
    files += list((ROOT / '05_Model_Training/g8_vww').glob('*'))
    return sorted({f for f in files if f.is_file()})


def make_lock(p):
    pools = load_inputs()
    scenarios = assign_inputs(reset_schedules(p) + stochastic_schedules(p), pools['holdout'])
    check_seed_disjoint(scenarios)
    OUT.mkdir(parents=True, exist_ok=True)
    dump(OUT / 'scenarios.json', scenarios)
    dump(OUT / 'input_splits.json', {s: {w: [{k: v for k, v in a.items() if k != 'x'} for a in items] for w, items in d.items()} for s, d in pools.items()})
    inputs = [ROOT / '05_Model_Training/reference_eembc' / a['id'] for a in pools['holdout']['kws'] + pools['development']['kws']]
    files = frozen_files() + [OUT / 'scenarios.json', OUT / 'input_splits.json'] + [f for f in inputs if f.is_file()]
    lock = dict(version=p['version'], locked_at_utc=datetime.now(timezone.utc).isoformat(), grounded_nvm_scale_range=p['grounded_nvm_scale_range'],
                sha256={f.relative_to(ROOT).as_posix(): sha(f) for f in sorted(set(files))}, python=sys.version,
                note='Main stage refuses to run while grounded_nvm_scale_range is null. Any change to a hashed file requires a new version and re-lock.')
    dump(LOCK, lock)
    return lock


def verify_lock(p):
    if not LOCK.exists():
        raise RuntimeError('no protocol lock; run --stage lock')
    lock = json.loads(LOCK.read_text())
    if lock['version'] != p['version']:
        raise RuntimeError('lock version differs from protocol version')
    bad = [n for n, d in lock['sha256'].items() if not (ROOT / n).is_file() or sha(ROOT / n) != d]
    if bad:
        raise RuntimeError('post-lock mutation: ' + ', '.join(bad[:5]))
    return lock


def evaluate(models, lookup, p, work, scenario, policy, scale, hazard=None):
    spec = p['policies'][policy.split('@')[0]]
    config = dict(p, nvm_energy_scale=scale)
    config.update({k: v for k, v in spec.items() if k != 'method'})
    if hazard is not None:
        config['planning_outage_rate_hz'] = hazard
    items = [dict(lookup[work][i], arrival_s=t, deadline_s=min(scenario['horizon_s'], t + scenario['deadline_interval_s']))
             for i, t in zip(scenario['input_ids'][work], scenario['arrivals_s'])]
    row = Runtime(ROOT, models[work], config, scenario, spec['method']).run(items)
    row.update(policy=policy, nvm_scale=scale, source_kind=scenario['source_kind'],
               rate_hz=scenario.get('actual_outage_rate_hz'), cap_idx=scenario.get('cap_index'))
    return row


def smoke(args):
    p = load_protocol()
    out = OUT / f'smoke-{args.run_id}'
    if out.exists():
        raise FileExistsError('smoke run exists')
    pools = load_inputs()
    models = {w: Model(ROOT, w) for w in p['workloads']}
    lookup = {w: {a['id']: a for a in pools['development'][w]} for w in p['workloads']}
    s = next(x for x in reset_schedules(p) if x['actual_outage_rate_hz'] == 4.0 and x['cap_index'] == 1)
    rows = []
    for work in p['workloads']:
        sc = dict(s, id='smoke_' + work, input_ids={work: [pools['development'][work][0]['id']] * 3})
        for policy in p['policies']:
            rows.append(evaluate(models, lookup, p, work, sc, policy, 1.0))
        for policy in ('RECAP_redo@matched', 'B5b_chime_dp@matched'):
            rows.append(evaluate(models, lookup, p, work, sc, policy, 1.0, hazard=sc['actual_outage_rate_hz']))
    for r in rows:
        if abs(r['energy_balance_error_j']) > 1e-9:
            raise AssertionError('ledger')
    dump(out / 'smoke.json', dict(status='SMOKE_ONLY_DEVELOPMENT_INPUTS', rows=[dict(workload=r['workload'], policy=r['policy'], completed=r['completed'],
         total=r['total_inputs'], energy_j=r['energy_j'], losses=r['losses'], chosen=r['chosen']) for r in rows]))
    print('smoke rows:', len(rows), 'all exact-output and ledger checks passed')


def main_stage(args):
    p = load_protocol()
    if p['grounded_nvm_scale_range'] is None:
        raise RuntimeError('grounded_nvm_scale_range is null: complete stage 3, set it, re-lock, then run')
    lock = verify_lock(p)
    if lock['grounded_nvm_scale_range'] != p['grounded_nvm_scale_range']:
        raise RuntimeError('lock was made before the grounded range was set; re-lock')
    out = OUT / args.run_id
    if out.exists():
        raise FileExistsError('Run exists; choose a new --run-id.')
    out.mkdir(parents=True)
    start = time.perf_counter()
    pools = load_inputs()
    models = {w: Model(ROOT, w) for w in p['workloads']}
    lookup = {w: {a['id']: a for a in pools['holdout'][w]} for w in p['workloads']}
    scenarios = json.loads((OUT / 'scenarios.json').read_text())
    reset = [s for s in scenarios if s['source_kind'] == 'external_reset']
    stoch = [s for s in scenarios if s['source_kind'] != 'external_reset']
    rows = []
    with (out / 'main.jsonl').open('w', encoding='utf-8') as f:
        for work in p['workloads']:
            for scale in p['grid']['nvm_energy_scale']:
                for s in reset:
                    for policy in p['policies']:
                        row = evaluate(models, lookup, p, work, s, policy, scale)
                        rows.append(row)
                        f.write(json.dumps(row, allow_nan=False) + '\n')
                print('main', work, 'nvm', scale, 'done', round(time.perf_counter() - start), 's', flush=True)
    secondary = []
    with (out / 'secondary.jsonl').open('w', encoding='utf-8') as f:
        for work in p['workloads']:
            for s in stoch:
                for policy in p['policies']:
                    r = evaluate(models, lookup, p, work, s, policy, 1.0)
                    r['analysis'] = 'stochastic_sources'
                    secondary.append(r)
                    f.write(json.dumps(r, allow_nan=False) + '\n')
            for scale in p['grid']['nvm_energy_scale']:
                for s in reset:
                    for policy in ('RECAP_redo', 'B5b_chime_dp'):
                        r = evaluate(models, lookup, p, work, s, policy + '@matched', scale, hazard=s['actual_outage_rate_hz'])
                        r['analysis'] = 'matched_hazard'
                        secondary.append(r)
                        f.write(json.dumps(r, allow_nan=False) + '\n')
    result = analyze_g9.analyze(rows, p)
    result.update(status='G9_MAIN_EXECUTED', calibrated=False, main_rows=len(rows), secondary_rows=len(secondary),
                  elapsed_s=time.perf_counter() - start,
                  limitations=['Assumed costs and planning hazard; model energy only.', 'VWW images reused from G8 (disclosed).',
                               'B5a from public code, B5b/B6 are adaptations; iNAS/INTERCEPT papers unavailable.'])
    dump(out / 'results.json', result)
    verify_lock(p)
    dump(out / 'manifest.json', dict(sha256={f.relative_to(ROOT).as_posix(): sha(f) for f in sorted(out.rglob('*')) if f.is_file()},
         command=f'python 10_Experiments/run_g9.py --stage main --run-id {args.run_id}'))
    print(json.dumps({'verdict_primary': result['primary']['verdict'], 'verdict_full_grid': result['full_grid']['verdict'],
                      'labels': result['label_counts']}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=['smoke', 'lock', 'main'], required=True)
    parser.add_argument('--run-id', default='run')
    a = parser.parse_args()
    if a.stage == 'lock':
        l = make_lock(load_protocol())
        print('locked', len(l['sha256']), 'files; grounded range:', l['grounded_nvm_scale_range'])
    elif a.stage == 'smoke':
        smoke(a)
    else:
        main_stage(a)
