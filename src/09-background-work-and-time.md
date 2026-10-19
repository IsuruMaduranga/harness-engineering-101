# Chapter 9: Background Work and Time

*Harness Engineering 101, Part II — Running Long.
[Series index](index.html) · [Prev](08-steering.md) ·
[Next: Frameworks Are Wrappers](10-frameworks-are-wrappers.md)*

---

**The failure:** everything we have built is synchronous. The model calls a
tool; the loop *waits*; the result comes back; the loop continues. If the
agent starts a 20-minute build, none of your options are good. Block the
whole loop for 20 minutes, and the agent can do nothing else while the user
watches a spinner. Time the tool out, and the model learns "builds fail
here." Or, worst and most common, the model polls: `sleep 30`, check,
`sleep 30`, check. That is forty API round trips of an expensive brain
doing a kitchen timer's job.

And beyond the single slow command sits the bigger version: work that should
happen *when something happens* ("tell me when CI goes green") or *at a
time* ("check the deploy every hour"). Our loop has no concept of time at
all. It runs when a message arrives and otherwise sits idle.

**The patch** comes in two halves that mirror each other:

1. **Let work leave the turn**: a tool result may be "started, still
   running" instead of "finished, here's the output."
2. **Let events start a turn**: the harness can call the model because
   something happened, not only because the user typed.

Together they change the shape of the system. The brain stops being a
subroutine of the user's keyboard and becomes something the harness
schedules, like any other process.

## Half one: tasks that outlive the tool call

The harness side of this is ordinary systems programming. It keeps a
**task registry**: a table of running background jobs, each with an ID, a
status, and a buffer collecting output. Three tool-visible pieces make it
work:

- The `run_command` tool grows a `run_in_background` flag. With it set, the
  tool starts the process detached and returns *immediately* with a task ID:
  `"started task b1 (npm run build), still running"`.
- A `task_output` tool: given an ID, return output collected so far, plus
  status. The model peeks when it has a reason to.
- A `task_stop` tool: kill a job that is no longer wanted.

```mermaid
sequenceDiagram
    participant B as Brain
    participant H as Harness
    participant P as build process
    B->>H: run_command("npm run build", background=true)
    H->>P: spawn, detached
    H-->>B: tool_result: "task b1 started"
    Note over B,H: loop continues — agent edits files,<br/>runs tests, answers the user
    P-->>H: (exits, code 0, output buffered)
    H-->>B: next round, injected reminder:<br/>"task b1 finished (exit 0)"
    B->>H: task_output("b1")
    H-->>B: tool_result: build log tail
```

The subtle part is the last arrow before the peek, where completion
arrives as a steering event. When the process exits, the harness does
not interrupt anything; it enqueues a chapter 8 reminder ("task b1
finished, exit 0"), which rides into the next round's user-side message.
If no round is running because the turn already ended, the harness
*starts* one: it appends the notification to the array and calls the
model. That is the first appearance of half two, something other than the
user causing an API call.

The pieces we already built made this cheap. The registry is a
dict; the notification channel is the reminder queue; the "wake the brain"
move is just `messages.append(...)` plus `call_llm(...)`, which is all a
turn ever was.

One steering detail from production looks trivial but isn't. The harness
should *block* the model from foreground `sleep`. Claude Code and
[One Code](https://github.com/IsuruMaduranga/one-code) both do this with a
guard that rejects `sleep`-style waiting and tells the model to use
background tasks and notifications instead. Models poll because polling is
what their training data does, so the harness has to make the good pattern
the easy one. How you design a tool shapes how the model behaves.

## Half two: the brain gets an alarm clock

Once "the harness can start a turn" exists for task completion, generalize
it. There are three forms, each a step up from the last. Each one is a
different *trigger* attached to the same wake-the-brain move:

**Monitors: wake on condition.** "Watch this log file for ERROR lines,"
"tell me when the CI run finishes." The harness watches cheaply
(filesystem events, a polling thread, a webhook); when the condition
trips, it injects a description of what happened and invokes the model.
So the expensive brain sleeps while the cheap body watches. This turns the
polling problem around exactly: with polling, the brain does the body's
waiting, and with monitors, the body does it.

**Schedules: wake at a time.** This is cron for agents. "Every morning,
summarize new issues"; "in an hour, check the deploy." The implementation
is a timestamp in a table and a timer loop. The interesting design
question is what the woken brain sees: a fresh array with a task prompt (a
scheduled *job*), or the continuation of an existing session (a
*follow-up*). Both are useful; the harness has to be explicit about which
it is doing, because chapter 1 taught us those are entirely different
conversations.

**Self-scheduling: the model sets its own alarm.** Give the model a
`schedule_wakeup` tool: "nothing to do until the deploy finishes, wake me
in 10 minutes." The model, mid-task, *chooses* to end the turn and name the
condition for resuming. This is the agentic version of an await: the model
yields, the harness resumes it. Claude Code's self-paced loop mode works
this way: each wakeup, the model does an increment of work and schedules the
next one, with the interval as its own judgment call ("CI takes ~8 minutes,
so check once in 8 minutes, not sixteen times in 30 seconds").

Put plainly, chapter 4's loop ran while *the model* had things to do, and
chapter 9's system runs while *anything* has things to do. User input
becomes just one event source among several: task completions, file
changes, timers, webhooks. Instead of running only when the user hits
enter, the agent becomes a long-lived process driven by events.

## The rules that keep this safe and sane

Long-running and self-waking agents amplify every earlier chapter's
concern, so the discipline matters more here:

- **Every wake costs money.** An idle "check again every 60 seconds" loop
  is a space heater made of API calls. Match wake frequency to how fast the
  watched thing actually changes; prefer condition triggers over short
  timers; make no-change wakes cheap (a short array, or a cheap model,
  Appendix A).
- **Notifications, like all steering, must be true and traceable to their
  source.** The model will act on "task b1 finished." If the registry lies
  (a crashed watcher, a dropped exit code), the model builds on a false
  world. Fail loud in the registry.
- **The user must be able to see and kill everything.** A background
  registry without a way to inspect and stop jobs ("what is running on my
  machine right now, stop it") is how agents earn distrust. This previews
  chapter 13: any autonomy you grant the agent has to stay visible and
  revocable.
- **Sessions are files, again.** A scheduled wake ten hours later lands in
  a process that may have restarted. Background work forces you to make the
  chapter 1 point literal: the array, the task registry, and the pending
  alarms all have to live on disk, or the agent's commitments die with the
  process.

## The toy harness note

I did not write a v5; the interesting parts are threads and bookkeeping
rather than new concepts, and the code would double in size for one
chapter. If you want the exercise, it is a good one: add a `tasks` dict, a
`run_in_background` flag that wraps `subprocess.Popen` and a reader thread,
a `task_output` tool, and a check at the top of each user turn that drains
finished-task notices into the next message. Every piece is standard
Python. The epilogue's full harness includes a minimal version.

## What you now know

- Slow work runs as a background task with an ID the model can check or
  stop.
- When a task finishes, the harness tells the model through the steering
  queue, and starts a turn if none is running.
- Monitors, schedules and model-set wakeups are one mechanism with three
  triggers. Keep every job visible and killable.

That finishes Part II, which covered context budgets, subagents, steering,
and background tasks. Part III steps back to look at the broader ecosystem,
starting with what actually sits inside agent frameworks.

*[Next: Chapter 10 — Every Framework Is a Wrapper Around Chapter 1](10-frameworks-are-wrappers.md)*
