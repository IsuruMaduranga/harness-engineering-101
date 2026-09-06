# Chapter 10: Every Framework Is a Wrapper Around Chapter 1

*Harness Engineering 101, Part III — The Ecosystem.
[Series index](README.md) · [Prev](09-background-work-and-time.md) ·
[Next: Extending the Body](11-extending-the-body.md)*

---

**The failure this chapter patches is in you, not the software:** abstraction
anxiety. Open any "how to build an agent" tutorial and you meet a wall of
proper nouns: LangChain, LangGraph, LlamaIndex, CrewAI, AutoGen, the OpenAI
Agents SDK, the Claude Agent SDK, Vercel's AI SDK. Each with its own
vocabulary: chains, runnables, graphs, crews, executors. The impression a
newcomer gets is that agents are a specialist technology with a steep
learning curve, and that the frameworks contain something you could not
build yourself.

You have spent nine chapters building what they contain. This chapter is a
decoder ring: for each kind of framework vocabulary, what it maps to in the
toy harness. Not a takedown; several of these libraries are good, and I will
say when to use them. But you should evaluate them the way you would
evaluate any dependency, from a position of knowing what the job is, rather
than adopting one because the job looks mysterious.

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
most aura. A LangChain chain is function composition: do A, feed its output
to B. A LangGraph graph is a state machine whose nodes call models. Both are
things Python already does with functions and `if`. The frameworks add
observability hooks, retries, and parallelism conveniences on top; useful,
but the *concept* is control flow you have written since your first year of
programming.

## Why frameworks look bigger than they are

The honest reason the ecosystem feels heavy is history. In the GPT-3.5 era,
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

Meanwhile, notice what the strongest production agents do. Claude Code is a
bespoke harness over the raw API. So are most serious coding agents, and so
is One Code (over a minimal general-purpose runtime, pi). When Anthropic
ships the Claude Agent SDK, it is a *thin* layer: the loop, tool dispatch,
context management: chapter 4 and 6, productized. The trend line of the
field points at models-plus-thin-harness, not at deep abstraction stacks.

## The real costs and the real benefits

What you actually get from a framework, stated without romance:

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

**The price, and it is exactly one thing:** the framework stands between
you and the array. Every chapter of this series has been about controlling
what enters the array, in what order, with what byte stability. A framework
that "manages the prompt for you" is managing your caching (ch. 5), your
steering (ch. 8), and your context budget (ch. 6), according to its idea of
what those should be, often invisibly. The classic experience: your agent
misbehaves, and the fix requires knowing exactly what was sent to the
model, and you spend a day digging through abstraction layers to find the
actual bytes on the wire. If the framework you choose makes the outgoing
request easy to see and shape, the price is small; if it hides the request
as an implementation detail, the price is your ability to do the job this
series describes.

So my rule, having built harnesses both ways:

> Take small, transparent layers for plumbing (an SDK; a provider-dialect
> wrapper). Be suspicious of layers that want to own the array. And never
> adopt one to avoid learning what it wraps, because what it wraps is nine
> short chapters.

## How to read an unfamiliar framework in ten minutes

The skill this chapter is really teaching: when the next framework arrives
(there will be a next one), you can locate it instead of learning it from
scratch. Ask four questions of its documentation:

1. **Where is the loop?** Find the code that calls the model repeatedly on
   `tool_use`. Everything is oriented around it.
2. **Who builds the array?** Can you see and modify the final request
   (messages, order, system prompt) before it is sent? This is the
   transparency question, and it is the make-or-break one.
3. **What is its unit of composition?** Chains (function composition),
   graphs (state machines), agents-as-tools (ch. 7): all fine, all just
   control flow. You are checking whether the unit fits your task's shape.
4. **What does it do that is *not* in this series?** Usually the honest
   answers are integrations, tracing, and deployment plumbing. Those are
   real; weigh them against the transparency answer from question 2.

A framework that answers all four cleanly is a fine tool. One whose docs
answer with vocabulary ("the executor invokes the runnable graph") is
telling you where the complexity will hurt.

## What you now know

- Framework vocabulary maps one-to-one onto things you built in chapters 1
  through 9. Chains and graphs are control flow; memory is the array;
  executors are the loop.
- The heaviness is historical: the tricks weak models needed became the
  abstractions, and then the models absorbed the tricks.
- Frameworks genuinely offer plumbing, provider abstraction, tracing, and
  team legibility. Their one real cost is distance from the array, which is
  where all the engineering in this series happens.
- Evaluate any framework with four questions, starting with: can I see the
  bytes going to the model?

Next: the parts of the ecosystem that are *not* wrappers: the standards and
mechanisms for getting new capabilities into the array from outside your
codebase. Tools someone else hosts, instructions loaded on demand, and what
to do when the tool list itself outgrows the context budget.

*[Next: Chapter 11 — Extending the Body: MCP, Skills, Deferred Loading, Hooks](11-extending-the-body.md)*
