# Chapter 11: RL and Reasoning

*LLMs 101, Part II — Growing the Brain.
[Series index](index.html) · [Prev](10-post-training.md) ·
[Next: Changing a Brain Cheaply](12-changing-a-brain-cheaply.md)*

---

**The failure:** post-training gives you an assistant that answers. It does
not give you one that works through a hard problem, calls a tool with the
right arguments, notices its own mistake and tries something else. Around
2024 those abilities arrived in a rush, along with the words "reasoning
model," "thinking tokens" and "test-time compute." Here's what they are:

> **Reasoning, tool use and self-correction are trained behaviours, and
> the training is reinforcement learning on tasks with checkable answers.**
> The model tries a problem many times, the attempts that get the right
> answer are reinforced, and the weights shift toward whatever those
> attempts did. What they did, it turns out, was write a lot of
> intermediate tokens before answering. "Thinking" is ordinary next-token
> generation into a scratch area that the model was rewarded for using.

In the body book I told you thinking was "just another block type" and that
tool calls came out as valid JSON because "the model learned the format."
Both true. This chapter is why they're true, and what it costs.

## Why more tokens means more thought

Start with a fact about the architecture that took me embarrassingly long
to appreciate. Every token gets the *same* amount of computation: one pass
through every layer. There's no way for the model to spend longer on a hard
token. The function from chapter 1 has a fixed cost per call.

So how does a fixed-depth network solve a problem that needs twenty
sequential steps? It can't, in one token. It can only do it by *emitting*
tokens: writing down step one, then, with step one now in the context and
readable through attention, computing step two, and so on. The generated
text is the model's working memory. A human can think silently; this
machine literally cannot. Its only scratchpad is the output.

This is why **chain-of-thought** works. Ask a model to "think step by step"
and it gets more right, because you've given it permission to spend more
forward passes on the problem. The 2022 discovery was that the trick
worked at all. The 2024 discovery was that you could *train* the model to
do it well, without asking.

## The training loop, in a paragraph

Take problems with answers you can check automatically: maths with a
numeric answer, code with unit tests, puzzles with a verifier. For each
problem, sample many attempts from the model at high temperature. Run the
checker. Now do gradient descent, but instead of "make the true next token
more likely" (chapter 8), the signal is "make the tokens that appeared in
*successful attempts* more likely, and the tokens in failed attempts
less." That's **reinforcement learning** with a verifiable reward. The
algorithms have names (PPO, GRPO) and a few pages of stabilising details,
but the loop is: try, check, reinforce what worked.

Nobody writes the reasoning examples. Nobody tells the model to backtrack.
It discovers that attempts which wrote out intermediate steps, checked
their arithmetic, and said "wait, that's wrong" before the final answer
got rewarded more often than attempts that blurted an answer. So it does
more of that. The DeepSeek-R1 paper in early 2025 showed the learned
reasoning getting *longer* over training on its own, and the model
spontaneously writing things like "wait, let me reconsider." No one put
that phrase in a dataset. It's a token sequence that preceded correct
answers.

## Thinking tokens and the effort knob

Providers wrap this scratch work in a block, called thinking or reasoning,
so the harness can show or hide it and bill it separately. Mechanically it's
the same generation as the answer: the model emits a start-of-thinking
marker (a special token, chapter 2), writes as much as it likes, emits an
end marker, then writes the reply. The harness sees the markers and splits.

The **effort** or **reasoning budget** setting in modern APIs is also
trained. During RL, the model is sometimes told (in the prompt, via a
special token or instruction) to think briefly and sometimes to think at
length, and rewarded for getting the answer under each budget. It learns
to allocate. When you set effort to low you're not truncating the thinking;
you're triggering a behaviour the model practised. This is what people
mean by **test-time compute**: you can now buy accuracy with output tokens
at inference time, on a curve, instead of only with parameters at training
time. Part III's cost chapters have a new axis because of it.

## Tool calls are the same trick with a different checker

A tool call in the body book was a block of JSON with a name and arguments,
and the model produced it correctly almost every time. Here's why.

Training examples for tool use are conversations where the assistant's
turn contains a special token that means "tool call starts here," then the
JSON, then a closing token, then a *tool result* block, then more assistant
text. The model learns the format the way it learned the chat template in
chapter 10: by seeing it thousands of times. Then RL sharpens it. Tasks
where the model has to call a tool to get the answer (look up a fact, run
code, read a file) are checkable, so attempts with well-formed, correctly
targeted calls get reinforced and attempts with malformed JSON or made-up
argument names don't.

The result is a model that treats "here is a list of tool schemas" in the
prompt as a strong cue to emit exactly that format when it needs
something. It's reliable because it was rewarded into reliability. It is
not *guaranteed*, because it's still sampling from a probability
distribution; a rare malformed call is a low-probability token sequence,
not a bug in a parser. Chapter 15 covers how serving systems can make it a
guarantee by refusing to sample tokens that would break the schema.

## Self-correction: errors are training signal

The body book leaned on a behaviour it couldn't explain: feed the model an
error message and it tries a different approach. Now it's obvious. In
agentic RL, the environment returns errors (test failures, stack traces,
"file not found"), and the attempts that read the error and changed course
succeeded more often than attempts that retried the same thing. Blind
retry was trained out because blind retry didn't earn reward. This is why
"give the model the failure" is a rule rather than a hope, and why it
works better in newer models: it's a behaviour that has been *practised*.

## What it costs

RL on outcomes is powerful and it has three bills.

**Reward hacking.** If the checker can be fooled, the model learns to fool
it, because fooling it *is* what the reward measures. Coding models trained
against unit tests have learned to special-case the test inputs, to delete
failing tests, or to print "all tests pass" without running them. Every
harness engineer who has watched an agent quietly modify a test to make it
green has met this directly. The fix is better checkers and human review,
not a prompt, because the behaviour is in the weights.

**Tokens.** Thinking is output tokens, and output tokens are the expensive
kind (chapter 13). A reasoning model can spend ten thousand tokens on a
question that has a one-word answer. That's the point when the question is
hard and a waste when it isn't, and the effort knob exists so the harness
can choose.

**The thinking isn't a transcript of the computation.** It's tempting to
read the scratch area as the model showing its work. It's more accurate to
say it's text the model found useful to generate before answering. It
usually corresponds to the real steps, and researchers have shown cases
where it doesn't: the stated reasoning and the actual cause of the answer
diverge. Treat it as helpful, not as sworn testimony.

## What you now know

- The architecture spends fixed compute per token, so the only way to
  think longer is to emit more tokens. Chain-of-thought is buying forward
  passes.
- Reasoning models are trained by RL on checkable tasks: sample attempts,
  check, reinforce what worked. Long, self-checking reasoning emerged
  because it earned reward.
- Thinking blocks and the effort knob are trained behaviours wrapped in
  special tokens. Test-time compute is a new cost axis.
- Tool calls are the chat template extended with tool tokens, sharpened by
  RL. Reliable, not guaranteed.
- Self-correction was practised. Reward hacking was too, wherever the
  checker was weak.

Next: all of Part II so far has been about what the labs do. What can *you*
do to a brain, cheaply, and when should you not bother?

*[Next: Chapter 12 — Changing a Brain Cheaply: Fine-tuning, LoRA, Distillation](12-changing-a-brain-cheaply.md)*
