# Appendix D: Retries, Rate Limits, and Streaming

*Harness Engineering 101, Appendix — Advanced Topics.
[Series index](index.html)*

---

The main series pretended two things: that `call_llm` always returns, and
(chapter 1's sidebar) that streaming is someone else's problem. In
production the first is false constantly, and the second is false the day
your users watch a spinner for ninety seconds. This appendix is the
boring checklist: what fails, what to do about it, how streaming works on
the wire, and where generic retry advice gets LLM APIs wrong. It is an
appendix because none of it changes the mental model; it is also the
difference between a demo and a
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
"did my first attempt half-apply?" problem at the API layer. The trouble
shows up in your own loop instead: don't execute a tool twice just because a
retry returned a duplicate-looking reply. Retry at the `call_llm` layer,
below the loop, never by re-running a whole round.

**Rate limits are measured in tokens, not requests.** Providers meter
tokens per minute (input and output separately), so an agent with a fat
array exhausts limits at a *request rate that looks tiny*. This couples
Appendix D to chapter 6: context bloat manifests as 429s. It also means
parallel fan-out (chapter 7) multiplies the pressure by array size. So
production harnesses cap concurrency and share a token budget above the
subagent spawner, not just backoff below it.

**A streaming failure is a *mid-reply* failure.** The chapter 1 sidebar
deferred exactly one real problem: with `"stream": true`, the connection
can die after you have received half an answer, or half a tool call.
The rule that keeps this simple: **partial output is not output.** Treat
a broken stream as a failed request. Discard the fragment: never append it
to the array as if the model said it. (A truncated tool call executed "best
effort" is chapter 13's nightmare made of plumbing.) Then retry the whole
call. Providers make this affordable: on a retry, the prefix
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

## The wrapper

You do not need a new harness for this. It is the complete harness from the
epilogue, with one thing different: the line that used to open the connection
now calls a version that retries. The full runnable file is
[`harness/appendix-d/harness.py`](https://github.com/IsuruMaduranga/harness-engineering-101/blob/main/src/harness/appendix-d/harness.py), and you run
it exactly like before — `python3 harness.py` — it just no longer falls over
on a blip. Two small functions do the work:

```python
RETRYABLE_STATUS = {408, 409, 429, 500, 502, 503, 504, 529}

class ApiError(Exception):
    def __init__(self, kind, status=None, retry_after=None, body=""):
        super().__init__(f"{kind} error (status={status}): {body[:200]}")
        self.kind = kind             # "http" = a status came back; "network" = nothing did
        self.status = status
        self.retry_after = retry_after
        self.retryable = kind == "network" or status in RETRYABLE_STATUS

def call_once(body):
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode(),
        headers={"content-type": "application/json", "x-api-key": API_KEY,
                 "anthropic-version": "2023-06-01"})
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:          # the server answered, with an error
        after = e.headers.get("retry-after")
        raise ApiError("http", status=e.code,
                       retry_after=float(after) if after else None,
                       body=e.read().decode(errors="replace")) from e
    except (urllib.error.URLError, http.client.HTTPException, OSError) as e:
        raise ApiError("network", body=str(e)) from e   # dropped, refused, timed out

def call_with_retries(body, max_attempts=6):
    for attempt in range(max_attempts):
        try:
            return call_once(body)
        except ApiError as e:
            if not e.retryable or attempt == max_attempts - 1:
                raise                            # your problem, or out of tries
            delay = e.retry_after or min(30.0, 2 ** attempt) + random.random()
            time.sleep(delay)
```

`call_once` makes one POST and sorts whatever comes back — a reply, an error
status, or a dead socket — into either the JSON you wanted or one `ApiError`
tagged "try again" or "give up". `call_with_retries` runs it in a loop and
only retries the ones worth retrying. Inside the harness, `call_llm` still
builds the body, sets the cache breakpoint, and prints the usage line; its one
network call is now `call_with_retries(body)` instead of a bare `urlopen`.

Two lines are easy to get wrong. The first is `retryable`. A network drop, or
one of the `RETRYABLE_STATUS` codes, is worth another go; a 400 or a 401 is
your bug or your key, so it raises on the first try instead of wasting five
attempts and hiding the real error. The second is the `except` line: it
catches `http.client.HTTPException`, not just `urllib.error.URLError`. The most
common real drop — a `RemoteDisconnected` in the middle of a reply — is the
first kind and not the second. Catch only `URLError` and you sail right past
the exact crash you wrote this to prevent.

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

*[Series index](index.html)*
