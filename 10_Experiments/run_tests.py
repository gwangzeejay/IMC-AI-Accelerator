"""Execute every Python unit suite without regenerating frozen experiments."""
import argparse
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--g8-only',action='store_true');parser.add_argument('--g9-only',action='store_true');args=parser.parse_args()
    suites=['tests_g9'] if args.g9_only else ['tests_g8'] if args.g8_only else ['tests','tests_g3','tests_g4','tests_g5','tests_g6','tests_g8','tests_g9']
    for suite in suites:
        result=subprocess.run([sys.executable,'-m','unittest','discover','-s','09_Simulation/'+suite,'-v'],cwd=ROOT)
        if result.returncode:raise SystemExit(result.returncode)
    print('PASS: all requested Python suites executed. Frozen experiment outputs unchanged.',flush=True)

if __name__=='__main__':main()
