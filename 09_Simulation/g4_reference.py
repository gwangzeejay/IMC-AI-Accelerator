"""Independent binary-v1 codec/transaction oracle and model-backed RTL vectors."""
import hashlib
import json
from pathlib import Path
import struct
import zlib
import numpy as np

HEADER=124
MARKER=0xa5


def identity_bytes(identity):
    descriptor=hashlib.sha256(json.dumps({k:identity[k] for k in ('descriptor_id','arithmetic_id','layout_id')},sort_keys=True).encode()).digest()
    return bytes.fromhex(identity['model_hash']),bytes.fromhex(identity['input_id']),descriptor


def encode(identity,generation,offset,z=None,ps=None,output=None):
    flags=int(z is not None)+2*int(ps is not None)+4*int(output is not None)
    parts=[b'' if a is None else bytes(a) for a in (z,ps,output)]
    payload=b''.join(parts)
    h=bytearray(HEADER);h[0]=MARKER;h[1]=1;h[2]=flags
    struct.pack_into('<I',h,4,generation)
    h[8:40],h[40:72],h[72:104]=identity
    struct.pack_into('<IHHHHI',h,104,offset,*map(len,parts),0,zlib.crc32(payload))
    struct.pack_into('<I',h,120,zlib.crc32(h[1:120]))
    return bytes(h),payload


def decode(memory,slot,slot_bytes,identity,z_bytes,ps_bytes,out_bytes,channels=64):
    start=slot*slot_bytes;h=bytes(memory[start:start+HEADER])
    if len(h)!=HEADER or h[0]!=MARKER or h[1]!=1 or h[2]>7 or h[3]!=0:return None
    if (h[8:40],h[40:72],h[72:104])!=identity:return None
    flags=h[2];gen=struct.unpack_from('<I',h,4)[0]
    offset,zlen,plen,olen,reserved,crc=struct.unpack_from('<IHHHHI',h,104)
    if not gen or reserved or offset>channels or [zlen,plen,olen]!=[z_bytes if flags&1 else 0,ps_bytes if flags&2 else 0,out_bytes if flags&4 else 0]:return None
    if flags&4 and (flags!=4 or offset!=channels):return None
    if not flags&6 and offset:return None
    if HEADER+zlen+plen+olen>slot_bytes:return None
    if zlib.crc32(h[1:120])!=struct.unpack_from('<I',h,120)[0]:return None
    payload=bytes(memory[start+HEADER:start+HEADER+zlen+plen+olen])
    if zlib.crc32(payload)!=crc:return None
    return dict(slot=slot,generation=gen,offset=offset,flags=flags,z=payload[:zlen] if zlen else None,
                ps=payload[zlen:zlen+plen] if plen else None,output=payload[zlen+plen:] if olen else None,payload=payload)


def latest(memory,config):
    records=[decode(memory,s,config['slot_bytes'],tuple(bytes.fromhex(x) for x in config['identity']),
                    config['z_bytes'],config['ps_bytes'],config['out_bytes']) for s in (0,1)]
    return max((r for r in records if r is not None),key=lambda r:r['generation'],default=None)


def commit_transactions(memory,config,save,keep,final,prefix,arrays):
    old=latest(memory,config)
    z=arrays['z'] if save else old['z'] if old else None
    ps=arrays['ps'][prefix] if keep else old['ps'] if old else None
    offset=prefix if keep else old['offset'] if old else 0
    if final:z=ps=None;offset=64
    slot=1-old['slot'] if old else 0
    gen=old['generation']+1 if old else 1
    h,payload=encode(tuple(bytes.fromhex(x) for x in config['identity']),gen,offset,z,ps,arrays['output'] if final else None)
    base=slot*config['slot_bytes']
    ops=[('W',base,0)]
    ops += [('W',base+HEADER+i,v) for i,v in enumerate(payload)]
    ops += [('W',base+i,h[i]) for i in range(1,HEADER)]
    ops += [('W',base,MARKER)]
    if final:ops.append(('W',2*config['slot_bytes'],1))
    return ops,len(payload)


def export_vectors(root):
    from recap.integer import depthwise,pointwise,pw_accumulate
    base=root/'10_Experiments/g4/vectors';base.mkdir(parents=True,exist_ok=True)
    catalog=json.loads((root/'10_Experiments/g3/descriptors/catalog.json').read_text())
    sources={'g2_micro':root/'10_Experiments/g2/reference/microtile.npz',
             'g3_selected_tile':root/'10_Experiments/g3/descriptors'/catalog['catalog']['h1w2_co16']['jobs'][0]['path']}
    configs={}
    def hexfile(path,array,bits):
        mask=(1<<bits)-1
        path.write_text(''.join(f'{int(v)&mask:0{bits//4}x}\n' for v in np.asarray(array).reshape(-1)))
    for name,source in sources.items():
        with np.load(source,allow_pickle=False) as f: arrays={k:f[k].copy() for k in f.files}
        spec=json.loads(source.with_suffix('.json').read_text())
        np.testing.assert_array_equal(depthwise(arrays['x'],arrays['wd'],arrays['bd'],spec['dw']),arrays['z'])
        np.testing.assert_array_equal(pointwise(arrays['z'],arrays['wp'],arrays['bp'],spec['pw']),arrays['y'])
        d=base/name;d.mkdir(exist_ok=True)
        for k in ('x','wd','wp','z','y'):hexfile(d/(k+'.hex'),arrays[k],8)
        for k in ('bd','bp'):hexfile(d/(k+'.hex'),arrays[k],32)
        for prefix,q in [('dw',spec['dw']),('pw',spec['pw'])]:
            for field in ('multipliers','shifts'):hexfile(d/(prefix+'_'+field+'.hex'),q[field],32)
        identity=identity_bytes(spec['identity']);ih,iw,ci=arrays['x'].shape[1:];_,oh,ow,_=arrays['z'].shape
        co=arrays['wp'].shape[1]
        config=dict(name=name,source=str(source.relative_to(root)).replace('\\','/'),identity=[x.hex() for x in identity],
                    slot_bytes=512,z_bytes=arrays['z'].nbytes,ps_bytes=arrays['y'].size*4,out_bytes=arrays['y'].nbytes,
                    ih=ih,iw=iw,oh=oh,ow=ow,ci=ci,co=co,dw=spec['dw'],pw=spec['pw'])
        (d/'config.json').write_text(json.dumps(config,indent=2)+'\n')
        lines=[f'localparam integer IH={ih},IW={iw},OH={oh},OW={ow},CI={ci},CO={co},PIXELS={oh*ow};',
               f'localparam integer ZB={config["z_bytes"]},PB={config["ps_bytes"]},OB={config["out_bytes"]},SLOT=512;',
               'localparam [255:0] MODEL_ID=256\'h'+identity[0][::-1].hex()+';',
               'localparam [255:0] INPUT_ID=256\'h'+identity[1][::-1].hex()+';',
               'localparam [255:0] DESCRIPTOR_ID=256\'h'+identity[2][::-1].hex()+';']
        for prefix,q in [('DW',spec['dw']),('PW',spec['pw'])]:
            for key in ('input_zero_point','output_zero_point','activation_min','activation_max'):
                lines.append(f'localparam integer {prefix}_{key.upper()}={q[key]};')
        lines.append('localparam VECTOR_DIR="10_Experiments/g4/vectors/'+name+'/";')
        (d/'params.vh').write_text('\n'.join(lines)+'\n')
        configs[name]=config
    return configs


def oracle_arrays(root,config):
    from recap.integer import pw_accumulate
    with np.load(root/config['source'],allow_pickle=False) as f:a={k:f[k].copy() for k in f.files}
    shape=a['y'].shape;ps=np.broadcast_to(a['bp'],shape).copy().astype(np.int32);prefixes={0:ps.astype('<i4').tobytes()}
    for ci in range(0,64,16):
        ps=pw_accumulate(a['z'],a['wp'],ps,ci,ci+16,config['pw']['input_zero_point'])
        prefixes[ci+16]=ps.astype('<i4').tobytes()
    return dict(z=a['z'].tobytes(),ps=prefixes,output=a['y'].tobytes())
