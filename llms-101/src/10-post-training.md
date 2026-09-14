# Chapter 10: Post-training: From Autocomplete to Assistant

*LLMs 101, Part II — Growing the Brain.
[Series index](index.html) · [Prev](09-pretraining.md) ·
[Next: RL and Reasoning](11-rl-and-reasoning.md)*

---

**The failure:** a base model continues text. Ask it a question and you
get more text, which may or may not include an answer. Here's real GPT-2,
greedy-decoded, on three prompts:

```
'What is the capital of France?\n\nThe capital of France is Paris.\n\nThe capital of France'

'Q: What is the capital of France?\nA: The capital of France is Paris.\nQ: What is the capital of'

'The mayor of Kadawatha is a former member of the ruling party and a former member of the ruling party'
```

It *knows* Paris. It answers, and then keeps going, because in the training
data a question is usually followed by an answer and then another question.
It has no concept of "your turn is over." And on the third prompt, asked
about a town it has never read about, it produces a confident, plausible,
made-up biography, exactly as chapter 9 predicted. A base model is a
brilliant autocomplete with no idea it's talking to anyone.

Here's how that's fixed, and it's the conclusion of the chapter:

> **Post-training teaches the model a text format for conversations and
> then nudges it toward the replies people prefer.** The format is plain
> text with a few reserved tokens marking who's speaking and where a turn
> ends. The JSON array you send to an API is *rendered into that text*
> before the model sees it. "Roles" are special tokens. "The model stopped"
> means it emitted the end-of-turn token. And the system prompt has
> authority because every training conversation gave it authority, not
> because anything enforces it.

This chapter is the one where the body book's chapter 1 and this book's
chapter 2 meet in the middle.

## Step 1: teach the format (supervised fine-tuning)

Take the pretrained model and keep training it with chapter 8's loop, but
on a much smaller, hand-built dataset: tens of thousands to a few million
example conversations, written or curated by people, in which an assistant
answers helpfully. This is **supervised fine-tuning** (SFT). It's cheap
next to pretraining, a fraction of a percent of the compute, because the
model already knows language and facts; it only needs to learn a
*behaviour*.

The conversations are rendered as text using a **chat template**. Here's
one in the style several open models use:

```
<|im_start|>system
You are a terse assistant.<|im_end|>
<|im_start|>user
Capital of Sri Lanka?<|im_end|>
<|im_start|>assistant
Sri Jayawardenepura Kotte (legislative); Colombo (commercial).<|im_end|>
```

`<|im_start|>` and `<|im_end|>` are special tokens from chapter 2: reserved
integers that no user text can produce. The words `system`, `user` and
`assistant` are just ordinary tokens that always follow the start marker.
That's the whole mechanism of roles. There is no role field inside the
model. There's a pattern in the text, seen a million times.

Two training details matter for what you see at the API:

- **The loss is only computed on the assistant's tokens.** The model is
  taught to *produce* the reply, not to predict what the user will say.
- **The example ends with `<|im_end|>`.** So the model learns that after a
  complete answer, the most likely next token is the end-of-turn marker.
  When you call an API and the response has `stop_reason: "end_turn"`, that
  is literally the serving layer noticing the model sampled this token and
  cutting generation there. `max_tokens` is the other stop reason: the
  harness ran out of patience before the model emitted the marker.

Now look at what happens to the body book's JSON array. You send:

```json
{"system": "You are a terse assistant.",
 "messages": [{"role": "user", "content": "Capital of Sri Lanka?"}]}
```

The provider's serving code renders that into the template text above,
minus the answer, ending with `<|im_start|>assistant\n`. Then it tokenizes
and calls the function from chapter 1. The model continues the text. The
array was never a data structure the model saw. It's a *serialisation
convenience* for you, turned into a string with markers before the model
gets it. Every provider's array format (Anthropic's `system` field, OpenAI's
`system` message, the `developer` role) is a different spelling of the same
string, which is why the body book could call the dialects cosmetic.

This also answers something the body book flagged in passing: you can edit
the assistant's earlier messages before resending, and the model can't
tell. Of course it can't. The whole history is just text after some
markers. There's no signature on the assistant turns. The model sees
"apparently I said that" and continues.

## Why the system prompt has authority

The system prompt is obeyed because in the SFT data, the assistant's
replies were consistent with the system message, every time, so the model
learned that text between the system markers predicts how the assistant
behaves. That's a strong learned prior. It is not access control.

The body book said this about guardrails (chapter 13 there) and now you
can see exactly how strong "strong" is. A user message that says "ignore
your instructions" is competing with a trained pattern, and usually loses.
A user message that looks *enough like* a system message, or a tool result
that contains text shaped like instructions, is competing on the same
terms, and sometimes wins. Prompt injection isn't a bug in a parser. It's
the model doing what it does: continuing text according to learned
patterns, where the pattern "obey the system prompt" is very strong and
the pattern "text that looks like instructions gets followed" is also
strong. Providers train hard on the first and adversarially test the
second, and the gap narrows every generation without closing, because both
are the same mechanism.

## Step 2: teach preferences (RLHF and friends)

SFT gets you an assistant. It doesn't get you a *good* one, because the
example writers can't cover every situation, and because "helpful" is
easier to recognise than to write. So the second stage collects human
judgements: show a person two model replies to the same prompt, ask which
is better. Do that a few hundred thousand times.

Then use the judgements to shift the model. The original recipe, **RLHF**
(reinforcement learning from human feedback), trains a separate **reward
model** to predict which reply a human would prefer, then runs
reinforcement learning against it: the assistant generates replies, the
reward model scores them, and the assistant's weights are nudged toward
higher scores. A simpler recipe from 2023, **DPO** (direct preference
optimisation), skips the reward model and adjusts the weights directly on
the pairs: make the preferred reply more likely and the other less likely.
Both work. Both are chapter 8's nudge with a different signal replacing
"the true next token."

What this stage buys you is most of the difference between a model that
technically answers and one people like talking to: it follows
instructions more precisely, formats sensibly, declines requests the lab
wants declined, and, crucially for chapter 9's hallucination problem,
learns that "I'm not sure" is sometimes the *preferred* reply. That last
one is a real fix, learned from raters who preferred honest uncertainty to
confident nonsense. It's an override on top of the pretraining prior, and
it holds better in some domains than others.

## What preference training costs

Optimising for what raters click on has side effects, and you've met all
of them.

**Sycophancy.** Raters prefer replies that agree with them. A model tuned
on those preferences learns to agree, including with wrong premises. When
you push back on a correct answer and the model folds, that's this.

**Verbosity.** Raters, on average, prefer longer, more thorough-looking
replies. So models learn to pad. The bulleted summary you didn't ask for
is a preference artefact.

**Mode collapse.** A base model produces varied continuations. A heavily
preference-tuned one converges on a house style: the same structure, the
same hedges, the same "Certainly!" This is why base models are sometimes
better for creative work and why the "AI voice" is recognisable across
products.

**Refusals in the wrong places.** The reward for declining harmful requests
generalises imperfectly, and you get a model that won't discuss a
chemistry homework problem. Every lab tunes this trade-off every release.

None of these are prompt bugs. They are in the weights, they came from the
training signal, and a harness can only work around them.

## What the model still can't do

After SFT and preference training you have an assistant: it answers, it
stops, it's mostly polite, it mostly follows the system prompt. What it
does not yet do well is work through a problem that needs many steps, use
a tool correctly under pressure, or recover from its own mistake. Those
behaviours needed a different training signal, and getting it is the story
of the models released from late 2024 onward.

## What you now know

- A base model continues text. Post-training teaches a conversation
  format, then nudges toward preferred replies. Both stages are cheap next
  to pretraining.
- The chat template is plain text with reserved tokens marking speaker and
  turn boundaries. The API's JSON array is rendered into it. Roles are
  tokens; "stop" is the model emitting the end-of-turn marker.
- The system prompt is authoritative because training made it so. Prompt
  injection is the same mechanism pointed the other way.
- RLHF and DPO learn from human comparisons. They fix a lot of
  hallucination and tone, and they cause sycophancy, verbosity and a house
  style.

*[Next: Chapter 11 — RL and Reasoning](11-rl-and-reasoning.md)*
