"""New, deterministic VWW images disjoint from G6; pinned official labels.

Downloads 24 JPEGs into a NEW directory. Does not touch G2-G6 evidence.
COCO images retain original image rights; do not redistribute blindly.
"""
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]

def digest(data):return hashlib.sha256(data).hexdigest()

def run():
    old=ROOT/'05_Model_Training/reference_vww/coco_subset'
    prior=json.loads((old/'manifest.json').read_text())
    labels=(old/'official_y_labels.csv').read_bytes()
    if digest(labels)!=prior['label_sha256']:raise ValueError('pinned labels mismatch')
    used={a['id'] for a in prior['images']}
    rows=list(csv.reader(io.StringIO(labels.decode())))
    chosen=[]
    for label in (0,1):
        chosen += [(Path(name).stem,label) for name,_,lab in rows if int(lab)==label and Path(name).stem not in used][:12]
    if len(chosen)!=24:raise ValueError('not enough fresh image IDs')
    dest=ROOT/'05_Model_Training/g8_vww';dest.mkdir(exist_ok=True)
    def fetch(item):
        name,label=item;url=f'https://s3.amazonaws.com/images.cocodataset.org/val2014/COCO_val2014_{name}.jpg'
        path=dest/(name+'.jpg')
        if not path.exists():
            with urllib.request.urlopen(url,timeout=60) as response:b=response.read()
            with Image.open(io.BytesIO(b)) as im:im.verify()
            path.write_bytes(b)
        b=path.read_bytes()
        with Image.open(io.BytesIO(b)) as im:
            x=(np.asarray(im.convert('RGB').resize((96,96),Image.Resampling.BILINEAR),dtype=np.int16)-128).astype(np.int8)
        return dict(id=name,label=label,url=url,source_sha256=digest(b),feature_sha256=digest(x.tobytes())),x
    with ThreadPoolExecutor(max_workers=4) as pool:result=list(pool.map(fetch,chosen))
    meta=dict(version='G8_DATA_1',selection='First 12 unused official IDs per class, excluding every G6 image; first 2/class development, next 10/class holdout',
        label_sha256=digest(labels),label_url=prior['label_url'],preprocessing=prior['preprocessing'],license_note=prior['license_note'],
        images=[dict(m,split='development' if i%12<2 else 'holdout') for i,(m,_) in enumerate(result)])
    x=np.stack([a for _,a in result]);feature_hash=digest(x.tobytes());meta['tensor_sha256']=feature_hash
    path=dest/'manifest.json'
    if path.exists():
        if json.loads(path.read_text())!=meta:raise ValueError('G8 dataset changed; refusing overwrite')
    else:
        np.savez_compressed(dest/'inputs.npz',x=x)
        path.write_text(json.dumps(meta,indent=2)+'\n',encoding='utf-8')
    with np.load(dest/'inputs.npz') as data:
        if digest(data['x'].tobytes())!=feature_hash:raise ValueError('G8 tensor mismatch')
    print('G8: 24 fresh VWW images verified; 4 development, 20 holdout; no G6 overlap',flush=True)

if __name__=='__main__':run()
