# Chapter 12: Debugging the Array

*Harness Engineering 101, Part III — The Ecosystem.
[Series index](README.md) · [Prev](11-extending-the-body.md) ·
[Next: Reflexes and Guardrails](13-reflexes-and-guardrails.md)*

---

**The failure:** your agent does something strange. It ignores an
instruction, calls a tool with nonsense arguments, insists a file says
something it does not. Your instinct, trained by ordinary software, is to
read your code. But your code is not where the behavior lives. The behavior
came from the model, and the model saw exactly one thing: the final
assembled request. Which, by now, is built by many hands: system prompt
composer, memory injection, skills menu, MCP schemas, reminder queue,
compaction. Your mental picture of the array and the actual bytes on the
wire drift apart, and every one of the strange behaviors above is usually
that drift.

The debugging rule for harness work is one sentence:

> **You cannot fix the prompt you cannot see. So look at the actual
> request, first, always.**

Almost nobody does this on day one, because no beginner tutorial mentions
it. Every production harness team learns it, usually after a painful week.
This chapter is the practice, so you can skip the week.

## Capture: log the bytes on the wire

The most basic tool is surprisingly small: intercept every request your
harness sends and write it to disk, whole. In the toy harness it is three
lines in `call_llm`:

```python
def call_llm(messages, tools, system):
    body = {...}
    if os.environ.get("HARNESS_DEBUG"):
        with open(f"debug/req_{time.time_ns()}.json", "w") as f:
            json.dump(body, f, indent=2)             # the WHOLE request
    ...
    # and mirror the response: stop_reason, content, usage
```

Not a summary, not your own log lines saying "injected memory": the request
body itself, plus the response with its `usage` block. Everything else in
this chapter stands on this file existing. Two design notes from production:

- **Capture at the last possible point** before the HTTP call. If any layer
  can modify the request after your logging (an SDK adding headers and
  defaults, a middleware reordering tools), your capture lies to you. The
  gap between "what my code assembled" and "what left the machine" is
  exactly where a class of bugs lives. This is also chapter 10's
  transparency question in operational form: a framework that will not let
  you see this point is a framework you cannot debug at this level.
- **Capture responses too, especially `usage`.** The response tells you the
  stop reason (chapter 4's control signal), and usage tells you the cache
  story, coming up next.

With capture on, the strange behaviors become findable. The model "ignored"
your instruction? Open the request: the instruction fell out during
compaction, or your reminder never drained from the queue, or it is
present but buried at token 3,000 of an 8,000-token system prompt. The
model misread a file? Find the `tool_result`: your truncation cut the file
at exactly the wrong line. In my experience the split is roughly: a third
"it was never in the array," a third "it was in the array but mangled or
misplaced," and only the last third anything like model failure.

## The vital sign: cache-read tokens

The response's `usage` block reports how the input was billed, including
`cache_read_input_tokens`. Chapter 5 made the promise; this is where you
verify it. On any round after the first, cache reads should be nearly the
whole input. So plot it, or just print it per round:

```
round 12: input 84,213 | cache_read 82,900 ✓
round 13: input 86,120 | cache_read 0      ← something rewrote the prefix
```

That second line is a silent 10x cost bug being caught in real time, and
*nothing else surfaces it*: no error, no behavior change, just money. A
timestamp crept into the system prompt; a tool list serialized in a
different order; some feature "helpfully" edited an old message. Cache-read
tokens are the harness's pulse. Production harnesses watch it continuously;
One Code surfaces the cache-hit rate in its status line, on the theory that
a vital sign belongs on the dashboard, not in a postmortem.

## Replay: the experiment the architecture gives you for free

Here is where statelessness (chapter 1) pays off for debugging. The
provider keeps nothing; the request is the entire world state. Therefore: a
captured request is a *perfect reproduction case*. Load the JSON, resend
it, and you re-run the exact moment of the bug, no setup, no session, no
"steps to reproduce."

And because it is just JSON, you can *edit it before resending*. This is
the experimental method for prompts:

1. Capture the request where the model went wrong.
2. Form a hypothesis: "it grabbed the wrong function because the truncated
   tool result lost the signature."
3. Edit that one block. Resend. Did the behavior change?
4. Repeat, changing one thing at a time.

This is chapter 1's "you can edit assistant messages and the model can't
tell," graduated into a lab technique: you can edit *history itself* and
ask "what would you have done if the past were this instead?" (Sampling is
random, so run the interesting cases a few times; temperature 0 tightens
it further.) A `replay.py` that loads, optionally tweaks, and resends a
captured request is thirty lines, and it converts prompt debugging from
folklore ("try rewording it?") into experiments.

## Fidelity tests: pinning the array in CI

Capture and replay are interactive. The durable version is asserting the
array's shape in your test suite, so drift gets caught by a robot instead
of a bill.

The trick is to fake only the API and keep everything else real: run the
harness against a mock that records requests, drive a scripted turn, then
assert on what got assembled. Three levels, from loose to strict, all
cheap because no real model is involved:

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
assert byte-equality against that. Behavior lives in the array; matching
arrays is matching behavior. That principle is also why capture is the
first thing to build, not the last: it is the ground truth for every other
claim about what your harness does.

## Seeing multi-agent and multi-part systems

Two places the "look at the array" rule needs extra plumbing:

**Subagents** (chapter 7): the parent sees only the report, by design, so
when a child returns a wrong answer, capture is your only window into its
thirty rounds. Persist every child's transcript (they are just arrays;
sessions are files) keyed by the spawning tool call, and make them
inspectable. Debugging then reads like a normal investigation: find the
round where the child went wrong, and it is usually one of the same three
causes: never in its array (a bad task briefing from the parent, most
common), mangled in its array, or model failure.

**The event side** (chapters 8, 9): reminders and wakeups originate outside
any request, so log the *queue* too: what was enqueued, by whom, when it
drained. The question "why did the model think a file changed?" is answered
in the queue log; the array only shows the sentence that arrived.

For teams, the grown-up form of all this is a tracing UI (LangSmith,
Langfuse, OTel-based setups) that draws turns, tool calls, children, and
token costs on a timeline. Useful, and by all means adopt one; but notice
it is a *viewer* over exactly what this chapter built: captured requests,
responses, and events. The capture is the capability. The UI is
convenience.

## What you now know

- Harness bugs live in the assembled request, and mostly divide into "not
  in the array" / "in the array but wrong" / actual model failure, in
  roughly that order. Look at the bytes first.
- Capture requests and responses at the last point before the wire; the
  drift between what you meant and what was sent is a bug factory.
- `cache_read_input_tokens` is the pulse. Zero after round one is a silent
  10x cost bug, and only this number tells you.
- Statelessness makes captures perfectly replayable and *editable*: prompt
  debugging becomes controlled experiments.
- Pin the array in CI: presence, placement, bytes. Persist subagent
  transcripts and the steering queue, or you have no way to check those
  subsystems.

Part III closed the ecosystem: what wraps the array, what extends it, and
how to see it. Part IV starts with the question all this visibility was
preparing for: the loop can now act on the real world with real
consequences, and some of what it wants to do, it should not be allowed to
do.

*[Next: Chapter 13 — Reflexes and Guardrails](13-reflexes-and-guardrails.md)*
