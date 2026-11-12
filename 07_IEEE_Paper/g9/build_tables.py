"""Builds G9 negative-result tables from the immutable run 20261111-m2. No parameter or rule is changed here."""
import csv, json, collections
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / '10_Experiments/g9/20261111-m2'
OUT = Path(__file__).resolve().parent / 'assets'
OUT.mkdir(exist_ok=True)
res = json.loads((RUN / 'results.json').read_text())
rows = [json.loads(l) for l in (RUN / 'main.jsonl').read_text().splitlines()]
CONTROLS = ['B3_adaptive', 'B4_ci16', 'B4_ci64', 'B5a_inas', 'B5b_chime_dp']


def pct(v):
    return 'undef.' if v is None else f'{100 * v:+.2f}'


def ci(v):
    return '' if v is None else f'[{100 * v[0]:+.2f}, {100 * v[1]:+.2f}]'


# Table A: every cell, RECAP_redo vs each strong control (relative energy reduction, %, paired by scenario).
with open(OUT / 'g9_cells.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['workload', 'nvm_scale', 'reset_hz', 'capacity_uJ', 'label', 'state_saving_fraction'] +
               [f'{c}_reduction_pct' for c in CONTROLS] + [f'{c}_ci95' for c in CONTROLS] + ['versus_B1_pct'])
    for t in res['cells']:
        w.writerow([t['workload'], t['nvm_energy_scale'], t['reset_rate_hz'], t['capacity_j'] * 1e6, t['label'],
                    t['state_saving_fraction']] + [pct(t['controls'][c]['reduction']) for c in CONTROLS] +
                   [ci(t['controls'][c]['ci95']) for c in CONTROLS] + [pct(t['versus_B1'])])

# Table B: per-policy totals over the whole grid (all replicates and cells pooled; descriptive only).
agg = collections.defaultdict(lambda: dict(inputs=0, completed=0, saved=0, total=0, rows=0))
for r in rows:
    a = agg[(r['workload'], r['policy'])]
    a['inputs'] += r['total_inputs']; a['completed'] += r['completed']; a['rows'] += 1
    for k, v in r['chosen'].items():
        a['total'] += v
        a['saved'] += v if ('_z1' in k or 'ps1' in k) else 0
with open(OUT / 'g9_policies.md', 'w', encoding='utf-8') as f:
    f.write('| Workload | Policy | Completed / arrivals | State-saving share of tile decisions |\n|---|---|---|---|\n')
    for (work, pol), a in sorted(agg.items()):
        share = 'n/a' if a['total'] == 0 else f"{100 * a['saved'] / a['total']:.1f}%"
        f.write(f"| {work.upper()} | {pol} | {a['completed']} / {a['inputs']} | {share} |\n")

# Table C: grounded-range cells (NVM 1x, 4x) in compact markdown.
lo, hi = res['primary']['scale_range']
with open(OUT / 'g9_primary_cells.md', 'w', encoding='utf-8') as f:
    f.write('| Workload | NVM x | Reset Hz | Cap uJ | State-saving share | vs B3 | vs B4-16 | vs B4-64 | vs B5a | vs B5b | Label |\n|---|---|---|---|---|---|---|---|---|---|---|\n')
    for t in res['cells']:
        if lo <= t['nvm_energy_scale'] <= hi:
            s = t['state_saving_fraction']
            f.write(f"| {t['workload'].upper()} | {t['nvm_energy_scale']:g} | {t['reset_rate_hz']:g} | {t['capacity_j'] * 1e6:g} | "
                    f"{'n/a' if s is None else f'{100 * s:.0f}%'} | " + ' | '.join(pct(t['controls'][c]['reduction']) for c in CONTROLS) +
                    f" | {t['label']} |\n")

undef = sum(1 for t in res['cells'] if all(t['controls'][c]['reduction'] is None for c in CONTROLS))
ties = sum(1 for t in res['cells'] if t['controls']['B3_adaptive']['reduction'] == 0.0)
summary = dict(verdict_primary=res['primary']['verdict'], verdict_full_grid=res['full_grid']['verdict'], labels=res['label_counts'],
               cells_all_controls_undefined=undef, cells_exact_zero_vs_B3=ties, main_rows=res['main_rows'], secondary_rows=res['secondary_rows'])
(OUT / 'g9_summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
print(json.dumps(summary, indent=2))
