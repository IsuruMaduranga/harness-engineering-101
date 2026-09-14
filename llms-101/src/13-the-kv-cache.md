# Chapter 13: The KV Cache: Why Prompt Caching Exists

*LLMs 101, Part III — Running the Brain.
[Series index](index.html) · [Prev](12-changing-a-brain-cheaply.md) ·
[Next: Context Windows](14-context-windows.md)*

---

**The failure:** chapter 7's `generate` re-ran the entire sequence through
all twelve layers for every new token. To produce token 26 it recomputed
everything about tokens 1 through 25, which it had already computed to
produce token 25. Twenty-five tokens took three and a half seconds. Nobody
could serve a model that way, and nobody does. Here's the fix, and it
explains half of the body book's chapter 5:

> **During generation, the keys and values of earlier tokens never
> change, so keep them.** Run the prompt once, storing every layer's K and V
> for every position (the **prefill**). Then, for each new token, compute
> only *its* Q, K and V, append the K and V to the store, and attend over
> the store (the **decode**). The store is the **KV cache**. Prompt caching
> at the API is saving that store between requests. The reason output
> tokens cost more than input tokens is that prefill and decode are
> different kinds of work.

I wrote a whole chapter in the body book on byte-stable prefixes without
being able to say *what* was being cached. This is what.

## Why the old tokens never change

Look back at chapter 5's attention. Position *i*'s key and value are
computed from position *i*'s vector alone (`x[i] @ Wk`, `x[i] @ Wv`), and
because of the causal mask, position *i*'s vector depends only on
positions up to *i*. Add a token at the end of the sequence and nothing
about the earlier positions is affected. Their K and V at every layer are
exactly what they were.

So the only new work when a token arrives is: embed it, and at each layer
compute its query, its key and its value, attend its query over *all*
stored keys, blend the stored values, and run the MLP on its vector alone.
Everything else is a lookup into memory you already filled.

## The code

[`gpt/v5_generate.py`](https://github.com/IsuruMaduranga/harness-engineering-101/blob/main/llms-101/src/gpt/v5_generate.py)
patches chapter 7's attention to take a cache:

```python
def attention_cached(x, p, cache):
    """x: (T_new, C). cache holds 'k','v' of shape (heads, T_old, 64) or None."""
    T, C = x.shape
    qkv = x @ p["attn.c_attn.weight"] + p["attn.c_attn.bias"]
    q, k, v = np.split(qkv, 3, axis=-1)
    q, k, v = split_heads(q), split_heads(k), split_heads(v)
    if cache["k"] is not None:                              # append this step's K,V to the stored ones
        k = np.concatenate([cache["k"], k], axis=1)
        v = np.concatenate([cache["v"], v], axis=1)
    cache["k"], cache["v"] = k, v                           # the cache IS the conversation so far
    scores = q @ k.transpose(0, 2, 1) / np.sqrt(C // N_HEAD)   # (heads, T_new, T_all)
    ...
```

And the generation loop splits into its two phases:

```python
def generate(prompt, W, tok, n=20, **sampling):
    ids = tok.encode(prompt)
    caches = [{"k": None, "v": None} for _ in range(12)]     # one per layer
    logits = gpt2_step(np.array(ids), W, caches, pos=0)      # PREFILL: the whole prompt, once
    out = list(ids)
    for _ in range(n):                                       # DECODE: one token at a time
        nxt = pick(logits, **sampling)
        out.append(nxt)
        logits = gpt2_step(np.array([nxt]), W, caches, pos=len(out) - 1)
    return tok.decode(out), caches
```

Run it against chapter 7's version on a realistic prompt, the first 500
tokens of the harness book, generating 40 tokens:

```
509-token prompt, 40 new tokens.  no cache: 36.2s   KV cache: 6.8s   (5.3x)
cache holds 10,119,168 floats for 549 tokens = 40.5 MB in float32 (72 KB per token)
```

Same output, token for token (the file asserts it). Five times faster, and
the gap widens with prompt length: on a 12-token prompt the cache barely
mattered, because there was nothing to recompute. This is the mechanism
behind every "tokens per second" figure you've ever seen quoted, and it's
why the first token of a reply takes noticeably longer than the rest. The
first token waits for prefill. The rest are decode steps.

## Prefill and decode are different kinds of work

Here is the fact that explains the price list. In **prefill**, the model
processes hundreds or thousands of tokens at once: big matrix multiplies,
every position in parallel, the GPU doing what it's built for. The weights
are loaded from memory once and used against many tokens. This is
**compute-bound** work, and it's efficient.

In **decode**, the model processes *one* token. But it still has to
multiply that one token by every weight in the network: all 124 million
numbers for GPT-2, all 70 billion for a big model. Each weight is read
from memory and used exactly once. The arithmetic is trivial; the time is
spent *moving weights from memory to the processor*. Decode is
**memory-bandwidth-bound**, and the GPU spends most of it waiting.

That's why the toy still takes 0.17 seconds per token even with the cache.
It isn't computing much; it's streaming 548 MB of weights through the CPU
for each token. And it's why an output token is priced at several times an
input token: an input token shares the cost of a weight read with a
thousand neighbours in prefill, while an output token pays for a whole
pass through the weights nearly alone. Chapter 17's batching is the
serving-side answer (make many users' decode steps share one weight read),
and it's the reason latency varies with load.

## Prompt caching is saving the store

Now the body book's chapter 5, mechanically. Two requests that start with
the same tokens produce the same K and V at every layer for those tokens,
because everything is causal and deterministic. So a provider can keep the
KV cache from your last request and, when the next one arrives, compare
token by token from the start, find the longest matching prefix, and skip
prefill for it. What you're charged a tenth of the price for is *the cache
lookup instead of the compute*.

Every rule the body book gave you falls out of that:

- **The prefix must match exactly**, byte for byte, from position zero,
  because the cache is indexed by position and one changed token changes
  the K and V of that position and, through attention, every position
  after it.
- **Order is load-bearing.** Stable stuff (system prompt, tool schemas)
  goes first; the thing that changes every turn goes last.
- **A timestamp in the system prompt kills the cache**, because it changes
  the tokens at the front and invalidates everything behind them.
- **Caches expire in minutes.** They're gigabytes of GPU memory per
  conversation, and that memory is the scarcest thing in the building.

## The cache is big, and shrinking it is an architecture decision

The toy's cache is 72 KB per token: 12 layers × 2 (K and V) × 768 numbers
× 4 bytes. Do that for a 70-billion-parameter model with a full set of K/V
heads: 80 layers × 2 × 8,192 × 2 bytes (16-bit) is about 2.6 MB per token. A 100,000-token
conversation would need 260 GB of cache, more than the GPU holds, before
you've loaded the weights. Long context isn't limited by attention's
quadratic compute alone (chapter 14). It's limited by where to *put* the
keys and values.

So modern models shrink the cache at the architecture level. Chapter 6's
multi-head attention gives each of the 64 query heads its own K and V.
**Grouped-query attention** (GQA) instead keeps only 8 K/V heads and has
each one serve 8 query heads. The queries still ask 64 different questions;
they just look them up in 8 shared tables. Quality barely moves, and the
cache drops eightfold, to about 0.33 MB per token for that 70B model.
**Multi-query attention** takes it to one K/V head. This is the row in
chapter 7's table that said "fewer K/V heads shared across query heads,"
and now you know why every model since 2023 has it: not for speed of
compute but for the size of this store. The epilogue's toy uses GQA so you
can see how few lines it is.

## What you now know

- Earlier tokens' keys and values never change, so generation keeps them.
  Prefill computes the prompt once; decode adds one token at a time. Five
  times faster on the toy, and the gap grows with prompt length.
- Prefill is parallel and compute-bound. Decode is one token against all
  the weights and memory-bound. That's why output tokens cost more and why
  the first token is slow.
- Prompt caching is reusing the KV store across requests, matched from
  position zero. Every byte-stability rule from the body book is a
  consequence.
- The cache is megabytes per token on a large model. Grouped-query
  attention exists to shrink it, and it's why long contexts are possible
  at all.

Next: the other half of the long-context story. Why the window has a hard
edge, what happens to quality as you approach it, and why "one million
tokens" on the box doesn't mean what it sounds like.

*[Next: Chapter 14 — Context Windows: The Limit and the Decay](14-context-windows.md)*
