"""Pre-registered G9 analysis. Pure functions; applies protocol decision_rule verbatim.

Input rows carry: workload, policy, nvm_scale, rate_hz, cap_idx plus the usual
Runtime row fields. Nothing here reads outcomes to choose cells or thresholds.
"""
import itertools
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '09_Simulation'))
from g5_experiments import comparison, bootstrap, aggregate


def analysis_params(p):
    q = dict(p)
    q['bootstrap_seed'] = p['seeds']['bootstrap_seed']
    q['bootstrap_replicates'] = p['decision_rule']['bootstrap_replicates']
    return q


def state_saving_fraction(rows):
    total = saved = 0
    for r in rows:
        for key, count in r['chosen'].items():
            total += count
            if '_z1' in key or 'ps1' in key:
                saved += count
    return None if total == 0 else saved / total


def classify_cell(by_policy, p):
    """by_policy: {policy: [rows of this (workload, cell)]}, paired by scenario_id."""
    q = analysis_params(p)
    rule = p['decision_rule']
    delta = rule['delta_min_relative_reduction']
    recap = by_policy[p['recap_primary']]
    detail = {}
    wins = []
    losses = []
    for control in p['strong_controls']:
        ctl = by_policy[control]
        c = comparison(recap, ctl, q)
        b = bootstrap(recap, ctl, q)
        ci = b['energy_reduction_ci95']
        red = c['relative_energy_reduction']
        win = bool(c['noninferior_point_estimate'] and red is not None and red >= delta and ci is not None and ci[0] > 0)
        reverse = comparison(ctl, recap, q)
        loss = bool(reverse['noninferior_point_estimate'] and red is not None and red <= -delta and ci is not None and ci[1] < 0)
        detail[control] = dict(reduction=red, ci95=ci, noninferior=c['noninferior_point_estimate'], win=win, loss=loss,
                               recap_completed=c['a']['completed'], control_completed=c['b']['completed'],
                               undefined_replicates=b['undefined_replicates'])
        wins.append(win)
        losses.append(loss)
    fraction = state_saving_fraction(recap)
    cell_win = all(wins)
    mechanism = bool(fraction is not None and fraction >= 0.10)
    if cell_win and mechanism:
        label = 'win'
    elif cell_win:
        label = 'win_without_state_saving'
    elif any(losses):
        label = 'loss_to_some_control'
    else:
        label = 'tie_or_inconclusive'
    return dict(label=label, state_saving_fraction=fraction, controls=detail,
                versus_B1=None if 'B1_layer' not in by_policy else comparison(recap, by_policy['B1_layer'], q)['relative_energy_reduction'])


def neighbours(a, b):
    diff = [abs(x - y) for x, y in zip(a, b)]
    return sorted(diff) == [0, 0, 1]


def has_region(win_cells):
    return any(neighbours(a, b) for a, b in itertools.combinations(win_cells, 2))


def verdict(cells, p, scale_range=None):
    """cells: {(workload, ni, ri, ci): classification}. scale_range=(lo, hi) restricts by nvm scale."""
    scales = p['grid']['nvm_energy_scale']
    result = {}
    for work in p['workloads']:
        wins = [(ni, ri, ci) for (w, ni, ri, ci), c in cells.items()
                if w == work and c['label'] == 'win'
                and (scale_range is None or scale_range[0] <= scales[ni] <= scale_range[1])]
        result[work] = dict(win_cells=sorted(wins), region=has_region(wins))
    both = all(result[w]['region'] for w in p['workloads'])
    one = any(result[w]['region'] for w in p['workloads'])
    name = 'REGION_BOTH_WORKLOADS' if both else 'REGION_ONE_WORKLOAD' if one else 'NO_REGION'
    return dict(verdict=name, per_workload=result, scale_range=scale_range)


def analyze(rows, p):
    scales = p['grid']['nvm_energy_scale']
    rates = p['grid']['reset_rates_hz']
    caps = p['grid']['capacities_j']
    cells = {}
    table = []
    for work in p['workloads']:
        for ni, scale in enumerate(scales):
            for ri, rate in enumerate(rates):
                for ci in range(len(caps)):
                    part = [r for r in rows if r['workload'] == work and r['nvm_scale'] == scale and r['rate_hz'] == rate and r['cap_idx'] == ci]
                    by = {}
                    for pol in p['policies']:
                        by[pol] = sorted([r for r in part if r['policy'] == pol], key=lambda r: r['scenario_id'])
                    if any(len(v) != p['grid']['replicates_per_cell'] for v in by.values()):
                        raise ValueError(f'incomplete cell {work} {scale} {rate} {ci}')
                    cells[(work, ni, ri, ci)] = classify_cell(by, p)
                    table.append(dict(workload=work, nvm_energy_scale=scale, reset_rate_hz=rate, capacity_j=caps[ci],
                                      label=cells[(work, ni, ri, ci)]['label'],
                                      state_saving_fraction=cells[(work, ni, ri, ci)]['state_saving_fraction'],
                                      controls=cells[(work, ni, ri, ci)]['controls'],
                                      versus_B1=cells[(work, ni, ri, ci)]['versus_B1']))
    rng = p.get('grounded_nvm_scale_range')
    return dict(cells=table, full_grid=verdict(cells, p), primary=verdict(cells, p, tuple(rng) if rng else None),
                label_counts={lab: sum(1 for t in table if t['label'] == lab) for lab in
                              ('win', 'win_without_state_saving', 'loss_to_some_control', 'tie_or_inconclusive')})
