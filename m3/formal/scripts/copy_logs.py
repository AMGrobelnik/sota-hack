"""Copy this package's lab logs into results/ with the home path replaced by ~, then check m3/formal for home paths.

usage: python copy_logs.py <logs_dir>
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HOME = str(Path.home())
NAMES = ["formal-repro-spike", "formal-check-iprove", "formal-lab-golden-spike", "formal-lab-golden-fuse3",
         "formal-iprove", "formal-remeasure", "formal-setup2", "formal-recheck-b77cc76", "formal-setup3"]

for n in NAMES:
    (ROOT / "results" / f"{n}.log").write_text((Path(sys.argv[1]) / f"{n}.log").read_text().replace(HOME, "~"))
bad = [str(p.relative_to(ROOT)) for p in ROOT.rglob("*") if p.is_file() and "runs" not in p.parts
       and "__pycache__" not in p.parts and HOME in p.read_text(errors="replace")]
print("[copy_logs] home path still in:", bad) if bad else print("[copy_logs] clean")
