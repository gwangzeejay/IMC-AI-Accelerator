"""Derive G7 publication assets from frozen results; never fit or run inference."""
from pathlib import Path
import csv
import hashlib
import json
import math
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = HERE / 'assets'
METHODS = ['B1_layer', 'B2_fixed', 'B3_adaptive', 'RECAP']
LABELS = ['Layer', 'Fixed', 'Adaptive', 'RECAP']
SOURCES = ['10_Experiments/g3/summary.json', '10_Experiments/g4/summary.json',
           '10_Experiments/g5/summary.json', '10_Experiments/g6/results.json',
           '10_Experiments/g6_analysis/analysis.json', '10_Experiments/g6/accuracy.json',
           '10_Experiments/g6/protocol_snapshot.json', '02_Research/novelty_matrix.md']

def read(name):
    return json.loads((ROOT / name).read_text(encoding='utf-8'))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def number(x, digits=4):
    return 'undefined' if x is None else f'{x:.{digits}f}'

def table(name, header, rows, note):
    with (OUT / (name + '.csv')).open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f); w.writerow(header); w.writerows(rows)
    lines = ['| ' + ' | '.join(header) + ' |', '| ' + ' | '.join(['---'] * len(header)) + ' |']
    lines += ['| ' + ' | '.join(map(str, row)) + ' |' for row in rows]
    lines += ['', note, '']
    (OUT / (name + '.md')).write_text('\n'.join(lines), encoding='utf-8')

def save(fig, name):
    fig.savefig(OUT / (name + '.svg'))
    fig.savefig(OUT / (name + '.pdf'))
    fig.savefig(OUT / (name + '.png'), dpi=300)
    from PIL import Image
    with Image.open(OUT / (name + '.png')) as im:
        im.convert('L').save(OUT / (name + '_bw.png'))
    plt.close(fig)

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.family': 'DejaVu Serif', 'font.size': 9,
                         'axes.labelsize': 9, 'axes.titlesize': 9,
                         'xtick.labelsize': 8, 'ytick.labelsize': 8,
                         'legend.fontsize': 8, 'pdf.fonttype': 42, 'svg.fonttype': 'none'})
    g3, g4, g5, g6, diag, accuracy, protocol = [read(p) for p in SOURCES[:-1]]
    assert not g6['calibrated'] and not g6['ready_for_paper_energy_results']
    domains = ['synthetic_stochastic', 'eth_measured_derived_rail']
    main_rows = []
    for work in ['kws', 'vww']:
        for domain in domains:
            item = g6['workloads'][work][domain]
            for method in METHODS:
                a = item['methods'][method]
                main_rows.append([work.upper(), domain, method,
                    f"{a['completed']}/{a['total_inputs']}", number(a['on_time_rate'] * 100, 2),
                    number(None if a['energy_per_completed_j'] is None else a['energy_per_completed_j'] * 1000, 6),
                    'infinity' if a['p95_is_infinite'] else number(a['p95_latency_s'])])
    table('table1_main', ['Workload', 'Domain', 'Method', 'Commits', 'On-time (%)',
                          'Assumed energy (mJ/commit)', 'p95 (s)'], main_rows,
          'All consumed model energy, including unfinished work, is in the numerator. '
          'Costs are assumed. Synthetic: 40 traces/120 arrivals; ETH-derived: six day blocks, '
          'two capacitors/day and 36 arrivals. Infinite p95 includes unfinished arrivals.')
    ablations = []
    for item in g6['ablations']:
        comp = item['comparison_ablation_vs_full']; a, b = comp['a'], comp['b']
        ablations.append([item['workload'].upper(), item['variant'],
                         f"{a['completed']}/{a['total_inputs']}", f"{b['completed']}/{b['total_inputs']}",
                         number(None if a['energy_per_completed_j'] is None else a['energy_per_completed_j'] * 1000, 6),
                         number(None if comp['relative_energy_reduction'] is None else -comp['relative_energy_reduction'] * 100, 6)])
    table('table2_ablations', ['Workload', 'Intervention', 'Commits', 'Full commits', 'Model mJ/commit',
                              'Energy change vs full (%)'], ablations,
          'Twelve preselected source cases/36 arrivals per variant. Ratios with unequal completions '
          'do not establish a benefit. all_live keeps the minimal-state planning objective: it is '
          'not an optimized full-state baseline. no_control changes energy and time together.')
    sensitivity = []
    for item in g6['sensitivity']:
        c = item['comparison_vs_adaptive']; a, b = c['a'], c['b']
        sensitivity.append([item['workload'].upper(), item['knob'], item['value'],
                            f"{a['completed']}/{a['total_inputs']}", f"{b['completed']}/{b['total_inputs']}",
                            number(None if c['relative_energy_reduction'] is None else c['relative_energy_reduction'] * 100, 6)])
    table('table3_sensitivity', ['Workload', 'Axis', 'Value', 'RECAP commits', 'Adaptive commits', 'Reduction (%)'],
          sensitivity, 'Eight preselected traces/24 arrivals per cell. These are engineering stress ranges, '
          'not calibrated parameter confidence intervals. VWW bandwidth x0.25 has only 3 vs 2 commits.')
    table('table4_validation', ['Level', 'Evidence', 'Boundary'], [
        ['G4 controller', str(g4['total_rtl_cases']) + ' cases; ' + str(g4['total_checked_transactions']) + ' byte ACKs', 'Two microtiles; finite simulation'],
        ['G4 arithmetic', str(g4['arithmetic']['mac_cases']) + ' MAC; ' + str(g4['arithmetic']['requant_cases']) + ' requantization cases', 'Scalar units, not full accelerator'],
        ['G5 model', '901/1000 reference labels; 0 own arithmetic mismatches', 'MFCC input; reference CPU head'],
        ['G6 model', str(accuracy['own_checked_elements']) + ' tensor elements; 0 mismatches', '16 inputs; reference CPU head'],
        ['G6 fault', '8 full networks + 1000 large-slot schedules', 'Large-slot campaign is not 1000 full networks'],
        ['G6 main', str(g6['completed_outputs_in_main']) + ' committed outputs checked', 'Hybrid event simulation; assumed costs'],
    ], 'No silicon energy, full-network RTL, formal proof, PPA, or compiled CPU arena is established.')
    table('table5_related_work', ['Work', 'Positive fact supported', 'Locator', 'Open comparison'], [
        ['Chime (2016)', 'Checkpoint/recomputation cost optimization', 'Sections 5-6, 9.5; G1 S1', 'Common-backend B4 adaptation not run'],
        ['Viadotto (2025)', 'Adaptive nonvolatile CRAM platform', 'Sections 2.1, 3.1-3.3; G1 S2', 'NVM/volatile hardware semantics differ'],
        ['CHRYSALIS (2024)', 'Energy/inference architecture co-design', 'Abstract/artifact; G1 S3', 'Full algorithm comparison outstanding'],
        ['CIM-Tuner (2026)', 'Weight-update and mapping trade-offs', 'Sections III-B-D, Eq. 5; G1 S4', 'Intermittent action/objective comparison outstanding'],
        ['FreeML (2024)', 'Compression, buffer reduction, energy-aware execution', 'Sections 3.1-3.3, 4.4, 5.3', 'Early exits change accuracy/output contract'],
        ['RECAP working implementation', 'Byte-level checkpoints and DW/PW candidate selection', 'G4/G6 pinned source', 'Nominal objective omits redo benefit; novelty unresolved'],
    ], 'Qualitative scope comparison only. No inferred absence is encoded as No. '
          'This is not a quantitative reproduction of the literature.')

    # Figure 1: architecture, scoped to what was actually implemented.
    fig, ax = plt.subplots(figsize=(3.5, 2.0)); ax.set(xlim=(0, 10), ylim=(0, 6)); ax.axis('off')
    boxes = [(2, 4.8, 'Pinned model/input\nNVM layer anchors'), (8, 4.8, 'Causal admission\ncurrent reservoir'),
             (2, 1.4, 'Volatile DW/PW\nINT8 + weight bank'), (8, 1.4, 'COW checkpoint\nCRC + publish byte')]
    for x, y, label in boxes:
        ax.text(x, y, label, ha='center', va='center', fontsize=8,
                bbox=dict(boxstyle='round,pad=.4', fc='white', ec='black'))
    for start, end in [((4,4.8),(6,4.8)),((8,3.9),(8,2.4)),((6,1.4),(4,1.4)),((2,2.4),(2,3.9))]:
        ax.annotate('', xy=end, xytext=start, arrowprops={'arrowstyle':'->'})
    ax.text(5, 3.05, 'Event-model integration;\nscalar/controller RTL separately', ha='center', fontsize=8)
    fig.tight_layout(pad=.4); save(fig, 'fig1_architecture')

    fig, axes = plt.subplots(2, 2, figsize=(7.16, 3.65), sharey=True)
    for row, work in enumerate(['kws', 'vww']):
        for col, domain in enumerate(domains):
            ax = axes[row, col]; ms = g6['workloads'][work][domain]['methods']
            bars = ax.bar(range(4), [100 * ms[m]['completion_rate'] for m in METHODS],
                          color=['white', '.8', '.55', '.25'], edgecolor='black',
                          hatch=['', '//', '..', 'xx'])
            for bar, m in zip(bars, METHODS):
                a=ms[m]; ax.text(bar.get_x()+bar.get_width()/2, bar.get_height()+2,
                                f"{a['completed']}/{a['total_inputs']}", ha='center', fontsize=8)
            ax.set_xticks(range(4), LABELS); ax.set_ylim(0, 106)
            ax.set_title(work.upper() + (' / synthetic' if col==0 else ' / ETH-derived'))
            ax.set_ylabel('Completed arrivals (%)' if col==0 else '')
    fig.tight_layout(pad=.6); save(fig, 'fig2_completion')

    comparisons = [('G3 microtile', g3['primary_comparison']['relative_energy_reduction'],
                    g3['primary_comparison']['bootstrap']['energy_reduction_ci95']),
                   ('G5 KWS', g5['comparison_vs_adaptive']['relative_energy_reduction'], g5['paired_bootstrap']['energy_reduction_ci95'])]
    for w in ['kws','vww']:
        d=g6['workloads'][w]['synthetic_stochastic']
        comparisons.append(('G6 '+w.upper(),d['comparison_vs_adaptive']['relative_energy_reduction'],d['paired_bootstrap']['energy_reduction_ci95']))
    fig,ax=plt.subplots(figsize=(3.5,2.25))
    for i,(label,point,ci) in enumerate(comparisons):
        ax.errorbar(point*100,i,xerr=[[100*(point-ci[0])],[100*(ci[1]-point)]],fmt='o',color='black',capsize=3)
    ax.set_yticks(range(4),[v[0] for v in comparisons]);ax.invert_yaxis()
    ax.axvline(0,color='.7',lw=.8);ax.axvline(20,color='.4',ls='--',lw=.8)
    ax.set_xlabel('Assumed energy reduction vs adaptive (%)')
    fig.tight_layout(pad=.5);save(fig,'fig3_intervals')

    variants=protocol['ablations']; short=['Ignore reload','Always save DW','Always replay DW','Fixed mapping',
        'Fixed recovery','Continuous fusion','Unfused','All live','No weight reuse','No control']
    fig,axes=plt.subplots(1,2,figsize=(7.16,3.7))
    for ax,w in zip(axes,['kws','vww']):
        vals={a['variant']:a['comparison_ablation_vs_full'] for a in g6['ablations'] if a['workload']==w}
        full=next(iter(vals.values()))['b']['completed']
        for i,v in enumerate(variants):
            c=vals[v];a=c['a']; y=i
            ax.barh(y,a['completed'],color='.6',edgecolor='black',height=.7)
            ax.text(a['completed']+.4,y,str(a['completed']),va='center',fontsize=8,zorder=4,
                    bbox={'facecolor':'white','edgecolor':'none','pad':.25})
        ax.axvline(full,color='black',ls='--',zorder=1);ax.set_yticks(range(len(short)),short if w=='kws' else [])
        ax.set_xlim(0,37);ax.invert_yaxis();ax.set_title(w.upper()+f' (full: {full}/36)');ax.set_xlabel('Commits / 36 arrivals')
    fig.tight_layout(pad=.6);save(fig,'fig4_ablations')

    fig,axes=plt.subplots(2,1,figsize=(7.16,3.65),layout='constrained')
    knob_labels=['NVM energy','Bandwidth','Compute energy','Active leakage','Admission margin','Retention']
    for ax,w in zip(axes,['kws','vww']):
        grid=np.full((1,18),np.nan);labels=[]
        for j,item in enumerate(a for a in g6['sensitivity'] if a['workload']==w):
            value=item['comparison_vs_adaptive']['relative_energy_reduction']
            grid[0,j]=np.nan if value is None else value*100
            a=item['comparison_vs_adaptive']['a'];b=item['comparison_vs_adaptive']['b']
            labels.append(f"{a['completed']}/{b['completed']}")
        image=ax.imshow(np.ma.masked_invalid(grid),cmap='Greys',vmin=0,vmax=35,aspect='auto')
        for j,val in enumerate(grid[0]):
            label='undef' if np.isnan(val) else f'{0 if abs(val)<.005 else val:.2f}'
            ax.text(j,0,label+'\n'+labels[j],ha='center',va='center',fontsize=8,color='white' if val>18 else 'black')
        values=['.25x','1x','4x']*3+['0','1','10','0','5','20','0','1','10']
        ax.set_yticks([0],[w.upper()]);ax.set_xticks(range(18),values)
        top=ax.secondary_xaxis('top');top.set_xticks([1,4,7,10,13,16],knob_labels)
        top.tick_params(length=0,labelsize=8)
        for x in [2.5,5.5,8.5,11.5,14.5]:ax.axvline(x,color='black',lw=.7)
    save(fig,'fig5_sensitivity')

    led=diag['steady_checkpoint_ledger']['kws']['ledger']
    fig,ax=plt.subplots(figsize=(3.5,2.3));bottom=np.zeros(2);names=['B1_layer','RECAP']
    for label,key,hatch in [('Scratch','scratch_j','//'),('Layer log','log_j','..'),('Weight load','weight_load_j','xx'),('Other',None,'')]:
        vals=[]
        for n in names:
            a=led[n];v=a[key] if key else a['total_j']-a['scratch_j']-a['log_j']-a['weight_load_j'];assert v>=0
            vals.append(v*1000)
        ax.bar(range(2),vals,bottom=bottom,label=label,hatch=hatch,edgecolor='black',color='white');bottom+=vals
    ax.set_xticks(range(2),['Layer','RECAP']);ax.set_ylabel('Total assumed energy (mJ)')
    ax.legend(ncols=2,loc='upper left',bbox_to_anchor=(0,1.28));ax.set_ylim(0,6)
    fig.tight_layout(pad=.6);save(fig,'fig6_steady_ledger')

    # Compact table for the letter. Values come from the same table1 records.
    tex=[r'\begin{table}[t]\caption{G6 results with assumed costs. S: stochastic; M: ETH-derived. Energy includes unfinished work.}\label{tab:main}',
         r'\centering\footnotesize\setlength{\tabcolsep}{2.5pt}',
         r'\begin{tabular}{llrrrr}\hline',
         r'Work & Method & S commits & S mJ & M commits & M mJ\\\hline']
    for w in ['kws','vww']:
        for m,label in zip(METHODS,['Layer','Fixed','Adaptive','RECAP']):
            s=g6['workloads'][w][domains[0]]['methods'][m];v=g6['workloads'][w][domains[1]]['methods'][m]
            es=number(None if s['energy_per_completed_j'] is None else s['energy_per_completed_j']*1000,3)
            em=number(None if v['energy_per_completed_j'] is None else v['energy_per_completed_j']*1000,3)
            tex.append(f"{w.upper()} & {label} & {s['completed']}/120 & {es} & {v['completed']}/36 & {em} \\\\")
        tex.append(r'\hline')
    tex += [r'\end{tabular}\end{table}']
    (OUT/'main_table.tex').write_text('\n'.join(tex)+'\n',encoding='utf-8')
    facts={'kws_gain_pct':g6['workloads']['kws'][domains[0]]['comparison_vs_adaptive']['relative_energy_reduction']*100,
           'vww_gain_pct':g6['workloads']['vww'][domains[0]]['comparison_vs_adaptive']['relative_energy_reduction']*100,
           'g6_rows':g6['raw_rows'],'g6_main_commits':g6['completed_outputs_in_main'],
           'g4_cases':g4['total_rtl_cases'],'scratch_fraction':diag['steady_checkpoint_ledger']['kws']['scratch_fraction_of_difference'],
           'calibrated':False,'submission_ready':False}
    (OUT/'paper_facts.json').write_text(json.dumps(facts,indent=2)+'\n',encoding='utf-8')
    manifests={p:sha(ROOT/p) for p in SOURCES}
    manifests['07_IEEE_Paper/g7/build_assets.py']=sha(Path(__file__))
    (OUT/'sources.json').write_text(json.dumps(manifests,indent=2)+'\n',encoding='utf-8')
    print('Built 6 figures (PDF/SVG/300-dpi PNG/BW), 5 CSV/Markdown tables, letter table, source hashes.')

if __name__=='__main__':main()
