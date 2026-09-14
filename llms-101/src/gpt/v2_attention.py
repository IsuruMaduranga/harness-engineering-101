#!/usr/bin/env python3
"""Toy GPT v2: causal self-attention, in plain NumPy.

Attention is a soft lookup. Every position asks a question (its query),
every position advertises what it holds (its key), and every position
carries a payload (its value). Each position's output is a weighted
average of all the values it is allowed to see, weighted by how well its
query matches each key. "Causal" means a position may only look backward.

    python3 v2_attention.py
"""
import numpy as np


def softmax(x, axis=-1):
    x = x - x.max(axis=axis, keepdims=True)         # for numerical stability
    e = np.exp(x)
    return e / e.sum(axis=axis, keepdims=True)


def attention(x, Wq, Wk, Wv):
    """x: (T, d) one row per token. Returns (T, d_v)."""
    T = x.shape[0]
    Q, K, V = x @ Wq, x @ Wk, x @ Wv                # what I want / what I have / what I carry
    scores = Q @ K.T / np.sqrt(K.shape[1])          # (T, T): how well each query matches each key
    mask = np.triu(np.ones((T, T)), k=1).astype(bool)
    scores[mask] = -np.inf                          # no looking at the future
    weights = softmax(scores)                       # each row sums to 1
    return weights @ V, weights                     # weighted average of values


if __name__ == "__main__":
    rng = np.random.default_rng(0)
    T, d = 5, 8                                     # five tokens, eight dims each
    x = rng.standard_normal((T, d))
    Wq, Wk, Wv = (rng.standard_normal((d, d)) * 0.5 for _ in range(3))
    out, weights = attention(x, Wq, Wk, Wv)
    np.set_printoptions(precision=2, suppress=True)
    print("attention weights (row = query position, col = key position):")
    print(weights)
    print("\nrows sum to 1:", weights.sum(axis=1))
    print("output shape:", out.shape)
