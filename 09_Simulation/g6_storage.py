"""General graph liveness and G4 binary-v1 persistence for two real models."""
import hashlib
import json
import struct
import numpy as np
from g4_reference import HEADER,MARKER,encode,decode
from g5_storage import Store as G5Store,digest


def geometry(p,d,f):
    if d['kind']=='head':return [(1,d['co'])]
    choices=[]
    for n,co in p['tiles']:
        co=min(co,d['co']);remaining=d['co']-f%d['co']
        if co>remaining or (f%d['co'] and n!=1):continue
        n=min(n,d['pixels']-f//d['co'])
        if co!=d['co']:n=1  # Each job is a contiguous NHWC output range.
        if (n,co) not in choices:choices.append((n,co))
    return choices


class Store(G5Store):
    def __init__(self,model,x,p,invocation='',all_live=False):
        self.model=model;self.p=p;self.ids=(bytes.fromhex(model.model_hash),digest(x.tobytes()+invocation.encode()))
        self.graph_hash=digest(json.dumps(model.stages,sort_keys=True).encode()).hex()
        self.log_bytes=max(d['size']+HEADER*d['pixels']*((d['co']+min(16,d['co'])-1)//min(16,d['co'])) for d in model.stages)
        self.scratch_bytes=p['scratch_slot_bytes'];self.root_bytes=p['root_slot_bytes']
        self.scratch_base=2*self.log_bytes;self.root_base=self.scratch_base+2*self.scratch_bytes+1
        self.aux_base=self.root_base+2*self.root_bytes+1;self.aux_slot=p['all_live_slot_bytes'] if all_live else 0
        self.memory=bytearray(self.aux_base+2*self.aux_slot)
        self.reserved_bytes=len(self.memory)+len(model.blob)+x.nbytes+4096
        if self.reserved_bytes>p['nvm_bytes']:raise ValueError('NVM capacity')
        self.x=x.copy()

    def tile_id(self,stage,f,n,co):return self.identity('g6_tile',graph=self.graph_hash,stage=stage,frontier=f,pixels=n,co=co)
    def root_id(self):return self.identity('g6_root',graph=self.graph_hash)
    def scratch(self,stage,f,n,co):
        d=self.model.stages[stage];ci=d['ci'];data=self.memory[self.scratch_base:self.root_base]
        records=[decode(data,s,self.scratch_bytes,self.tile_id(stage,f,n,co),n*ci,n*co*4,n*co,channels=ci) for s in (0,1)]
        return max((r for r in records if r is not None),key=lambda r:r['generation'],default=None)
    def scan(self,stage):
        d=self.model.stages[stage];size=d['size'];flat=np.zeros(size,dtype=np.int8)
        f=offset=records=0;base=stage%2*self.log_bytes
        while f<size:
            h=self.memory[base+offset:base+offset+HEADER]
            if len(h)!=HEADER or h[0]!=MARKER:break
            outlen=struct.unpack_from('<H',h,112)[0];found=None
            for n,co in geometry(self.p,d,f):
                length=n*co
                if outlen!=length or f+length>size:continue
                r=decode(self.memory[base+offset:base+offset+HEADER+length],0,HEADER+length,
                    self.tile_id(stage,f,n,co),n*d['ci'],n*co*4,length,channels=d['ci'])
                if r is not None:found=(r,length);break
            if found is None:break
            r,length=found;flat[f:f+length]=np.frombuffer(r['output'],dtype=np.int8)
            f+=length;offset+=HEADER+length;records+=1
        return dict(array=flat,frontier=f,offset=offset,records=records,read_bytes=offset+(HEADER if f<size else 0))
    def log_ops(self,stage,f,n,co,offset,out):
        h,b=encode(self.tile_id(stage,f,n,co),1,self.model.stages[stage]['ci'],output=out)
        if offset+len(h)+len(b)>self.log_bytes:raise ValueError('log capacity')
        return self.transactions(stage%2*self.log_bytes+offset,h,b),len(b)
    def restore(self):
        root=self.root();done=self.stage();last=len(self.model.stages)-1
        if done>last:raise ValueError('invalid graph root stage')
        source=self.x.copy() if done<0 else self.scan(done)['array']
        if done>=0:
            r=self.scan(done)
            if r['frontier']!=len(source) or digest(source.tobytes())!=root['output'][4:36]:raise ValueError('root/source integrity')
            source=source.reshape(self.model.stages[done]['outshape'])
        return done,source,None if done==last else self.scan(done+1)
    def aux_ops(self,stage,f,prefix,contents,generation):
        if not self.aux_slot:raise ValueError('no all-live allocation')
        if HEADER+len(contents)>self.aux_slot:raise ValueError('all-live slot capacity')
        identity=self.identity('g6_redundant_live_buffers',stage=stage,frontier=f,prefix=prefix)
        h,b=encode(identity,generation,0,z=contents)
        return self.transactions(self.aux_base+(generation%2)*self.aux_slot,h,b),len(b)
