# LLMs 101: Inside the Brain

*The harness is the body. This is the brain.*

*By [Isuru Wijesiri](https://isuruwijesiri.com). Version 1.0 — September 2026.*

Everyone talks about large language models like they're a new kind of
physics: attention, transformers, 175 billion parameters, RLHF, mixture of
experts, reasoning models, 1M-token context windows. Stack enough of those
words together and it sounds like there's a machine underneath that only
people with a PhD are allowed to understand.

There isn't. Here's the whole thing:

> An LLM is one function: a sequence of tokens in, a probability for every
> possible next token out. Everything the field talks about is one of three
> things: how that function is **built** (the transformer), how it was
> **taught** (training), or how it is **run** (inference). Every part of each
> was added because something concrete failed, and none of it is magic.

I came at this from the outside. In [Harness Engineering
101](https://isuruwijesiri.com/harness-engineering-101/) I wrote about the
*body*: the program that wraps a model in a loop and gives it hands. I spent
a chapter there calling the model a black box and moving on, because for
building the body that was enough. But the body kept raising questions the
box wouldn't answer. Why is the order of my prompt load-bearing for the
bill? Why does an output token cost five times an input token? Why does the
model hallucinate in a way no prompt can fix? Why does it emit valid JSON
for a tool call it has never seen? Every one of those questions had a
mechanical answer one level down, and every answer turned out to be simpler
than the word for it.

So this series opens the box. It has the same shape as the last one: here's
the failure, here's the minimal patch, here's what the patch costs you. A
toy GPT in plain NumPy grows alongside the text, and in chapter 7 it loads
the real GPT-2 weights and writes English, with no framework anywhere in the
file. By the epilogue you'll have trained your own small model on a laptop
in a few minutes and you'll know what every line does. The full source is
on
[GitHub](https://github.com/IsuruMaduranga/harness-engineering-101/tree/main/llms-101).

Learn the parts in the order they were invented, as fixes to real failures,
and none of it is complicated. No equations you can't read aloud, no
framework, no buzzword tour.

## Reading order

Every chapter opens with a question the body book left dangling, and closes
having answered it. If you haven't read *Harness Engineering 101* that's
fine; the questions stand on their own.

### Part I — One Function (nothing is magic)

| # | Chapter | The failure it patches | The body-book question it answers |
|---|---------|------------------------|-----------------------------------|
| 1 | [It's Just Next-Token Prediction](01-its-just-next-token-prediction.md) | "What is on the other end of the POST?" | What the black box is. A counting table already generates text. |
| 2 | [Tokens](02-tokens.md) | Characters are too many, words are too few | Why everything is priced and limited in tokens |
| 3 | [Embeddings](03-embeddings.md) | A counting table can't generalise | Why RAG embeddings are the same idea, pointed at search |
| 4 | [Before Attention](04-before-attention.md) | Fixed windows, forgetting, no parallelism | Why "context window" is even a concept |
| 5 | [Attention: A Soft Lookup](05-attention.md) | The model must look back at anything, all at once | How the model "sees" the whole array |
| 6 | [The Patches Around Attention](06-the-patches-around-attention.md) | Deleting the RNN lost word order; one lookup isn't enough; depth breaks training | The "Attention Is All You Need" chapter |
| 7 | [The Whole Transformer in 200 Lines](07-the-whole-transformer.md) | "Surely there's more to it" | The black box, opened, running real weights |

### Part II — Growing the Brain (training)

| # | Chapter | The failure it patches | The body-book question it answers |
|---|---------|------------------------|-----------------------------------|
| 8 | [Loss and Gradient Descent](08-loss-and-gradient-descent.md) | The weights have to come from somewhere | What "trained" means, mechanically |
| 9 | [Pretraining](09-pretraining.md) | A laptop-trained toy is gibberish | Why it knows things, why it hallucinates by design, why the cutoff exists |
| 10 | [Post-training](10-post-training.md) | "Capital of France?" continues with "Capital of Germany?" | The JSON array is a plain string with special tokens. Why roles have authority. |
| 11 | [RL and Reasoning](11-rl-and-reasoning.md) | An assistant that answers is not one that reasons or acts | Why tool JSON comes out valid, why thinking works |
| 12 | [Changing a Brain Cheaply](12-changing-a-brain-cheaply.md) | You want it to know or do *your* thing | When a prompt beats a fine-tune |

### Part III — Running the Brain (inference)

| # | Chapter | The failure it patches | The body-book question it answers |
|---|---------|------------------------|-----------------------------------|
| 13 | [The KV Cache](13-the-kv-cache.md) | Generating each token recomputes everything | Why order is load-bearing, why output tokens cost more |
| 14 | [Context Windows](14-context-windows.md) | The array gets long | Why there is a limit, and why "1M context" is not 1M useful tokens |
| 15 | [Sampling and Structured Output](15-sampling-and-structured-output.md) | The model gives probabilities; someone must pick | Temperature, non-determinism, guaranteed-valid JSON |
| 16 | [Mixture of Experts](16-mixture-of-experts.md) | Every parameter fires for every token | What "active parameters" means on a model card |
| 17 | [Making It Cheaper](17-making-it-cheaper.md) | The bill | Where the cost tiers come from, why latency varies |
| 18 | [Seeing and Hearing: Multimodal](18-multimodal.md) | Images aren't tokens | Why an image costs what it costs |

### Part IV — Decoder Ring

| # | Chapter | |
|---|---------|---|
| 19 | [Reading a Model Card](19-reading-a-model-card.md) | "7B", base vs instruct, open weights vs open source, benchmarks. Every noun points back to a chapter. |
| 20 | [The Snake Eats Its Tail](20-the-snake-eats-its-tail.md) | Humans ran out of text, judgement and research capacity. A model in a harness with the training stack as tools builds the next model. What has been shown, where it jams, and what "AGI" is pointing at. |

### Epilogue

| | Chapter | |
|---|---------|---|
| E | [Train Your Own](21-epilogue-train-your-own.md) | The complete toy GPT, trained on the text of *Harness Engineering 101*, generating harness prose |

### Appendix — Advanced Topics

Standalone pieces. Read them when you need them.

- [A. Backprop by Hand](appendix-a-backprop-by-hand.md) — the calculus PyTorch does for you, on a model small enough to do it yourself
- [B. Training at Scale](appendix-b-training-at-scale.md) — why it takes a datacenter: data, tensor and pipeline parallelism
- [C. Serving Systems](appendix-c-serving-systems.md) — paged attention and continuous batching: what a provider does with your request
- [D. What the Layers Seem to Do](appendix-d-what-the-layers-do.md) — interpretability intuition: induction heads, features, superposition
- [E. Life After Attention](appendix-e-life-after-attention.md) — linear attention, state-space models, and hybrids

## The toy GPT

The running example lives in
[`src/gpt/`](https://github.com/IsuruMaduranga/harness-engineering-101/tree/main/llms-101/src/gpt)
on GitHub. Each file is the previous one plus the chapter's patch:

- `gpt/v0_bigram.py` — chapter 1: a counting table that generates text
- `gpt/v1_tokenizer.py` — chapter 2: byte-pair encoding, trained from scratch
- `gpt/v2_attention.py` — chapter 5: causal attention in fifteen lines of NumPy
- `gpt/v3_forward.py` — chapter 7: the full forward pass, loading real GPT-2 weights
- `gpt/v4_train.py` — chapter 8: training on the harness book, PyTorch for autograd only
- `gpt/v5_generate.py` — chapters 13 and 15: the KV cache and real sampling
- `gpt/gpt.py` — epilogue: the whole thing in one file

Python 3.10+, NumPy for Parts I and III, PyTorch only for the training
chapters. The rule from the body book was "raw HTTP, no SDK." The rule here
is "plain matrices, no framework" everywhere the intuition lives. The
training data is the text of *Harness Engineering 101* itself: 182 KB,
which is tiny, which is the point of chapter 9.

## Out of scope

Picking a model for your product, prompt engineering, CUDA and hardware,
machine-learning theory beyond intuition, and alignment policy debates. This
series is about how the brain works, not which brain to buy.

## License

The prose is CC BY-NC-ND 4.0; the code is MIT. See [License](license.md) for
the terms.
