"""Standalone scientific figures; all energy panels are assumed-model results."""
import json
import numpy as np


def plot(out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    result=json.loads((out/'results.json').read_text())
    methods=['B1_layer','B2_fixed','B3_adaptive','RECAP','RECAP_no_control']
    labels=['Layer','Fixed','Adaptive','RECAP','No control\n(ablation)']
    fig,axes=plt.subplots(1,2,figsize=(10,3.8),layout='constrained')
    axes[0].bar(labels,[100*result['methods'][m]['completion_rate'] for m in methods],color='#3879a8')
    axes[0].set(ylabel='Committed arrivals (%)',ylim=(0,105),title='Held-out source traces')
    values=[result['methods'][m]['energy_per_completed_j'] for m in methods]
    axes[1].bar(labels,[np.nan if v is None else 1e3*v for v in values],color='#b37332')
    for i,v in enumerate(values):
        if v is None:axes[1].text(i,0,'undefined',rotation=90,ha='center',va='bottom')
    axes[1].set(ylabel='Model mJ / committed inference',title='ASSUMED costs; not measured energy')
    for ax in axes:ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    fig.savefig(out/'heldout.png',dpi=180);fig.savefig(out/'heldout.svg');plt.close(fig)
