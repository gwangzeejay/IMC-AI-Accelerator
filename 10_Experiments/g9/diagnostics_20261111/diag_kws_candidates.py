import sys
from pathlib import Path
ROOT = Path(r'D:\Học tập\Claude_project\Vi mạch project demo\In_Memory_Computing_AI_Accelerator')
sys.path.insert(0, str(ROOT / '09_Simulation')); sys.path.insert(0, str(ROOT / '10_Experiments'))
import run_g9
from g6_model import Model
from g9_runtime import Runtime

p = run_g9.load_protocol()
pools = run_g9.load_inputs()
sc0 = next(x for x in run_g9.reset_schedules(p) if x['actual_outage_rate_hz'] == 4.0 and x['cap_index'] == 1)
work = 'kws'
model = Model(ROOT, work)
sc = dict(sc0, capacity_j=p['grid']['capacities_j'][1], input_ids={work: [pools['development'][work][0]['id']] * 3})
rt = Runtime(ROOT, model, dict(p, nvm_energy_scale=1.0), sc, 'RECAP_redo')
print('ci_chunks', p['ci_chunks'], 'scratch_slot_bytes', p['scratch_slot_bytes'], 'sram_bytes', p['sram_bytes'], 'capacity', rt.power.capacity)
for st, d in enumerate(model.stages):
    print('stage', st, d['kind'], 'ci', d['ci'], 'co', d['co'], 'pixels', d['pixels'])
for lam in (2.0, 1e5):
    rt.planning_rate = lam; rt.plan_cache.clear()
    for st in (1, 2):
        d = model.stages[st]
        plans = rt.plans(st, 0)
        print('lambda', lam, 'stage', st, d['kind'], 'ci', d['ci'], 'n_plans', len(plans), 'with state-saving', sum(1 for a in plans if a['z'] or a['ps']))
        best = min(plans, key=lambda a: (a['score_expected'], a['score_energy'], -a['n'] * a['co'], -a['chunk']))
        print('  best', {k: (round(v, 12) if isinstance(v, float) else v) for k, v in best.items()})
        same = [a for a in plans if a['n'] == best['n'] and a['co'] == best['co']]
        for a in sorted(same, key=lambda a: a['score_expected'])[:6]:
            print('  cand chunk', a['chunk'], 'z', a['z'], 'ps', a['ps'], 'nominal/px %.4e' % a['score_energy'], 'expected/px %.4e' % a['score_expected'], 'time/px %.4e' % a['score_time'])
        ps_only = [a for a in same if a['ps'] or a['z']]
        print('  state-saving candidates same tile:', len(ps_only), 'bound-feasible filter drops?')
