# Appendix A: One Harness, Many Brains

*Harness Engineering 101, Appendix — Advanced Topics.
[Series index](index.html)*

---

The main series treated "the model" as one thing. A production harness
makes dozens of *kinds* of model calls per session, and they differ wildly
in difficulty. The main loop of a coding task needs the best brain money
buys. But also in the same session: summarizing a conversation for
compaction (chapter 6), judging whether a command is safe (chapter 13),
answering a subagent's search errand (chapter 7), writing the one-line
"Cooking..." status verb, generating a recap of what happened while the
user was away. Sending every one of those to the frontier model is like
hiring a surgeon to take blood pressure. It works. It is also several
times the cost and latency you needed to pay.

**Model routing** is the fix: the harness assigns each *job* the cheapest
brain that does it reliably. This appendix is the patterns, and the traps
that make it an advanced topic rather than chapter 5½.

## The routing table

Think of it as a column in your harness's design, next to every LLM call
site:

| Job | Difficulty profile | Typical brain |
|---|---|---|
| Main loop | open-ended, multi-step, judgment | frontier |
| Subagent: search/verify errands | narrow, factual, tool-driven | mid-tier |
| Safety classifier (ch. 13) | narrow but adversarial | small + fast, verified |
| Compaction summaries (ch. 6) | reading comprehension, structure | mid-tier |
| Recaps, status lines, labels | cosmetic | smallest available |
| Web page → answer extraction | reading comprehension | small/mid |

Two principles generate the table, and they matter more than the table:

**Route by consequence, not by difficulty alone.** A compaction summary
that is 10% worse loses a little context. A safety verdict that is 10%
worse approves `rm -rf`. The classifier job *looks* small (one yes/no),
but the risk is lopsided: a wrong "yes" is far worse than a wrong "no."
That's why chapter 13 wraps it in verification and fail-closed defaults.
Cheap brains get dangerous seats only with those seatbelts. Meanwhile the
recap job can be wrong daily and nobody is harmed. Consequence, not token
count, sets the
floor.

**A delegated task worth doing is worth a capable model.** The tempting
mistake is routing subagent work to the cheapest tier because it is
"background." Then the search agent returns a confidently wrong answer,
the main loop builds on it, and you spend frontier tokens debugging a
haiku-sized mistake. My working rule after being burned: route *down* for
jobs whose output you can verify cheaply or whose failure is cosmetic;
stay *up* for anything whose report the main loop will trust blindly
(chapter 7's whole design is that the parent cannot check the child's
work).

## Prompt tiers: the body adapts to the brain

Routing is half the pattern. The other half, less discussed: **the same
harness should not send the same array to different brains.**

Chapter 14 touched the reason: weaker models need more body. Concretely,
in a harness that runs on multiple tiers (One Code runs the same loop on
frontier models and on cheap local ones), the request itself is tiered:

- **System prompt tiers.** The frontier model gets the lean prompt; it
  does not need three paragraphs on how to use tools. The mid-tier prompt
  adds worked examples and firmer procedural scaffolding; the low-tier
  prompt is close to a checklist. Same policies, different level of
  instruction.
- **Tool set tiers.** Frontier models are happy driving everything through
  a shell (chapter 14's terminal argument is *almost* true up there).
  Weaker models do measurably better with dedicated `grep`/`find`/`ls`
  tools whose schemas constrain them, so those tools activate only on
  lower tiers. More structure as capability drops.
- **Steering density.** Reminders that a frontier model treats as noise
  are load-bearing for a small model. The reminder queue (chapter 8) can
  carry tier-dependent traffic.

The general law: **capability and scaffolding trade off.** As brains
improve, bodies simplify; at any fixed moment, a harness serving several
brains carries several densities of scaffolding. If you only ever target
one frontier model, you get to skip this machinery, which is exactly why
it is an appendix.

## Operational traps

- **Dialect drift.** Cheap-model calls often go to *different providers*
  (a local model, a budget API), so your chapter 1 dialect layer gets
  exercised. Beware silent parameter incompatibilities: one provider's
  optional field is another's hard error (temperature and reasoning
  settings are the classic offenders). Fail loudly per provider; never let
  a routing layer silently swap providers on a safety-relevant call.
- **Account for the invisible calls.** Classifier, summarizer, recap: none
  of them appear in the conversation, but all of them appear on the bill.
  Count every out-of-band call into the same usage accounting as the main
  loop (chapter 12's capture should see them too), or your cost dashboard
  is fiction.
- **Pin versions per job.** "Upgrade the main model" should not silently
  change the safety classifier's behavior. Each seat in the routing table
  is its own dependency with its own upgrade test.
- **Let the user override.** Model choice is policy, and chapter 13's
  rule applies: policy belongs in config the user can see, not constants
  in the body.

## What to remember

Routing is the harness deciding *which* brain, per job, by consequence;
tiering is the harness reshaping the array *for* that brain. Both are the
same lesson the whole series taught, applied to the brain itself: the body
adapts to what it is driving. And both are optional until the day your
bill or your latency says otherwise, which is why this lives in the
appendix and not the spine.

*[Series index](index.html)*
