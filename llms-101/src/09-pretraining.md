# Chapter 9: Pretraining: Compression of the Internet

*LLMs 101, Part II — Growing the Brain.
[Series index](index.html) · [Prev](08-loss-and-gradient-descent.md) ·
[Next: Post-training](10-post-training.md)*

---

**The failure:** the toy from chapter 8 learned the harness book's rhythm
and none of its meaning, and after five hundred steps it stopped learning
and started memorising. A model with 875,000 parameters and 82,000 training
tokens can't do anything else. Here's the conclusion this chapter builds
to:

> **Pretraining is chapter 8's loop, run on trillions of tokens of text
> with billions of parameters, for months.** Nothing about the algorithm
> changes. What changes is that at that scale, the cheapest way to lower
> the loss is to actually learn the structure of language, code, and the
> world, because there's too much text to memorise. The result is a
> compressed copy of the training data's regularities. That compression is
> where the knowledge lives, and its nature explains why models
> hallucinate, why they have a cutoff, and why "bigger" kept working.

In the body book I described this stage in a paragraph and called the
result "a raw pattern-completion engine." This chapter is what I'd have
written if I'd known then what a loss curve looks like at scale.

## Scale, in numbers you can feel

Put the toy and a real model side by side:

| | Toy (chapter 8) | GPT-2 small (2019) | A 2024 open model (Llama 3 8B) |
|---|---|---|---|
| Parameters | 875 thousand | 124 million | 8 billion |
| Training tokens | 82 thousand | roughly 10 billion | 15 trillion |
| Tokens per parameter | 0.1 | ~80 | ~1,900 |
| Hardware | a laptop CPU | dozens of GPUs | thousands of GPUs (16,000 for the 405B sibling) |
| Wall clock | 5 minutes | weeks | weeks to months |

Look at the tokens-per-parameter row. The toy had one training token for
every ten parameters, which means it had ten knobs to spend on remembering
each token. Of course it memorised. Llama 3 8B saw nearly two thousand
tokens per parameter. There is no way to store two thousand tokens in one
floating-point number. The only way to keep lowering the loss is to find
things that are *true across* thousands of examples: how English grammar
works, how a Python function is shaped, that the word after "capital of
France is" tends to be "Paris." Generalisation isn't something added to
training. It's what memorisation turns into when the data is too big to
memorise.

The compute is easy to estimate and worth doing once. Training costs about
six floating-point operations per parameter per token (two for the forward
pass, four for the backward). For Llama 3 405B on 15 trillion tokens:

> 6 × 405 × 10⁹ × 15 × 10¹² ≈ 4 × 10²⁵ operations

A modern GPU does about 10¹⁵ per second at these precisions. That's
4 × 10¹⁰ GPU-seconds, or 16,000 GPUs running flat out for about a month,
before any of the inefficiency that shows up in real clusters. This is why
frontier pretraining is a capital project rather than an experiment, and
why so few organisations do it.

## Scaling laws: "bigger" was a measurement, not a bet

The reason anyone spent that money is that in 2020 researchers at OpenAI
plotted loss against model size, data size and compute, on log axes, and
got straight lines. Double the parameters, the loss falls by a predictable
amount. Double the data, likewise. The lines held over seven orders of
magnitude. This is the **scaling law** result, and its significance is
easy to miss: it turned "build a bigger model" from a hope into an
engineering forecast. You could plot where a model ten times larger would
land before building it, and it landed there.

A 2022 follow-up from DeepMind, the **Chinchilla** paper, refined the
recipe: for a fixed compute budget, the loss-minimising choice is roughly
20 tokens per parameter. Models before it were undertrained on data. Models
after it swung the other way, on purpose: Llama 3's 1,900 tokens per
parameter is far past the compute-optimal point, because a smaller model
trained on more data is cheaper to *run*, and running cost matters more
than training cost once millions of people are using it. When you see a
small model that's surprisingly good, that's usually why: someone paid
extra at training time to save at inference time (Part III).

## What's in the data, and why that's the secret

"Trained on the internet" is roughly true and hides where the work is.
The raw material is web crawls (Common Crawl is the public one), code from
GitHub, books, papers, and licensed text. The real engineering is what's
done to it before training: stripping boilerplate and navigation menus,
detecting and removing duplicate documents (duplicates are the memorisation
problem again, in miniature), filtering out spam and machine-generated
junk, choosing the mix of code to prose to other languages, and deciding
what to leave out. Two labs with the same architecture and the same compute
get different models from different data pipelines, and the pipelines are
the part nobody publishes in detail.

Two consequences follow directly. The **knowledge cutoff**: the crawl
stopped on some date, so anything after it is not in the weights and must
arrive through the prompt (this is the whole premise of retrieval, body
book chapter 15). And the **data mix decides the personality**: a model
trained on lots of code is better at code; a model trained on little
Sinhala is bad at Sinhala, for the tokenizer reason in chapter 2 and the
data reason here, compounding.

## Why it hallucinates, mechanically

Now the question the body book could only assert. Look at the loss from
chapter 8 again: it's the model's surprise at the actual next token. It is
minimised by assigning high probability to whatever text is *likely*, and
nothing in that number knows or cares whether the text is *true*.

Consider what happens at training time when the text says "the capital of
Australia is Canberra." The model is rewarded for predicting "Canberra."
Now consider text about some obscure town's mayor. The model has seen the
pattern "the mayor of X is [Name]" a million times and the specific name
zero times. The lowest-loss move is to output *a plausible name*, because
that's what the data does: it names the mayor. "I don't know" almost never
appears in that slot in web text, so predicting it would be *high loss*. The
model learns, correctly for its objective, that confident specific
continuation is what text looks like.

That's a hallucination, and it's the training goal working as designed.
There's no separate "lying" behaviour to remove. Post-training (chapter
10) can teach the model to say "I'm not sure" more often, and that helps
a lot, but it's a learned override on top of a pretraining prior that
always wants to complete the pattern. This is why the body book's rule
holds mechanically, not just empirically: **feed the model facts through
the prompt instead of trusting its recall.** Text in the context window is
attended to directly (chapter 5). Facts in the weights are reconstructed
from a compression, and compressions have artefacts.

## Memorisation at scale: what actually gets remembered

The toy memorised its whole corpus because it saw every token thirty
times. A frontier model sees most of its data roughly once, so it can't
memorise most of it. What it *does* memorise is anything that appears many
times across the web: famous quotes, song lyrics, the MIT license, popular
code snippets, the opening of well-known books, the exact phrasing of
frequently copied news articles. That's the mechanism behind the
regurgitation cases in the copyright lawsuits, and behind the amusing fact
that models can recite `pip install` instructions perfectly but paraphrase
a novel they've only seen once. Deduplication in the data pipeline is
partly an attempt to control this.

## What a pretrained model can do

At the end of pretraining you have a **base model**: the function from
chapter 1, very well trained, and nothing else. Give it text and it
continues the text. It has no idea it's supposed to answer questions. Ask
"What is the capital of France?" and a plausible continuation is another
question, because the web is full of quiz pages.

But something important appeared at scale that the toy never showed.
Because the training data is full of *patterns inside documents* (lists,
tables, question-answer pairs, examples followed by more examples), the
model learned to detect a pattern in its input and continue it. Show a
base model three examples of English-to-French translation and it will
translate a fourth, having never been trained to translate. This is
**in-context learning**, the surprise result of GPT-3 in 2020, and it's
the seed of everything in the body book: a prompt can *program* the model,
temporarily, without touching the weights. Post-training makes the model
want to be programmed that way. Pretraining is where it became able to.

## What you now know

- Pretraining is gradient descent on next-token loss, at a scale where
  memorising is impossible and learning general structure is the only way
  down. About 6 × parameters × tokens operations; months on thousands of
  GPUs.
- Scaling laws made "bigger" a forecast. Chinchilla set a compute-optimal
  ratio around 20 tokens per parameter; modern models deliberately overshoot
  it to be cheaper to run.
- The data pipeline (filtering, deduplication, mix) is where labs differ.
  The cutoff and the language skew come straight from it.
- Hallucination is the objective working correctly: plausible completion is
  rewarded and "I don't know" is rare in the data. Retrieval works because
  attended text beats reconstructed memory.
- The output is a base model that continues text and can pick up patterns
  from its prompt. It is not yet an assistant.

Next: the short, cheap stage that turns a document-continuer into
something that answers you, and why the JSON array you send an API is
secretly a text file with a few special tokens in it.

*[Next: Chapter 10 — Post-training: From Autocomplete to Assistant](10-post-training.md)*
