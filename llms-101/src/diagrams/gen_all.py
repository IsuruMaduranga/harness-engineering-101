#!/usr/bin/env python3
"""Regenerate every quantitative figure. Run from this directory."""
import subprocess, sys
for script in ["gen_loss_curve.py", "gen_attention_heatmap.py"]:
    subprocess.run([sys.executable, script], check=True)
