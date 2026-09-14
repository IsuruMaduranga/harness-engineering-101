# Chapter 12: Changing a Brain Cheaply: Fine-tuning, LoRA, Distillation

*LLMs 101, Part II — Growing the Brain.
[Series index](index.html) · [Prev](11-rl-and-reasoning.md) ·
[Next: The KV Cache](13-the-kv-cache.md)*

---

**The failure:** everything in Part II so far was done by a lab with a
datacenter. You have a model that's nearly right for your job and a
budget of one GPU and a weekend. Here's what you can do to it, and the
conclusion first, because it's the decision that matters:

> **There are three ways to change what a model does, in order of cost:
> put text in the prompt, train a small patch onto the weights, or retrain
> the weights themselves.** Fine-tuning is for changing *behaviour*: format,
> style, a narrow task done a million times. It is a poor way to add
> *knowledge*, because facts reconstructed from weights are worse than facts
> read from the context, and they go stale. The body book's rule, "feed it
> facts, don't rely on recall," is also the rule for when not to fine-tune.

I've watched teams spend a month fine-tuning a model to know their product
docs, when a retrieval tool and a paragraph in the system prompt would have
beaten it in an afternoon. This chapter is the mechanics, so the decision is
obvious next time.

## Option 1: the prompt (no weights change)

Chapter 9 ended on in-context learning: a pretrained model picks up
patterns from its input. Post-training made it eager to. So the cheapest
way to change a model's behaviour is to tell it, and the cheapest way to
give it knowledge is to paste the knowledge in. This costs nothing at
training time, is reversible per request, works across model upgrades, and
is what the entire body book is about. Its price is paid at inference: the
instructions and facts ride along in every call (chapter 13's caching is
how that price is kept down), and there's a ceiling on how much behaviour
you can specify in text before the model starts ignoring some of it.

Start here. Most teams should also stop here.

## Option 2: LoRA (a small patch on frozen weights)

Suppose the prompt isn't enough: the output format is elaborate and the
model keeps drifting from it, or you need a small model to do one narrow
task as well as a big one, or your latency budget can't afford a
2,000-token instruction block in every call. Now you want to move the
weights. Full fine-tuning (option 3) moves all of them and is expensive.
**LoRA** (low-rank adaptation, 2021) moves almost none of them and gets
most of the benefit.

The idea is a matrix trick. A weight matrix `W` in the model is, say,
4,096 × 4,096: 16 million numbers. Instead of learning a change to all of
them, freeze `W` and learn two thin matrices, `A` (4,096 × 16) and `B`
(16 × 4,096), and use `W + B·A` in the forward pass. `B·A` is a full-size
matrix, but it's built from 130,000 numbers instead of 16 million, and
those 130,000 are the only things gradient descent touches.

```python
class LoRALinear(nn.Module):
    def __init__(self, W, rank=16):
        self.W = W; self.W.requires_grad = False        # the original, frozen
        self.A = nn.Parameter(torch.randn(W.shape[1], rank) * 0.01)
        self.B = nn.Parameter(torch.zeros(rank, W.shape[0]))   # starts at zero: no change on day one
    def forward(self, x):
        return x @ self.W.T + (x @ self.A) @ self.B     # original + patch
```

Apply that to the attention and MLP matrices of every block and you're
training under 1% of the parameters. The gradient computation is cheap,
the optimiser state is tiny, and it fits on one consumer GPU for a 7B
model. The result is a small file, tens of megabytes, that you can load on
top of the base weights or merge into them permanently. Because the patch
is separate, one deployment can hold a hundred customers' LoRAs and swap
them per request, which is how "custom model per tenant" products actually
work.

Why does such a small patch work? Because the change you want is usually
*small in a specific sense*: "write in this format," "use this tone,"
"classify these tickets" is a modest steer on a model that already knows
how to write and classify. A low-rank matrix is exactly a modest steer.
What LoRA cannot do well is teach the model a large body of new facts,
because facts are spread across the MLP weights (chapter 6) in a way that
isn't low-rank, and forcing them in tends to damage what was already there.

## Option 3: full fine-tuning

Move every weight, with chapter 8's loop on your data. This is what labs do
for post-training (chapter 10) and it's the right tool when the behaviour
change is large: a new language, a specialised domain like legal or medical
text at volume, a model that must be small and must be excellent at one
thing. It costs a multi-GPU setup and real engineering, and it has a
signature failure: **catastrophic forgetting**. Train hard on your data and
the model gets worse at everything else, because the weights that encoded
general ability were the same weights you just moved. Labs mitigate this by
mixing general data back in during fine-tuning, which you should assume you
need to do too.

## Distillation: how small models get good

There's a fourth technique that looks like fine-tuning and does a different
job. **Distillation** trains a small model to imitate a large one. Run the
big **teacher** on a lot of prompts, record its outputs (either the text it
generated, or, better, its full next-token probabilities), and train the
small **student** to reproduce them. The student learns from a far richer
signal than "the next token was X": it learns that the teacher thought X
was 60% likely and Y 30%, which encodes the teacher's uncertainty and
generalises better than raw text does.

This is how most of the small models you can run locally were made, how a
lab's cheap tier relates to its flagship, and how the first wave of open
"reasoning" small models appeared within weeks of the large ones: generate
a million long reasoning traces with the big model, fine-tune the small one
on them. It's also the mechanism behind a practical shortcut you'll see in
chapter 17: a small draft model that guesses what a big model will say has
to be a good imitator, and distillation is how you make one.

Distillation has a cost that isn't technical. Providers' terms of service
mostly forbid using their outputs to train a competing model, and the
question of which released models were distilled from which is a live
argument in the industry.

## Choosing, in one table

| You want to... | Do this | Because |
|---|---|---|
| Give the model facts about your business | prompt + retrieval | attended text beats reconstructed memory (ch. 9); facts change |
| Get a consistent output format or tone | prompt first; LoRA if the prompt keeps failing | behaviour is a small steer, which is what low-rank patches are |
| Do one narrow task cheaply at high volume | LoRA or distil into a small model | you're paying per token forever; a smaller model pays back the training |
| Handle a new language or specialist domain deeply | full fine-tune, mixed with general data | the change is large and spread across the weights |
| Match a big model with a small one | distillation | soft targets carry more signal than text |

The row that gets ignored is the first one. Fine-tuning to inject knowledge
*feels* like the serious option, and it produces a model that confidently
recalls a slightly wrong version of your docs from last quarter. The
serious option is the boring one.

## What you now know

- Three levers, in cost order: prompt, LoRA patch, full fine-tune. Try them
  in that order.
- LoRA freezes the weights and learns a thin low-rank correction per
  matrix. Under 1% of parameters, one GPU, swappable per tenant. Good for
  behaviour, poor for facts.
- Full fine-tuning moves everything and forgets things unless you mix
  general data back in.
- Distillation trains a small model on a big one's outputs, ideally its
  probabilities. It's how small models got good and how cheap tiers exist.
- Knowledge belongs in the context. Fine-tune for how the model behaves,
  not for what it knows.

That closes Part II. You now know how the numbers in the file came to be,
from random floats to a model that answers, reasons, and can be patched.
Part III is about running the thing: why a prompt cache exists, why output
tokens cost more, why the context window has a limit, and where every line
of the bill comes from.

*[Next: Chapter 13 — The KV Cache: Why Prompt Caching Exists](13-the-kv-cache.md)*
