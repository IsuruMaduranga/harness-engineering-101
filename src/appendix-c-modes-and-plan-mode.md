# Appendix C: Modes and Plan Mode

*Harness Engineering 101, Appendix — Advanced Topics.
[Series index](README.md)*

---

Chapter 13 mentioned **permission modes** as the answer to approval
fatigue: a session-level dial the user sets, from "ask me about
everything" to "run free." This appendix looks closer at modes as a
mechanism, and at the one mode interesting enough to deserve its own
essay: plan mode. It sits in the appendix because the specifics are
coding-agent-shaped; the underlying idea (the body has operating states)
transfers anywhere, but the worked example is code.

## A mode is a body state, not a brain state

The defining property: **a mode changes what the harness will do, not
what the model is.** Same brain, same array mechanics; different rules at
the gate. A typical coding-agent dial:

| Mode | Reads | Edits in project | Shell / risky | Meaning |
|---|---|---|---|---|
| default / ask | auto | prompt | prompt | trust nothing yet |
| accept-edits | auto | auto | prompt | trust its editing, not its shell |
| auto / full | auto | auto | classifier + reflexes (ch. 13) | flow state |
| plan | auto | **refused** | **refused** | think, don't touch |

The implementation is exactly where you would put it: the gate from
chapter 13 takes the mode as an input. Three engineering notes that make
modes work in practice:

- **The brain must be told, on the body's channel.** A mode switch
  mid-session becomes a steering reminder (chapter 8): "the user switched
  to plan mode; do not modify anything until further notice." Not a system
  prompt edit, for chapter 5's caching reason. But remember chapter 13's
  hierarchy: the reminder is *advice* so the model behaves sensibly; the
  gate is the *enforcement*. Both, always. A mode that exists only in the
  prompt is a suggestion; only in the gate, a source of baffling refusals.
- **Switching must be one keystroke.** Modes fight approval fatigue only
  if changing them is cheaper than clicking "yes" repeatedly
  (Claude Code cycles modes on a single hotkey). A buried setting becomes
  a permanent setting, and users end up in the wrong trust setting for
  the task at hand.
- **Mode is policy, so it lives in visible config** with sane defaults
  per project (chapter 13's rule). A repository can ship "this project
  defaults to ask" the same way it ships a linter config; note the trust
  question, though: project-level config that *grants* autonomy is config
  an attacker can commit, so production harnesses deliberately refuse to
  read permission *grants* from files a repo can carry, or gate them
  behind user confirmation.

## Plan mode: approve the intention, not the keystrokes

The dial above trades safety against interruptions action by action. Plan
mode moves the trade to a better place: **separate deciding from doing.**

The flow: the user poses a substantial task with the body in a read-only
state. The agent explores freely (reads, searches, subagents: all safe),
then produces a *plan*: the files it will change, the approach, the
risks. The plan is presented as a document; the human reviews and
approves *it*, once; the body switches to an execution mode and the loop
carries the plan out, usually with edit-level prompts now waved through
because the intention was already reviewed.

Why this is the most valuable mode, in the terms this series built:

- **Humans are better at judging plans than diffs at 40 actions per
  turn.** One review of "rename the module and update 12 call sites"
  beats twelve interruptions asking about call site #7 with attention
  already spent. Approval moves up to a higher level, where human
  judgment is actually good (chapter 13's scoped autonomy, realized).
- **Exploration is free when writing is impossible.** In plan mode the
  gate refuses writes *by design*, so the agent can be given full
  autonomy to read: no fatigue at all during the phase that generates
  most tool calls on a hard task. The read-only Explore subagent
  (chapter 7) was this same trick at the agent level; plan mode applies
  it to a session phase.
- **The plan is a steering document.** Once approved, the plan text
  enters the array and works like the todo list (chapter 8): a standing,
  re-injectable statement of intent that execution rounds stay anchored
  to. Drift from an approved plan is also *detectable*: a hook or
  reflex can flag "editing a file the plan never mentioned."
- **Interruption becomes cheap.** Approve-then-execute has a natural
  checkpoint: rejecting the plan costs nothing, versus unwinding a
  half-applied change. In transaction terms (Appendix B): plan mode makes
  the intention itself the first transaction.

The failure mode to design against: **plan-and-forget.** A plan approved
against the codebase as it was ten minutes ago can be invalidated by the
world (a teammate's push, a failing dependency install). Execution still
needs chapter 13's reflexes live: the plan authorizes intent, not stale
assumptions. Production plan modes re-verify as they go, and treat "the
plan no longer matches reality" as a stop-and-replan event, not something
to push past.

## What to remember

Modes are the gate controlled by a trust setting, switched cheaply, mirrored
to the brain as steering but enforced in the body. Plan mode is the
standout: make writing impossible, let the agent think at full autonomy,
review the intention once, then execute against the approved plan.
It converts the human from a click-through checkpoint into a reviewer of
intentions, which is the job they were always better at.

*[Series index](README.md)*
