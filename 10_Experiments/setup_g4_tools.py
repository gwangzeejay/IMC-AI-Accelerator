"""Fetch pinned OSS CAD Suite; extract only local Icarus/Yosys runtime files.

No installer, registry changes or global PATH edits. Network access required.
"""
import hashlib
import json
from pathlib import Path
import tarfile
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
TAG='2026-10-14'
ASSET='oss-cad-suite-windows-x64-20261014.tgz'


def setup():
    out=ROOT/'tmp/g4_tools';out.mkdir(parents=True,exist_ok=True)
    release=json.load(urllib.request.urlopen(f'https://api.github.com/repos/YosysHQ/oss-cad-suite-build/releases/tags/{TAG}',timeout=40))
    asset=next(a for a in release['assets'] if a['name']==ASSET)
    archive=out/ASSET
    if not archive.exists() or archive.stat().st_size!=asset['size']:
        with urllib.request.urlopen(asset['browser_download_url'],timeout=90) as response,archive.open('wb') as f:
            count=0;last=0
            while block:=response.read(1024*1024):
                f.write(block);count+=len(block)
                if count-last>=50*1024*1024:
                    print(f'Downloaded {count//1048576}/{asset["size"]//1048576} MiB',flush=True);last=count
    checksum=hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()
    expected=asset.get('digest')
    if archive.stat().st_size!=asset['size'] or expected and expected!='sha256:'+checksum:
        raise ValueError('tool archive integrity mismatch')
    selected=[]
    with tarfile.open(archive,'r:gz') as tar:
        for member in tar:
            name=member.name.replace('\\','/')
            pick=(name.startswith('oss-cad-suite/lib/ivl/') or name.startswith('oss-cad-suite/share/yosys/') or
                  name.startswith('oss-cad-suite/lib/') and name.endswith('.dll') or
                  name.startswith('oss-cad-suite/bin/') and (name.endswith('.dll') or name.rsplit('/',1)[-1] in
                      ('iverilog.exe','vvp.exe','yosys.exe','yosys-abc.exe','abc.exe')))
            if not pick or not member.isfile(): continue
            target=(out/name).resolve()
            if not target.is_relative_to(out.resolve()): raise ValueError('unsafe archive path')
            target.parent.mkdir(parents=True,exist_ok=True)
            source=tar.extractfile(member)
            with target.open('wb') as dest:
                while block:=source.read(1024*1024): dest.write(block)
            selected.append(name)
    manifest=dict(release_tag=TAG,release_url=release['html_url'],asset_url=asset['browser_download_url'],
                  bytes=asset['size'],sha256=checksum,published_digest=expected,extracted_files=selected,
                  installation_scope='workspace tmp/g4_tools only; no global PATH or registry changes')
    (out/'source_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(f'Extracted {len(selected)} files for Icarus/Yosys',flush=True)


if __name__=='__main__': setup()
