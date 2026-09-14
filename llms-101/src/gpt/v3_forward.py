#!/usr/bin/env python3
"""Toy GPT v3: the complete GPT-2 forward pass in plain NumPy, running
the real 124-million-parameter weights OpenAI published in 2019.

No framework. Matrix multiplies, a softmax, a tanh, and a lookup table.
Run it and English comes out. That is the whole "black box".

    python3 download_gpt2.py      # once, ~550 MB
    python3 v3_forward.py
"""
import json, os, struct, sys, time
import numpy as np
from gpt2_tokenizer import GPT2Tokenizer, GPT2_DIR

HERE = os.path.dirname(os.path.abspath(__file__))
N_HEAD = 12                                             # GPT-2 small: 12 heads, 12 layers, 768 dims


# ---- 1. load the weights: a safetensors file is a JSON header + raw bytes
def load_safetensors(path):
    with open(path, "rb") as f:
        (n,) = struct.unpack("<Q", f.read(8))
        header = json.loads(f.read(n))
        data = f.read()
    out = {}
    for name, meta in sorted(header.items()):
        if name == "__metadata__" or name.endswith(".attn.bias"):   # skip the stored causal-mask buffers: not weights
            continue
        a, b = meta["data_offsets"]
        out[name] = np.frombuffer(data[a:b], dtype=np.float32).reshape(meta["shape"])
    return out


def layers(W, n_layer=12):
    """Group the flat weight dict by block: layers(W)[3]['mlp.c_fc.weight']."""
    return [{k.split(f"h.{i}.", 1)[1]: v for k, v in W.items() if k.startswith(f"h.{i}.")}
            for i in range(n_layer)]


# ---- 2. the four building blocks
def gelu(x):                                            # a smooth "off below zero, on above"
    return 0.5 * x * (1 + np.tanh(np.sqrt(2 / np.pi) * (x + 0.044715 * x**3)))

def softmax(x):
    x = x - x.max(axis=-1, keepdims=True)
    e = np.exp(x)
    return e / e.sum(axis=-1, keepdims=True)

def layer_norm(x, w, b, eps=1e-5):                      # re-centre and re-scale each token's vector
    mean = x.mean(-1, keepdims=True)
    var = x.var(-1, keepdims=True)
    return (x - mean) / np.sqrt(var + eps) * w + b

def attention(x, p):
    """Multi-head causal self-attention. x: (T, 768)."""
    T, C = x.shape
    qkv = x @ p["attn.c_attn.weight"] + p["attn.c_attn.bias"]      # (T, 3*768): one matmul makes Q, K and V
    q, k, v = np.split(qkv, 3, axis=-1)
    split = lambda m: m.reshape(T, N_HEAD, C // N_HEAD).transpose(1, 0, 2)   # (heads, T, 64)
    q, k, v = split(q), split(k), split(v)
    scores = q @ k.transpose(0, 2, 1) / np.sqrt(C // N_HEAD)         # (heads, T, T)
    mask = np.triu(np.ones((T, T), dtype=bool), k=1)
    scores = np.where(mask, -1e10, scores)                           # causal: no peeking forward
    out = softmax(scores) @ v                                        # (heads, T, 64)
    out = out.transpose(1, 0, 2).reshape(T, C)                       # glue heads back together
    return out @ p["attn.c_proj.weight"] + p["attn.c_proj.bias"]

def mlp(x, p):
    """Two matmuls with a bend in the middle. Where the facts live."""
    h = gelu(x @ p["mlp.c_fc.weight"] + p["mlp.c_fc.bias"])         # 768 -> 3072
    return h @ p["mlp.c_proj.weight"] + p["mlp.c_proj.bias"]         # 3072 -> 768


# ---- 3. stack them
def gpt2(ids, W, n_layer=12):
    """Token ids in (T,), logits out (T, vocab). The one function."""
    x = W["wte.weight"][ids] + W["wpe.weight"][np.arange(len(ids))]  # what + where
    for p in layers(W, n_layer):                                     # 12 identical blocks, different numbers
        x = x + attention(layer_norm(x, p["ln_1.weight"], p["ln_1.bias"]), p)   # residual: add, don't replace
        x = x + mlp(layer_norm(x, p["ln_2.weight"], p["ln_2.bias"]), p)
    x = layer_norm(x, W["ln_f.weight"], W["ln_f.bias"])
    return x @ W["wte.weight"].T                                     # unembed with the same table, transposed


def generate(prompt, W, tok, n=20):
    ids = tok.encode(prompt)
    for _ in range(n):
        logits = gpt2(np.array(ids), W)                              # recompute EVERYTHING every step (chapter 13 fixes this)
        ids.append(int(logits[-1].argmax()))                         # greedy: most likely token
    return tok.decode(ids)


if __name__ == "__main__":
    W = load_safetensors(os.path.join(GPT2_DIR, "model.safetensors"))
    tok = GPT2Tokenizer()
    n_params = sum(v.size for v in W.values())
    print(f"{len(W)} weight tensors, {n_params:,} parameters")
    print("block 0, in full:", *[f"\n  {k:28} {v.shape}" for k, v in W.items() if k.startswith("h.0.")])
    print("plus:", *[f"\n  {k:28} {v.shape}" for k, v in W.items() if not k.startswith("h.")])

    prompt = "The capital of France is"
    logits = gpt2(np.array(tok.encode(prompt)), W)
    probs = softmax(logits[-1])
    top = np.argsort(probs)[::-1][:5]
    print(f"\nafter {prompt!r}, the top next tokens:")
    for i in top:
        print(f"  {probs[i]:.3f}  {tok.decode([int(i)])!r}")

    for prompt in ["The capital of France is", "def fibonacci(n):",
                   "An LLM is a next-token predictor, which means"]:
        t = time.time()
        print(f"\n> {generate(prompt, W, tok, n=25)}")
        print(f"  ({time.time() - t:.1f}s for 25 tokens, recomputing the whole prompt every step)")
