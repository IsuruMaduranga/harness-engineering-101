#!/usr/bin/env python3
"""Chapter 5 figure: cumulative input-token cost of an agent turn,
with and without prefix caching.

Model of the turn: the array starts at BASE tokens and grows by
GROWTH tokens per round (one tool call + result). Without caching every
round bills its full array. With caching, previously-seen prefix tokens
bill at CACHE_PRICE of full price (cache-write surcharge ignored for
clarity; it does not change the picture).

Regenerate: python3 gen_cache_economics.py
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BASE = 10_000          # tokens in the array at round 1
GROWTH = 2_000         # tokens added per round
ROUNDS = 40
CACHE_PRICE = 0.10     # cached input price as a fraction of full price

rounds = list(range(1, ROUNDS + 1))
sizes = [BASE + GROWTH * (r - 1) for r in rounds]

cum_nocache, cum_cache = [], []
total_n = total_c = 0.0
for i, size in enumerate(sizes):
    total_n += size                                   # everything full price
    new = size if i == 0 else GROWTH                  # only the tail is new
    total_c += new + (size - new) * CACHE_PRICE       # prefix at 10%
    cum_nocache.append(total_n / 1e6)
    cum_cache.append(total_c / 1e6)

fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
ax.plot(rounds, cum_nocache, lw=2.5, color="#c0392b",
        label="no caching — every round re-billed in full")
ax.plot(rounds, cum_cache, lw=2.5, color="#2471a3",
        label=f"prefix caching — cached tokens at {int(CACHE_PRICE*100)}% price")
ax.fill_between(rounds, cum_cache, cum_nocache, color="#c0392b", alpha=0.08)

ax.annotate(f"{cum_nocache[-1]:.2f}M token-equivalents",
            xy=(ROUNDS, cum_nocache[-1]), xytext=(24, 1.72),
            fontsize=9, color="#c0392b",
            arrowprops=dict(arrowstyle="->", color="#c0392b", lw=1))
ax.annotate(f"{cum_cache[-1]:.2f}M",
            xy=(ROUNDS, cum_cache[-1]), xytext=(33, 0.55),
            fontsize=9, color="#2471a3",
            arrowprops=dict(arrowstyle="->", color="#2471a3", lw=1))

ax.set_xlabel("agent-loop round within one user turn")
ax.set_ylabel("cumulative billed input (millions of\nfull-price-token equivalents)")
ax.set_title("One 40-round agent turn: what prefix caching does to the bill",
             fontsize=11)
ax.legend(frameon=False, fontsize=9, loc="upper left")
ax.grid(True, alpha=0.25)
ax.set_xlim(1, ROUNDS)
ax.set_ylim(0, None)
fig.tight_layout()
fig.savefig("cache_economics.png")
print("wrote cache_economics.png")
