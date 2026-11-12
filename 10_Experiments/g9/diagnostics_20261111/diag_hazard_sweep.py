"""Read-only diagnostic of why RECAP_redo never ranks a state-saving plan first.
Uses development inputs only; imports locked code unmodified; writes nothing to the project."""
import sys, json
from pathlib import Path
ROOT = Path(r'D:\Học tập\Claude_project\Vi mạch project demo\In_Memory_Computing_AI_Accelerator')
sys.path.insert(0, str(ROOT / '09_Simulation')); sys.path.insert(0, str(ROOT / '10_Experiments'))
import run_g9
from g6_model import Model
from g9_runtime import Runtime

p = run_g9.load_protocol()
pools = run_g9.load_inputs()
sc0 = next(x for x in run_g9.reset_schedules(p) if x['actual_outage_rate_hz'] == 4.0 and x['cap_index'] == 1)
for work in ('kws', 'vww'):
    model = Model(ROOT, work)
    for cap_idx, cap in enumerate(p['grid']['capacities_j']):
        for scale in (0.25, 1.0, 16.0):
            sc = dict(sc0, capacity_j=cap, input_ids={work: [pools['development'][work][0]['id']] * 3})
            cfg = dict(p, nvm_energy_scale=scale)
            rt = Runtime(ROOT, model, cfg, sc, 'RECAP_redo')
            names = list(range(len(model.stages)))
            # decision-level: first tile of every stage
            res = {}
            for lam in (2.0, 16.0, 1e2, 1e3, 1e4, 1e5):
                rt.planning_rate = lam; rt.plan_cache.clear()
                saved = total = 0
                for st in names:
                    d = model.stages[st]
                    plans = rt.plans(st, 0)
                    if not plans:
                        continue
                    best = min(plans, key=lambda a: (a['score_expected'], a['score_energy'], -a['n'] * a['co'], -a['chunk']))
                    total += 1
                    saved += int(best['z'] or best['ps'])
                res[lam] = f'{saved}/{total}'
            print(work, 'cap', cap, 'nvm', scale, 'state-saving first-ranked stages by planning hazard:', res)
