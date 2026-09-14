# Chapter 15: Sampling and Structured Output

*LLMs 101, Part III — Running the Brain.
[Series index](index.html) · [Prev](14-context-windows.md) ·
[Next: Mixture of Experts](16-mixture-of-experts.md)*

---

**The failure:** chapter 7 took the most likely token every time and the
real GPT-2 said "the capital of the French Republic is the capital of the
French Republic" until it ran out of budget. The model returns a
distribution; *someone has to pick*, and the naive pick is wrong.

> **Picking a token is the serving layer's job, not the model's, and how it
> picks decides repetition, variety, determinism and validity.** Temperature,
> top-p and top-k reshape the distribution before sampling. "Deterministic"
> output is harder than setting temperature to zero, for reasons that live
> in the hardware. And structured output, the guaranteed-valid JSON that
> makes tool calls reliable, is the picker refusing to sample any token that
> would break the grammar.

The body book said temperature was a knob outside the model. This chapter
is the knob, and the other knobs next to it.

## Why greedy loops

Take the top token every step and you get a **repetition trap**. Once a
phrase has appeared, a model has learned (correctly, from text) that
repeated phrases tend to recur, so the phrase's tokens get a probability
bump. Greedy takes the bump. Now the phrase has appeared twice, and the
bump is bigger. Small models fall into this in a sentence; large ones take
longer but do it too, especially in lists. The output is also *boring* in a
precise sense: the single most likely continuation of every sentence is
the most generic one, so greedy text reads like the average of the
internet.

## The knobs

Here is the entire picker from
[`gpt/v5_generate.py`](https://github.com/IsuruMaduranga/harness-engineering-101/blob/main/llms-101/src/gpt/v5_generate.py):

```python
def pick(logits, temperature=1.0, top_k=0, top_p=1.0, rng=np.random.default_rng(0)):
    if temperature == 0:
        return int(logits.argmax())                               # greedy
    probs = softmax(logits / temperature)
    order = np.argsort(probs)[::-1]
    if top_k:
        order = order[:top_k]                                     # keep only the k most likely
    if top_p < 1.0:
        keep = np.cumsum(probs[order]) <= top_p                   # smallest set covering p of the mass
        keep[0] = True
        order = order[keep]
    p = probs[order] / probs[order].sum()
    return int(rng.choice(order, p=p))
```

**Temperature** divides the logits before the softmax. Below 1 it sharpens
the distribution (the top token gets more, the tail gets less); above 1 it
flattens it. At 0 it's greedy. It doesn't add information; it changes how
much the picker trusts the model's ranking.

**Top-k** throws away everything but the *k* most likely tokens, then
samples among those. **Top-p** (nucleus sampling) is the smarter version:
keep the smallest set of tokens whose probabilities add up to *p*. When the
model is confident, that set is one or two tokens; when it's torn, the set
is large. Top-p adapts to the shape of each step's distribution, which is
why it's the default nearly everywhere and top-k mostly isn't.

Watch all three on the real model, prompted with "The harness is":

```
{'temperature': 0}:
  'The harness is made of a lightweight, lightweight material that is easy to
   clean and is easy to clean. The harness is made of a lightweight'

{'temperature': 0.7, 'top_p': 0.9}:
  "The harness is not a standard harness for each bike, but we can make one
   for you. If you're looking for a lighter and more"

{'temperature': 1.5}:
  'The harness is larger Protoss850760 groupsular commander 2 ten nose gloves
   setshawk iOS92 37 black straw about cap Europeans840 64 over burned'
```

Greedy repeats itself inside one sentence. The middle setting reads like a
web page (about a bicycle harness; the model has never heard of *Harness
Engineering 101* and is right to guess bikes). At 1.5 the tail of the
distribution gets sampled and the tail is where the nonsense lives:
`Protoss850760` is a real token sequence with a real, tiny probability, and
a flat enough distribution will eventually pick it.

For agents, the body book recommended low temperature, and now the reason
is precise: you want the probable action, and you want the picker to stay
out of the tail where malformed tool calls live. For prose, you want some
temperature or you get the average of the internet. A **repetition
penalty**, which lowers the logits of tokens that have already appeared,
is the third common knob and a blunt one; it also penalises the legitimate
repeats that code and structured text need.

## Why temperature zero isn't deterministic

You'd think greedy decoding makes the output a pure function of the input.
It nearly does, and the exceptions matter for anyone who has tried to write
a test against a model:

- **Floating-point addition isn't associative.** A GPU sums the terms of a
  matrix multiply in whatever order its threads finish, and (a + b) + c
  differs from a + (b + c) in the last bit. Run the same prompt twice and
  the logits differ by a rounding error. Usually harmless, until two tokens
  are nearly tied and the rounding decides.
- **Batching changes the arithmetic.** Your request shares a GPU with other
  people's (chapter 17). The kernel chosen for a batch of 7 sums in a
  different order than the kernel for a batch of 12. Same weights, same
  prompt, different last bits, different tie-breaks.
- **Mixture-of-experts routing** (chapter 16) makes it worse: a near-tie in
  the router sends a token to a different expert, and now the logits
  differ by a lot, not a rounding error.

Providers offer a `seed` parameter and say "best effort," and best effort
is the honest answer. Determinism needs a fixed batch composition and
deterministic kernels, which cost throughput, so nobody serves that way at
scale. Design for a distribution of outputs, not a fixed string.

## Structured output: the picker as a grammar checker

Chapter 11 said tool calls come out as valid JSON because the model was
trained to, and that this is reliable but not guaranteed. Here's how it's
made guaranteed.

The picker sees the full distribution over the vocabulary at every step.
It can *zero out* tokens before sampling. So compile the JSON schema you
want into a state machine over tokens: at this point in the output, the
grammar allows a `"`, a `}` or whitespace, and nothing else. Mask every
other token to probability zero, renormalise, sample. The model can only
ever emit a sequence the grammar accepts. This is **constrained decoding**
(you'll also see "grammar-guided" or "JSON mode"), and it's how "forced
tool call" and "response format: JSON schema" features work. A forced tool
call is a grammar that says "the next thing you emit is a tool block with
this exact shape."

Two costs, both real:

- **Tokens don't align with grammar symbols.** A single token might be
  `":` or `},{`, spanning several grammar states. The masking machinery has
  to handle tokens that partially match, which is why implementations are
  fiddly and why early ones were slow.
- **Forcing can lower quality.** If the model's probability was spread over
  several ways to say something and the grammar allows only one, you've
  pushed it down a path it thought unlikely. Its subsequent tokens are
  conditioned on text it wouldn't have written. Loose grammars ("valid
  JSON") cost little. Tight ones ("exactly these seven fields in this
  order") can noticeably dull the content inside the fields. If quality
  drops when you turn on strict schemas, this is why, and the fix is to let
  the model think in free text first and constrain only the final block.

## Stop sequences, max tokens, and reading the distribution

Three more things the picker does that show up in every API:

**Stop.** After each token, check whether the model emitted an end-of-turn
token (chapter 10) or a string you asked to stop at. That's `stop_reason`.

**Max tokens.** Count. Cut off when the budget is spent. The reply ends
mid-sentence and `stop_reason` says so. This is also the only real guard
against a model that never emits its end token, which happens.

**Logprobs.** Some APIs will return the probabilities for the top few
tokens at each step. It's the chapter 1 distribution, exposed, and it's
underused: it tells you how confident the model was, per token, which is a
real signal for detecting a hallucinated name (low probability, torn
between candidates) versus a recalled one.

## What you now know

- Greedy decoding falls into repetition and produces generic text. Nobody
  serves with it.
- Temperature reshapes the distribution; top-p adapts the candidate set to
  the model's confidence at each step. Low for actions, higher for prose.
- Determinism is defeated by floating-point summation order, batching and
  expert routing. Treat output as a distribution even at temperature zero.
- Constrained decoding masks out grammar-violating tokens before sampling.
  Validity becomes a guarantee; the price is tokenizer alignment headaches
  and a possible quality hit from tight schemas.
- Stop tokens, max tokens and logprobs all live in the picker, not the
  model.

Next: the architecture change that let models get ten times bigger without
getting ten times more expensive to run, and what the "8x7B" on a model
card is telling you.

*[Next: Chapter 16 — Mixture of Experts](16-mixture-of-experts.md)*
