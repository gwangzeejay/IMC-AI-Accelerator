"""Pinned image/features, new source seeds and native measured ETH windows."""
import hashlib
import json
from pathlib import Path
import random
import h5py
import numpy as np
from g5_experiments import data as kws_data,dump,sha


def inputs(root):
    p5=json.loads((root/'09_Simulation/configs/g5_protocol.json').read_text())
    items,_=kws_data(root,p5)
    prior=json.loads((root/'10_Experiments/g5/scenarios.json').read_text())
    used={name for group in prior.values() for s in group for name in s['input_ids']}
    checks=json.loads((root/'10_Experiments/g5/accuracy.json').read_text())['checks']
    used|={a['input_id'] for a in checks}
    used_hashes={a['sha256'] for a in items if a['id'] in used}
    available=[a for a in items if a['sha256'] not in used_hashes and a['index']>=200]
    base=root/'05_Model_Training/reference_vww/coco_subset'
    manifest=json.loads((base/'manifest.json').read_text())
    if sha(base/'inputs.npz')!=manifest['inputs_sha256']:raise ValueError('VWW input hash')
    with np.load(base/'inputs.npz') as f:
        images=[dict(id=m['id'],label=m['label'],x=f['x'][i:i+1].copy(),sha256=m['feature_sha256']) for i,m in enumerate(manifest['images'])]
    for a in images:
        if hashlib.sha256(a['x'].tobytes()).hexdigest()!=a['sha256']:raise ValueError('image feature bytes')
    # Two/class are reserved for preflight arithmetic and diagnostic faults.
    images=[a for label in (0,1) for a in [a for a in images if a['label']==label][2:]]
    return dict(kws=available,vww=images)


def synthetic(p):
    result=[]
    for capidx,cap in enumerate(p['capacities_j']):
        for family in ('steady','mild','severe','zero'):
            repetitions=p['synthetic_replicates_per_family'] if family in ('mild','severe') else 1
            for rep in range(repetitions):
                seed=p['test_seed_base']+capidx*10000+('steady','mild','severe','zero').index(family)*100+rep
                rng=random.Random(seed);trace=[]
                for step in range(40):
                    if family=='steady':power=p['source_mean_w']
                    elif family=='zero':power=0.
                    else:
                        zero=.2 if family=='mild' else .8
                        power=0. if rng.random()<zero else p['source_mean_w']*rng.uniform(.2,1.8)
                    trace.append([step*p['horizon_s']/40,power])
                result.append(dict(id=f'g6_{seed}',seed=seed,family=f'{family}_cap{capidx}',source_kind=family,
                    capacity_j=cap,trace=trace,horizon_s=p['horizon_s'],arrivals_s=p['arrivals_s'],deadline_interval_s=p['deadline_interval_s'],
                    ci_eligible=family in ('mild','severe')))
    return result


def measured(root,p,out):
    base=root/'09_Simulation/traces/g6_eth';manifest=json.loads((base/'source_manifest.json').read_text())
    path=root/manifest['local_hdf5']
    if sha(path)!=manifest['expected_sha256']:raise ValueError('ETH full member hash')
    result=[];windows=[]
    with h5py.File(path,'r') as f:
        g=f['dataset'];columns=[b.decode() for b in g['axis0'][:]];times=g['axis1'];values=g['block0_values']
        # Deliberately index-based, not power/performance-based window selection.
        starts=np.linspace(0,len(times)-180,p['real_trace_windows'],dtype=int)
        for number,start in enumerate(starts):
            start=int(start)
            for skipped in range(10000):
                timestamps=times[start:start+180];raw=values[start:start+180]
                t=(timestamps-timestamps[0])/1e9
                valid=np.isfinite(raw[:,:4]).all() and np.all(np.diff(t)>0) and np.max(np.diff(t))<1.1 and t[-1]>=p['real_trace_horizon_s']
                if valid:break
                start+=180
            else:raise ValueError('no valid native solar window near predefined start')
            count=int(np.searchsorted(t,p['real_trace_horizon_s'],side='left'))
            t=t[:count];raw=raw[:count];timestamps=timestamps[:count]
            # Official processing_python.ipynb defines P_in = -I_in * V_in.
            pin=-raw[:,columns.index('I_in')]*raw[:,columns.index('V_in')]
            rail=np.maximum(0,pin)*p['real_trace_efficiency']
            day=str(np.datetime64(int(timestamps[0]),'ns')).split('T')[0]
            win=dict(window=number,index_start=start,skipped_invalid_blocks=skipped,
                timestamp_start_ns=int(timestamps[0]),native_dt_s=float(np.median(np.diff(t))),
                original_negative_power_samples=int(np.count_nonzero(pin<0)),samples=len(t),
                columns=columns,measured_power_mean_w=float(pin.mean()),
                rail_transfer='max(0,-I_in*V_in)*0.70; converter efficiency assumed; no amplitude normalization or time compression',
                day=day,source_sha256=manifest['expected_sha256'])
            np.savez_compressed(out/f'eth_window_{number}.npz',timestamp_ns=timestamps,t_s=t,measurements=raw,p_in_w=pin,assumed_rail_w=rail)
            windows.append(win)
            for capidx,cap in enumerate(p['capacities_j']):
                result.append(dict(id=f'eth_{number}_cap{capidx}',seed=360000+number*100+capidx,
                    family=f'eth_day_{day}',cluster_id=day,source_kind='eth_measured_derived_rail',
                    capacity_j=cap,trace=np.stack([t,rail],axis=1).tolist(),horizon_s=p['real_trace_horizon_s'],
                    arrivals_s=p['real_trace_arrivals_s'],deadline_interval_s=40.0,ci_eligible=False,window=number))
    dump(out/'eth_windows.json',dict(attribution=manifest['attribution'],record=manifest['record'],license=manifest['license'],
        scope='measured panel input power with assumed 70% transfer to simulated capacitor rail; fixed-MPPT measurement, not a validated load-dependent harvester I-V model',
        windows=windows))
    return result


def assign_inputs(scenarios,pools):
    for s in scenarios:
        s['input_ids']={}
        for name,pool in pools.items():
            rng=random.Random(s['seed']+(0 if name=='kws' else 1))
            s['input_ids'][name]=[rng.choice(pool)['id'] for _ in s['arrivals_s']]
    return scenarios
