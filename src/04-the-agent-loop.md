# Chapter 4: The Agent Loop

*Harness Engineering 101, Part I — The Wire.
[Series index](index.html) · [Prev](03-tools.md) ·
[Next: Caching](05-caching.md)*

---

**The failure:** v2 of our harness executes one tool call, lets the model
react, and hands control back to the human. Ask it to "find the bug in this
project and fix it" and it stalls after the first step, because step two
needs the result of step one, and nobody is there to keep the conversation
going.

**The patch:** keep the conversation going automatically, in a loop.

That is the entire chapter, and I want to be honest about that up front,
because this is the point where the industry's vocabulary gets grand:
"agentic AI," "autonomous systems," "orchestration." Here is what the words
mean in code:

```python
while True:
    reply = call_llm(messages)
    messages.append(assistant_message(reply))
    if reply["stop_reason"] != "tool_use":       # model is done talking
        break
    results = [execute_tool(b) for b in tool_calls(reply)]
    messages.append(tool_results_message(results))
```

Call the model. If it asked for tools, run them, append the results, and
call the model again. Repeat until it stops asking. **An agent is a while
loop around a chat completion.** Everything else in this series is a patch
to this loop.

## Why such a small loop does so much

The loop looks too simple to produce the behavior you have seen from coding
agents: exploring a codebase, forming a plan, hitting an error, changing
approach, finishing the job. But recall from chapter 2 that the model was
RL-trained on exactly this pattern of multi-step work: observe the result,
decide the next step. The intelligence is in the brain, and the loop's job
is to keep feeding results back so that trained behavior can run.

This is worth remembering, because it tells you where effort pays off. When
an agent performs badly, beginners add orchestration: hardcoded step
sequences, planner modules, state machines around the model. Usually the
better fix is in the array: clearer tool descriptions, better error
messages, the right context. The loop rarely needs to be smarter, but the
messages do need to be better. (Chapter 10 returns to this when we look at
frameworks.)

## Stop reasons: how the loop knows when to stop

Each API response carries a `stop_reason` telling you why the model stopped
generating. The loop is really a dispatch on this field:

| stop_reason | Meaning | Loop's job |
|---|---|---|
| `tool_use` | "I want tools run" | execute, append results, continue |
| `end_turn` | "I'm done" | exit loop, show the user the text |
| `max_tokens` | reply hit the length cap | continuation is truncated; handle it (retry higher, or continue) |
| `refusal` / safety | model declined | exit, show the message |

At the core there are two states: `tool_use` means the turn is still in
progress; `end_turn` means the brain considers the task done. A "turn" in
an agent is one user request plus however many model+tool rounds the loop
runs before `end_turn`, not one API call. A single "fix the tests" turn
might be 40 API calls. The user sees one answer; the array saw 40 round
trips. (Remember chapter 1: each of those 40 calls resent the whole array.
Hold that thought for chapter 5.)

```mermaid
flowchart TD
    U[user message] --> A[append to array]
    A --> C[call LLM]
    C --> S{stop_reason?}
    S -- tool_use --> E[execute each tool call]
    E --> R[append tool_results]
    R --> C
    S -- end_turn --> D[show reply, wait for user]
    D --> U
```

## Errors are fuel

The most surprising habit in agent building is to treat a tool failure as
information you deliver to the model, not an error you handle.

In normal software, an exception is a problem for the *programmer*. In an
agent, a failed command is a problem for the *model*, and the model is good
at it. Send back the compiler error, the stack trace, the "file not found,"
exactly as the tool produced it, and the model reads it and adjusts: fixes
the typo in the path, installs the missing package, takes another approach.
Agents debug themselves, but only if the loop delivers the failure.

Here are the three failure modes to avoid, from least to most common in the
code I review:

- **Crashing the loop on a tool error.** The model never learns what
  happened; the turn dies.
- **Swallowing the error** and returning something vague like "command
  failed." You just replaced the model's best signal with noise.
- **Fixing it silently in the harness** (retrying with a "corrected"
  argument you guessed). Now the model's picture of the world is wrong,
  and its next step builds on a state it does not know about.

The rule I follow is that a tool result is either the real output or the
real error, marked as an error, with enough detail that a person could act
on it. The model gets the same courtesy.

I learned this while building the agent mode of MI Copilot. A file write
failed, and the model never found out. It assumed the write had worked and
kept editing on top of a file that did not hold what it thought. With no
safeguard to catch it, the model corrupted the files.

The loop does need one limit, a maximum round count (say, 50). A model
stuck alternating between two failing approaches will happily burn your API
budget forever. When you hit the cap, stop and tell the user. The cap is a
failure signal for you, not for the model.

## ReAct: the loop's ancestor

You will run into the name **ReAct** (from a 2022 paper, "Reasoning +
Acting"), so let me place it for you.

Before models were trained for tool use, we got agent behavior by prompt
formatting. You instructed the model to answer in a rigid pattern:

```
Thought: I should check what files exist here.
Action: run_command["ls"]
Observation: main.py  test_main.py
Thought: Now I should read main.py.
Action: ...
```

The harness parsed the `Action:` line with string matching, executed it,
appended a fake `Observation:` line, and called the model again. It was the
same loop as ours, but with the tool protocol built from prose and hope. It
broke whenever the model varied the wording, which was often.

ReAct matters for two reasons. First, historically, its "reason, act,
observe" cycle is what got baked into models during the RL training chapter
2 described. Native tool calling is ReAct moved from the prompt into the
weights, keeping the cycle while dropping the string parsing. Second, in
practice, when you see a framework or tutorial teaching ReAct-style
prompting today, you are looking at a technique for models that lack tool
training, or at a tutorial older than it looks. With a modern model you get
the Thought (as thinking blocks), the Action (as tool_use blocks), and the
loop, natively.

## The toy harness, v3

[`harness/v3_agent.py`](https://github.com/IsuruMaduranga/harness-engineering-101/blob/main/src/harness/v3_agent.py) turns v2 into a real agent.
Here is the main change:

```python
def run_turn(messages):
    """One user turn = as many model/tool rounds as the task needs."""
    for _ in range(MAX_ROUNDS):                      # NEW: the agent loop
        reply = call_llm(messages)
        messages.append({"role": "assistant", "content": reply["content"]})
        for block in reply["content"]:
            if block["type"] == "text" and block["text"].strip():
                print(f"\nassistant> {block['text']}")

        if reply["stop_reason"] != "tool_use":       # done: hand back to user
            return

        results = []                                 # run EVERY requested tool
        for block in reply["content"]:
            if block["type"] == "tool_use":
                print(f"[tool] {block['name']}({json.dumps(block['input'])})")
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block["id"],
                    "content": execute_tool(block["name"], block["input"]),
                })
        messages.append({"role": "user", "content": results})
    print("\n[harness] hit MAX_ROUNDS, stopping this turn")
```

v3 also adds one new tool, `write_file`, so the agent can change the world
as well as observe it. With three tools and one loop in about 90 lines
total, this program can genuinely do things: try `"clone this repo, find out
why the tests fail, and fix it"` on something small. Watching your own 90
lines do that is the moment this field stops being mysterious.

Run it and watch the shape of the transcript scroll by: tool call, result,
tool call, result, text. That shape *is* the agent. Everything after this
chapter is about keeping that loop healthy when it runs long, gets
expensive, or does something dumb.

> **A note on parallel tool calls.** Models often request several tools in
> one reply (read three files at once). That is why the code collects every
> `tool_use` block before calling the API again: all results for one
> assistant message must come back in one user message, matched by ID. Run
> them concurrently if you like; deliver them together.

## What you now know

- An agent is a while loop: call the model, run the requested tools, append
  the results, and repeat until `end_turn`.
- One user turn can be dozens of API calls, so cap the rounds.
- Tool failures are input for the model. Pass them back as they are.

The loop works, so now look at what it costs. Forty rounds each resend the
entire growing array. If the array is 50,000 tokens by mid-task, forty
rounds will send roughly two million input tokens for a single user request.
Prompt caching fixes that cost, and it is why the *order* of your array
affects your API bill.

*[Next: Chapter 5 — Caching: Why Order Matters](05-caching.md)*
