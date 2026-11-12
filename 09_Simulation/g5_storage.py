"""Bounded byte-addressed NVM; G4 binary-v1 slots plus immutable layer logs.

The graph-level log/root extension is software simulation, not G4 RTL proof.
Atomic byte, ACK persistence, CRC32 and no delayed write after reset are assumed.
"""
import hashlib
import json
import struct
import numpy as np
from g4_reference import HEADER, MARKER, encode, decode


def digest(data):
    return hashlib.sha256(data).digest()


class Store:
    def __init__(self, model_hash, x, protocol, invocation=''):
        # Repeated identical features are distinct arrivals, not cached completions.
        self.p=protocol;self.ids=(bytes.fromhex(model_hash),digest(x.tobytes()+invocation.encode()))
        self.log_bytes=protocol['layer_log_bytes'];self.scratch_bytes=protocol['scratch_slot_bytes']
        self.root_bytes=protocol['root_slot_bytes']
        self.scratch_base=2*self.log_bytes
        self.root_base=self.scratch_base+2*self.scratch_bytes+1
        self.memory=bytearray(self.root_base+2*self.root_bytes+1)
        # Model blob, immutable 490-byte feature input and descriptor/runtime reserve.
        self.reserved_bytes=len(self.memory)+53936+x.nbytes+4096
        if self.reserved_bytes>protocol['nvm_bytes']:raise ValueError('NVM capacity')
        self.x=x.copy()

    def identity(self,kind,**desc):
        return (*self.ids,digest(json.dumps(dict(kind=kind,**desc),sort_keys=True).encode()))

    def tile_id(self,stage,f,n,co):
        return self.identity('tile_v1',stage=stage,frontier=f,pixels=n,co=co,
            arithmetic='int8_int32_gemmlowp_double',layout='NHWC')

    def root_id(self):return self.identity('graph_root_v1')

    def root(self):
        data=self.memory[self.root_base:]
        records=[decode(data,s,self.root_bytes,self.root_id(),0,0,48,channels=1) for s in (0,1)]
        return max((r for r in records if r is not None),key=lambda r:r['generation'],default=None)

    def stage(self):
        r=self.root()
        return -1 if r is None else struct.unpack_from('<i',r['output'])[0]

    def scratch(self,stage,f,n,co):
        data=self.memory[self.scratch_base:self.root_base]
        identity=self.tile_id(stage,f,n,co)
        records=[decode(data,s,self.scratch_bytes,identity,n*64,n*co*4,n*co,channels=64) for s in (0,1)]
        return max((r for r in records if r is not None),key=lambda r:r['generation'],default=None)

    @staticmethod
    def transactions(base,h,payload,frontier=None):
        ops=[(base,0)]
        ops.extend((base+HEADER+i,v) for i,v in enumerate(payload))
        ops.extend((base+i,h[i]) for i in range(1,HEADER))
        ops.append((base,MARKER))
        if frontier is not None:ops.append((frontier,1))
        return ops

    def scratch_ops(self,stage,f,n,co,prefix,z=None,ps=None,out=None):
        old=self.scratch(stage,f,n,co);slot=1-old['slot'] if old else 0
        generation=1+old['generation'] if old else 1
        if generation>0xffffffff:raise ValueError('generation wrap')
        h,b=encode(self.tile_id(stage,f,n,co),generation,prefix,z,ps,out)
        if HEADER+len(b)>self.scratch_bytes:raise ValueError('scratch capacity')
        return self.transactions(self.scratch_base+slot*self.scratch_bytes,h,b,
            self.scratch_base+2*self.scratch_bytes if out is not None else None),len(b)

    def scan(self,stage):
        """Decode valid ordered output records. Missing/torn suffix is unfinished."""
        size=12 if stage==5 else 8000
        flat=np.zeros(size,dtype=np.int8);f=0;offset=0;records=0
        base=(stage%2)*self.log_bytes
        while f<size:
            h=self.memory[base+offset:base+offset+HEADER]
            if len(h)!=HEADER or h[0]!=MARKER:break
            outlen=struct.unpack_from('<H',h,112)[0]
            choices=[(1,12)] if stage==5 else self.p['tiles']
            found=None
            for n,co in choices:
                if stage!=5:
                    if f%64 and (n!=1 or co>64-f%64):continue
                    n=min(n,125-f//64)
                length=n*co
                if outlen!=length or f+length>size:continue
                identity=self.tile_id(stage,f,n,co)
                r=decode(self.memory[base+offset:base+offset+HEADER+length],0,HEADER+length,
                    identity,n*64,n*co*4,length,channels=64)
                if r is not None:found=(r,n,co,length);break
            if found is None:break
            r,n,co,length=found
            flat[f:f+length]=np.frombuffer(r['output'],dtype=np.int8)
            f+=length;offset+=HEADER+length;records+=1
        return dict(array=flat,frontier=f,offset=offset,records=records,
            read_bytes=offset+(HEADER if f<size else 0))

    def log_ops(self,stage,f,n,co,offset,out):
        h,b=encode(self.tile_id(stage,f,n,co),1,64,output=out)
        if offset+len(h)+len(b)>self.log_bytes:raise ValueError('layer log capacity')
        return self.transactions((stage%2)*self.log_bytes+offset,h,b),len(b)

    def root_ops(self,stage,output):
        old=self.root();slot=1-old['slot'] if old else 0
        payload=struct.pack('<i',stage)+digest(output)+b'\0'*12
        h,b=encode(self.root_id(),1+old['generation'] if old else 1,1,output=payload)
        return self.transactions(self.root_base+slot*self.root_bytes,h,b,
            self.root_base+2*self.root_bytes),len(b)

    def apply(self,ops,count=None):
        for address,value in ops if count is None else ops[:count]:
            self.memory[address]=value

    def restore(self):
        root=self.root();done=self.stage()
        source=self.x.copy() if done<0 else self.scan(done)['array']
        if done>=0:
            scan=self.scan(done)
            if scan['frontier']!=len(source) or digest(source.tobytes())!=root['output'][4:36]:
                raise ValueError('committed root/source integrity failure')
            if done<5:source=source.reshape(1,25,5,64)
        current=None if done==5 else self.scan(done+1)
        return done,source,current
