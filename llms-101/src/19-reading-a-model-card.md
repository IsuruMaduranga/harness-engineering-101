# Chapter 19: Reading a Model Card

*LLMs 101, Part IV — Decoder Ring.
[Series index](index.html) · [Prev](18-multimodal.md) ·
[Next: The Snake Eats Its Tail](20-the-snake-eats-its-tail.md)*

---

**The failure this chapter patches is in you:** the model release
announcement. A name like `Llama-3.1-70B-Instruct-Q4_K_M`, a table of
benchmark scores, a paragraph about "state-of-the-art reasoning," and a
context length with six zeros. It's designed to be read by people who
already know what each token in the name means, and after eighteen
chapters you're one of them. This chapter is the decoder ring: every noun
on a model card, what it is underneath, and where you built it.

The body book had a chapter like this for frameworks, and the lesson was
the same: nothing on the card is new. It's a list of choices from the
chapters you've read.

## Parsing the name

`DeepSeek-R1-Distill-Qwen-7B`, read left to right:

| Piece | Meaning | Chapter |
|---|---|---|
| `DeepSeek` | the lab that did the *post*-training | 10, 11 |
| `R1` | a reasoning model: RL-trained to think before answering | 11 |
| `Distill` | a small student trained on the big model's outputs | 12 |
| `Qwen` | the *base* model's lab; this is someone else's pretrained weights, fine-tuned | 9, 12 |
| `7B` | seven billion parameters, all active (dense) | 6, 16 |

And `Mixtral-8x22B-Instruct-v0.1-AWQ`:

| Piece | Meaning | Chapter |
|---|---|---|
| `8x22B` | mixture of experts: 8 experts of 22B each, shared attention; ~141B total, ~39B active | 16 |
| `Instruct` | post-trained to follow instructions (as opposed to a `base` model that only continues text) | 10 |
| `AWQ` | 4-bit quantization, a specific recipe | 17 |

The habit: every hyphen-separated piece is one decision from Part I, II or
III.

## The decoder ring

| The card says | What it is underneath | Where you built it |
|---|---|---|
| Parameters, "7B", "405B" | the count of floats in the weight dictionary | ch. 6, 7 |
| Active parameters | how many of those a single token touches; the cost driver | ch. 16 |
| Dense / MoE | one MLP per block, or many with a router | ch. 16 |
| Layers, hidden size, heads | how many blocks, how wide the residual stream, how many parallel lookups | ch. 6 |
| GQA, "8 KV heads" | fewer key/value heads than query heads, to shrink the cache | ch. 13 |
| RoPE, "rope theta" | rotary position encoding and how slowly it rotates (bigger = longer context) | ch. 6, 14 |
| SwiGLU, RMSNorm | the modern MLP and norm variants | ch. 6, 7 |
| Vocabulary size, "128k vocab" | how many BPE merges; bigger is fairer to non-English and costs embedding parameters | ch. 2, 3 |
| Context length | the longest position trained; hard edge | ch. 14 |
| Training tokens, "15T" | how much text pretraining saw; compare to parameters for the memorisation story | ch. 9 |
| Knowledge cutoff | when the crawl stopped | ch. 9 |
| Base | pretrained only; continues text | ch. 9 |
| Instruct / Chat | supervised fine-tuning plus preference tuning | ch. 10 |
| Reasoning / thinking / "R1", "o-series" | RL on verifiable tasks; emits thinking tokens | ch. 11 |
| "Distilled" | trained to imitate a larger model's outputs | ch. 12 |
| Q4_K_M, GPTQ, AWQ, FP8, "GGUF" | quantization recipes and file formats | ch. 17 |
| Multimodal, "vision" | a patch encoder and projector feeding the same sequence | ch. 18 |
| Tokens per second, TTFT | decode speed (bandwidth-bound) and prefill time | ch. 13 |
| Temperature, top-p defaults | the serving layer's picker settings | ch. 15 |
| Function calling, JSON mode, "structured outputs" | tool-format training plus constrained decoding | ch. 11, 15 |

If a term isn't in the table, it's usually a marketing word for one that
is. "Frontier," "flagship," "mini" and "flash" are sizes. "Omni" is
multimodal. "Turbo" is a cheaper serving configuration of the same
weights. "Preview" means the post-training isn't finished.

## Open weights versus open source

A card that says "open" almost always means **open weights**: you can
download the dictionary of floats and run it, under a license. It nearly
never means you get the training data, the data pipeline (chapter 9's
secret), or the training code. You can fine-tune it (chapter 12), quantize
it (chapter 17), and serve it, but you can't reproduce it, and you can't
audit what it read. The license matters too: several "open" licenses forbid
commercial use above a user threshold or in certain domains. Read the
license, not the adjective.

## Benchmarks, and how to read a table of them

Every card has a table of scores, and the scores are less informative than
they look. Here's what each common one measures and what it doesn't:

| Benchmark | What it tests | The catch |
|---|---|---|
| MMLU | multiple-choice questions across 57 subjects | contamination: the questions are on the internet and in the training data. Near-saturated. |
| GSM8K, MATH | grade-school and competition maths | the same contamination, plus chain-of-thought dependence: scores depend on how many thinking tokens were allowed (ch. 11) |
| HumanEval | write a Python function to pass tests | small, old, memorised. SWE-bench (fix a real GitHub issue) is the harder successor and depends heavily on the harness used to run it |
| Needle in a haystack | find one sentence in a long context | measures the edge, not the slope (ch. 14) |
| Chatbot Arena / human preference | which reply do people prefer, blind | rewards the same things RLHF does: confidence, length, formatting (ch. 10). A style, not a capability. |

Two structural problems apply to all of them. **Contamination**: any
benchmark public long enough is in the pretraining data, and a model can
score well by recall. Labs decontaminate and the process is imperfect.
**Configuration**: a reasoning model's score depends on its thinking
budget, and a coding score depends on the agent harness around it, so two
numbers on two cards are rarely measured the same way. Treat a benchmark
table as a rough ordering within one lab's releases, and run your own task
before believing a comparison across labs.

## Five questions for any new model

The skill this book was actually teaching. When the next model arrives,
you don't need to learn it. Ask:

1. **How many active parameters, and dense or MoE?** That's the cost per
   token and the knowledge capacity (chapters 9, 16).
2. **What did post-training do?** Base, instruct, or reasoning; how much
   RL; on what tasks. That's the behaviour (chapters 10, 11).
3. **What's the context, and how was it measured?** The trained length, the
   needle score, and, if you're lucky, a multi-fact or reasoning score at
   length (chapter 14).
4. **What does the tokenizer do to my text?** Tokenize a real sample. For
   non-English and code this changes the price and the quality (chapter 2).
5. **What's the output-to-input price ratio, and does it cache?** That
   tells you the serving setup and whether the body book's array
   discipline will pay off (chapters 13, 17).

Five answers locate any model on the map you now carry. Nothing in the
announcement will be outside it, except one claim that isn't about a model
at all, and that gets its own chapter.

## What you now know

- A model name is a list of decisions: base lab, size, dense or MoE,
  post-training type, quantization. Each is a chapter.
- Every technical term on a card maps to one mechanism in this book. The
  decoder ring above is the whole vocabulary.
- "Open" means open weights, not open data or code. Read the license.
- Benchmarks are contaminated and configuration-dependent. Use them for
  rough ordering; measure your own task.
- Five questions locate any new model. Ask them instead of reading the
  adjectives.

*[Next: Chapter 20 — The Snake Eats Its Tail: Harnesses Training Brains](20-the-snake-eats-its-tail.md)*
