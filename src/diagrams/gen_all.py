#!/usr/bin/env python3
"""Regenerate every figure in this folder. Run from blogs/diagrams/."""
import subprocess
import sys
from pathlib import Path

here = Path(__file__).parent
for script in sorted(here.glob("gen_*.py")):
    if script.name == "gen_all.py":
        continue
    print(f"== {script.name}")
    subprocess.run([sys.executable, script.name], cwd=here, check=True)
print("done")
