# Appendix B: Worktrees and Isolation

*Harness Engineering 101, Appendix — Advanced Topics.
[Series index](index.html)*

---

Chapter 7 gave each subagent its own *array*. That isolates their
attention. It does not isolate their *world*: every agent still reads and
writes the same directory. The moment you run two agents concurrently on
the same project (a fan-out of fixers, or just the main loop plus a
background child), you have reinvented the race condition. Say agent A edits
`utils.py` while agent B is mid-refactor of the same file. B's
read-before-write guard (chapter 13) starts firing constantly. Or worse, it
doesn't, and their work merges by accident, in place, with no record.

The fix is the same one operating systems and CI systems reached: **give
each worker its own copy of the world, and merge deliberately.**

## Git worktrees: cheap parallel worlds

For coding agents the mechanism already exists in git. A **worktree**
(`git worktree add ../task-a branch-a`) is an additional checkout of the
same repository in another directory, sharing the object store: creating
one is fast and cheap, unlike a full clone. Each agent gets:

- its own directory (no file-level races),
- its own branch (its work is a named, reviewable, revertable unit),
- the shared history (chapter 13's recoverability, per agent).

The harness pattern: when spawning an agent whose task is "make changes"
(rather than "look things up"), create a worktree, point the child's tools
at that directory as their root, and record the branch. When the child
reports done, the *merge* is its own deliberate step: show the human a diff,
or run tests, then `git merge` / rebase, then remove the worktree. If the
child failed or went wrong, removal is the whole cleanup: the main tree
never saw a byte of the mess. An unchanged worktree can be deleted
automatically; a changed one is evidence.

Claude Code exposes exactly this as an option on its Agent tool and as
`EnterWorktree` for the main session; One Code implements the same. The
noteworthy design choice in both: isolation is *opt-in per task*, because
worktrees have a cost (below), and read-only errands don't need them.

## What worktrees don't isolate

A worktree fences the *files under version control*, and nothing else.
The remaining shared surfaces, in the order they will cause you trouble:

- **Untracked state**: `node_modules`, build caches, `.env` files.
  A fresh worktree has none of them, so the child's first `npm test`
  fails mysteriously, or spends ten minutes reinstalling. Harnesses
  handle this with setup hooks (chapter 11) or by copying/symlinking
  known state; you must decide per project, which is why "isolation:
  worktree" sometimes disappoints people expecting magic.
- **Global mutable state**: databases, docker daemons, package caches,
  the network. Two agents "isolated" in worktrees can still fight over
  port 3000 or the same test database. Worktrees isolate the *code*, not
  the *runtime*.
- **The machine itself.** For that, you're back to chapter 13's
  sandboxes: containers or VMs per agent. A worktree is just the
  lightweight, code-only version of one. The spectrum is: same directory
  (free, unsafe) → worktree (cheap, code-isolated) → container (heavier,
  runtime-isolated) → VM (heaviest, machine-isolated). Pick per task
  risk, and remember the spectrum composes: a worktree *inside* a
  container is a perfectly sensible rung.

## The non-coding version

The pattern goes beyond git. It's the actual principle:
**agents should work on transactions, not on the
live world.** A draft email, not the send button. A staging table, not
production. A proposed diff, not an applied one. The worktree is just the
coding domain's excellent built-in transaction. When you build a harness
for a domain without one, building the "propose, review, commit" step is
some of the most valuable safety work available (chapter 13's blast
radius, implemented as workflow rather than walls).

## What to remember

Context isolation (chapter 7) and world isolation are two separate things;
you need the second the moment writers run in parallel. Git worktrees are the
cheap, natural unit for code: directory + branch per agent, deliberate
merge, trivial cleanup. They do not isolate runtime or untracked state,
and they are one rung on a spectrum that ends at VMs. The principle
underneath is transactions: let agents propose in private, and make the
integration a visible step a human can approve.

*[Series index](index.html)*
