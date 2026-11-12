"""Mechanical consistency checks for the manuscript and selected evidence."""
from pathlib import Path
import csv
import json
import re
import sys
from PIL import Image

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def main():
    sys.path.append(str(ROOT/'tmp/g7_python'))
    import pymupdf
    paper=(HERE/'manuscript.md').read_text(encoding='utf-8')
    refs=json.loads((HERE/'references.json').read_text())
    citations=[int(a) for a in re.findall(r'\[(\d+)\]',paper)]
    assert set(citations)==set(range(1,len(refs)+1))
    assert len({a['key'] for a in refs})==len(refs)==9
    assert paper.startswith('# '+json.loads((HERE/'submission_metadata.json').read_text())['title'])
    for fact in ['1.368%','99 versus 98 of 120','1,882','1,794,096','481','174','97.76%',
                 '3/2000','178/2000','All energy and timing coefficients are assumed']:
        assert fact in paper,'Missing audited statement: '+fact
    rows={}
    for name,count in [('table1_main',16),('table2_ablations',20),('table3_sensitivity',36)]:
        with (HERE/'assets'/f'{name}.csv').open(encoding='utf-8',newline='') as f:data=list(csv.DictReader(f))
        assert len(data)==count;rows[name]=count
    for p in (HERE/'assets').glob('fig*.png'):
        with Image.open(p) as im:
            assert im.width in [1050,2148] and im.height>500
            assert max(im.convert('L').getextrema())>min(im.convert('L').getextrema())
    images=len(list((HERE/'assets').glob('fig*.svg')));assert images==6
    d=pymupdf.open(ROOT/'output/pdf/recap_cim_g7.pdf');assert len(d)<=4
    txt='\n'.join(p.get_text() for p in d)
    assert 'Acknowledgments'.lower() in txt.lower() and 'Codex' in txt and '[9]' in txt
    for p in d:
        assert list(p.rect)==[0,0,567,774]
        for font in p.get_fonts():assert d.extract_font(font[0])[3]
    metadata=json.loads((HERE/'submission_metadata.json').read_text())
    assert not metadata['submission_ready'] and not metadata['all_authors_approved'] and metadata['authors'] is None
    report={'status':'PASS_PAPER_CONSISTENCY','references':len(refs),'table_rows':rows,
            'figures':images,'pdf_pages':len(d),'all_fonts_embedded':True,
            'submission_ready':False,'scope':'Mechanical/source consistency only; not a scientific or editorial acceptance certificate.'}
    (HERE/'paper_checks.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
