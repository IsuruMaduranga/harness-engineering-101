# Epilogue: Train Your Own

*LLMs 101.
[Series index](index.html) · [Prev](20-the-snake-eats-its-tail.md) ·
[Appendix A](appendix-a-backprop-by-hand.md)*

---

Twenty chapters ago I claimed that an LLM is one function and that
everything else is how it's built, taught, or run. The honest way to close
is to put the whole function on the table. This is
[`gpt/gpt.py`](https://github.com/IsuruMaduranga/harness-engineering-101/blob/main/llms-101/src/gpt/gpt.py):
230 lines, every mechanism from the series, trainable on a laptop in three
minutes, on the text of the book that came before this one.

```bash
cd src/gpt
python3 make_corpus.py                 # the harness book -> corpus.txt
python3 gpt.py train                   # ~3 min on a laptop CPU -> gpt.pt
python3 gpt.py generate "The harness" --temperature 0.8 --top-p 0.9
```

It is a toy, deliberately. Four blocks, 128-dimensional vectors, 809,216
parameters, a 128-token window, and a training set two hundred thousand
times smaller than a real one. It has no rotary embeddings, no mixture of
experts, no flash attention, no quantization. But every organ is present,
real, and small enough to hold the whole organism in your head, which no
production model will ever again allow you to do. That is what makes it
worth studying.

## The anatomy, block by block

Every block comment in the file carries its chapter number, so this table
is also the file's map:

| Lines (about) | Block | Chapter | The one-line reason it exists |
|---|---|---|---|
| config | `VOCAB, BLOCK, N_LAYER, N_HEAD, N_EMBD, N_KV_HEAD` | 2, 6, 13, 14 | every model card's numbers, in six constants |
| `Tokenizer` | byte-pair encoding: train, encode, decode | 2 | the model sees integers, never letters |
| `Attention` | Q from every head, K and V from fewer, a cache, a causal mask, softmax, blend | 5, 6, 13 | the soft lookup, with grouped-query K/V so the cache is half size |
| `Block` | norm, attend, add; norm, MLP, add | 6 | move information, then look up facts; add, don't replace |
| `GPT` | embed what and where, blocks, norm, unembed with the same table | 3, 6, 7 | the eight-line spine |
| `pick` | temperature, top-k, top-p | 15 | the picker lives outside the model |
| `generate` | prefill the prompt once, then decode one token at a time against the cache | 13 | why output tokens cost more |
| `train` | batches shifted by one, cross-entropy, backward, step; keep the best-validation checkpoint | 8, 9 | measure surprise, nudge, stop before memorising |

A few details reward a second look, because they're where chapters
intersect in one line:

- **`keep = probs.cumsum(0) - probs < top_p`** is all of nucleus sampling.
  One comparison decides which tail of the distribution the model is
  allowed to fall into.
- **`if len(out) >= BLOCK: break`** is the context window. The position
  table has 128 rows; there is no row 129. Every "context length" on every
  model card is this line with a bigger number.
- **`N_KV_HEAD = 2`** with `N_HEAD = 4` is grouped-query attention in one
  constant. Set it to 4 and the cache doubles; set it to 1 and you have
  multi-query attention. The `repeat_interleave` two lines later is the
  entire mechanism.
- **The checkpoint is saved when validation improves, not at the end.**
  The final weights, after 1,500 steps, have memorised the book (training
  loss 0.35, validation 5.5). The saved weights, from step 600 (validation
  3.49), are the ones that generalise. Chapter 8's chart, enforced in code.

## What it writes

Sampled from the best checkpoint, temperature 0.8, top-p 0.9:

```
The harness
[Compectree`](https:///github.com/IsuruMaduranga/harness-engineering-engineering-101/
bresrc/blob/main/src/harness-engineering-engineering-10101/blob/main/src/src/harness/
harness/v2_agent.py]
```

```
The LLM is the brain.

*[Series index](index.html) · [Prev](04-the-body.md) ·
[Next: Loop](07-subagents.md) ·
[Next: LangGuaring-Guargineering.md) ·
```

And greedily, temperature 0:

```
The harness is authority worth.
- **Tools.** The body is allows.** The brain cannot tells.
- **Sixes**: the body is about the brain can re
```

Look at what 809,216 parameters and 600 steps learned. That a chapter
opens with a navigation line of the form `*[Series index](index.html) ·
[Prev](...) · [Next: ...](...)*`. That code links go to a GitHub URL
beginning `https://github.com/IsuruMaduranga/harness-engineering-101/blob/main/src/`.
That bullets are bold-led. That "the body" and "the brain" are the nouns
this book uses. It has never seen a link it can reproduce correctly, so it
produces plausible ones: `v2_agent.py` doesn't exist, but `v2_tools.py` and
`v3_agent.py` do, and the model has blended them. That is a hallucination,
mechanically, in a model small enough to see it happen: chapter 9's
"plausible continuation is what the loss rewards," on a corpus of 83,000
tokens.

## Exercises

The file is the textbook; these are the problem sets. Each one is a real
property of production models, sized for an evening:

1. **Break the causal mask** (ch. 5). Delete the `masked_fill` line and
   retrain. Training loss collapses toward zero within a hundred steps,
   because every position can now see the token it's meant to predict. Then
   try to generate with it. You've built a model that cheats on its exam
   and can't write a sentence, and you've seen why the mask is what makes
   it a *next*-token predictor.
2. **Move the memorisation point** (ch. 8, 9). Halve `N_EMBD` and retrain;
   watch the best-validation step move later and the best loss get worse.
   Then swap `corpus.txt` for something ten times bigger (your own notes,
   a public-domain novel) and watch it move again. You're tracing the
   scaling-law logic by hand.
3. **Size the cache** (ch. 13). After a `generate`, sum the sizes of the
   tensors in `caches`. Then set `N_KV_HEAD = 4` and `= 1` and measure
   again. Compute what the same ratios would mean for an 80-layer,
   8,192-wide model at 100,000 tokens.
4. **Watch temperature do its job** (ch. 15). Generate twenty samples each
   at temperature 0.3, 0.8 and 1.5 from the same prompt and count distinct
   first words. Then add a repetition penalty to `pick` and see what it
   does to the markdown bullets.
5. **Constrain the output** (ch. 15). In `pick`, zero the probability of
   every token whose bytes aren't valid inside a markdown link, and force
   the model to write nothing but links. It will, and they'll all be
   plausible and wrong, which is the whole structured-output trade in one
   run.
6. **Add rotary positions** (ch. 6, 14). Replace `wpe` with a rotation of
   `q` and `k` by an angle proportional to position. Then generate past
   128 tokens, which the learned table couldn't do at all, and see how far
   the quality holds before it decays.
7. **Load the real thing** (ch. 7). Set the constants to 12 layers, 12
   heads, 768 wide, a 50,257 vocabulary and a 1,024 window, use
   `N_KV_HEAD = 12`, and write a loader that maps the safetensors names
   from `v3_forward.py` onto this class (the linear weights are transposed
   relative to PyTorch's convention). The same 230 lines, minus the
   trainer, now run GPT-2.

## Where this leaves you

Two books, one loop. *Harness Engineering 101* said: an agent is a program
that maintains a JSON array and loops. This one said: the thing reading
the array is a function from tokens to probabilities, built from a lookup
table and a stack of identical blocks, taught by nudging its numbers toward
less surprise, and run with a cache and a picker. Chapter 20 closed the
circle: the array is now also where the next function's training signal
gets made. Between the two books there is no gap left for magic to hide
in, and no gap between them either.

The next model announcement will arrive on schedule, with a new name and a
new adjective. You now have the questions. How many active parameters? What
did post-training do? How long is the context, and measured how? What does
the tokenizer do to my text? What's the output-to-input price ratio? Ask
them, and the adjective dissolves into a row of chapter 19's table.

Then build something with it. That's what the body book is for.

*[Appendix A — Backprop by Hand](appendix-a-backprop-by-hand.md) ·
[Series index](index.html)*
