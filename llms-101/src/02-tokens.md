# Chapter 2: Tokens: Why It Can't Count the R's in Strawberry

*LLMs 101, Part I — One Function.
[Series index](index.html) · [Prev](01-its-just-next-token-prediction.md) ·
[Next: Embeddings](03-embeddings.md)*

---

**The failure:** the bigram model's tokens were characters, and characters
are a bad unit. A sentence is a hundred of them, each carrying almost no
meaning on its own, so the model spends its effort learning to spell. Words
are the obvious alternative and they're worse: the vocabulary is unbounded,
"run", "runs" and "running" share nothing, and code, URLs and Sinhala don't
have words in the English sense.

The fix, and the conclusion of this chapter:

> **A token is a chunk of text chosen by counting.** Start with single
> bytes, repeatedly glue together the pair that appears most often, stop
> when you have as many chunks as you want. The model never sees letters
> after that. It sees a list of integers, one per chunk. Nearly every odd
> thing you've noticed about tokens, from the price list to the strawberry
> problem, falls out of that one fact.

In the body book I defined a token as "about three or four characters of
English" and moved on. This chapter is the part I skipped, and it took me
a while to appreciate how much behaviour it explains.

## Byte-pair encoding, in full

The algorithm is called **byte-pair encoding** (BPE), and it's the
tokenizer behind GPT-2, GPT-4, Llama and Claude alike. Here's the training
half, from
[`gpt/v1_tokenizer.py`](https://github.com/IsuruMaduranga/harness-engineering-101/blob/main/llms-101/src/gpt/v1_tokenizer.py),
trimmed of bookkeeping:

```python
def train(text, vocab_size):
    words = count_chunks(text)                   # {tuple_of_bytes: how_often}
    merges = {}
    for new_id in range(256, vocab_size):        # ids 0..255 are the raw bytes
        pairs = Counter()
        for word, n in words.items():
            for a, b in zip(word, word[1:]):
                pairs[(a, b)] += n               # count every adjacent pair
        best = max(pairs, key=pairs.get)         # the most frequent one ...
        merges[best] = new_id                    # ... becomes a new token
        words = {merge(w, best, new_id): n for w, n in words.items()}
    return merges
```

Start with 256 tokens, one per possible byte, so that *any* text in any
language is representable from the first moment. Count every adjacent pair.
Glue the most common pair into a new token. Repeat until the vocabulary is
the size you want. Encoding new text later means replaying those merges in
the order they were learned. That's the whole thing. It's the bigram
counting from chapter 1, pointed at a different job.

The one production detail worth knowing: before counting, the text is split
into chunks (words, numbers, punctuation runs) by a regular expression, and
merges never cross a chunk boundary. This stops the tokenizer from learning
tokens like `.The` that glue a sentence's end to the next one's start. It
also means the space *before* a word becomes part of the word's token,
which is why ` strawberry` and `strawberry` are different tokens. Keep that
in mind; it comes back in a minute.

Train it on the harness book to a vocabulary of 512 and watch what it
learns:

```
vocab 512: 182,219 chars -> 91,972 tokens (1.98 chars/token)
first merges: [' t', 'he', ' a', 'in', 're', 'er', ' the', 'on', 'es', '  ']
longest tokens: [' your', 'ppend', 'hapter', ' model', ' array', '        ', ' harness', ' chapter']
```

The first merge is ` t`, because a space followed by `t` is the most common
pair of bytes in English prose. Seven merges later ` the` is a single
token. By merge 256 the tokenizer has invented tokens for ` harness`,
` array`, ` model` and ` chapter`, because those are what the book is about,
and a token for eight spaces, because the book has indented code.
Nobody told it those were words. It counted. A tokenizer trained on a
medical corpus would have tokens for drug names; one trained on GitHub
has tokens for `self.` and `();`.

## The real thing

GPT-2's tokenizer has 50,257 tokens: 256 bytes, 50,000 merges learned from
web text, and one special marker, `<|endoftext|>`. Run some strings through
it
([`gpt/gpt2_tokenizer.py`](https://github.com/IsuruMaduranga/harness-engineering-101/blob/main/llms-101/src/gpt/gpt2_tokenizer.py)
loads the two published files, no library):

```
'The harness is the body.'          ->  6 tokens ['The', ' harness', ' is', ' the', ' body', '.']
'strawberry'                        ->  3 tokens ['st', 'raw', 'berry']
' strawberry'                       ->  1 tokens [' strawberry']
"How many r's are in strawberry?"   ->  8 tokens ['How', ' many', ' r', "'s", ' are', ' in', ' strawberry', '?']
'def call_llm(messages):'           ->  9 tokens ['def', ' call', '_', 'll', 'm', '(', 'mess', 'ages', '):']
'1234567'                           ->  3 tokens ['123', '45', '67']
'  indented'                        ->  3 tokens [' ', ' ind', 'ented']
'මොඩලය මොළයයි.'                     -> 35 tokens (every byte on its own)
```

Each of those lines is a behaviour you have probably seen in a real model,
and now you can see the cause.

## Five things tokens explain

**The strawberry problem.** Look at the question `How many r's are in
strawberry?` The word ` strawberry` is *one token*, id 41236 in GPT-2. The
model does not receive s, t, r, a, w. It receives 41236. Its only knowledge
of what letters are inside that token comes from statistics: how often, in
its training data, text about "strawberry" was followed by text spelling
it out. It's being asked to count the r's in a word it has never seen
written down. When models get this wrong it isn't a reasoning failure. It's
that you asked a blind person about a colour. Newer models usually get it
right anyway, because there's now plenty of training text explaining
exactly this, and because reasoning models (chapter 11) learn to spell the
word out token by token first, which turns it into a problem they can see.

**Why everything is priced in tokens.** One token is one position in the
sequence, and the model does the same fixed amount of work per position:
one pass through every layer. The cost of running a model is therefore the
number of tokens times a constant, and the context window is a count of
positions the architecture can handle. Tokens aren't a billing
abstraction someone chose. They're the unit of work.

**The language tax.** "The model is the brain" in English is six tokens. In
Sinhala it's thirty-five, because GPT-2's merges were learned from mostly
English text and Sinhala never earned a single merge, so it falls through
to raw bytes, three per character. Same sentence, six times the price, six
times less of it fits in the context window, and the model is also *worse*
at it, because it's learning the language from byte fragments rather than
meaningful chunks. Modern tokenizers have grown to 100,000 to 250,000
tokens partly to spread the merges over more languages, and the tax has
shrunk, but it hasn't gone away. If you build for a non-English market,
tokenize a sample of your real text before you estimate cost.

**Arithmetic.** `1234567` becomes `123`, `45`, `67`. The model is asked to
add numbers that arrive pre-chopped into arbitrary chunks, where the chunk
boundaries depend on frequency in web text rather than on place value.
That's a hostile format for arithmetic, and it's part of why early models
were bad at it. Newer tokenizers split digits one or three at a time,
deliberately, so every number is chunked the same way. When a model's
arithmetic improves between versions, some of that is training and some is
a tokenizer decision.

**Code and whitespace.** `  indented` is a lone space token plus two more.
Indentation, so cheap to a human eye, is real tokens with real cost, and in
early models a run of eight spaces could be eight tokens. Tokenizers built
with code in mind now have tokens for common indentation runs, which is one
unglamorous reason coding models got better and cheaper.

## Special tokens: the ones that aren't text

`<|endoftext|>` is not a piece of text that appeared in the training data.
It's a token the tokenizer reserves and the training pipeline inserts
between documents, so the model can learn that "a document ends here and
something unrelated begins." Modern models have a handful more of these:
markers for the start and end of a message, for who is speaking, for the
start of a tool call. They're ordinary integers to the model, but the
tokenizer guarantees no user text ever encodes to them. Chapter 10 shows how
those few reserved integers are the entire mechanism behind roles, chat
templates and the JSON array you send to an API. Keep this fact in your
pocket until then: **the model has no concept of "user" or "system."** It
has token 50256 and its friends.

## What the model receives

After the tokenizer runs, the input to the function from chapter 1 is a
list of integers, each between 0 and about 50,000 (or 200,000, for a modern
vocabulary). No letters. No words. No spaces, except where a space was
glued into a chunk. Everything the model knows about what token 41236 *is*
has to come from somewhere other than its spelling.

That's the next failure. An integer id, on its own, tells the model
nothing: 41236 is no more related to 41237 than to 7. The bigram table had
the same problem in chapter 1, with a separate row per character and
nothing shared between rows. The fix is to give every token a position in
a space, so that similar tokens sit near each other and what's learned
about one carries over to its neighbours.

## What you now know

- A token is a frequently-seen chunk of bytes, found by repeatedly merging
  the most common adjacent pair. That's all of byte-pair encoding.
- The model sees integers, never letters. Spelling, counting letters and
  arithmetic on digits are all done blind, from statistics about whole
  tokens.
- Tokens are the unit of compute, so they are the unit of price and of the
  context window.
- Tokenizers trained on English make other languages several times more
  expensive and harder to learn. Measure your real text.
- A few reserved tokens that never appear in user text are the entire
  basis of roles and chat formats. Chapter 10.

*[Next: Chapter 3 — Embeddings: Words as Coordinates](03-embeddings.md)*
