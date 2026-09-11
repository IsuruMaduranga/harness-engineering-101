# Chapter 8: Steering the Running Loop

*Harness Engineering 101, Part II — Running Long.
[Series index](index.html) · [Prev](07-subagents.md) ·
[Next: Background Work and Time](09-background-work-and-time.md)*

---

**The failure:** the loop is autonomous now, and autonomy has a cost: the
brain only knows what is in the array, and the array only updates when a
tool result happens to mention something. Three concrete versions of the
problem:

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
about that mechanism plus its most elegant special case, the todo list.

## The injection mechanism

Recall two facts already established. The array is just data your program
owns (chapter 1), and new information must enter at the *bottom*, because
the top is frozen by caching (chapter 5). So the mechanism almost designs
itself: when the harness has something to say, it appends a block to the
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

The `<system-reminder>` tags are not an API feature. They are a convention:
plain text markers that tell the model "this part of the user message is
from the harness, not the human." Models follow this partly because the
labeling is honest and clear, and in Claude's case because training has
seen the convention. The system prompt typically also explains it
("`<system-reminder>` blocks are injected by the environment").

Why the user channel and not the system prompt, if it's "system"
information? Three reasons, all from earlier chapters:

1. **Caching.** Editing the system prompt invalidates the entire cached
   array. Appending a block costs only itself (chapter 5).
2. **Position.** Models attend most reliably to recent tokens. A rule
   restated at the bottom beats a rule buried at the top. That's also why a
   reminder actually fixes context rot, instead of just passing a message
   along.
3. **Timing.** The system prompt is set per request, but what you usually
   want is to react to an *event* between two rounds: precisely where the
   next user-side message is about to be built anyway.

The important discipline is that steering is a **queue, not one-off string
pasting**. A production harness has one component that owns "pending
reminders": anything (a file watcher, a permission system, a memory module)
can enqueue a note, and the queue drains into the next outgoing message in a
stable order. Centralizing this matters because scattered injections turn
the array into a place where no one can say what the model saw and why. In
[One Code](https://github.com/IsuruMaduranga/one-code) that queue is a first-class internal channel with ordering rules,
and every feature that needs to whisper to the model goes through it. When
you build a harness, build the queue early; you will be surprised how many
features turn out to be "enqueue a reminder."

## What production harnesses steer with

A tour of real reminders, so this stays concrete. Claude Code injects,
among others:

- **File-change notices.** A watcher detects that an open file changed on
  disk; next round, the model is told which file, and that its cached
  picture is stale. (This pairs with a deterministic guard in chapter 13
  that *blocks* edits based on stale reads. Notice the doubling: informing
  the brain and restraining the hand are different organs.)
- **Rule refreshers.** Standing constraints re-attached near critical
  moments rather than trusted to survive from the top of the array.
- **Session context.** The memory file (chapter 6) itself arrives wrapped in
  a system-reminder block inside the first user message: labeled machine
  context on the user channel, top of conversation but *not* in the system
  prompt.
- **Mode changes.** "The user switched you to plan mode; don't edit files
  until further notice" is a reminder, not a new system prompt, for exactly
  the caching reason above.

The general pattern: **events in the body become sentences in the array.**
That is the whole interface between the harness's event-driven world and
the brain's text-only world.

## The todo list: self-steering

The most instructive reminder in production harnesses is one the model
writes *to itself*.

Give the agent a `todo_write` tool: "maintain your task list; update
statuses as you work." The tool's implementation stores a small list in
harness state, and here is the trick: **after each update, the harness
injects the current list back into the conversation as a reminder.** The
model plans. That plan becomes an artifact outside the model, and it comes
back as fresh tokens at the bottom of the array, round after round.

Why does a model need to be reminded of its own plan? Because (chapter 2,
always chapter 2) the model has no memory: its "plan" was tokens it emitted
50,000 tokens ago, subject to the same rot as everything else. The
externalized list turns the plan from a fading memory into a standing
input. Step seven no longer depends on attention reaching back to step one;
the list is *right there*, recent and short. The same mechanism gives the
user a live progress display for free, which is why you see those checkbox
lists in Claude Code: you are watching the steering system, not a UI
gimmick.

I find this pattern neat and clean: the harness does not make the model
smarter, it gives the model a *whiteboard*, and then makes sure the
whiteboard stays in view. Much of harness engineering is exactly this shape.

## Steering the other brain: OpenAI's developer role

One more thread to connect. OpenAI's newer API added a `developer` role,
distinct from `user` and the now-deprecated `system` name. It carries
messages from the application author, with authority above the user's and
below the platform's. If you are targeting OpenAI models, mid-conversation
harness guidance can ride as a developer message instead of a tagged block
inside a
user message: the same idea this chapter built by convention, promoted to a
first-class citizen of the wire format.

Two honest caveats. First: as chapter 2 keeps insisting, the roles'
authority ordering is *trained* behavior, not enforcement. A developer
message isn't a security boundary either. Second, the promotion covers the
labeling, not the machinery: you still need the queue, the events, the
decisions about *when* to speak. The hard part of steering was never the
role name.

This pattern keeps repeating: today's
harness convention keeps becoming tomorrow's API feature (ReAct became tool
calling; steering conventions became a role). Learning the conventions is
not wasted effort when the feature ships; the feature is the convention,
standardized.

## Restraint

A closing warning from experience: steering is tempting, and over-steering
is a real failure mode. Every reminder spends tokens, and a model buried in
machine-generated notes starts treating them like background noise;
reminders regain power when they are rare, specific, and true. Two simple
rules I use. A reminder should be triggered by an *event*, not a schedule
("file changed," not "every round, remind it to be careful"). And if you
find yourself injecting the same reminder constantly, the content probably
belongs in the system prompt or a tool description instead; recurring need
is a design signal, not a steering job.

## What you now know

- The harness talks to a running loop by appending labeled blocks
  (`<system-reminder>`) to user-side messages: bottom of the array, cache
  respected, recency exploited.
- Steering goes through a central queue; events in the body become
  sentences in the array.
- The todo tool is self-steering: the model's plan is externalized, then
  re-injected so it cannot fade. Whiteboard, kept in view.
- OpenAI's developer role is the same pattern with first-class wire
  support. Conventions become features.
- Steer on events, sparingly. A constant reminder is a sign of a design
  problem.

The loop can now be informed and re-aimed while it runs. Next failure: time
itself. Everything so far happens *inside* one synchronous turn, but real
work has slow builds, long test suites, and things worth checking every
hour. The loop needs to let work outlive the turn, and the brain needs an
alarm clock.

*[Next: Chapter 9 — Background Work and Time](09-background-work-and-time.md)*
