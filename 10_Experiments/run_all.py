"""Read-only evidence audit. This does not rerun G2-G6 or overwrite frozen results. See 07_IEEE_Paper/g7/README.md."""
from pathlib import Path
import runpy
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-only", action="store_true", help="Explicit alias for the default read-only audit")
    parser.parse_args()
    runpy.run_path(str(Path(__file__).resolve().parents[1] / "07_IEEE_Paper/g7/verify_evidence.py"), run_name="__main__")
