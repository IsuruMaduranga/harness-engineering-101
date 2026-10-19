# Chapter 10: Every Framework Is a Wrapper Around Chapter 1

*Harness Engineering 101, Part III — The Ecosystem.
[Series index](index.html) · [Prev](09-background-work-and-time.md) ·
[Next: Extending the Body](11-extending-the-body.md)*

---

**The failure this chapter patches is in you, not the software:** abstraction
anxiety. Open any "how to build an agent" tutorial and you meet a wall of
proper nouns: LangChain, LangGraph, LlamaIndex, CrewAI, AutoGen, the OpenAI
Agents SDK, the Claude Agent SDK, Vercel's AI SDK. Each has its own
vocabulary: chains, runnables, graphs, crews, executors. A newcomer comes away
thinking agents are a specialist skill with a steep learning curve, and
that these frameworks hold something you couldn't build yourself.

You have spent nine chapters building what they contain. This chapter is a
decoder ring: for each kind of framework vocabulary, what it maps to in the
toy harness. This is not an attack on them; several of these libraries are
good, and I will say when to use them. But evaluate them the way you'd
evaluate any dependency: know what the job is first, instead of adopting one
because it looks mysterious.

## The decoder ring

| Framework word | What it is underneath | Where you built it |
|---|---|---|
| Model / LLM wrapper | `call_llm()` with provider dialects | ch. 1 |
| Prompt template | an f-string that builds a message | ch. 1 |
| Memory | the messages array, kept and resent | ch. 1 |
| Conversation store / thread | the array, saved to disk | ch. 1 |
| Tool / function | schema + a dispatch table entry | ch. 3 |
| Structured output parser | a forced tool call | ch. 3, sidebar |
| Agent / AgentExecutor | the while loop over stop_reason | ch. 4 |
| ReAct agent | the same loop for models without tool training | ch. 4 |
| Multi-agent / crew / handoff | the loop, called as a function with a fresh array | ch. 7 |
| Middleware / callbacks | code at the append points of the array | ch. 8 |
| Human-in-the-loop node | an `ask_user` tool, or an approval gate | ch. 3, 13 |
| Retriever | a search that pastes results into the array | ch. 15 |
| Chain / graph / workflow | ordinary control flow (function calls, ifs) around model calls | everywhere |

The last row deserves a sentence, because "chains" and "graphs" carry the
most mystery. A LangChain chain is function composition: do A, feed its
output to B. A LangGraph graph is a state machine whose nodes call models. Both are
things Python already does with functions and `if`. The frameworks add
observability hooks, retries, and parallelism conveniences on top; useful,
but the *concept* is control flow you have written since your first year of
programming.

## Why frameworks look bigger than they are

The ecosystem feels heavy because of its history. In the GPT-3.5 era,
the models were much less capable, so the harness had to do more:
ReAct-style output parsing with regex (ch. 4), few-shot templates for every
task, chains of small calls because one call could not carry a multi-step
task. LangChain (2022) is a museum of that era's necessary tricks, kept
alive by compatibility. Then the RL training described in chapter 2 moved
the hard parts *into the models*: tool calling replaced output parsing,
long contexts replaced elaborate chain topologies, trained agentic behavior
replaced hand-built planning loops. The frameworks did not shrink when the
models grew; they pivoted to orchestration, observability, and enterprise
integration, and the vocabulary stayed.

Meanwhile, look at what the strongest production agents do. Claude Code is
a custom harness over the raw API. So are most serious coding agents, and
so is [One Code](https://github.com/IsuruMaduranga/one-code) (over a
minimal general-purpose runtime, pi). The Claude Agent SDK that Anthropic
ships is a *thin* layer: the loop, tool dispatch and context management,
which is chapters 4 and 6 productized. And the field is moving toward
models plus a thin harness, and away from deep abstraction stacks.

## The real costs and the real benefits

My rule is to use small, transparent layers and stay skeptical of any layer
that wants to own the array. Here is what you actually get from a framework,
and what it costs.

**Worth paying for:**

- **Provider abstraction** when you genuinely serve multiple model vendors:
  someone maintains the dialect zoo (ch. 1's table, times every provider)
  so you don't.
- **The boring plumbing**: retries, rate-limit backoff, streaming plumbing,
  usage accounting (Appendix D), written once and tested by thousands of
  users.
- **Observability integrations**: tracing UIs that show every request and
  response, which chapter 12 will convince you that you need in some form.
- **Team legibility**: a known framework is documentation. A new hire who
  knows LangGraph reads your LangGraph app.

**What it costs:** the framework stands between you and the array. Every
chapter of this series has been about controlling what enters the array, in
what order, with what byte stability. A framework that "manages the prompt
for you" is managing your caching (ch. 5), your steering (ch. 8), and your
context budget (ch. 6), according to its idea of what those should be, often
invisibly. A common failure goes like this: your agent misbehaves, the fix
requires knowing exactly what was sent to the model, and you spend a day
digging through abstraction layers to find the actual bytes on the wire. If
the framework makes the outgoing request easy to see and shape, the price is
small. If it hides the request as an implementation detail, it makes
debugging and tuning the harness much harder.

I have built harnesses both ways: on the raw OpenAI SDK for MI Copilot, on
the Vercel AI SDK for the Ballerina copilot, and on top of pi for One Code.
This is my rule:

> Take small, transparent layers for plumbing (an SDK; a provider-dialect
> wrapper). Be suspicious of layers that want to own the array. And never
> adopt one to avoid learning what it wraps, because what it wraps is nine
> short chapters.

## How to read an unfamiliar framework in ten minutes

What this chapter is really teaching is how to place the next framework
when it arrives (there will be a next one), instead of learning it from
scratch. Ask four questions of its documentation:

1. **Where is the loop?** Find the code that calls the model repeatedly on
   `tool_use`. Everything is oriented around it.
2. **Who builds the array?** Can you see and modify the final request
   (messages, order, system prompt) before it is sent? This is the
   transparency question, and it is the make-or-break one.
3. **What is its unit of composition?** Chains (function composition),
   graphs (state machines) and agents-as-tools (ch. 7) are all fine, and
   all of them are control flow. You are checking whether the unit fits
   your task's shape.
4. **What does it do that is *not* in this series?** Usually the honest
   answers are integrations, tracing, and deployment plumbing. Those are
   real; weigh them against the transparency answer from question 2.

A framework that answers all four cleanly is a fine tool. One whose docs
answer with vocabulary ("the executor invokes the runnable graph") is
telling you where the complexity will hurt.

## What you now know

- Framework terms map onto things you built in chapters 1 to 9: chains are
  control flow, memory is the array, executors are the loop.
- Frameworks give real value in plumbing, provider abstraction and tracing.
- Their cost is distance from the array, so first ask whether you can see
  the bytes sent to the model.

The next chapter covers the parts of the ecosystem that are *not*
wrappers: the standards and mechanisms for getting new capabilities into
the array from outside your codebase. That means tools someone else hosts,
instructions loaded on demand, and what to do when the tool list itself
outgrows the context budget.

*[Next: Chapter 11 — Extending the Body: MCP, Skills, Deferred Loading, Hooks](11-extending-the-body.md)*
