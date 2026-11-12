"""Fetch pinned official EEMBC MFCC inputs; no training or synthetic labels."""
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
COMMIT = 'cf7c2f2634608a7c0ea7458ab7cb3379f2863424'
URL = f'https://codeload.github.com/eembc/energyrunner/zip/{COMMIT}'


def run():
    dest = ROOT/'05_Model_Training/reference_eembc'
    manifest = dest/'source_manifest.json'
    if manifest.exists():
        old = json.loads(manifest.read_text())
        for name, digest in old['sha256'].items():
            if hashlib.sha256((dest/name).read_bytes()).hexdigest() != digest:
                raise ValueError('dataset checksum mismatch: '+name)
        print('Verified existing pinned EEMBC dataset', flush=True)
        return
    blob = urllib.request.urlopen(URL, timeout=90).read()
    archive = zipfile.ZipFile(io.BytesIO(blob))
    dest.mkdir(parents=True, exist_ok=True)
    hashes = {}
    for member in archive.namelist():
        relative = member.split('/', 1)[-1]
        if relative.startswith('datasets/kws01/') and not member.endswith('/'):
            name = relative.split('/')[-1]
        elif relative in ('datasets/README.md', 'LICENSE', 'LICENSE.md', 'LICENSE.txt'):
            name = relative.replace('/', '_')
        else:
            continue
        data = archive.read(member)
        if name.endswith('.bin') and len(data) != 490:
            raise ValueError('unexpected MFCC length')
        (dest/name).write_bytes(data)
        hashes[name] = hashlib.sha256(data).hexdigest()
    if len(list(dest.glob('*.bin'))) != 1000:
        raise ValueError('expected exactly 1000 stimuli')
    manifest.write_text(json.dumps(dict(repository='https://github.com/eembc/energyrunner',
        commit=COMMIT, url=URL, archive_sha256=hashlib.sha256(blob).hexdigest(),
        source_path='datasets/kws01', feature_shape=[1,49,10,1], dtype='int8',
        scope='precomputed MFCC feature input; audio acquisition/preprocessing excluded',
        sha256=hashes), indent=2)+'\n')
    print(json.dumps(dict(files=len(hashes), inputs=1000, commit=COMMIT)), flush=True)


if __name__ == '__main__':
    run()
