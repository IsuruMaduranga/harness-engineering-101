# Chapter 3: Embeddings: Words as Coordinates

*LLMs 101, Part I — One Function.
[Series index](index.html) · [Prev](02-tokens.md) ·
[Next: Before Attention](04-before-attention.md)*

---

**The failure:** after the tokenizer, the model receives integers. Token
41236 (` strawberry`) has nothing in common with token 41237, and the
bigram table from chapter 1 had the same disease: one row per token, no
row learning anything from any other. Whatever the model learns about
` king` should help it with ` queen`. Integers can't do that.

The fix is the first genuinely neural idea in the book, and it's a lookup
table:

> **An embedding is a row of numbers, one row per token, in a big table.**
> GPT-2's table has 50,257 rows of 768 numbers. Training moves the rows
> around so that tokens which show up in similar contexts end up near each
> other. After that, "the meaning of a token" *is* its position relative to
> the other rows, and anything the model learns about one region of the
> space applies to everything nearby. The same table, read backwards, turns
> the model's final output back into a probability for every token.

The body book used the word "embeddings" once, in the RAG chapter, as
"grep for meaning." That's the same object as this one, and by the end of
this chapter the connection will be exact.

## The table

Here it is, from the real GPT-2 weights (chapter 7 explains the loading;
for now, trust that `W["wte.weight"]` is a NumPy array read from the file
OpenAI published):

```
embedding table: (50257, 768) -> 38,597,376 numbers

the row for ' strawberry', first 8 of 768 numbers:
[-0.109  0.146  0.055 -0.002  0.057  0.141 -0.36  -0.117]
```

That's it. Token 41236 goes in, row 41236 comes out: 768 floating-point
numbers, and those numbers are what the rest of the network works with.
There's no dictionary definition in there, no list of properties. Just
coordinates. Individually the numbers mean nothing; dimension 6 isn't
"redness" or "fruitness." Only the geometry means anything: which rows are
near which.

The table is a third of GPT-2 small by parameter count (38.6 million of
124 million). In a modern model with a 128,000-token vocabulary and
8,192-dimensional vectors, it's over a billion numbers. That's a real cost
of a big vocabulary, and one reason chapter 2's tokenizer decisions aren't
free.

## What the geometry holds

Ask which rows are nearest to a given row, measured by the angle between
the vectors (cosine similarity, which is a dot product after normalising).
This is
[`gpt/embeddings_demo.py`](https://github.com/IsuruMaduranga/harness-engineering-101/blob/main/llms-101/src/gpt/embeddings_demo.py),
run on the real table:

```
' king'    -> kings 0.73, King 0.70, queen 0.66, prince 0.59, monarch 0.58, emperor 0.56, ruler 0.55
' Python'  -> python 0.77, Python 0.76, Django 0.61, PHP 0.57, Py 0.56, Java 0.53
' happy'   -> happy 0.70, Happy 0.69, happier 0.67, unhappy 0.66, pleased 0.63, glad 0.62
' Paris'   -> Paris 0.83, France 0.63, French 0.58, London 0.58, Copenhagen 0.57, Brussels 0.55
' Monday'  -> Tuesday 0.89, Thursday 0.85, Wednesday 0.84, Friday 0.82, Sunday 0.81
```

Nobody wrote these relationships down. The training objective was only
"predict the next token" (chapter 8), and this structure fell out of it,
because ` Monday` and ` Tuesday` appear in the same kinds of sentence and
the cheapest way for the model to predict well in both cases is to give
them nearly the same vector. Notice ` unhappy` sitting next to ` happy`:
they're opposites to us, but they occur in identical contexts ("I was very
___ about it"), and the table records *contexts*, not sentiment. The
geometry captures how a token is *used*. Meaning, in the human sense, is
whatever the rest of the network builds on top.

And the party trick, which was the result that made everyone take this
seriously back in 2013:

```
king - man + woman    -> queen 0.71, princess 0.60
Paris - France + Germany -> Berlin 0.67, Munich 0.60
walked - walk + swim  -> swimming 0.64
```

Vector arithmetic on the table does analogies. The direction from ` man`
to ` woman` is roughly the same direction as from ` king` to ` queen`, so
you can add it. The direction from ` France` to ` Paris` is "capital of."
This isn't a feature anyone built. It's what "similar contexts, similar
positions" produces when the corpus is large enough to have consistent
patterns.

One honest failure, because they matter as much as the successes:

```
' harness' -> brid 0.45, leveraging 0.45, utilizing 0.44, restraints 0.44, straps 0.44
```

Weak matches, and a strange mix of the verb sense ("harness the power of")
and the noun sense (straps). ` harness` is a rare token in web text, so its
row was nudged fewer times during training and landed somewhere vaguer.
Rare tokens have worse embeddings. That's a fact about every model,
including the one you're using in production, and it's part of why models
are shakier on jargon and proper nouns.

## Why this fixes the bigram problem

Go back to chapter 1's complaint: the counting table had a row per
character and nothing connecting rows. Now imagine the model has learned,
from thousands of sentences about kings, that after ` the king` a likely
continuation is ` ruled`. In the bigram world that knowledge is locked in
the ` king` row. In the embedding world, ` queen` sits right next to
` king`, so any computation the model does downstream of the embedding
gives nearly the same answer for both. It learned about queens by learning
about kings. That's **generalisation**, and it's the reason a model can
say sensible things about a word it saw twelve times in training: the
twelve sightings only had to place the word near its neighbours, and the
neighbours did the rest.

## The table, read backwards

There's a second use for the same table, and it closes the loop with
chapter 1. After the model has done all its work (Part I's remaining
chapters), what comes out at the last position is a vector of 768 numbers,
the same shape as an embedding. The model needs to turn that into a
probability for every one of 50,257 tokens.

It does it by comparing the vector against every row of the table:

```python
logits = x @ W["wte.weight"].T     # (768,) · (768, 50257) -> one score per token
probs = softmax(logits)            # chapter 1's distribution
```

A dot product with each row gives a score for how much the output vector
"points toward" each token. Softmax turns the scores into probabilities.
This is the **unembedding**, and GPT-2 uses the *same* matrix as the
embedding, transposed, which is called tying the weights. It saves 38
million parameters, and it makes a kind of sense: the space you read tokens
into is the space you write them out of. Most modern models untie them for
a small quality gain, but the picture is identical either way.

So the whole model is: look up a vector for each token, do something to
the vectors, compare the final vector against the table. Chapters 4 to 6
are the "do something."

## The same trick, pointed at search

Now the body book connection. Chapter 15 of *Harness Engineering 101*
said RAG embeddings turn text into vectors so that "how do I get my money
back" lands near "refund policy" without sharing a word. That's this
chapter's idea with one change of objective. An **embedding model** for
search is a transformer trained so that the vector for a whole sentence or
paragraph lands near the vectors of texts with similar meaning: pairs of
questions and their answers, or paraphrases, are pushed together during
training. The output is a single vector per document instead of one per
token, and the space is organised by topic instead of by grammatical
context. But it is the same object, similarity is still a dot product, and
"nearest neighbours in the space" is still the whole search algorithm.
"Grep for meaning" is literally: embed everything, embed the query, find
the closest rows.

That also tells you the limits. Embeddings record what things are *used
like*, so exact identifiers, rare product codes and the difference between
"not approved" and "approved" are exactly where they're weak (the
` happy`/` unhappy` result above is a preview). That's why production search
is hybrid: a vector index for meaning, a keyword index for the strings.

## What you now know

- An embedding is a row in a learned table: one vector of a few hundred to
  several thousand numbers per token. The table is a big chunk of the
  model's parameters.
- Training arranges the rows so that tokens used in similar contexts are
  near each other. Similarity is a dot product; analogies are vector
  arithmetic. Rare tokens get worse rows.
- Generalisation comes from geometry: what the model learns about one
  region applies to its neighbours.
- The same table, transposed, converts the model's output vector into a
  score for every token. That's the unembedding, and softmax of it is
  chapter 1's distribution.
- Search embeddings are the same object trained with a different goal,
  which is why they're good at meaning and bad at exact strings.

Now the model has a vector per token. It still can't see more than one
token at a time. Before attention solved that, two other ideas tried, and
their failures are what make attention make sense.

*[Next: Chapter 4 — Before Attention: N-grams and RNNs](04-before-attention.md)*
