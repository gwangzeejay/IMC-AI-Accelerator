"""One read-only integrity command for original G2-G6 and current G8 evidence."""
import argparse
import json
from pathlib import Path
from audit_g8 import audit,sha

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--legacy-only',action='store_true')
    parser.add_argument('--run-id',default='20261023-v2')
    parser.add_argument('--rtl-run-id',default='rtl-20261023-v3')
    args=parser.parse_args();count=0
    for g in range(2,7):
        m=json.loads((ROOT/f'10_Experiments/manifests/g{g}_run.json').read_text())
        for name,digest in m['sha256'].items():
            if sha(ROOT/name)!=digest:raise AssertionError('Legacy mismatch: '+name)
            count+=1
    report=dict(status='PASS_PROJECT_INTEGRITY',legacy_hash_entries=count,fresh_execution=False,checker_sha256=sha(Path(__file__)))
    if not args.legacy_only:
        report['g8']=audit(args.run_id)
        out=ROOT/'10_Experiments/g8'/args.rtl_run_id
        rtl=json.loads((out/'rtl_report.json').read_text())
        for name,digest in rtl['source_sha256'].items():
            if sha(ROOT/name)!=digest:raise AssertionError('RTL source changed: '+name)
        for name,digest in rtl['artifact_sha256'].items():
            if sha(ROOT/name)!=digest:raise AssertionError('RTL artifact changed: '+name)
        if rtl['status']!='PASS_G8_OUTPUT_LOG_RTL':raise AssertionError('RTL did not pass')
        report['rtl']=dict(status=rtl['status'],reset_cut_cases=rtl['reset_cut_cases'],invalid_commands=rtl['invalid_commands'])
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
