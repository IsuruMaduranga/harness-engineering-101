# Chapter 12: Debugging the Array

*Harness Engineering 101, Part III — The Ecosystem.
[Series index](index.html) · [Prev](11-extending-the-body.md) ·
[Next: Reflexes and Guardrails](13-reflexes-and-guardrails.md)*

---

**The failure:** your agent does something strange. It ignores an
instruction, calls a tool with nonsense arguments, insists a file says
something it does not. Your instinct, trained by ordinary software, is to
read your code. In an agent, though, that behavior comes from the model,
and the model only ever sees the final assembled request. By now many parts
of the harness build that request: the system prompt composer, memory
injection, the skills menu, MCP schemas, the reminder queue, compaction.
Your mental picture of the array and the actual bytes on the wire drift
apart, and each of the strange behaviors above usually comes from that
drift.

The debugging rule for harness work is one sentence:

> **You cannot fix the prompt you cannot see. So look at the actual
> request, first, always.**

Almost nobody does this on day one, because no beginner tutorial mentions
it. Every production harness team learns it, usually after a painful week.
This chapter shows how to do it, so you can skip that week.

## Capture: log the bytes on the wire

The most basic tool is surprisingly small. You intercept every request your
harness sends and write the whole thing to disk. In the toy harness it is
three lines in `call_llm`:

```python
def call_llm(messages, tools, system):
    body = {...}
    if os.environ.get("HARNESS_DEBUG"):
        with open(f"debug/req_{time.time_ns()}.json", "w") as f:
            json.dump(body, f, indent=2)             # the WHOLE request
    ...
    # and mirror the response: stop_reason, content, usage
```

Log the request body itself, plus the response with its `usage` block. A
summary or your own log lines saying "injected memory" are not enough.
Everything else in this chapter depends on this file existing. Two design
notes from production:

- **Capture at the last possible point** before the HTTP call. If any layer
  can modify the request after your logging (an SDK adding headers and
  defaults, a middleware reordering tools), your capture is wrong. A whole
  class of bugs comes from the gap between "what my code assembled" and
  "what left the machine." This is also chapter 10's transparency question
  in practice: if a framework will not let you see this point, you cannot
  debug it at this level.
- **Capture responses too, especially `usage`.** The response tells you the
  stop reason (chapter 4's control signal), and usage tells you how the
  cache did, which is the next section.

With capture on, you can find the cause of the strange behaviors. If the
model "ignored" your instruction, open the request. You'll find the
instruction fell out during compaction, or your reminder never drained from
the queue, or it is there but buried at token 3,000 of an 8,000-token
system prompt. If the model misread a file, find the `tool_result`, and
you'll see your truncation cut the file at exactly the wrong line. In my
experience, when I blame the model, the cause is often in the array
instead: the thing was never there, or it was there but mangled or
misplaced.

## The vital sign: cache-read tokens

The response's `usage` block reports how the input was billed, including
`cache_read_input_tokens`. This is where you verify that chapter 5's
caching actually works. On any round after the first, cache reads should be
nearly the whole input. So plot it, or just print it per round:

```
round 12: input 84,213 | cache_read 82,900 ✓
round 13: input 86,120 | cache_read 0      ← something rewrote the prefix
```

That second line catches a silent 10x cost bug in real time, and *nothing
else shows it*. There's no error and no behavior change; it only costs
money. The cause could be a timestamp that crept into the system prompt, a
tool list serialized in a different order, or some feature that "helpfully"
edited an old message. Production harnesses watch `cache_read_input_tokens`
continuously.
[One Code](https://github.com/IsuruMaduranga/one-code) shows the cache-hit
rate in its status line, on the theory that you should see this number
while the session runs instead of finding it in a postmortem.

## Replay: the experiment the architecture gives you for free

Statelessness (chapter 1) pays off for debugging here. The provider keeps
nothing, and the request is the entire world state, so a captured request
is a *perfect reproduction case*. Load the JSON, resend it, and you re-run
the exact moment of the bug without setting up a session or writing "steps
to reproduce."

And because it is just JSON, you can *edit it before resending*. This is
the experimental method for prompts:

1. Capture the request where the model went wrong.
2. Form a hypothesis: "it grabbed the wrong function because the truncated
   tool result lost the signature."
3. Edit that one block. Resend. Did the behavior change?
4. Repeat, changing one thing at a time.

This is chapter 1's "you can edit assistant messages and the model can't
tell," used as a lab technique: you can edit *history itself* and
ask "what would you have done if the past were this instead?" (Sampling is
random, so run the interesting cases a few times; temperature 0 tightens
it further.) A `replay.py` that loads, optionally tweaks, and resends a
captured request is thirty lines, and it converts prompt debugging from
folklore ("try rewording it?") into experiments.

## Fidelity tests: pinning the array in CI

Capture and replay are interactive. The durable version is asserting the
array's shape in your test suite, so a test catches drift before a bill
does.

The trick is to fake only the API and keep everything else real: run the
harness against a mock that records requests, drive a scripted turn, then
assert on what got assembled. You can test at three levels, from loose to
strict, and all of them are cheap because no real model is involved:

- **Presence:** memory injected on the first message; the reminder drained
  into the next request; the deferred tool activated after search.
- **Placement:** system prompt is exactly [prompt, then tool schemas, in
  sorted order]; reminders land at the bottom (chapter 8), never the top.
- **Bytes:** for prefix-critical regions, assert on the exact string. The
  same request twice must produce byte-identical prefixes; a session's
  turn-2 prefix must extend turn-1's. This is chapter 5 as a unit test, and
  it turns "someone's refactor quietly broke caching" from a mystery into a
  red X.

One more fidelity variant from my own work: when the goal is *compatibility*
(One Code exists to reproduce Claude Code's behavior on other runtimes),
the reference is a capture of the original's real payloads, and tests
assert byte-equality against that. Behavior comes from the array, so
matching the arrays matches the behavior. That is also why capture is the
first thing to build. It is the ground truth for every other claim about
what your harness does.

## Seeing multi-agent and multi-part systems

Two places the "look at the array" rule needs extra plumbing:

**Subagents** (chapter 7): the parent sees only the report, by design, so
when a child returns a wrong answer, capture is your only window into its
thirty rounds. Persist every child's transcript (they are just arrays;
sessions are files) keyed by the spawning tool call, and make them
inspectable. From there, you find the round where the child went wrong, and
the cause is usually one of the same three: never in its array (a bad task
briefing from the parent, most common), mangled in its array, or model
failure.

**The event side** (chapters 8, 9): reminders and wakeups originate outside
any request, so log the *queue* too: what was enqueued, by whom, when it
drained. The question "why did the model think a file changed?" is answered
in the queue log; the array only shows the sentence that arrived.

For teams, the grown-up form of all this is a tracing UI (LangSmith,
Langfuse, OTel-based setups) that draws turns, tool calls, children, and
token costs on a timeline. These are useful, and by all means adopt one.
But a tracing UI is a *viewer* over exactly what this chapter built:
captured requests, responses, and events. The capture is what lets you
debug, and the UI makes it more convenient to look at.

## What you now know

- When the model misbehaves, look at the request it actually received before
  blaming the model.
- Capture requests and responses at the last point before the wire. Captures
  replay exactly, so you can edit one and rerun it.
- Pin the array in tests, and watch `cache_read_input_tokens` for silent
  cost bugs.

Part III covered the ecosystem: what wraps the array, what extends it, and
how to see it. Part IV starts with the question all this visibility was
preparing for: the loop can now act on the real world with real
consequences, and some of what it wants to do, it should not be allowed to
do.

*[Next: Chapter 13 — Reflexes and Guardrails](13-reflexes-and-guardrails.md)*
