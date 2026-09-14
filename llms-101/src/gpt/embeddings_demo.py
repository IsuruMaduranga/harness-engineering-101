#!/usr/bin/env python3
"""Chapter 3: what GPT-2's embedding table actually contains.

Nearest neighbours by cosine similarity, and the classic vector arithmetic.
Uses only the `wte.weight` tensor: 50,257 rows of 768 numbers.

    python3 embeddings_demo.py
"""
import os
import numpy as np
from gpt2_tokenizer import GPT2Tokenizer, GPT2_DIR
from v3_forward import load_safetensors

HERE = os.path.dirname(os.path.abspath(__file__))
W = load_safetensors(os.path.join(GPT2_DIR, "model.safetensors"))
tok = GPT2Tokenizer()
E = W["wte.weight"]
print("embedding table:", E.shape, "->", E.size, "numbers")

unit = E / np.linalg.norm(E, axis=1, keepdims=True)

def one(word):
    ids = tok.encode(word)
    assert len(ids) == 1, f"{word!r} is {len(ids)} tokens"
    return ids[0]

def nearest(vec, k=8, skip=()):
    sims = unit @ (vec / np.linalg.norm(vec))
    out = []
    for i in np.argsort(sims)[::-1]:
        if i in skip: continue
        out.append((tok.decode([int(i)]), round(float(sims[i]), 2)))
        if len(out) == k: break
    return out

for w in [" king", " Python", " happy", " Paris", " Monday", " harness"]:
    print(f"{w!r:12} ->", nearest(E[one(w)], skip={one(w)}))

print("\nvector arithmetic:")
for a, b, c in [(" king", " man", " woman"), (" Paris", " France", " Germany"), (" walked", " walk", " swim")]:
    v = E[one(a)] - E[one(b)] + E[one(c)]
    print(f"{a} - {b} + {c} ->", nearest(v, k=5, skip={one(a), one(b), one(c)}))

print("\nthe row for ' strawberry', first 8 of 768 numbers:")
print(np.round(E[one(" strawberry")][:8], 3))
