"""G3 descriptors from checksummed G2 tensors, with fixed workload coverage."""
from dataclasses import dataclass
import hashlib
import itertools
import json
from pathlib import Path
import numpy as np
from .integer import depthwise, pointwise
from .simulator import Policy
from .storage import PAYLOAD_START


def sha(data):
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class Mapping:
    h: int
    w: int
    co: int
    ci: int
    save_z: bool
    keep_ps: bool

    @property
    def name(self):
        return f'h{self.h}w{self.w}_co{self.co}_ci{self.ci}_z{int(self.save_z)}ps{int(self.keep_ps)}'

    @property
    def policy(self):
        return Policy(self.save_z,self.keep_ps,self.ci)


def mappings(protocol):
    return [Mapping(h,w,co,ci,z,ps) for (h,w),co,ci,z,ps in itertools.product(
        protocol['spatial_tiles'],protocol['co_tiles'],protocol['ci_chunks'],protocol['save_z'],protocol['keep_ps'])]


def build_descriptors(root, destination, protocol):
    reference=root/'10_Experiments/g2/reference'
    hashes=json.loads((reference/'artifact_hashes.json').read_text())
    for name,expected in hashes.items():
        if sha((reference/name).read_bytes())!=expected:
            raise ValueError('G2 golden checksum mismatch: '+name)
    ds=json.loads((reference/'microtile.json').read_text())['dw']
    report=json.loads((reference/'reference_report.json').read_text())
    with np.load(reference/'official_sample.npz',allow_pickle=False) as a:
        data={k:a['pair0_'+k].copy() for k in ('x','wd','bd','wp','bp','z','y')}
    # G2 exports only the first 4 PW scales in microtile.json. All per-channel
    # multipliers must be reconstructed from the pinned model for CO expansion.
    params=destination/'pair0_quantization.json'
    if not params.exists():
        raise ValueError('run export_g3_quantization.py first')
    ps=json.loads(params.read_text())
    if ps['model_hash']!=report['model_sha256']:
        raise ValueError('quantization/model mismatch')
    pw=ps['pw']
    y0,y1=protocol['workload']['y'];x0,x1=protocol['workload']['x'];c0,c1=protocol['workload']['co']
    expected=data['y'][:,y0:y1,x0:x1,c0:c1].copy()
    np.save(destination/'expected_output.npy',expected,allow_pickle=False)
    catalog={}
    for (h,w),co in itertools.product(protocol['spatial_tiles'],protocol['co_tiles']):
        key=f'h{h}w{w}_co{co}'
        jobs=[]
        coverage=np.zeros_like(expected,dtype=np.int32)
        for y in range(y0,y1,h):
            for x in range(x0,x1,w):
                hh,ww=min(h,y1-y),min(w,x1-x)
                for c in range(c0,c1,co):
                    cc=min(co,c1-c)
                    desc=dict(y=y,x=x,h=hh,w=ww,co_start=c,co_count=cc,ci=64,padding='VALID',halo=1)
                    descriptor=sha(json.dumps(desc,sort_keys=True).encode())
                    arrays=dict(x=data['x'][:,y-1:y+hh+1,x-1:x+ww+1,:].copy(),wd=data['wd'],bd=data['bd'],
                                wp=data['wp'][:,c:c+cc].copy(),bp=data['bp'][c:c+cc].copy(),
                                z=data['z'][:,y:y+hh,x:x+ww,:].copy(),y=data['y'][:,y:y+hh,x:x+ww,c:c+cc].copy())
                    pws=dict(pw,multipliers=pw['multipliers'][c:c+cc],shifts=pw['shifts'][c:c+cc])
                    np.testing.assert_array_equal(depthwise(arrays['x'],arrays['wd'],arrays['bd'],ds),arrays['z'])
                    np.testing.assert_array_equal(pointwise(arrays['z'],arrays['wp'],arrays['bp'],pws),arrays['y'])
                    path=destination/(descriptor+'.npz')
                    np.savez_compressed(path,**arrays)
                    identity=dict(model_hash=report['model_sha256'],input_id=sha(arrays['x'].tobytes()),
                                  descriptor_id=descriptor,arithmetic_id='int8_int32_gemmlowp_double_v1',layout_id='NHWC_KH_KW_C_CI_CO_v1')
                    path.with_suffix('.json').write_text(json.dumps(dict(identity=identity,dw=ds,pw=pws,descriptor=desc),indent=2)+'\n')
                    z_bytes=arrays['z'].nbytes;ps_bytes=arrays['y'].size*4
                    slot=((PAYLOAD_START+max(z_bytes+ps_bytes,arrays['y'].nbytes)+255)//256)*256
                    jobs.append(dict(path=path.name,descriptor=desc,slot_bytes=slot,
                                     immutable_bytes=sum(arrays[k].nbytes for k in ('x','wd','bd','wp','bp')),
                                     spatial_key=sha(arrays['x'].tobytes()+arrays['wd'].tobytes()+arrays['bd'].tobytes())))
                    coverage[:,y-y0:y-y0+hh,x-x0:x-x0+ww,c-c0:c-c0+cc]+=1
        if not np.all(coverage==1):
            raise AssertionError('descriptor coverage not exact')
        # Full model blob retained as conservative extra reservation, even though
        # immutable weight/anchor copies for each descriptor are also counted.
        reserved=report['model_file_bytes']+sum(j['immutable_bytes']+2*j['slot_bytes']+128+1 for j in jobs)
        catalog[key]=dict(jobs=jobs,nvm_reserved_bytes=reserved,output_elements=int(expected.size))
    result=dict(workload=protocol['workload'],model_hash=report['model_sha256'],
                expected_output_sha256=sha(expected.tobytes()),catalog=catalog,descriptor_count=len(list(destination.glob('*.npz'))))
    (destination/'catalog.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
