"""Convert the reviewable English manuscript into an IEEEtran source file."""
from pathlib import Path
import json
import re

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def esc(s):
    mapping={'\\':r'\textbackslash{}','&':r'\&','%':r'\%','$':r'\$','#':r'\#','_':r'\_',
             '{':r'\{','}':r'\}','~':r'\textasciitilde{}','^':r'\textasciicircum{}'}
    return ''.join(mapping.get(c,c) for c in s)

def main():
    text=(HERE/'manuscript.md').read_text(encoding='utf-8')
    title=text.splitlines()[0][2:]
    sections=re.split(r'^## (.+)\n',text,flags=re.M)
    tex=[r'\RequirePackage[T1]{fontenc}',r'\documentclass[journal,10pt]{IEEEtran}',
         r'\usepackage[paperwidth=7.875in,paperheight=10.75in,left=0.5in,right=0.5in,top=0.6in,bottom=0.65in]{geometry}',
         r'\usepackage{graphicx,url,amsmath,mathptmx}',r'\usepackage[hidelinks]{hyperref}',
         r'\hyphenation{inter-mit-tent depth-wise point-wise}',
         r'\begin{document}',r'\title{'+esc(title)+'}',
         r'\author{Working draft for internal review --- October 16, 2026}',
         r'\maketitle',r'\special{papersize=7.875in,10.75in}',
         r'\markboth{RECAP-CIM: Simulation Study --- Not Approved for Submission}{Working Draft}']
    figures={
      'architecture':('fig1_architecture','Implemented evaluation boundary. Graph execution is simulated; G4 validates scalar/controller RTL separately.'),
      'intervals':('fig3_intervals','Assumed energy reduction against each stage\'s adaptive control. Bars: paired-bootstrap 95% intervals. The dashed line is the 20% research target. Stages differ in scope and costs; this is not a controlled longitudinal experiment.')}
    for heading,body in zip(sections[1::2],sections[2::2]):
        body=body.strip()
        if heading=='Abstract':tex += [r'\begin{abstract}',esc(body),r'\end{abstract}'];continue
        if heading=='Index Terms':tex += [r'\begin{IEEEkeywords}',esc(body),r'\end{IEEEkeywords}'];continue
        tex.append((r'\section*{' if heading=='Acknowledgments' else r'\section{')+esc(heading)+'}')
        for paragraph in body.split('\n\n'):
            if paragraph==':::table main':tex.append(r'\input{g7/assets/main_table.tex}')
            elif paragraph.startswith(':::figure '):
                name,caption=figures[paragraph.split()[-1]]
                tex += [r'\begin{figure}[t]\centering',r'\includegraphics[width=\columnwidth]{g7/assets/'+name+'.pdf}',
                        r'\caption{'+esc(caption)+r'}\end{figure}']
            else:tex += [esc(paragraph.replace('\n',' ')),'']
    tex += [r'\begin{thebibliography}{9}']
    for r in json.loads((HERE/'references.json').read_text(encoding='utf-8')):
        tex += [r'\bibitem{'+r['key']+'} '+esc(r['text'])]
    tex += [r'\end{thebibliography}',r'\end{document}','']
    (HERE/'manuscript.tex').write_text('\n'.join(tex),encoding='utf-8')
    # Original active path is now an entry point, with its legacy content backed up.
    (ROOT/'07_IEEE_Paper/imc_tinyml_ieee_paper.tex').write_text(
        '% G7 active evidence-scoped draft; compile from 07_IEEE_Paper.\n'
        '% Legacy manuscript preserved in _backups/G7_before_review_2026-10-16/.\n'
        '\\input{g7/manuscript.tex}\n',encoding='utf-8')
    print('Generated IEEEtran source from manuscript.md; author identities remain required.')

if __name__=='__main__':main()
