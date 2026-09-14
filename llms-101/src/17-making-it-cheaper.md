# Chapter 17: Making It Cheaper: Quantization, Speculative Decoding, Batching

*LLMs 101, Part III — Running the Brain.
[Series index](index.html) · [Prev](16-mixture-of-experts.md) ·
[Next: Multimodal](18-multimodal.md)*

---

**The failure:** the bill. Chapter 13 established that a decode step is one
token dragged through every weight, with the processor mostly waiting on
memory. Every trick in this chapter attacks that one fact from a different
side, and together they're where the price tiers in the body book's
Appendix A come from:

> **Three ways to make a token cheaper: move fewer bytes per weight
> (quantization), check several tokens per weight-read (speculative
> decoding), or serve many users per weight-read (batching).** None of them
> changes the model. They change how much of the hardware's time is spent
> doing arithmetic instead of waiting.

## Quantization: the weights don't need all their bits

GPT-2's file was 548 MB because 124 million weights were stored as 32-bit
floats. Nobody serves in 32-bit. Training happens in 16-bit, mostly, and
the file you download is 16-bit. **Quantization** goes further: store each
weight in 8 bits, or 4, and convert back to 16-bit on the fly as the
matrix multiply runs.

The mechanism is arithmetic you learned in school. Take a block of 32
weights, find the largest one, and store a single 16-bit **scale** for the
block. Then store each weight as a small integer: the weight divided by the
scale, rounded, fitting in 4 bits (sixteen levels). Reconstruction is
`integer × scale`. You've replaced 32 × 16 = 512 bits with 32 × 4 + 16 =
144 bits. Fancier schemes keep a few outlier weights at full precision or
choose per-block scales cleverly, and the names you see on downloadable
files (`Q4_K_M`, `GPTQ`, `AWQ`, `FP8`) are recipes for where to spend the
saved bits.

Why does this work at all? Because trained weights are redundant and
noise-tolerant. A model that survived dropout and stochastic gradient noise
during training has a loss surface that's flat around its minimum; nudging
every weight by a rounding error moves it a little along that flat region.
Measured quality at 8-bit is indistinguishable from 16-bit. At 4-bit it's a
small, real drop, larger on small models than large ones (big models are
*more* redundant). Below 4 bits the cliff arrives.

What it buys is exactly what chapter 13 said decode is starved of: memory
bandwidth. Half the bytes per weight, half the time to stream the weights
past the processor per token, roughly twice the tokens per second, and a
70B model that fits on one GPU instead of two. This is the entire reason
you can run a decent model on a laptop: 4-bit quantization turned a 140 GB
weight file into 35 GB. It also applies to the KV cache (chapter 13), where
8-bit keys and values double the context that fits in memory at nearly no
quality cost.

## Speculative decoding: guess ahead, check in bulk

Here's the trick that exploits the prefill/decode asymmetry directly.

Decode is one token per pass through the weights, and the pass is
bandwidth-bound, meaning the processor has arithmetic to spare. Prefill
runs many tokens through the weights in one pass for about the same
memory cost. So: what if you could turn decode into prefill?

Use a small, fast **draft model** (a distilled cousin of the big one,
chapter 12) to guess the next *k* tokens, say five, cheaply. Then run the
big model *once* on all five guesses at the same time, as if they were a
prompt. That single pass gives you the big model's next-token distribution
at each of the five positions. Compare: where the big model agrees with the
draft, accept the token and move on. At the first disagreement, take the big
model's token instead and throw the rest of the draft away.

```
draft proposes:   " the"  " capital"  " of"  " the"  " French"
big model says:   " the"  " capital"  " of"  " France" ...
accepted:         " the"  " capital"  " of"  " France"      <- 4 tokens for one big-model pass
```

The acceptance rule uses rejection sampling, arranged so that the output
distribution is *exactly* the big model's. Not approximately: the tokens
you get are drawn from the same distribution as if the draft model didn't
exist. The draft only changes speed. On text where the continuation is
predictable (code, boilerplate, the middle of a familiar phrase), the draft
is right most of the time and you get two to three tokens per big-model
pass. On text where every token is a surprise, you get roughly one and a
little overhead. The speedup is free in quality and paid for in the memory
for a second model, and it's now standard in serving stacks. Some models
ship with a built-in draft head that predicts several tokens at once from
the main model's own state, which is the same idea without the second
model.

## Batching: many users, one weight-read

The third trick is the one that determines what a provider's costs
actually are, and therefore what you pay.

A decode step for one user reads all the weights to produce one token. A
decode step for sixty-four users reads all the weights *once* and produces
sixty-four tokens, because the matrix multiply that was `weights × one
vector` becomes `weights × sixty-four vectors`, and the weights are the
expensive part to move. Throughput scales almost linearly with batch size
until the arithmetic finally catches up with the memory traffic.

The complication is that users arrive at different times and their
replies finish at different times. **Continuous batching** handles this:
the serving system runs a decode step for whichever requests are active
right now, adds new arrivals into the next step, and drops finished ones,
so the batch is always full. Appendix C covers the memory management
(paged attention) that makes the KV caches of a shifting batch fit.

Two things you've observed follow directly:

- **Latency varies with load.** A step over a batch of 64 takes longer than
  a step over a batch of 4, so your tokens-per-second falls when the
  provider is busy. Speed isn't a property of the model; it's a property of
  who else is using it.
- **Batch APIs are half price.** A request that can wait hours can be
  slotted into whatever capacity is idle. The provider's marginal cost for
  it is nearly zero because the weight-read was happening anyway.

## Where the price list comes from

Put Part III together and the body book's cost tiers stop being a menu and
become a calculation:

| Line item | The mechanism behind it |
|---|---|
| Price per input token | prefill: parallel, compute-bound, cheap; roughly proportional to active parameters (ch. 13, 16) |
| Price per output token, several times higher | decode: bandwidth-bound, one token per weight-read, less batchable (ch. 13) |
| Cached input at a tenth of the price | a KV-cache lookup instead of prefill (ch. 13) |
| Higher rates past a context threshold | quadratic prefill and a linearly growing cache in scarce memory (ch. 14) |
| Cheap tier vs flagship | fewer active parameters, more quantization, distillation (ch. 12, 16, 17) |
| Thinking tokens billed as output | they *are* output tokens (ch. 11) |
| Batch discount | filling idle capacity (ch. 17) |

Every row is a fact about the hardware and the architecture, not a pricing
strategy. When a new model is announced at a surprising price, this table
is how to read it: it's a smaller active parameter count, a harder
quantization, a bigger batch, or a subsidy.

## What you now know

- Quantization stores weights in 4 to 8 bits with per-block scales. It
  halves or quarters memory and bandwidth, which is exactly what decode is
  starved of. Quality holds at 8 bits, dips slightly at 4, and cliffs below.
- Speculative decoding has a small model guess several tokens and the big
  model verify them in one pass. Output distribution is unchanged; speed
  doubles on predictable text.
- Batching shares one weight-read across many users' decode steps. It's why
  throughput is high, why your latency depends on load, and why batch APIs
  are cheap.
- The price list is these mechanisms, priced.

Next: the one capability that looks like it needs a different brain.

*[Next: Chapter 18 — Seeing and Hearing: Multimodal](18-multimodal.md)*
