# Chapter 5: Attention: A Soft Lookup

*LLMs 101, Part I — One Function.
[Series index](index.html) · [Prev](04-before-attention.md) ·
[Next: The Patches Around Attention](06-the-patches-around-attention.md)*

---

**The failure:** chapter 4 ended with a demand. Every position in the
sequence must be able to look at every earlier position, decide for itself
which ones matter, and pull information from them, all in one parallel
step with no recurrence. That sounds like it should need something
elaborate.

It needs a dictionary with soft edges. Here's the whole mechanism:

> **Attention is a lookup.** Every token asks a question (its **query**),
> every token advertises what it holds (its **key**), and every token
> carries a payload (its **value**). A token's output is the weighted
> average of all the values it's allowed to see, weighted by how well its
> query matches each key. That's it. Everything else in this chapter is
> making those three sentences precise.

I resisted this for a while because the word "attention" sounds
psychological, as if the model is *paying attention*. It isn't doing
anything of the kind. It's doing a database join where the match is a dot
product instead of an equality test. Once I saw it as a lookup, the
transformer stopped being mysterious.

## Hard lookup, then soft lookup

You know what a hard lookup is. A Python dict: give it a key, it finds the
one entry whose key is *exactly* equal, and returns that entry's value.
Nothing else contributes.

Now loosen two things. First, let a query match every key *a bit*, with a
score for how well it matches. Second, instead of returning one value,
return a blend of all the values, weighted by those scores. A query that
strongly matches one key gets mostly that key's value. A query that half
matches two keys gets half of each. That's a **soft lookup**, and it has a
property the hard version lacks: it's made of multiplications and
additions, so it can be run on a GPU and trained by gradient descent
(chapter 8). You can't differentiate a dict. You can differentiate a
weighted average.

The last piece is where the keys, queries and values come from. In
attention, every token produces all three from its own embedding, by
multiplying it with three learned matrices. A token *is* simultaneously a
question, an advertisement, and a payload. The learned matrices decide
what kind of question each token asks and what it offers in reply.

## The code

Here is causal self-attention, complete, from
[`gpt/v2_attention.py`](https://github.com/IsuruMaduranga/harness-engineering-101/blob/main/llms-101/src/gpt/v2_attention.py):

```python
import numpy as np

def softmax(x, axis=-1):
    x = x - x.max(axis=axis, keepdims=True)
    e = np.exp(x)
    return e / e.sum(axis=axis, keepdims=True)

def attention(x, Wq, Wk, Wv):
    """x: (T, d) one row per token. Returns (T, d_v)."""
    T = x.shape[0]
    Q, K, V = x @ Wq, x @ Wk, x @ Wv                # what I want / what I have / what I carry
    scores = Q @ K.T / np.sqrt(K.shape[1])          # (T, T): how well each query matches each key
    mask = np.triu(np.ones((T, T)), k=1).astype(bool)
    scores[mask] = -np.inf                          # no looking at the future
    weights = softmax(scores)                       # each row sums to 1
    return weights @ V, weights                     # weighted average of values
```

Line by line, with `x` being a matrix of `T` token vectors, one per row:

1. **`Q, K, V = x @ Wq, x @ Wk, x @ Wv`.** Three matrix multiplies turn
   each token's vector into a query, a key and a value. The three `W`
   matrices are the learned part. Everything below this line has no
   parameters at all.
2. **`scores = Q @ K.T`.** Every query dotted with every key. The result
   is a `T × T` grid: row *i* holds how well token *i*'s question matches
   each token's advertisement. A dot product is large when two vectors
   point the same way, so "matches well" means "points the same way in the
   learned space."
3. **`/ np.sqrt(d)`.** Dot products of longer vectors are bigger on
   average, just because there are more terms. Big scores make the softmax
   in step 5 nearly one-hot, which kills the gradient during training.
   Dividing by the square root of the vector length keeps the scores in a
   sane range. This is a plumbing detail, and it's the only piece of the
   original paper's formula that people find mysterious.
4. **`scores[mask] = -np.inf`.** The **causal mask**. Set every score
   where the key position is *after* the query position to negative
   infinity. After the softmax those become exactly zero. A token can look
   at itself and at the past, never at the future. This is what makes the
   model a *next*-token predictor rather than a fill-in-the-blank model.
   It's also why you can train on a whole sequence at once: every
   position's prediction is legitimately made from only what came before
   it.
5. **`weights = softmax(scores)`.** Turn each row of scores into
   probabilities: all positive, summing to one. Now row *i* says what
   fraction of token *i*'s output should come from each earlier token.
6. **`weights @ V`.** The blend. Each token's output is the weighted sum of
   the values it attended to.

That's the one equation in this book that's worth seeing written as an
equation, because you'll meet it everywhere:

> softmax(QKᵀ / √d) · V

Run the file with five random tokens and print the weights:

```
attention weights (row = query position, col = key position):
[[1.   0.   0.   0.   0.  ]
 [0.98 0.02 0.   0.   0.  ]
 [0.51 0.24 0.25 0.   0.  ]
 [0.31 0.22 0.33 0.14 0.  ]
 [0.45 0.01 0.22 0.04 0.27]]
```

Read it. Token 0 can only see itself, so its row is `1.0` and zeros. Token
4 spreads itself over five positions, but leans on token 0 and token 2 and
nearly ignores token 1. The upper-right triangle is all zeros: the causal
mask. Each row sums to one. With random matrices the pattern is
meaningless; after training, rows like these are where "the verb attends
to its subject" lives, and you can look at them in a real model (chapter 7
does).

## What "self" means, and what the alternative was

This is **self**-attention because queries, keys and values all come from
the same sequence. The tokens are looking up each other. In the original
2017 paper there was also **cross**-attention: the queries came from the
output sentence being written, the keys and values from the input sentence
being translated. Same code, different `x` for the K and V side. GPT-style
models dropped the encoder half and with it cross-attention, so if you're
here to understand LLMs you can file "cross-attention" under
translation-era history. Everything in a modern decoder-only model is
self-attention over one sequence: the prompt and the generated text,
together.

## What it costs

Look at step 2 again. The score grid is `T × T`. Double the sequence
length and you quadruple the work and the memory for that grid. This is
the famous **quadratic cost of attention**, and it's the direct reason
context windows have a limit and why the industry spent years on tricks to
push the limit up. Chapter 14 is about that bill. For now: the lookup is
cheap per pair, but every token looks at every token, and that's a lot of
pairs.

The good news is what the cost buys. Every operation in the code above is
a matrix multiply or an elementwise function over a whole matrix. There is
no loop over positions. All `T` tokens compute their lookups in the same
instant, which is exactly what a GPU wants and exactly what the RNN
couldn't offer. The transformer didn't win because attention is smarter
than recurrence. It won because attention is *parallel*, so you could
train it on a hundred times more text in the same wall-clock time. Scale
did the rest (chapter 9).

## What one lookup can't do

The `attention` function above is the heart of a transformer, and on its
own it's nearly useless. Three things are missing, and each is a patch in
chapter 6:

- **It doesn't know where anything is.** Shuffle the rows of `x` and the
  outputs shuffle identically; nothing in the code depends on position.
  "Dog bites man" and "man bites dog" produce the same lookups. Order was
  free in the RNN (it read tokens in sequence) and deleting the RNN lost
  it. It has to be put back.
- **It's one kind of question.** A single set of `Wq, Wk, Wv` learns one
  notion of relevance. Real text needs several at once: who is the
  subject, what did the previous sentence refer to, which bracket is this
  closing. The fix is to run several small attentions side by side.
- **It moves information; it doesn't store any.** Attention shuffles
  values between positions. It has nowhere to keep the fact that Paris is
  the capital of France. That knowledge lives in a different, duller
  layer that sits right after attention in every block.

## What you now know

- Attention is a soft lookup: queries dotted with keys give match scores,
  a softmax turns scores into weights, the weights blend the values.
- Queries, keys and values are all made from the same token vectors by
  three learned matrices. The rest of the mechanism has no parameters.
- The causal mask zeroes out the future. That's what makes it a
  next-token predictor and what lets you train on every position of a
  sequence at once.
- The cost is quadratic in sequence length. The payoff is that every
  position is computed in parallel, which is why transformers could be
  scaled and RNNs couldn't.
- One attention alone knows no order, asks one question, and stores no
  facts. Chapter 6 patches all three.

*[Next: Chapter 6 — The Patches Around Attention](06-the-patches-around-attention.md)*
