"""Pinned VWW/COCO subset and SHA-verified ETH solar member via HTTP Range."""
from concurrent.futures import ThreadPoolExecutor
import csv
import hashlib
import io
import json
from pathlib import Path
import urllib.request
from PIL import Image
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
COMMIT='4addd0fa08d216e20637637874e084895f289da4'
BASE=f'https://raw.githubusercontent.com/mlcommons/tiny/{COMMIT}/'


def fetch(url):return urllib.request.urlopen(url,timeout=120).read()
def sha(b):return hashlib.sha256(b).hexdigest()


def run():
    dest=ROOT/'05_Model_Training/reference_vww';dest.mkdir(exist_ok=True)
    source=dest/'source_manifest.json'
    if not source.exists():
        paths={'vww_96_int8.tflite':'benchmark/training/visual_wake_words/trained_models/vww_96_int8.tflite',
            'vww_inputs.cc':'benchmark/training/visual_wake_words/trained_models/vww/vww_inputs.cc',
            'vww_model.py':'benchmark/training/visual_wake_words/vww_model.py',
            'download_and_train_vww.sh':'benchmark/training/visual_wake_words/download_and_train_vww.sh','LICENSE.md':'LICENSE.md'}
        files={}
        for name,path in paths.items():
            b=fetch(BASE+path);(dest/name).write_bytes(b);files[name]=dict(url=BASE+path,bytes=len(b),sha256=sha(b))
        source.write_text(json.dumps(dict(commit=COMMIT,files=files),indent=2))
    for name,info in json.loads(source.read_text())['files'].items():
        if sha((dest/name).read_bytes())!=info['sha256']:raise ValueError('model/source hash')
    images=dest/'coco_subset';images.mkdir(exist_ok=True)
    labels_url=BASE+'benchmark/evaluation/datasets/vww01/y_labels.csv'
    labels=images/'official_y_labels.csv'
    if not labels.exists():labels.write_bytes(fetch(labels_url))
    rows=list(csv.reader(io.StringIO(labels.read_text())))
    selected=[]
    for label in ('0','1'):selected += [(name,int(lab)) for name,_,lab in rows if lab==label][:20]
    def image(item):
        name,label=item;image_id=Path(name).stem
        url=f'https://s3.amazonaws.com/images.cocodataset.org/val2014/COCO_val2014_{image_id}.jpg'
        path=images/(image_id+'.jpg')
        if not path.exists():path.write_bytes(fetch(url))
        b=path.read_bytes()
        with Image.open(io.BytesIO(b)) as im:
            x=np.asarray(im.convert('RGB').resize((96,96),Image.Resampling.BILINEAR),dtype=np.uint8)
        x=(x.astype(np.int16)-128).astype(np.int8).reshape(1,96,96,3)
        return dict(id=image_id,label=label,url=url,source_sha256=sha(b),feature_sha256=sha(x.tobytes())),x
    with ThreadPoolExecutor(max_workers=6) as ex:result=list(ex.map(image,selected))
    np.savez_compressed(images/'inputs.npz',x=np.concatenate([x for _,x in result]),labels=np.array([m['label'] for m,_ in result],dtype=np.int32))
    manifest=dict(label_url=labels_url,label_sha256=sha(labels.read_bytes()),selection='first 20 IDs per class in pinned official label file; chosen before G6 results',
        preprocessing='research preprocessing: Pillow RGB full-image resize BILINEAR to 96x96; uint8 minus 128; not official MLPerf performance inputs',
        license_note='COCO images retain source image rights; Apache MLCommons source license does not relicense photos',
        inputs_sha256=sha((images/'inputs.npz').read_bytes()),images=[m for m,_ in result])
    old=images/'manifest.json'
    if old.exists():
        prior=json.loads(old.read_text())
        if prior!=manifest:raise ValueError('VWW dataset provenance drift')
    old.write_text(json.dumps(manifest,indent=2)+'\n')
    print('VWW pinned model and 40 real labeled images verified',flush=True)
    trace=ROOT/'09_Simulation/traces/g6_eth';trace.mkdir(parents=True,exist_ok=True)
    member=dict(url='https://zenodo.org/api/records/3715472/files/2019_08_processed.tar/content',
        member='processed/pos16_power_relative.h5',offset=32322122240,size=179789688,
        expected_sha256='e781fdff077a340495a88c7351f423bea21ebf7d12359cd996377d1591d44b89')
    local=ROOT/'tmp/g6_sources/pos16_power_relative.h5'
    if not local.exists() or local.stat().st_size!=member['size']:
        local.parent.mkdir(parents=True,exist_ok=True);a=member['offset'];b=a+member['size']-1
        r=urllib.request.urlopen(urllib.request.Request(member['url'],headers={'Range':f'bytes={a}-{b}'}),timeout=120)
        if r.status!=206 or r.headers.get('Content-Range')!=f'bytes {a}-{b}/32501913600':raise ValueError('range mismatch')
        with local.open('wb') as f:
            while chunk:=r.read(1024*1024):f.write(chunk)
    if sha(local.read_bytes())!=member['expected_sha256']:raise ValueError('full member SHA-256 mismatch')
    for name in ('README.md','LICENSE','2019_08_processed.files.md','processing_python.ipynb'):
        path=trace/name
        if not path.exists():path.write_bytes(fetch('https://zenodo.org/api/records/3715472/files/'+name+'/content'))
    member.update(record='https://zenodo.org/records/3715472',attribution='Lukas Sigrist, Andres Gomez, Lothar Thiele; ETH Zurich; DATA 2019',
        license='CC BY 4.0',download='Only 179789688-byte member, not 32 GB archive; whole member SHA-256 verified',
        local_hdf5=local.relative_to(ROOT).as_posix())
    (trace/'source_manifest.json').write_text(json.dumps(member,indent=2)+'\n')
    print('ETH measured solar source member verified',flush=True)


if __name__=='__main__':run()
