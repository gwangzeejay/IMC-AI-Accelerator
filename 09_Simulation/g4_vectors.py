"""Finite arithmetic checks: real DW/PW dot products and seeded edge cases."""
from pathlib import Path
import json
import random
import numpy as np
from recap.integer import multiply_quantized,quantize_multiplier


def arithmetic_vectors(root,configs):
    out=root/'10_Experiments/g4/vectors';rng=random.Random(82400)
    mac=[];quant=[]
    for cfg in configs.values():
        with np.load(root/cfg['source'],allow_pickle=False) as f:a={k:f[k].copy() for k in f.files}
        for p in range(a['z'].shape[1]*a['z'].shape[2]):
            yy,xx=divmod(p,a['z'].shape[2])
            for c in range(64):
                acts=a['x'][0,yy:yy+3,xx:xx+3,c].reshape(-1)
                weights=a['wd'][:,:,c].reshape(-1)
                bias=int(a['bd'][c]);zp=cfg['dw']['input_zero_point']
                acc=bias+sum((int(x)-zp)*int(w) for x,w in zip(acts,weights))
                mac.append((9,bias,zp,acc,0,list(zip(map(int,acts),map(int,weights)))))
                quant.append((acc,cfg['dw']['multipliers'][c],cfg['dw']['shifts'][c],cfg['dw']['output_zero_point'],cfg['dw']['activation_min'],cfg['dw']['activation_max'],int(a['z'].reshape(-1,64)[p,c]),0))
            for c in range(a['wp'].shape[1]):
                acts=a['z'].reshape(-1,64)[p];weights=a['wp'][:,c];bias=int(a['bp'][c]);zp=cfg['pw']['input_zero_point']
                acc=bias+sum((int(x)-zp)*int(w) for x,w in zip(acts,weights))
                mac.append((64,bias,zp,acc,0,list(zip(map(int,acts),map(int,weights)))))
                quant.append((acc,cfg['pw']['multipliers'][c],cfg['pw']['shifts'][c],cfg['pw']['output_zero_point'],cfg['pw']['activation_min'],cfg['pw']['activation_max'],int(a['y'].reshape(-1,a['wp'].shape[1])[p,c]),0))
    for n in (1,2,9,16,64,255,256):
        for _ in range(30):
            zp=rng.choice([-128,-9,0,83,127]);bias=rng.randrange(-1000000,1000000)
            pairs=[(rng.randrange(-128,128),rng.randrange(-128,128)) for _ in range(n)]
            acc=bias+sum((x-zp)*w for x,w in pairs);mac.append((n,bias,zp,acc,0,pairs))
    mac.extend([(256,0,-128,256*255*127,0,[(127,127)]*256),
                (1,2147483647,-128,0,1,[(127,127)]),(1,-2147483648,127,0,1,[(-128,127)]),
                (0,0,0,0,1,[]),(257,0,0,0,1,[(0,0)]*257)])
    for _ in range(5000):
        acc=rng.randrange(-(1<<31),1<<31);m,shift=quantize_multiplier(10**rng.uniform(-7,.7))
        zp=rng.choice([-128,-17,0,83,127]);lo=-128;hi=127
        try:
            val=multiply_quantized(acc,m,shift)+zp;expected=max(lo,min(hi,val));error=0
        except OverflowError:expected=0;error=1
        quant.append((acc,m,shift,zp,lo,hi,expected,error))
    for acc in (-(1<<31),-3,-1,0,1,3,(1<<31)-1):
        for shift in (-31,-1,0,1,30):
            try:expected=max(-128,min(127,multiply_quantized(acc,1<<30,shift)));error=0
            except OverflowError:expected=0;error=1
            quant.append((acc,1<<30,shift,0,-128,127,expected,error))
    quant.append((-(1<<31),-(1<<31),0,0,-128,127,127,0))
    with (out/'mac.txt').open('w') as f:
        for n,b,z,e,err,pairs in mac:
            f.write(f'{n} {b} {z} {e} {err}\n')
            for x,w in pairs:f.write(f'{x} {w}\n')
    (out/'requant.txt').write_text(''.join(' '.join(map(str,row))+'\n' for row in quant))
    report=dict(mac_cases=len(mac),requant_cases=len(quant),seed=82400,includes_real_model_dot_products=True,
                includes_256_terms=True,includes_overflow_and_invalid_length=True)
    (out/'arithmetic_manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
