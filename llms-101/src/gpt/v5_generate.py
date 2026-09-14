#!/usr/bin/env python3
"""Toy GPT v5: generation done properly. Two changes to v3_forward.py:

1. A KV cache. v3 re-ran the whole prompt through all 12 layers for every
   new token. But the keys and values for old tokens never change, so keep
   them and only compute the new token's. This is why "prefill" and
   "decode" are different phases, why prompt caching exists, and why
   output tokens cost more than input tokens.
2. Real sampling: temperature, top-k, top-p. The model returns
   probabilities; this file is the part of the "serving layer" that picks.

    python3 v5_generate.py
"""
import os, time
import numpy as np
from gpt2_tokenizer import GPT2Tokenizer, GPT2_DIR
from v3_forward import load_safetensors, layers, softmax, layer_norm, mlp, gpt2, N_HEAD

HERE = os.path.dirname(os.path.abspath(__file__))


def attention_cached(x, p, cache):
    """x: (T_new, C). cache: dict with 'k','v' of shape (heads, T_old, 64) or None."""
    T, C = x.shape
    qkv = x @ p["attn.c_attn.weight"] + p["attn.c_attn.bias"]
    q, k, v = np.split(qkv, 3, axis=-1)
    split = lambda m: m.reshape(T, N_HEAD, C // N_HEAD).transpose(1, 0, 2)
    q, k, v = split(q), split(k), split(v)
    if cache["k"] is not None:                                    # append this step's K,V to the stored ones
        k = np.concatenate([cache["k"], k], axis=1)
        v = np.concatenate([cache["v"], v], axis=1)
    cache["k"], cache["v"] = k, v                                 # the cache IS the conversation so far
    T_all = k.shape[1]
    scores = q @ k.transpose(0, 2, 1) / np.sqrt(C // N_HEAD)      # (heads, T_new, T_all)
    mask = np.triu(np.ones((T, T_all), dtype=bool), k=T_all - T + 1)
    scores = np.where(mask, -1e10, scores)
    out = (softmax(scores) @ v).transpose(1, 0, 2).reshape(T, C)
    return out @ p["attn.c_proj.weight"] + p["attn.c_proj.bias"]


def gpt2_step(ids, W, caches, pos):
    """Run only the NEW tokens `ids` (starting at position `pos`) through the model."""
    x = W["wte.weight"][ids] + W["wpe.weight"][np.arange(pos, pos + len(ids))]
    for p, cache in zip(layers(W), caches):
        x = x + attention_cached(layer_norm(x, p["ln_1.weight"], p["ln_1.bias"]), p, cache)
        x = x + mlp(layer_norm(x, p["ln_2.weight"], p["ln_2.bias"]), p)
    x = layer_norm(x, W["ln_f.weight"], W["ln_f.bias"])
    return x[-1] @ W["wte.weight"].T                              # logits for the last position only


def pick(logits, temperature=1.0, top_k=0, top_p=1.0, rng=np.random.default_rng(0)):
    """The serving layer's job: turn a distribution into one token."""
    if temperature == 0:
        return int(logits.argmax())
    probs = softmax(logits / temperature)
    order = np.argsort(probs)[::-1]
    if top_k:
        order = order[:top_k]                                     # keep only the k most likely
    if top_p < 1.0:
        keep = np.cumsum(probs[order]) <= top_p                   # keep the smallest set covering p of the mass
        keep[0] = True
        order = order[keep]
    p = probs[order] / probs[order].sum()
    return int(rng.choice(order, p=p))


def generate(prompt, W, tok, n=20, **sampling):
    ids = tok.encode(prompt)
    caches = [{"k": None, "v": None} for _ in range(12)]
    logits = gpt2_step(np.array(ids), W, caches, pos=0)           # PREFILL: the whole prompt, once
    out = list(ids)
    for _ in range(n):                                            # DECODE: one token at a time
        nxt = pick(logits, **sampling)
        out.append(nxt)
        logits = gpt2_step(np.array([nxt]), W, caches, pos=len(out) - 1)
    return tok.decode(out), caches


if __name__ == "__main__":
    W = load_safetensors(os.path.join(GPT2_DIR, "model.safetensors"))
    tok = GPT2Tokenizer()
    # 1. same answer, with and without the cache, on a realistic prompt length
    book = open(os.path.join(HERE, "corpus.txt")).read()
    prompt = tok.decode(tok.encode(book)[:500]) + "\n\nIn short, an LLM is"
    n_prompt = len(tok.encode(prompt))
    t = time.time(); ids = tok.encode(prompt)
    for _ in range(40):
        ids.append(int(gpt2(np.array(ids), W)[-1].argmax()))   # v3 style: whole sequence, every step
    t_no = time.time() - t
    t = time.time(); text, caches = generate(prompt, W, tok, n=40, temperature=0); t_yes = time.time() - t
    assert tok.decode(ids) == text
    print("..." + text[-300:])
    print(f"\n{n_prompt}-token prompt, 40 new tokens.  no cache: {t_no:.1f}s   KV cache: {t_yes:.1f}s   ({t_no / t_yes:.1f}x)")
    n_tok = len(tok.encode(text))
    kv_floats = sum(c["k"].size + c["v"].size for c in caches)
    print(f"cache holds {kv_floats:,} floats for {n_tok} tokens = {kv_floats * 4 / 1e6:.1f} MB in float32 "
          f"({kv_floats * 4 // n_tok // 1024} KB per token)")

    # 2. sampling knobs
    for kw in [dict(temperature=0), dict(temperature=0.7, top_p=0.9), dict(temperature=1.5)]:
        text, _ = generate("The harness is", W, tok, n=25, **kw)
        print(f"\n{kw}:\n  {text!r}")
