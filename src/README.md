# Harness Engineering 101

*The LLM is the brain. The harness is the body.*

*By [Isuru Wijesiri](https://isuruwijesiri.com) — originally published at
[isuruwijesiri.com/blog/2026/harness-engineering-101](https://isuruwijesiri.com/blog/2026/harness-engineering-101/).*

A blog series about building AI agents from first principles. No frameworks, no
buzzword tour, no architecture diagrams with twelve boxes. One idea, developed
carefully:

> An LLM API is stateless. Every turn, you send the entire conversation as a
> JSON array and get text back. A **harness** is the program that builds,
> maintains, and protects that array. Everything the field calls "agents" is
> a set of patches to that one loop, and each patch exists because something
> concrete broke.

I started building generative AI systems when GPT-3.5 was the frontier. There
were no tool calls, no caching, no agents. We used the OpenAI SDK to send a
message array and got formatted text out. Everything that has been added since
then was added for a reason, and if you learn the additions in order, as
solutions to failures, none of it is complicated. That is what this series
does.

Each chapter follows the same shape: here is the failure, here is the minimal
patch, here is what the patch costs you. A toy harness in plain Python (raw
HTTP, no SDK) grows across the series. By the epilogue you will have a working
mini coding agent in about 300 lines, and the durable knowledge that there is
no magic anywhere in the stack.

Production harnesses (Claude Code, and One Code, my reimplementation of it on
another agent runtime) appear as evidence that the patterns are real, never as
the vehicle for the explanation.

## Reading order

### Part I — The Wire (nothing is magic)

| # | Chapter | The failure it patches |
|---|---------|------------------------|
| 1 | [It's Just a JSON Array](01-its-just-a-json-array.md) | "How do I even talk to this thing?" |
| 2 | [The Brain: A Next-Token Black Box](02-the-brain.md) | "Why does it behave like that?" |
| 3 | [Tools: JSON Mapped to Functions](03-tools.md) | The brain can't touch the world |
| 4 | [The Agent Loop](04-the-agent-loop.md) | One tool call isn't enough |
| 5 | [Caching: Why Order Is Load-Bearing](05-caching.md) | Resending the array gets expensive |

### Part II — Running Long (the array under pressure)

| # | Chapter | The failure it patches |
|---|---------|------------------------|
| 6 | [Context Is a Budget, Not a Bag](06-context-is-a-budget.md) | The window fills up |
| 7 | [Subagents: Fork the Context](07-subagents.md) | One array can't hold all the work |
| 8 | [Steering the Running Loop](08-steering.md) | The brain drifts mid-task |
| 9 | [Background Work and Time](09-background-work-and-time.md) | The loop is synchronous; the world isn't |

### Part III — The Ecosystem (naming what you already understand)

| # | Chapter | The failure it patches |
|---|---------|------------------------|
| 10 | [Every Framework Is a Wrapper Around Chapter 1](10-frameworks-are-wrappers.md) | Abstraction anxiety |
| 11 | [Extending the Body: MCP, Skills, Deferred Loading, Hooks](11-extending-the-body.md) | Capabilities don't fit in the array |
| 12 | [Debugging the Array](12-debugging-the-array.md) | You can't fix the prompt you can't see |

### Part IV — Trust, Domains, and Data

| # | Chapter | The failure it patches |
|---|---------|------------------------|
| 13 | [Reflexes and Guardrails](13-reflexes-and-guardrails.md) | The loop will do something dumb |
| 14 | [Case Study: Coding Agents](14-coding-agents.md) | How specialized does the body need to be? |
| 15 | [RAG Was a Harness Pattern All Along](15-rag.md) | A thousand names for one idea |

### Epilogue

| | Chapter | |
|---|---------|---|
| E | [Build Your Own](16-epilogue-build-your-own.md) | The complete toy harness, annotated |

### Appendix — Advanced Topics

Standalone pieces. Read them when you need them.

- [A. One Harness, Many Brains](appendix-a-one-harness-many-brains.md) — model routing, prompt tiers, cost engineering
- [B. Worktrees and Isolation](appendix-b-worktrees-and-isolation.md) — giving parallel agents separate copies of the world
- [C. Modes and Plan Mode](appendix-c-modes-and-plan-mode.md) — harness-enforced operating states (coding-specific)
- [D. Retries, Rate Limits, and Streaming](appendix-d-retries-rate-limits-streaming.md) — the unglamorous plumbing, plus how streaming works on the wire

## The toy harness

The running example lives in [`harness/`](harness/). Each version is the
previous one plus the chapter's patch:

- `harness/v1_chat.py` — chapter 1: the 30-line chat loop
- `harness/v2_tools.py` — chapter 3: tools bolted on
- `harness/v3_agent.py` — chapter 4: the agent loop
- `harness/v4_subagents.py` — chapter 7: forked contexts
- `harness/harness.py` — epilogue: the complete ~300-line agent

Python 3.10+, zero dependencies (raw `urllib`), Anthropic Messages API by
default. Swapping the wire format for OpenAI's is chapter 1 homework, and the
point of the whole series is that it's *only* the wire format you'd swap.

## Diagrams

Flow and structure diagrams are inline [mermaid](https://mermaid.js.org/)
blocks (GitHub renders them natively). Quantitative plots are PNGs generated
by the scripts in [`diagrams/`](diagrams/):

```bash
cd diagrams && python3 gen_all.py   # regenerates every PNG
```

Edit a script, rerun, and the chapter picks up the new image.

## Out of scope

Training or fine-tuning models, TUI implementation, provider billing and
OAuth plumbing. This series is about the body, not about growing a brain.
