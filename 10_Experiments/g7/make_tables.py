"""Build corrected G7 assets from frozen JSON schemas."""
from pathlib import Path
import runpy

if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).resolve().parents[2] / "07_IEEE_Paper/g7/build_assets.py"), run_name="__main__")
