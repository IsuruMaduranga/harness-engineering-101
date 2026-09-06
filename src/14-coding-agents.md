# Chapter 14: Case Study: Coding Agents

*Harness Engineering 101, Part IV — Trust, Domains, and Data.
[Series index](README.md) · [Prev](13-reflexes-and-guardrails.md) ·
[Next: RAG](15-rag.md)*

---

Every pattern in this series was demonstrated on a coding body, but I have
mostly kept the coding-specific machinery out of view. This chapter puts it
in view, for two reasons. First, coding agents are where harness
engineering is most developed, so they preview what other domains will
build. Second, they host the best design argument in the field: how
specialized should the body be? We will build up the specialized answer,
then give the "a terminal is all you need" counterargument its full due,
because it is not a strawman; it is half right.

## Why coding won

It is not an accident that agents got good at coding first. The domain is
almost suspiciously well suited to the loop from chapter 4:

- **The world is text.** Code, configs, logs, diffs, docs: everything the
  agent must perceive serializes losslessly into the array. No cameras, no
  robots. A coding agent's "perception problem" was solved by `cat`.
- **The world pushes back, cheaply and honestly.** Compilers, test suites,
  linters, and type checkers are free oracles: run them and the array
  receives an objective, detailed verdict on the agent's last action.
  Chapter 4 said errors are fuel; software is the domain where fuel is
  unlimited and free. (This same property, verifiable outcomes, is why
  chapter 2's RL training used so much coding, which made models better at
  coding, which justified better coding harnesses. The flywheel was
  domain-specific.)
- **Mistakes are reversible.** Chapter 13's recoverability layer comes for
  free: the entire world state is files in a version-controlled directory.
  `git checkout` undoes an afternoon. Compare a robotics harness, where the
  world has no undo, and notice how much of chapter 13 the filesystem
  quietly gave us.

When you evaluate "agents for X" in any other domain, this list is the
checklist: how much of X's world is text, does X give fast honest feedback,
can X's mistakes be undone? The distance from "yes, yes, yes" is a fair
estimate of the harness work ahead.

## The organs of a coding body

What Claude Code-class harnesses actually add on top of the generic loop.
Each is a chapter of this series, specialized:

**Edit tools shaped for how models fail.** The naive write tool (chapter
3's `write_file`) makes the model retype whole files: slow, expensive, and
an invitation to transcription errors in the 900 lines it did *not* mean to
change. Production harnesses use targeted edits: the model supplies an
exact existing snippet and its replacement, and the *harness* refuses the
edit if the snippet does not match the file exactly (or matches twice).
Notice what that constraint does: it converts hallucination into a loud,
harmless error. The edit tool's design *is* a guardrail; tool shape is
behavior shape.

**Search as a first-class sense.** Real repositories dwarf the context
budget (chapter 6), so the body ships fast, targeted perception: glob by
name, grep by content, with results as compact hit-lists rather than file
dumps. Cheap senses are what make "pull, don't push" (chapters 6 and 15)
actually work; a model with good grep reads 2% of the codebase instead of
loading 100%.

**LSP: the IDE's nervous system, replumbed.** The Language Server Protocol
is how editors get diagnostics, go-to-definition, and references from
per-language analyzers. Your IDE is an LSP client; a serious coding
harness is one too. The headline use is the **diagnostics delta**: after
each edit, ask the language server what is *newly* broken, and inject the
answer as a chapter 8 reminder ("your last edit introduced: line 42, `foo`
possibly undefined"). The agent hears about the type error it just created
in seconds, without compiling, without being told to check, in exactly the
event-triggered, bottom-of-array form steering wants. It closes the same
feedback loop a human closes by seeing red squiggles, and the difference in
agent quality between "finds out at test time" and "finds out immediately"
is large. Go-to-definition and find-references similarly replace expensive
grep-and-read excursions with precise single answers: budget again.

**Git as an organ.** Not just "the agent can run git" (the terminal gives
that), but the harness *itself* leaning on git: snapshot state so chapter
13's recoverability holds, show the user diffs of what the agent changed,
gate auto-approval on whether damage would be recoverable, fence parallel
agents into worktrees (Appendix B).

Beyond these come the coding-specific deployments of everything else you
have seen: read-tracking reflexes on edits (chapter 13's file tracker),
project memory files with build commands and conventions (chapter 6),
plan-then-execute modes for large changes (Appendix C). None of it is a new
mechanism. That is the point of a case study: the domain body is the
generic patterns, instantiated with domain knowledge.

## The counterargument: a terminal is all you need

Now the argument that deserves its own section, because a real school of
practitioners holds it and ships on it:

> Give the model `bash` and nothing else. Reading is `cat`, searching is
> `grep` and `find`, editing is `sed` or a heredoc, diagnostics is running
> the compiler, git is git. Fifty years of Unix already built every tool
> the job needs, the models were *pre-trained on* those tools' manuals and
> a million shell transcripts, and every organ above is redundant plumbing
> that will age badly as models improve.

The strong points are genuinely strong. Generality: the terminal handles
the long tail (awk one-liners, docker, obscure build systems) that no
finite tool list covers; every curated toolset eventually meets a task its
designer did not anticipate, and the escape hatch is always the shell.
Fidelity: chapter 2 says the model has seen vastly more `grep` usage than
usage of your bespoke `search_files` schema. And the trend argument has
history on its side: this series has already recorded harness machinery
dissolving into model capability twice (ReAct into tool training, chapter
4; elaborate chains into long contexts, chapter 10). Betting that
edit-snippet tools and diagnostic injection also dissolve is not crazy.

Where it breaks down today, and notice each of these is a *body* concern,
not a smarts concern:

- **Permissioning** (chapter 13). A structured `edit_file(path, old, new)`
  can be gated by path, tracked, and diffed. `bash -c "sed -i ..."` is an
  opaque string; the reflex layer degrades to parsing shell, which is a
  losing game. The terminal-only body has one giant hand that the spinal
  cord cannot see into.
- **The feedback loops are real wins.** Nothing in the terminal *pushes*
  diagnostics after an edit; the model must remember to check (probability
  < 1, chapter 11's hooks lesson). Read-tracking, stale-edit refusal,
  injected deltas: these caught real mistakes deterministically, and
  dropping them costs actual quality today.
- **Weaker brains need more body.** On frontier models, terminal-only is
  serviceable. Run the same experiment on a mid-tier model (I have, while
  testing One Code against cheap models) and structured tools with tight
  schemas and loud errors visibly outperform free-form shell: the
  structure is doing steering work the weak brain cannot do alone.
  Appendix A returns to this trade.

So my scorecard, honestly held: terminal-only is directionally right about
where value lives (the model, improving) and materially wrong about
what today's body still buys: safety legibility, deterministic feedback,
and floor-raising for cheaper models. Production harnesses agree by
behavior: every major one ships the shell *and* the structured organs, and
lets the model choose. The synthesis is not a compromise; it is the design:
**structured tools for the hot paths where shape buys safety and feedback,
the terminal for the long tail, and guardrails around both.**

## What you now know

- Coding won because its world is text, its feedback is free and honest,
  and its mistakes are undoable. Use that triple as a yardstick for any
  other domain.
- The coding body's organs: mismatch-refusing edit tools (tool shape as
  guardrail), cheap search senses, LSP diagnostics injected as steering,
  git as recoverability infrastructure.
- The terminal-only argument is half right: the shell is the irreplaceable
  long tail, and history favors bodies dissolving into brains. It
  undercounts what structure buys *now*: permissionability, pushed
  feedback, and weak-model floors.
- Ship both. Let the model choose. Gate everything.

One chapter of the main sequence remains, and it is the retrospective one:
the pattern this whole series has been circling (put the right data in the
array at the right time) had a famous name before agents were mainstream.
Time to demystify RAG.

*[Next: Chapter 15 — RAG Was a Harness Pattern All Along](15-rag.md)*
