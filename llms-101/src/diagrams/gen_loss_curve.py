#!/usr/bin/env python3
"""Chapter 8 figure: the toy GPT's training and validation loss.

Reads ../gpt/loss.csv, written by v4_train.py. The two curves part company
around step 500: training loss keeps falling while validation loss rises,
which is the model switching from learning to memorising.

Regenerate: python3 gen_loss_curve.py
"""
import csv, math, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
rows = list(csv.DictReader(open(os.path.join(HERE, "..", "gpt", "loss.csv"))))
steps = [int(r["step"]) for r in rows]
train = [float(r["train_loss"]) for r in rows]
val = [float(r["val_loss"]) for r in rows]
best_i = min(range(len(val)), key=lambda i: val[i])

fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
ax.axhline(math.log(512), color="#7f8c8d", lw=1, ls="--")
ax.text(steps[-1], math.log(512) + 0.08, "ln(512) = 6.24: a uniform guess over the vocabulary",
        ha="right", fontsize=8, color="#7f8c8d")
ax.plot(steps, train, lw=2, color="#2471a3", label="training loss (text it is learning from)")
ax.plot(steps, val, lw=2, color="#c0392b", label="validation loss (held-out 10% of the book)")
ax.axvline(steps[best_i], color="#c0392b", lw=1, alpha=0.4)
ax.annotate(f"best validation: {val[best_i]:.2f} at step {steps[best_i]}\nafter this it is memorising",
            xy=(steps[best_i], val[best_i]), xytext=(steps[best_i] + 550, 2.1),
            fontsize=9, color="#c0392b",
            arrowprops=dict(arrowstyle="->", color="#c0392b", lw=1))
ax.annotate(f"{train[-1]:.2f}: it has learned the book by heart",
            xy=(steps[-1], train[-1]), xytext=(steps[-1] - 900, train[-1] + 0.9),
            fontsize=9, color="#2471a3",
            arrowprops=dict(arrowstyle="->", color="#2471a3", lw=1))
ax.set_xlabel("training step (32 sequences of 128 tokens each)")
ax.set_ylabel("loss (average surprise at the true next token)")
ax.set_title("875k-parameter GPT on 83k tokens: learning, then memorising", fontsize=11)
ax.legend(frameon=False, fontsize=9, loc="center", bbox_to_anchor=(0.55, 0.5))
ax.grid(True, alpha=0.25)
ax.set_xlim(0, steps[-1])
ax.set_ylim(0, 7)
fig.tight_layout()
fig.savefig(os.path.join(HERE, "loss_curve.png"))
print("wrote loss_curve.png")
