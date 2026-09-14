# Chapter 14: Context Windows: The Limit and the Decay

*LLMs 101, Part III — Running the Brain.
[Series index](index.html) · [Prev](13-the-kv-cache.md) ·
[Next: Sampling and Structured Output](15-sampling-and-structured-output.md)*

---

**The failure:** the array gets long. The body book spent a chapter on
treating context as a budget, and took the budget's existence on faith.
Here is where the budget comes from, and why a bigger number on the box
doesn't buy what it seems to:

> **The context window has a hard edge and a soft slope.** The edge comes
> from two places: positions the model was never trained on, and a KV cache
> that has to fit in memory. The slope comes from attention itself: softmax
> over more keys spreads weight thinner, so the model gets worse at finding
> things as the window fills, long before it hits the edge. "1M tokens" means
> the model *accepts* a million. How much of that it can *use* is a curve,
> and it's your job to know the curve.

Since GPT-2's 1,024, the number on the box has grown a thousandfold. Every
step of that growth was one of the patches below, and each one moved the
edge without flattening the slope.

## Where the hard edge comes from

**Positions.** GPT-2 has a learned table with exactly 1,024 rows (chapter
6). Token 1,025 has no row. It's not that the model does badly there; the
code indexes past the end of an array. Sine-wave positions don't crash, but
a position the model never saw in training produces vectors it never
learned to read, and quality collapses within a few hundred tokens of the
training length. Rotary embeddings (chapter 6) helped because attention
scores depend on relative distance, but a distance never seen in training
is still a distance never seen. So the edge, in every model, is roughly
"the longest sequences it was trained on," and pushing it out means
training on longer sequences, which is expensive because of the next two
paragraphs.

**Compute.** Attention's score grid is T × T (chapter 5). At 128,000 tokens
that's 16 billion scores per head per layer, and a 2019-style
implementation materialises that grid in memory. It doesn't fit. **Flash
attention** (2022) is the fix that made long contexts feasible: compute the
softmax and the weighted sum in tiles, streaming through the keys a block
at a time and never writing the full grid anywhere. The result is exactly
the same numbers (it's not an approximation) using memory that grows with
T instead of T². The compute is still quadratic, but quadratic compute on
a GPU that's no longer waiting on memory turned out to be affordable up to
a few hundred thousand tokens.

**Memory for the cache.** Chapter 13's arithmetic: megabytes per token,
gigabytes per conversation. Grouped-query attention shrank it eightfold and
that bought most of the jump from 8k to 128k. Beyond that, providers page
the cache in and out of GPU memory (Appendix C) and price long contexts
accordingly.

## Stretching the edge

Given a model trained at 8k, there are three ways to make it accept 128k,
and modern models use all three:

- **Rescale the positions.** With rotary embeddings you can slow down the
  rotation so that position 128,000 looks to the model like position
  8,000 did. It's a lie about distance, and it works surprisingly well with
  a short burst of additional training on long documents. Most "extended
  context" releases are this.
- **Look at a window, not everything.** In **sliding-window attention**
  each position attends only to the last few thousand tokens. One layer
  can't see further than that, but stacked layers can: layer 2's position
  *i* reads layer 1's outputs, which each already summarise their own
  window, so the reach grows by one window per layer. Cheap, and the model
  can no longer directly look up a token that's twenty thousand positions
  back. Several models mix full-attention layers and windowed layers to get
  most of both.
- **Train on long data.** The one that actually works, and the one that
  costs the most: continue pretraining on sequences of the target length so
  the model has genuinely seen distances that large.

None of these changes the slope.

## The slope: why quality decays inside the window

Go back to the softmax. Each query distributes exactly 1.0 of attention
weight across every key it can see. With a hundred keys, a relevant one
might get 0.3. With a hundred thousand keys, the same query, wanting the
same one token, has to fight off 99,999 others that each get a small
positive weight, and the relevant one might get 0.003. The blend that comes
out is mostly noise from everywhere else. Nothing broke; the mechanism is
doing what it does with more inputs. But the signal-to-noise ratio of
every lookup falls as the context grows, and stacked layers compound it.

The measurable consequences have names:

**Lost in the middle.** Put a fact at the start, middle or end of a long
context and ask about it. Accuracy is high at the start (where the model
was trained to expect instructions), high at the end (nearest to the
question, and recency is a strong learned prior), and lowest in the middle.
The curve is a U, and it's why the body book's advice to put the
important thing first *and repeat it last* has a mechanical basis.

**Attention sinks.** Look at the right-hand heatmap in chapter 7 again:
nearly every position puts a large weight on the very first token, `The`,
regardless of what it is. That's not the model finding `The` relevant.
It's the softmax needing somewhere to dump weight when a head has nothing
useful to look at: every row must sum to one, and the first token, visible
to everyone, becomes the drain. Models learn to use position zero this
way, which has a practical consequence: throw away the first few tokens of
a long conversation to save space and quality drops off a cliff, because
you've removed the sink. Keep the head of the array.

**Needle-in-a-haystack, and what it doesn't measure.** The standard
long-context benchmark hides one sentence in a long document and asks for
it. Modern models pass at 100% across the whole window, and the results
get printed on the box. But finding one distinctive sentence is the
*easiest* possible long-context task: it's one lookup with a very sharp
key. Ask the model to find five related facts, compare them, and reason
about the differences, and accuracy at 100k tokens is well below accuracy
at 10k on every model measured. The box says the edge. Your task lives on
the slope.

## What this means for the array

The body book's chapter 6 rules now have mechanisms behind them:

- **Context is a budget, not a bag**, because every token you add dilutes
  every lookup a little. A tool result you don't need isn't free even if it
  fits.
- **Compaction improves quality, not just cost.** A summary that replaces
  twenty thousand tokens of tool output makes every subsequent attention
  sharper.
- **Instructions at the top and the live question at the bottom** is the
  U-curve, used deliberately.
- **Don't strip the front of the array.** Attention sinks.
- **Long-context cost has two terms.** Prefill is quadratic in length. The
  cache is linear in length but has to live in the scarcest memory there
  is. Both show up on the price list as a higher rate past some threshold.

## What you now know

- The hard edge is untrained positions and cache memory. Flash attention,
  grouped-query attention and rotary rescaling moved it from 1k to 1M
  tokens.
- Sliding windows trade direct long-range lookup for cheap reach; long-data
  training is the expensive fix that actually works.
- The soft slope is softmax dilution: more keys, thinner weights, noisier
  lookups. Lost-in-the-middle and attention sinks are its visible symptoms.
- Needle tests measure the edge. Your workload lives on the slope; measure
  it there.
- Every context-budget rule from the body book is a consequence of one of
  these.

*[Next: Chapter 15 — Sampling and Structured Output](15-sampling-and-structured-output.md)*
