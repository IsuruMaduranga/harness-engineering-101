# Appendix D: Retries, Rate Limits, and Streaming

*Harness Engineering 101, Appendix — Advanced Topics.
[Series index](README.md)*

---

The main series pretended two things: that `call_llm` always returns, and
(chapter 1's sidebar) that streaming is someone else's problem. In
production the first is false constantly, and the second is false the day
your users watch a spinner for ninety seconds. This appendix is the
boring checklist: what fails, what to do about it, how streaming
actually works on the wire, and the failure modes specific to LLM APIs
that generic retry wisdom gets wrong. It is an appendix because none of it
changes the mental model; it is also the difference between a demo and a
service.

## The kinds of failure

| Failure | Signal | Correct reaction |
|---|---|---|
| Overloaded / server error | 500/529, or Anthropic's `overloaded_error` | retry with backoff |
| Rate limited | 429, often with `retry-after` | wait *what the header says*, then retry |
| Timeout / connection drop | no response | retry, but safely (see below) |
| Context too long | 400 with explicit message | **do not retry**: compact (ch. 6) or fail up |
| Invalid request | other 400s | **do not retry**: it's your bug; capture it (ch. 12) |
| Auth / billing | 401/403 | stop, tell the human |

The first discipline is just the split: **temporary vs permanent.**
Retrying a 529 is correct; retrying a 400 is a loop that burns budget and
buries the real error. Your wrapper should distinguish them on day one.

Standard mechanics, briefly, since they are the same as any API client:
exponential backoff with jitter (1s, 2s, 4s..., randomized so parallel
subagents don't stampede in sync), honor `retry-after` when present, cap
total attempts, and surface the *last real error* when giving up, not
"retries exhausted."

## How streaming actually works

Chapter 1's sidebar made the architectural claim: streaming is
presentation. Here is the mechanical half it deferred.

Set `"stream": true` and the provider keeps the HTTP connection open and
sends **server-sent events** (SSE): a long series of small
`data: {...}` lines instead of one JSON body. Each event is a fragment.
Anthropic's stream, slightly simplified, looks like:

```
event: message_start          → shell of the reply (id, model, empty content)
event: content_block_start    → block 0 begins (type: "text")
event: content_block_delta    → {"text": "The bug"}
event: content_block_delta    → {"text": " is on line"}
event: content_block_delta    → {"text": " 12: ..."}
event: content_block_stop     → block 0 done
event: message_delta          → stop_reason, output token usage
event: message_stop           → the reply is complete
```

OpenAI's version is a series of chunks carrying `choices[0].delta`
fragments; different spelling, same idea. The harness's job is
**accumulation**: append each delta to the block it belongs to, and when
the stream ends, you hold *exactly* the assistant message a non-streaming
call would have returned. You append it to the array and continue the loop
as if streaming never happened. That is the precise sense in which
streaming is presentation: it changes how the reply *travels*, not what
the array *stores*. The model never knows, and neither does any code above
`call_llm`.

Two wrinkles worth knowing before you meet them:

- **Tool calls stream too, as partial JSON.** The arguments of a
  `tool_use` block arrive as string fragments (`{"pa`, `th": "ma`,
  `in.py"}`) that only parse once the block completes. So streaming buys
  you nothing for tool *execution*: you must wait for
  `content_block_stop` anyway. What it buys is display: showing the user
  which tool is being called while the arguments are still arriving. Never
  execute from a partially assembled call; that is the appendix's earlier
  rule (partial output is not output) in its sharpest form.
- **Streaming stops being optional as requests grow.** This is the
  operational surprise: providers enforce timeouts on non-streaming
  requests, and a big-context, long-output call (exactly what agents make)
  can exceed them. Anthropic requires streaming for large `max_tokens`
  values, and SDKs quietly stream under the hood for long calls. So a
  production harness ends up streaming *everything* and accumulating,
  even when no UI wants the deltas. The toy harness gets away without it
  only because its outputs are modest.

The engineering reason to stream even a headless call: **first-token
latency becomes your health signal.** A stream that has produced nothing
for 60 seconds is distinguishable from a model thinking hard (thinking
deltas and fine-grained events keep arriving); one connection carries both
the answer and the liveness check.

## What's LLM-specific

Four things the generic checklist misses:

**Retries are only safe because the API is stateless.** Chapter 1's
property earns its keep here: a retried request is *identical* in effect
to the first attempt, because the server holds nothing. There is no
"did my first attempt half-apply?" problem at the API layer. The place this
*does* cause trouble is your own loop: never execute tools twice
because a retry returned a duplicate-looking reply, so retry at the
`call_llm` layer, below the loop, never by re-running a round.

**Rate limits are measured in tokens, not requests.** Providers meter
tokens per minute (input and output separately), so an agent with a fat
array exhausts limits at a *request rate that looks tiny*. This couples
Appendix D to chapter 6: context bloat manifests as 429s. It also means
parallel fan-out (chapter 7) multiplies pressure by array size, so
production harnesses put a concurrency cap and a shared token-budget
limiter above the subagent spawner, not just backoff below it.

**A streaming failure is a *mid-reply* failure.** The chapter 1 sidebar
deferred exactly one real problem: with `"stream": true`, the connection
can die after you have received half an answer, or half a tool call.
The rule that keeps this simple: **partial output is not output.** Treat
a broken stream as a failed request: discard the fragment (never append
it to the array as if the model said it: a truncated tool call executed
"best effort" is chapter 13's nightmare made of plumbing), then retry
the whole call. Providers make this affordable: on a retry, the prefix
you already sent is cache-hit (chapter 5), so re-asking costs a fraction
of the original. Statelessness plus caching is what makes "just retry
the whole thing" the right architecture rather than a waste.

**Long requests need long timeouts, and one more distinction.** A
frontier model thinking hard over a big array can legitimately take
minutes; a timeout tuned for REST APIs will kill healthy requests. Set
generous ceilings (streaming helps here operationally: first-token
latency is your health signal, and a stalled stream is distinguishable
from a slow think). And when a request dies from *your* side, log it as
such (chapter 12's capture should record failures and retries too), or
your debugging sessions will chase model behavior that was actually your
socket config.

## The wrapper, sketched

Everything above is thirty lines around chapter 1's function:

```python
def call_llm_reliable(body, max_attempts=5):
    for attempt in range(max_attempts):
        try:
            return call_llm_once(body)
        except ApiError as e:
            if not e.retryable:                    # 400s, auth: your problem
                raise
            delay = min(60, 2 ** attempt) * (1 + random.random())
            delay = e.retry_after or delay          # server knows best
            log(f"attempt {attempt+1} failed ({e.kind}), sleeping {delay:.1f}s")
            time.sleep(delay)
    raise LastError
```

Plus the two policies that don't fit in a function: a token-aware
concurrency cap above your fan-out, and "discard partial streams, retry
whole." That is the entire subject. SDKs and gateways will happily do the
function part for you (a fine use of chapter 10's plumbing category);
the policies stay yours either way.

## What to remember

Split temporary failures from permanent ones and only retry the temporary.
Statelessness makes API-level retries free of side effects; keep them below
the loop so tools never re-run. Rate limits are measured in tokens, so
context size and fan-out, not request count, are what exhaust them. Partial streamed output
is not output. And capture failures like you capture requests, because
"the model is being weird" is sometimes a half-dead socket.

*[Series index](README.md)*
