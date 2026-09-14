# Appendix B: Training at Scale

*LLMs 101, Appendix. [Series index](index.html) · [Prev](appendix-a-backprop-by-hand.md) ·
[Next: Appendix C](appendix-c-serving-systems.md)*

---

Chapter 9 said frontier pretraining takes thousands of GPUs for months and
left it there. This appendix is why one GPU isn't enough and how thousands
are made to act as one. You'll never do this, but knowing the shape of it
explains why models cost what they cost and why they come out of a dozen
organisations rather than a thousand.

> **A model too big for one GPU's memory is split across many, in one of
> three directions: copies of the model on different data, slices of each
> matrix on different GPUs, or different layers on different GPUs. Real
> runs do all three at once, and the engineering is in keeping the GPUs
> from waiting on each other.**

## Why one GPU isn't enough: the memory arithmetic

Training a parameter costs far more memory than storing it. Per parameter,
in a standard mixed-precision run:

| What | Bytes |
|---|---|
| the weight, in 16-bit, used for the forward and backward pass | 2 |
| its gradient, 16-bit | 2 |
| a 32-bit "master" copy of the weight, so tiny updates don't round to zero | 4 |
| Adam's two running statistics (chapter 8), 32-bit each | 8 |
| **total** | **16** |

Sixteen bytes per parameter, before any activations. A 70-billion-parameter
model needs 1.1 TB just to *hold* the training state. A GPU has 80 to 192
GB. So the question isn't whether to split; it's how.

## Three ways to split

**Data parallelism.** Put a full copy of the model on each GPU. Give each a
different slice of the batch. Each computes its own gradient; then all of
them average their gradients (an operation called all-reduce, which is
what the fast interconnects between GPUs exist for) and every copy applies
the same update. This scales the batch, not the model: every GPU still
holds all 16 bytes per parameter. **Sharded data parallelism** (ZeRO,
FSDP) fixes that by having each GPU keep only a slice of the optimiser
state and master weights and fetch the rest when needed, so the 16 bytes
are divided across the group.

**Tensor parallelism.** Split each weight matrix into columns and put each
column-block on a different GPU. A matrix multiply becomes several smaller
ones followed by a gather. This shrinks per-GPU memory and per-GPU compute
in proportion, but every layer now needs a communication step, so it only
works across GPUs with a very fast link, typically the eight in one
server.

**Pipeline parallelism.** Put layers 1 to 10 on GPU one, 11 to 20 on GPU
two, and so on. A batch flows through like an assembly line. The problem
is the bubble: GPU two idles while GPU one processes the first batch, and
GPU one idles while the last batch drains. The fix is to cut each batch
into micro-batches and keep several in flight so every stage is busy most
of the time.

A real frontier run nests them: tensor parallelism within a server,
pipeline parallelism across a handful of servers, data parallelism across
the hundreds of resulting groups. The configuration is tuned per model per
cluster and is a substantial part of what a lab's infrastructure team does.

## The rest of the iceberg

**Mixed precision.** Forward and backward in 16-bit (bfloat16, a format
with the range of 32-bit and the precision of 16) for speed and memory,
with 32-bit master weights so that a nudge of one part in a million doesn't
round away. Newer hardware pushes parts of the matrix multiply to 8-bit.
This is chapter 17's quantization applied *during* training, more
carefully.

**Activation checkpointing.** Appendix A noted that backprop needs the
forward pass's intermediate values. For a long sequence through a hundred
layers that's more memory than the weights. So store only some of them and
recompute the rest during the backward pass. It trades about a third more
compute for a large memory saving, and nearly every large run uses it.

**Failures.** With ten thousand GPUs running for two months, hardware
fails daily: a GPU dies, a link drops, a node reboots. The run checkpoints
its full state every few hours to a distributed file system, and the
orchestration detects the failure, swaps in a spare, and resumes from the
last checkpoint. Public reports from large runs describe hundreds of such
interruptions. A loss spike that doesn't recover is handled the same way:
roll back and skip the bad batch.

**Throughput.** The number a lab actually tunes is model FLOPs utilisation:
what fraction of the GPUs' theoretical arithmetic is spent on the model
rather than on waiting for communication or memory. Good runs reach 40 to
50 percent. That gap, between peak and achieved, is where chapter 9's
"before any of the inefficiency in real clusters" went.

## Why this matters for the reader who won't do it

Two reasons. First, cost: chapter 9's 6 × parameters × tokens is the floor,
and everything in this appendix is the multiplier on top of it. The
multiplier is roughly two to three, and it's the difference between a
model being economically possible and not. Second, concentration: the
engineering above is hard, proprietary and expensive to learn, which is
why frontier pretraining happens in perhaps a dozen places. Everything
downstream of it (chapters 10 to 12) is accessible to far more people, and
the open-weights ecosystem exists because those dozen sometimes release
the result of this appendix for everyone else to fine-tune.

*[Next: Appendix C — Serving Systems](appendix-c-serving-systems.md)*
