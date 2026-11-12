"""Standalone scientific plots from raw G3 summary; all costs are assumptions."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def plot(output):
    report=json.loads((output/'summary.json').read_text())
    dest=output/'plots';dest.mkdir(exist_ok=True)
    names=['B1_micro','B2_micro','B3_micro','RECAP_proto','fixed_mapping_joint_recovery','no_weight_reuse','matched_SAVE','matched_REPLAY']
    labels=['B1','B2','B3 adaptive','Mapper','Fixed mapping','No weight reuse','SAVE DW','REPLAY DW']
    values=[report['methods'][n] for n in names]
    fig,axes=plt.subplots(1,2,figsize=(12,4.8),layout='constrained')
    x=np.arange(len(names));colors=['#94a3b8']*len(names);colors[3]='#2563eb'
    axes[0].bar(x,[100*v['completion_rate'] for v in values],color=colors)
    axes[0].set(ylabel='Completed workloads (%)',ylim=(0,105),title='Held-out completion (18 independent traces)')
    energies=[np.nan if v['energy_per_completed_j'] is None else 1e6*v['energy_per_completed_j'] for v in values]
    axes[1].bar(x,energies,color=colors)
    for i,e in enumerate(energies):
        if np.isnan(e): axes[1].text(i,0,'undefined',rotation=90,ha='center',va='bottom',fontsize=8)
    axes[1].set(ylabel='Model energy / completed workload (uJ)',title='Includes energy of unfinished work')
    for ax in axes:
        ax.set_xticks(x,labels,rotation=35,ha='right');ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
        ax.set_xlim(-.6,len(names)-.4)
    fig.suptitle('G3 — assumed architectural costs; no calibrated hardware energy claim',fontsize=12)
    for ext in ('png','svg'): fig.savefig(dest/f'heldout_comparison.{ext}',dpi=180)
    plt.close(fig)
    plot_sensitivity(output,report)


def plot_episodes(output):
    report=json.loads((output/'recovery_episodes.json').read_text())
    cells=report['cells'];dw=sorted({p['dw_scale'] for p in cells});writes=sorted({p['write_scale'] for p in cells})
    maximum=max(5,max(abs(100*p['save_relative_energy_reduction']) for p in cells))
    fig,axes=plt.subplots(1,2,figsize=(10,4.7),layout='constrained')
    for loss,ax in enumerate(axes):
        data=np.zeros((len(dw),len(writes)))
        for p in cells:
            if p['controlled_cold_losses']==loss:
                data[dw.index(p['dw_scale']),writes.index(p['write_scale'])]=100*p['save_relative_energy_reduction']
        im=ax.imshow(data,cmap='RdBu',vmin=-maximum,vmax=maximum)
        for i in range(len(dw)):
            for j in range(len(writes)):
                ax.text(j,i,f'{data[i,j]:+.1f}%',ha='center',va='center')
        ax.set_xticks(range(len(writes)),[f'{v:g}x' for v in writes]);ax.set_yticks(range(len(dw)),[f'{v:g}x' for v in dw])
        ax.set(title='No outage' if loss==0 else 'One cold loss after prefix CI=16',xlabel='NVM write energy',ylabel='DW compute energy')
    fig.colorbar(im,ax=axes,label='Model energy reduction of SAVE (%)')
    fig.suptitle('Exploratory state-aligned recovery episodes — one descriptor, assumed costs\nPositive = SAVE wins; not held-out full-workload performance',fontsize=11)
    for ext in ('png','svg'): fig.savefig(output/'plots'/f'recovery_episodes.{ext}',dpi=180)
    plt.close(fig)


def plot_sensitivity(output,report):
    dest=output/'plots'
    points=report['sensitivities'];dw=sorted({p['dw_scale'] for p in points});writes=sorted({p['write_scale'] for p in points})
    data=np.full((len(dw),len(writes)),np.nan)
    for point in points:
        c=point['comparison'];v=c['relative_energy_reduction']
        if v is not None and c['noninferior_point_estimate']:
            data[dw.index(point['dw_scale']),writes.index(point['write_scale'])]=100*v
    fig,ax=plt.subplots(figsize=(6.4,4.7),layout='constrained')
    cmap=plt.get_cmap('RdBu').copy();cmap.set_bad('#e2e8f0')
    maximum=max(5,float(np.nanmax(np.abs(data))) if np.any(np.isfinite(data)) else 5)
    im=ax.imshow(data,cmap=cmap,vmin=-maximum,vmax=maximum)
    for i in range(len(dw)):
        for j in range(len(writes)):
            ax.text(j,i,'undefined' if np.isnan(data[i,j]) else f'{data[i,j]:+.1f}%',ha='center',va='center',fontsize=10)
    ax.set_xticks(range(len(writes)),[f'{v:g}x' for v in writes])
    ax.set_yticks(range(len(dw)),[f'{v:g}x' for v in dw])
    ax.set(xlabel='NVM write-energy multiplier',ylabel='DW compute-energy multiplier',
           title='Matched SAVE vs REPLAY — model-only sensitivity\nPositive = lower SAVE energy; comparable completion required')
    fig.colorbar(im,ax=ax,label='Energy reduction of SAVE (%)')
    for ext in ('png','svg'): fig.savefig(dest/f'save_replay_sensitivity.{ext}',dpi=180)
    plt.close(fig)


if __name__=='__main__': plot(Path(__file__).resolve().parent/'g3')
