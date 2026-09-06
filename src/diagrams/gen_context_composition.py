#!/usr/bin/env python3
"""Chapter 6 figure: what actually fills a coding agent's context window
in a long session (illustrative proportions).

Regenerate: python3 gen_context_composition.py
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Illustrative long-session composition, in thousands of tokens.
parts = [
    ("system prompt + tool schemas", 14, "#7d3c98"),
    ("memory files (CLAUDE.md etc.)", 4, "#2471a3"),
    ("user + assistant text", 16, "#229954"),
    ("model thinking", 14, "#d4ac0d"),
    ("tool results (files, command output, searches)", 92, "#c0392b"),
]
total = sum(v for _, v, _ in parts)

fig, ax = plt.subplots(figsize=(8.6, 2.9), dpi=150)
left = 0
for label, value, color in parts:
    ax.barh([0], [value], left=left, height=0.55, color=color,
            edgecolor="white", linewidth=1.2)
    pct = value / total * 100
    if value >= 10:
        ax.text(left + value / 2, 0, f"{pct:.0f}%", ha="center",
                va="center", color="white", fontsize=10, fontweight="bold")
    left += value

ax.set_xlim(0, total)
ax.set_yticks([])
ax.set_xlabel(f"tokens in the array after a long session (~{total}k total, illustrative)")
ax.set_title("Where the context budget actually goes", fontsize=11)
for spine in ("top", "right", "left"):
    ax.spines[spine].set_visible(False)

handles = [plt.Rectangle((0, 0), 1, 1, color=c) for _, _, c in parts]
ax.legend(handles, [f"{l} — {v}k" for l, v, _ in parts],
          loc="upper center", bbox_to_anchor=(0.5, -0.55),
          frameon=False, fontsize=8.5, ncol=2)
fig.tight_layout()
fig.savefig("context_composition.png", bbox_inches="tight")
print("wrote context_composition.png")
