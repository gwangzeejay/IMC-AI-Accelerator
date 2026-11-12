"""Fresh same-host diagnostics. This is not cross-host or hardware calibration."""
from pathlib import Path
import runpy

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parents[2] / "07_IEEE_Paper/g7/validate_execution.py"), run_name="__main__")
