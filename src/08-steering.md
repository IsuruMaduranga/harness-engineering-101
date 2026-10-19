# Chapter 8: Steering the Running Loop

*Harness Engineering 101, Part II — Running Long.
[Series index](index.html) · [Prev](07-subagents.md) ·
[Next: Background Work and Time](09-background-work-and-time.md)*

---

**The failure:** the loop is autonomous now, and autonomy has a cost. The
brain only knows what is in the array, and the array only updates when a
tool result happens to mention something. Here are three concrete versions
of the problem:

- The user edits a file *while* the agent is mid-task. The agent's picture
  of that file is now stale, and nothing tells it.
- A standing rule ("never commit without asking") was stated 80,000 tokens
  ago. Context rot (chapter 6) means it has effectively faded.
- The task has twelve steps, and around step seven the model, deep in a
  debugging rabbit hole, loses the thread of what remains.

In a chat product, none of this matters; the human course-corrects every
turn. In an agent running forty rounds unattended, the drift builds up. The
harness needs a way to talk to the brain *while the loop runs*.

**The patch:** the harness writes messages into the array itself, on the
user channel, clearly labeled as coming from the machinery rather than the
person. Claude Code calls these **system reminders**, and this chapter is
about that mechanism and its most useful special case, the todo list.

## The injection mechanism

Recall that the array is just data your program owns (chapter 1), and that
new information must enter at the *bottom*, because the top is frozen by
caching (chapter 5). The mechanism follows almost directly from those two
facts. When the harness has something to say, it appends a block to the
next outgoing user-side message:

```json
{
  "role": "user",
  "content": [
    {"type": "tool_result", "tool_use_id": "toolu_07", "content": "..."},
    {"type": "text", "text": "<system-reminder>\nThe user edited src/app.py while you were working. Its contents changed on disk. Re-read it before editing.\n</system-reminder>"}
  ]
}
```

The API knows nothing about the `<system-reminder>` tags. They are plain
text markers, a convention that tells the model "this part of the user
message is from the harness, not the human." Models follow this partly
because the labeling is honest and clear, and in Claude's case because
training has seen the convention. The system prompt typically also explains it
("`<system-reminder>` blocks are injected by the environment").

This is "system" information, but it goes on the user channel instead of
in the system prompt. There are three reasons, all from earlier chapters:

1. **Caching.** Editing the system prompt invalidates the entire cached
   array. Appending a block costs only itself (chapter 5).
2. **Position.** Models attend most reliably to recent tokens. A rule
   restated at the bottom beats a rule buried at the top. That's also why a
   reminder actually fixes context rot, instead of just passing a message
   along.
3. **Timing.** The system prompt is set per request, but what you usually
   want is to react to an *event* between two rounds, which is exactly
   where the next user-side message is about to be built anyway.

The important discipline is to send all steering through a **queue**
instead of pasting strings into the array one at a time. A production
harness has one component that owns "pending reminders": anything (a file
watcher, a permission system, a memory module) can enqueue a note, and the
queue drains into the next outgoing message in a stable order. Centralizing
this matters because scattered injections turn the array into a place where
no one can say what the model saw and why. In
[One Code](https://github.com/IsuruMaduranga/one-code) that queue is a
dedicated internal channel with ordering rules, and every feature that
needs to tell the model something goes through it. When you build a
harness, build the queue early; you will be surprised how many features
turn out to be "enqueue a reminder."

## What production harnesses steer with

To keep this concrete, here are some real reminders. Claude Code injects,
among others:

- **File-change notices.** A watcher detects that an open file changed on
  disk; next round, the model is told which file, and that its cached
  picture is stale. (This pairs with a deterministic guard in chapter 13
  that *blocks* edits based on stale reads. Both exist because informing
  the brain and blocking the hand are separate jobs.)
- **Rule refreshers.** Standing constraints re-attached near critical
  moments rather than trusted to survive from the top of the array.
- **Session context.** The memory file (chapter 6) itself arrives wrapped in
  a system-reminder block inside the first user message: labeled machine
  context on the user channel, top of conversation but *not* in the system
  prompt.
- **Mode changes.** "The user switched you to plan mode; don't edit files
  until further notice" is a reminder, not a new system prompt, for exactly
  the caching reason above.

The general pattern is that **events in the body become sentences in the
array.** That is the whole interface between the harness's event-driven
world and the brain's text-only world.

## The todo list: self-steering

The most instructive reminder in production harnesses is one the model
writes *to itself*.

Give the agent a `todo_write` tool: "maintain your task list; update
statuses as you work." The tool's implementation stores a small list in
harness state. **After each update, the harness injects the current list
back into the conversation as a reminder.** So the model's plan becomes an
artifact outside the model, and it comes back as fresh tokens at the
bottom of the array, round after round.

A model needs to be reminded of its own plan because, as chapter 2 showed,
it has no memory. Its "plan" is just tokens it emitted 50,000 tokens ago,
subject to the same context rot as everything else. Keeping the list
outside the model turns the plan from a fading memory into a standing
input. Step seven no longer depends on attention reaching back to step one;
the list is *right there*, recent and short. The same mechanism gives the
user a live progress display for free. Those checkbox lists you see in
Claude Code are the steering system itself, shown on screen.

I find this pattern neat and clean. The harness doesn't make the model
smarter here; it gives the model a *whiteboard* and keeps that whiteboard
in view. A lot of harness
engineering works the same way.

## Steering the other brain: OpenAI's developer role

One more thread to connect is the `developer` role in OpenAI's newer API,
distinct from `user` and the now-deprecated `system` name. It carries
messages from the application author, with authority above the user's and
below the platform's. If you are targeting OpenAI models, mid-conversation
harness guidance can ride as a developer message instead of a tagged block
inside a user message. That is the same idea this chapter built by
convention, made an official part of the wire format.

There are two caveats, and the first is the one chapter 2 keeps insisting
on: the roles' authority ordering is *trained* behavior, and nothing
enforces it. A developer message isn't a security boundary either. Second,
the role only covers the labeling. You still need the queue and the
events, and you still have to decide *when* to speak. The role name was
never the hard part of steering.

Today's harness conventions keep becoming tomorrow's API features: ReAct
became tool calling, and steering conventions became a role. So learning
the conventions isn't wasted effort when the feature ships, because the
feature is the same convention, standardized.

## Restraint

Steering is tempting, and from experience I can say that over-steering is
a real failure mode. Every reminder spends tokens, and a model buried in
machine-generated notes starts treating them like background noise.
Reminders keep their effect when they are rare, specific and true. I use
two simple rules: trigger a reminder from an *event* rather than a schedule
("file changed," not "every round, remind it to be careful"), and if you
find yourself injecting the same reminder constantly, move that content
into the system prompt or a tool description instead. A reminder you need
all the time points to a design problem, and more steering won't fix it.

## What you now know

- The harness talks to a running loop by appending labeled blocks
  (`<system-reminder>`) to user-side messages: bottom of the array, cache
  respected, recency exploited.
- Steering goes through a central queue; events in the body become
  sentences in the array.
- The todo tool is self-steering: the model's plan is externalized, then
  re-injected so it cannot fade. It is a whiteboard kept in view.
- OpenAI's developer role is the same pattern with official wire support.
  Harness conventions tend to become API features.
- Steer on events, sparingly. A constant reminder is a sign of a design
  problem.

The loop can now be informed and re-aimed while it runs. The next failure
is time itself. Everything so far happens *inside* one synchronous turn,
but real work has slow builds, long test suites, and things worth checking
every hour. The loop needs to let work outlive the turn, and the brain
needs an alarm clock.

*[Next: Chapter 9 — Background Work and Time](09-background-work-and-time.md)*
