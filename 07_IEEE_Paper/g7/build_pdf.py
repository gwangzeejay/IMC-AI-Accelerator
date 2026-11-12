"""Compile the IEEEtran letter, verify geometry/fonts, and render every page."""
from pathlib import Path
import argparse
import json
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tectonic',default=str(ROOT/'tmp/g7_tools/tectonic.exe'))
    args=parser.parse_args()
    for script in ['build_assets.py','render_source.py']:
        subprocess.run([sys.executable,str(HERE/script)],cwd=ROOT,check=True)
    build=ROOT/'tmp/pdfs';build.mkdir(parents=True,exist_ok=True)
    exe=shutil.which(args.tectonic) or args.tectonic
    process=subprocess.run([exe,'imc_tinyml_ieee_paper.tex','--outdir',str(build),
                            '--keep-logs','--keep-intermediates'],cwd=HERE.parent,
                           capture_output=True,text=True,encoding='utf-8',errors='replace')
    (HERE/'build_console.txt').write_text(process.stdout+process.stderr,encoding='utf-8')
    if process.returncode:
        print(process.stdout+process.stderr);raise SystemExit(process.returncode)
    log=(build/'imc_tinyml_ieee_paper.log').read_text(encoding='utf-8',errors='replace')
    assert 'Overfull' not in log,'Fix overfull boxes before delivering'
    assert 'undefined' not in log.lower(),'Resolve undefined references or fonts'
    assert 'defaults substituted' not in log.lower(),'Resolve font substitution'
    sys.path.append(str(ROOT/'tmp/g7_python'))
    import pymupdf
    source=build/'imc_tinyml_ieee_paper.pdf';doc=pymupdf.open(source)
    assert len(doc)<=4,'ESL page limit exceeded'
    render=build/'g7_review';render.mkdir(exist_ok=True)
    pages=[]
    for i,page in enumerate(doc):
        assert abs(page.rect.width-567)<.1 and abs(page.rect.height-774)<.1,'Incorrect trim'
        text=page.get_text();assert text.strip(),'Blank page'
        for font in page.get_fonts():
            assert doc.extract_font(font[0])[3], 'Unembedded PDF font'
        for block in page.get_text('dict')['blocks']:
            if block['type']!=0:continue
            x0,y0,x1,y1=block['bbox']
            assert x0>=0 and y0>=0 and x1<=567 and y1<=774,'Text outside media box'
        page.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5)).save(render/f'page_{i+1}.png')
        pages.append({'page':i+1,'width_pt':page.rect.width,'height_pt':page.rect.height,
                      'text_characters':len(text),'fonts':[x[3] for x in page.get_fonts()]})
    doc.close();out=ROOT/'output/pdf';out.mkdir(parents=True,exist_ok=True)
    dest=out/'recap_cim_g7.pdf';shutil.copy2(source,dest)
    report={'status':'PASS_MECHANICAL_PDF_CHECKS','pages':pages,'page_count':len(pages),
            'format':'IEEEtran journal, 10pt, Times-compatible fonts, 7.875 x10.75 inch trim',
            'visual_review':'Required separately on rendered pages; this script does not certify visual inspection.',
            'submission_ready':False,'output':dest.relative_to(ROOT).as_posix()}
    (HERE/'pdf_checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print('PDF built:',dest.relative_to(ROOT),'; pages:',len(pages),'; rendered pages:',render.relative_to(ROOT))

if __name__=='__main__':main()
