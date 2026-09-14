# Chapter 1: It's Just Next-Token Prediction

*LLMs 101, Part I — One Function. [Series index](index.html) ·
[Next: Tokens](02-tokens.md)*

---

In *Harness Engineering 101* I spent a
[chapter](https://isuruwijesiri.com/harness-engineering-101/02-the-brain.html)
calling the model a black box: text goes in, text comes out, don't worry
about the middle. That was the right call for building the body. It is the
wrong call for this series, so here is the box, opened, in one sentence:

> **An LLM is a function that takes a sequence of tokens and returns one
> number for every token in its vocabulary: the probability that this token
> comes next.** That's the entire interface. It has no memory, no goals, no
> loop. Something outside the function picks a token from those
> probabilities, appends it, and calls the function again.

Everything in this series is about that one function. Part I is how it's
built. Part II is how it was taught. Part III is how it's run. If you keep
the sentence above in your head, every buzzword you meet later will land on
one of those three shelves.

This chapter proves the sentence by building the dumbest possible LLM. It
has no neural network in it, and it still has the exact shape of GPT.

## The dumbest possible language model

Ask: given the character I just wrote, which character usually comes next?
In English, after `t` you mostly see `h`, a space, or `e`. You can find that
out by counting. Take a big pile of text, look at every pair of adjacent
characters, and tally them. That tally *is* a language model. It's called a
**bigram model**, and here it is in full, trained on the text of *Harness
Engineering 101*
([`gpt/v0_bigram.py`](https://github.com/IsuruMaduranga/harness-engineering-101/blob/main/llms-101/src/gpt/v0_bigram.py)):

```python
from collections import Counter, defaultdict

text = open("corpus.txt").read()

following = defaultdict(Counter)        # following['t']['h'] = how often 'h' follows 't'
for a, b in zip(text, text[1:]):
    following[a][b] += 1

def next_token_distribution(context):
    """The one function every LLM is: sequence in, probabilities out."""
    counts = following[context[-1]]     # a bigram model only looks at the last token
    total = sum(counts.values())
    return {ch: n / total for ch, n in counts.items()}
```

Nine lines, and `next_token_distribution` has exactly the signature I
promised: a sequence in, a probability for every possible next token out.
Run it on the book (182,219 characters, 99 distinct) and ask what follows
`t`:

```
after 't', most likely next: [('h', 0.24), (' ', 0.19), ('e', 0.13), ('o', 0.09), ('i', 0.08)]
```

Those are real probabilities, from real counting. Twenty-four percent `h`,
because "the", "that", "this" and "with" are everywhere in the book. This is
already a model of English, in the only sense that matters: it assigns
higher probability to text that looks like the training data.

## The loop lives outside the model

Now make it talk. Notice that the function above doesn't generate anything.
It returns probabilities and stops. Generating text is a *second* piece of
code, and keeping the two separate is the most useful habit this chapter
can give you:

```python
import random

def sample(probs, temperature=1.0):
    chars = list(probs)
    weights = [p ** (1 / temperature) for p in probs.values()]
    return random.choices(chars, weights)[0]

def generate(prompt, n=300, temperature=1.0):
    out = prompt
    for _ in range(n):
        probs = next_token_distribution(out)   # the model
        out += sample(probs, temperature)       # the serving layer
    return out
```

Model, pick, append, repeat. That loop is text generation, for this toy and
for every frontier model. Here is what it produces, prompted with "The
harness":

```
--- temperature 1.0 ---
The harnessasut lont `
Thabigappe.
| nd-
|
TP ilsacooke | cavis anareatio
t or cal mirilyp Gre wa

--- temperature 0.5 ---
The harnesstoutres cod an athecathest  atheril the t.
 d  te s allyoringent wind theng t  as at pusere ** t re Everitin
```

It's garbage, but look at *which* garbage. The spaces land where word
boundaries land. `th`, `the`, `ing`, `es` show up constantly. There are
pipe characters and asterisks, because the book has tables and bold text.
The model has learned the *texture* of the corpus and nothing else.

Look at the temperature knob too, because in the body book I told you
temperature was a setting outside the model and asked you to take it on
faith. Now you can see it: `temperature` is an argument to `sample`, not to
`next_token_distribution`. The model's probabilities are identical in both
runs. At temperature 0.5 the picker leans harder on the likely characters,
so you get more `the` and fewer `Thabigappe`. At temperature 0 it would
always pick the top choice and loop forever on `the the the`. The randomness
is a property of the picker, and the picker is a dozen lines of code you
control. Chapter 15 spends a whole chapter on what a good picker does.

## Why this counts as an LLM

I'm not being cute. Structurally, a bigram table and GPT-4 are the same
object:

| | Bigram table | A frontier model |
|---|---|---|
| Input | the sequence so far | the sequence so far |
| Output | a probability for every possible next token | a probability for every possible next token |
| Vocabulary | 99 characters | roughly 100,000 to 200,000 tokens |
| How the probabilities are computed | look up a row in a table | run the sequence through a few hundred matrix multiplies |
| How the table was filled | counting pairs | chapters 8 through 11 |
| What generates text | the loop above | the loop above |

Every row that differs is one of the three questions from the top of the
chapter. The vocabulary row is how it's *built* (chapter 2). The
"how computed" row is how it's *built* (chapters 3 to 7). The "how filled"
row is how it's *taught* (Part II). The loop is how it's *run* (Part III).
Nothing is missing from that table. There is no row labelled
"understanding" that the big model has and the small one lacks. Whatever
understanding a frontier model has is *inside* the "how computed" row, and
this series is about what's in there.

## What the toy gets wrong, and where each fix lives

The bigram model fails in three specific ways, and each failure is a
chapter:

1. **It looks one character back.** After `t` it doesn't know whether the
   sentence was about tea or taxes. It has no context beyond a single
   token. A model with more context needs some way to *look back*, and
   how far back and how cheaply is the whole story of chapters 4, 5 and 14.
2. **It cannot generalise.** The table has a row for `q` and a row for `x`
   and nothing connects them. If the training text never contained a
   particular character pair, the model gives it probability zero, forever.
   Real models represent tokens as points in a space where similar things
   sit near each other, so what they learn about one carries to its
   neighbours. That's chapter 3.
3. **Its tokens are characters.** Characters are a terrible unit: too many
   of them per sentence, and each one carries almost no meaning. Real
   models use chunks of a few characters each, chosen by an algorithm that
   is also just counting. That's chapter 2, and it explains a lot of odd
   behaviour you've seen, like models that can't count letters in a word.

Fix those three and you're most of the way to a transformer. The rest of
Part I is those fixes in order, and by chapter 7 the toy is running the
real GPT-2 weights with English coming out.

## What you now know

- An LLM is one function: tokens in, a probability for every possible next
  token out. No memory, no goals, no loop.
- Generation is a separate loop that picks a token, appends it, and calls
  the function again. Temperature and every other "creativity" knob live in
  the picker, not the model.
- A counting table already has the full shape of an LLM. The difference
  between it and GPT is entirely in how the probabilities are computed and
  how the machine that computes them was filled in.
- The three shelves: built, taught, run. Every term you meet from here on
  goes on one of them.

Next: the smallest fix first. What is a token, why isn't it a word or a
character, and why does the answer explain your API bill and the strawberry
problem at the same time?

*[Next: Chapter 2 — Tokens: Why It Can't Count the R's in Strawberry](02-tokens.md)*
