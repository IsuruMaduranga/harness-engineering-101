#!/usr/bin/env python3
"""Chapter 7 figure: two real attention heads from GPT-2, on one sentence.

Runs the NumPy forward pass from ../gpt/v3_forward.py, keeps the attention
weights of every head, and plots the head that most strongly looks at the
previous token and the head that most strongly looks back at an earlier
copy of the current token. Nobody designed either; training produced them.

Regenerate: python3 gen_attention_heatmap.py   (needs ../../models/gpt2/)
"""
import os, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "gpt"))
from v3_forward import load_safetensors, layers, softmax, layer_norm, mlp, N_HEAD
from gpt2_tokenizer import GPT2Tokenizer, GPT2_DIR

SENTENCE = "The harness sends the array to the model, and the model reads the array."


def attention_with_weights(x, p):
    T, C = x.shape
    qkv = x @ p["attn.c_attn.weight"] + p["attn.c_attn.bias"]
    q, k, v = np.split(qkv, 3, axis=-1)
    split = lambda m: m.reshape(T, N_HEAD, C // N_HEAD).transpose(1, 0, 2)
    q, k, v = split(q), split(k), split(v)
    scores = q @ k.transpose(0, 2, 1) / np.sqrt(C // N_HEAD)
    scores = np.where(np.triu(np.ones((T, T), dtype=bool), k=1), -1e10, scores)
    w = softmax(scores)
    out = (w @ v).transpose(1, 0, 2).reshape(T, C)
    return out @ p["attn.c_proj.weight"] + p["attn.c_proj.bias"], w


W = load_safetensors(os.path.join(GPT2_DIR, "model.safetensors"))
tok = GPT2Tokenizer()
ids = tok.encode(SENTENCE)
labels = [s.replace(" ", "␣") for s in tok.pieces(ids)]
T = len(ids)

all_w = []                                                   # (layer, head, T, T)
x = W["wte.weight"][ids] + W["wpe.weight"][np.arange(T)]
for p in layers(W):
    a, w = attention_with_weights(layer_norm(x, p["ln_1.weight"], p["ln_1.bias"]), p)
    all_w.append(w)
    x = x + a
    x = x + mlp(layer_norm(x, p["ln_2.weight"], p["ln_2.bias"]), p)
all_w = np.array(all_w)

# head that looks at the previous token most consistently
prev = np.array([[w[np.arange(1, T), np.arange(0, T - 1)].mean() for w in layer] for layer in all_w])
L1, H1 = np.unravel_index(prev.argmax(), prev.shape)
# head that most strongly looks from the second " model" back at the first " model"
first, second = [i for i, t in enumerate(tok.pieces(ids)) if t == " model"][:2]
copy = all_w[:, :, second, first]
L2, H2 = np.unravel_index(copy.argmax(), copy.shape)

fig, axes = plt.subplots(1, 2, figsize=(11, 5.2), dpi=150)
for ax, (L, H, title) in zip(axes, [
        (L1, H1, f"layer {L1}, head {H1}: 'look at the previous token'\n(mean weight on previous token: {prev[L1, H1]:.2f})"),
        (L2, H2, f"layer {L2}, head {H2}: 'find the earlier copy of me'\n(second ' model' → first ' model': {copy[L2, H2]:.2f})")]):
    im = ax.imshow(all_w[L, H], cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(T)); ax.set_yticks(range(T))
    ax.set_xticklabels(labels, rotation=90, fontsize=7)
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_xlabel("key position (looked at)", fontsize=8)
    ax.set_ylabel("query position (looking)", fontsize=8)
    ax.set_title(title, fontsize=9)
    ax.tick_params(length=0)
fig.colorbar(im, ax=axes, fraction=0.02, pad=0.02, label="attention weight")
fig.suptitle(f"Two of GPT-2's 144 attention heads on: “{SENTENCE}”", fontsize=10)
fig.savefig(os.path.join(HERE, "attention_heads.png"), bbox_inches="tight")
print(f"wrote attention_heads.png  (prev-token head: L{L1}H{H1} {prev[L1,H1]:.2f}; copy head: L{L2}H{H2} {copy[L2,H2]:.2f})")
