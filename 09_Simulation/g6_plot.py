"""Static G6 figures from frozen raw results; no post-test parameter selection."""
import json
import numpy as np


def plot(out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    result=json.loads((out/'results.json').read_text());methods=['B1_layer','B2_fixed','B3_adaptive','RECAP']
    fig,axes=plt.subplots(2,2,figsize=(10,7),layout='constrained')
    for row,name in enumerate(('kws','vww')):
        for col,domain in enumerate(('synthetic_stochastic','eth_measured_derived_rail')):
            part=result['workloads'][name][domain]['methods'];ax=axes[row,col]
            ax.bar(['Layer','Fixed state','Adaptive','RECAP'],[100*part[m]['completion_rate'] for m in methods],color='#377a9a')
            ax.set(ylim=(0,105),ylabel='Committed arrivals (%)',title=f'{name.upper()}: '+('synthetic' if col==0 else 'ETH measured source + assumed transfer'))
            ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    fig.savefig(out/'multiworkload.png',dpi=160);fig.savefig(out/'multiworkload.svg');plt.close(fig)
    fig,axes=plt.subplots(2,3,figsize=(12,7),layout='constrained')
    knobs=list(dict.fromkeys(a['knob'] for a in result['sensitivity']))
    for ax,knob in zip(axes.flat,knobs):
        for name in ('kws','vww'):
            rows=[a for a in result['sensitivity'] if a['knob']==knob and a['workload']==name]
            values=[a['comparison_vs_adaptive']['relative_energy_reduction'] for a in rows]
            ax.plot([str(a['value']) for a in rows],[np.nan if v is None else 100*v for v in values],marker='o',label=name.upper())
        ax.axhline(0,color='grey',lw=.7);ax.set(title=knob,ylabel='Energy reduction vs adaptive (%)');ax.legend();ax.grid(alpha=.2)
    fig.suptitle('ASSUMED costs; one-factor-at-a-time diagnostics on fixed source seeds')
    fig.savefig(out/'sensitivity.png',dpi=160);fig.savefig(out/'sensitivity.svg');plt.close(fig)
