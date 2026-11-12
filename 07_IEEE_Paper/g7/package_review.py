"""Make a local source/review ZIP; no upload and no research-data redistribution."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    files=set(p for p in HERE.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.name!='package_manifest.json')
    patterns=['02_Research/G7_deliverables.md','02_Research/venue_*.md','02_Research/coverage_log.md',
              '02_Research/novelty_matrix.md','02_Research/references.bib',
              '10_Experiments/g3/summary.json','10_Experiments/g4/summary.json','10_Experiments/g5/summary.json',
              '10_Experiments/g6/results.json','10_Experiments/g6/accuracy.json','10_Experiments/g6/protocol_snapshot.json',
              '10_Experiments/g6_analysis/analysis.json','10_Experiments/g6/raw/*.jsonl',
              '10_Experiments/g7/cv_report.json','10_Experiments/g7/cv_report.md',
              '07_IEEE_Paper/imc_tinyml_ieee_paper.tex','output/pdf/recap_cim_g7.pdf']
    for pattern in patterns:files.update(p for p in ROOT.glob(pattern) if p.is_file())
    assert (ROOT/'output/pdf/recap_cim_g7.pdf') in files,'Build PDF first'
    manifest={'status':'LOCAL_REVIEW_PACKAGE_NOT_SUBMISSION','submission_ready':False,
              'scope':'Manuscript source, figures/tables, review documents and selected frozen evidence; '
                      'not a full model/data/tool artifact and not independently reviewed.',
              'sha256':{p.relative_to(ROOT).as_posix():sha(p) for p in sorted(files)}}
    dest=HERE/'package_manifest.json';dest.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    out=ROOT/'output/g7';out.mkdir(parents=True,exist_ok=True);archive=out/'recap_cim_g7_review_package.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(files|{dest}):z.write(p,p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name,digest in manifest['sha256'].items():assert hashlib.sha256(z.read(name)).hexdigest()==digest
    print('Verified local review ZIP:',archive.relative_to(ROOT),';',len(files)+1,'files; not submission-ready.')

if __name__=='__main__':main()
