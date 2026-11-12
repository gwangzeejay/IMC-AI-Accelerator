"""Two fixed copy-on-write slots containing actual bytes and integrity hashes.

One-byte marker publication is an explicit simulator assumption, NOT a
guarantee made for the candidate physical FRAM.
"""
import hashlib
import json
import struct
import numpy as np

META_BYTES=1024
PAYLOAD_START=37+META_BYTES
MARKER=0xA5


def digest(data):
    return hashlib.sha256(data).hexdigest()


class TwoSlotStore:
    def __init__(self, identity, slot_bytes=4096, capacity_bytes=262144, immutable_bytes=0):
        if slot_bytes <= PAYLOAD_START or 2*slot_bytes+immutable_bytes > capacity_bytes:
            raise ValueError('NVM capacity exceeded')
        self.identity=identity.copy()
        self.slot_bytes=slot_bytes
        self.slots=[bytearray(slot_bytes),bytearray(slot_bytes)]
        self.immutable_bytes=immutable_bytes
        self.capacity_bytes=capacity_bytes

    def encode(self, generation, offset, z, ps, output):
        payload=bytearray()
        arrays={}
        for name,array in [('z',z),('ps',ps),('output',output)]:
            if array is None:
                continue
            dtype='|i1' if name in ('z','output') else '<i4'
            value=np.asarray(array,dtype=dtype)
            raw=value.tobytes(order='C')
            arrays[name]=dict(offset=len(payload),bytes=len(raw),shape=list(value.shape),dtype=dtype)
            payload.extend(raw)
        record=dict(generation=generation,identity=self.identity,offset=offset,arrays=arrays,
                    payload_bytes=len(payload),sha256=digest(payload),output_committed=output is not None)
        meta=json.dumps(record,sort_keys=True,separators=(',',':')).encode('ascii')
        if len(meta)>META_BYTES or PAYLOAD_START+len(payload)>self.slot_bytes:
            raise ValueError('checkpoint does not fit fixed slot')
        header=struct.pack('<I',len(meta))+hashlib.sha256(meta).digest()+meta
        return record,bytes(payload),header

    def candidates(self):
        valid=[]
        for index,slot in enumerate(self.slots):
            if slot[0]!=MARKER:
                continue
            try:
                n=struct.unpack('<I',slot[1:5])[0]
                if not 0<n<=META_BYTES:
                    continue
                meta=bytes(slot[37:37+n])
                if hashlib.sha256(meta).digest()!=bytes(slot[5:37]):
                    continue
                record=json.loads(meta)
                if record['identity']!=self.identity or record['generation']<1:
                    continue
                size=record['payload_bytes']
                if not isinstance(size,int) or not 0<=size<=self.slot_bytes-PAYLOAD_START:
                    continue
                payload=bytes(slot[PAYLOAD_START:PAYLOAD_START+size])
                if digest(payload)!=record['sha256']:
                    continue
                valid.append((record['generation'],index,record))
            except (ValueError,TypeError,KeyError,UnicodeError,struct.error):
                continue
        return sorted(valid,reverse=True)

    def latest(self):
        valid=self.candidates()
        if not valid:
            return None,None
        _,slot,record=valid[0]
        return slot,record

    def payload(self, slot_index, record, name):
        ref=record['arrays'][name]
        start=PAYLOAD_START+ref['offset']
        raw=bytes(self.slots[slot_index][start:start+ref['bytes']])
        return np.frombuffer(raw,dtype=ref['dtype']).reshape(ref['shape']).copy()
