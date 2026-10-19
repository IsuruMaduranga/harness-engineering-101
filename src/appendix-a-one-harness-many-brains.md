# Appendix A: One Harness, Many Brains

*Harness Engineering 101, Appendix — Advanced Topics.
[Series index](index.html)*

---

The main series treated "the model" as one thing. A production harness
makes dozens of *kinds* of model calls per session, and they differ wildly
in difficulty. The main loop of a coding task needs the best brain money
buys. But the same session also summarizes a conversation for compaction
(chapter 6), judges whether a command is safe (chapter 13), answers a
subagent's search errand (chapter 7), writes the one-line "Cooking..."
status verb, and generates a recap of what happened while the user was
away. Sending every one of those to the frontier model is like hiring a
surgeon to take blood pressure. It works, but it costs several times the
money and latency you needed to pay.

**Model routing** is the fix: the harness assigns each *job* the cheapest
brain that does it reliably. This appendix covers the patterns, and the
traps that make it an advanced topic rather than chapter 5½.

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

Two rules matter more than the table itself:

**Route by consequence, not by difficulty alone.** A compaction summary
that is 10% worse loses a little context. A safety verdict that is 10%
worse approves `rm -rf`. The classifier job *looks* small (one yes/no),
but the risk is lopsided: a wrong "yes" is far worse than a wrong "no."
That's why chapter 13 wraps it in verification and fail-closed defaults.
You only put a cheap model in a high-risk role when you have those extra
checks around it. Meanwhile the recap job can be wrong daily and nobody is
harmed. The consequence of a mistake sets the floor, not the token count.

**A delegated task worth doing is worth a capable model.** The tempting
mistake is routing subagent work to the cheapest tier because it is
"background." Then the search agent returns a confidently wrong answer,
the main loop builds on it, and you spend frontier tokens debugging a
haiku-sized mistake. This happened to me while testing One Code, and the
reason is that the main model usually trusts what its subagent reports.
Pairing a weak subagent with a strong main model is a bad idea. My working
rule now is to route
*down* for jobs whose output you can verify cheaply or whose failure is
cosmetic, and to stay *up* for anything whose report the main loop will
trust blindly (chapter 7's whole design is that the parent cannot check
the child's work). One Code applies this rule on its own. When the session
runs on a mid-tier or frontier model, the subagent model it picks
automatically is never below mid-tier, and it never picks the smallest
models.

## Prompt tiers: the body adapts to the brain

Routing is only half of the work. The other half is that **the same harness
should not send the exact same array to different models.**

Chapter 14 touched on the reason: weaker models need more body. Concretely,
in a harness that runs on multiple tiers
([One Code](https://github.com/IsuruMaduranga/one-code) runs the same loop
on frontier models and on cheap local ones), the request itself is tiered:

- **System prompt tiers.** The frontier model gets the lean prompt; it
  does not need three paragraphs on how to use tools. The mid-tier prompt
  adds worked examples and firmer procedural scaffolding; the low-tier
  prompt is close to a checklist. The policies are the same; only the
  level of instruction changes.
- **Tool set tiers.** Frontier models are happy driving everything through
  a shell (chapter 14's terminal argument is *almost* true up there).
  Weaker models do measurably better with dedicated `grep`/`find`/`ls`
  tools whose schemas constrain them, so those tools activate only on
  lower tiers. Structure goes up as capability drops.
- **Steering density.** Reminders that a frontier model treats as noise
  are what a small model depends on. The reminder queue (chapter 8) can
  carry tier-dependent traffic.

The general rule is that **capability and scaffolding trade off.** As
models improve, the harness needs less scaffolding, and a harness that
supports several model tiers needs a different amount of scaffolding for
each. If you only ever target one frontier model, you get to skip this
machinery, which is why it is an appendix.

## Operational traps

- **Dialect drift.** Cheap-model calls often go to *different providers*
  (a local model, a budget API), so your chapter 1 dialect layer gets
  exercised. Beware silent parameter incompatibilities: one provider's
  optional field is another's hard error (temperature and reasoning
  settings are the classic offenders). Fail loudly per provider; never let
  a routing layer silently swap providers on a safety-relevant call.
- **Account for the invisible calls.** The classifier, summarizer and recap
  calls never appear in the conversation, but all of them appear on the
  bill.
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
