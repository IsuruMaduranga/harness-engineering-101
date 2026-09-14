# Chapter 16: Mixture of Experts

*LLMs 101, Part III — Running the Brain.
[Series index](index.html) · [Prev](15-sampling-and-structured-output.md) ·
[Next: Making It Cheaper](17-making-it-cheaper.md)*

---

**The failure:** chapter 9 said bigger is better, and chapter 13 said every
token pays for a pass through every weight. Together they're a trap. Ten
times the parameters means ten times the knowledge and ten times the cost
per token, forever, for every user. Here's the way out, and the sentence
that decodes every "8x7B" and "active parameters" you'll see on a model
card:

> **Replace each block's single MLP with several, and add a tiny router
> that sends each token to only a few of them.** The model gets the
> knowledge capacity of all the MLPs and pays the compute of a few. Total
> parameters can be enormous; *active* parameters per token stay modest. The
> price is memory: every expert has to be loaded, even though most sit idle
> for any given token. That's why mixture-of-experts is a provider's
> technique, not a laptop's.

I put off understanding this one for a long time because the word
"experts" suggested something semantic, as if there were a maths expert and
a poetry expert. There isn't. There are eight MLPs and a softmax.

## Why the MLP is the thing to split

Chapter 6 made two claims worth recalling. The MLP is where facts live, and
the MLP is two-thirds of each block's parameters. If you want more knowledge
in the model, the MLPs are what need to grow. But the MLP is applied to
every token identically, so growing it grows the cost of every token.

Now observe: a given token almost never needs *all* of that knowledge. A
token in the middle of a Python function doesn't need the weights that
encode French irregular verbs. Dense models pay for the irrelevant weights
anyway, because every weight is multiplied by every token. The whole idea
of MoE is to stop doing that.

## The mechanism

Replace the block's one MLP with *N* MLPs of the same shape, called
**experts**. Add a **router**: a single small matrix that maps a token's
vector to *N* scores. Softmax the scores, take the top *k* (typically 1 or
2, or 8 out of a few hundred in newer designs), run the token through only
those experts, and combine their outputs weighted by the router's scores.

```python
def moe_layer(x, router_W, experts, k=2):
    scores = softmax(x @ router_W)                  # (N,): how much each expert "wants" this token
    top = np.argsort(scores)[::-1][:k]              # pick the k highest
    out = sum(scores[i] * experts[i](x) for i in top)
    return out / scores[top].sum()
```

That's the whole layer, and everything else in the block (attention,
norms, residuals) is unchanged and shared. During training, the router
learns which experts to send which tokens to, and the experts specialise as
a side effect of receiving different traffic. When researchers look at
what the specialisation is, it's mostly *not* by topic. It's by token
shape: one expert receives punctuation, one gets numbers, one gets
whatever follows a verb. The "experts" are experts in statistical
neighbourhoods of the token space, not in subjects. The name was
aspirational.

## Reading the model card

Now the arithmetic that makes the numbers on a card make sense:

| Model | Experts | Active per token | Total parameters | Active parameters |
|---|---|---|---|---|
| Mixtral 8x7B (2023) | 8 | 2 | ~47B | ~13B |
| DeepSeek-V3 (2024) | 256 routed + 1 always-on | 8 routed + the shared one | 671B | 37B |

"8x7B" does *not* mean 56B: attention and embeddings are shared, so it's
eight 7B-shaped MLP stacks on one shared skeleton, about 47B total. And
"13B active" is the per-token cost: attention plus two experts. Mixtral runs
at roughly the speed and price of a 13B dense model while carrying 47B
parameters' worth of knowledge, and it beat the dense 70B models of its
generation on most benchmarks. DeepSeek-V3 pushes the same trick to 671
billion total with only 37 billion touched per token, which is how a model
that size can be served at a low per-token price. When a provider's
flagship is much cheaper than its size suggests, this is almost always why.
Most frontier models since 2024 are believed to be MoE, though the closed
labs don't say.

## What it costs

**Memory.** Every expert must be resident on the GPUs, because any token
might route to any of them. A 671B model needs 671B parameters' worth of
memory (well over a terabyte at 16-bit) even though each token uses 37B.
Serving it means a rack of GPUs holding experts that mostly idle. This is
fine for a provider with a thousand users sharing the rack (chapter 17's
batching makes the idle experts busy again), and hopeless for one user on
one GPU. It's why the models you run locally are dense or small-MoE, and
why the giant MoEs are API products.

**Load balancing.** Left alone, the router finds a couple of experts it
likes and sends everything there, and the others never learn. Training
adds a balancing term (an extra loss, or a bias that nudges the router
toward underused experts) to force even traffic. Get it wrong and you've
trained an expensive dense model with a lot of dead weight attached.

**Routing is a hard decision inside a soft network.** Gradient descent
(chapter 8) needs everything to be differentiable, and "pick the top two"
isn't. The standard trick is to multiply the chosen experts' outputs by the
router's soft scores so at least the *weighting* gets gradients, and to
accept that the choice itself is learned indirectly. This makes MoE
training touchier than dense training, and it's a large part of why the
technique took years to become standard after it was first published.

**Non-determinism.** Chapter 15's rounding errors are amplified here. A
near-tie in the router, disturbed by a last-bit difference from batching,
sends a token to a different expert, and the output changes noticeably
rather than imperceptibly. MoE models are the ones where "same prompt,
temperature zero, different answer" is most visible.

**Fine-tuning.** LoRA (chapter 12) on an MoE model has to decide which
experts to patch, and the router may not send your fine-tuning data where
you expect. It works, with more care.

## The pattern behind it

Step back and this is the same move as the KV cache, grouped-query
attention and (next chapter) quantization: **find the work that's being
done and not used, and stop doing it.** Dense MLPs compute contributions
from every fact for every token and throw most of them away. MoE computes
only the contributions the router thinks will matter. The knowledge
capacity of the model is decoupled from the cost per token for the first
time, and once that decoupling exists, the scaling-law logic of chapter 9
changes: you can keep growing total parameters (more knowledge) while
holding active parameters (cost) roughly flat. That's the bet most of the
industry has made.

## What you now know

- MoE replaces one MLP per block with many, plus a router that picks a few
  per token. Attention and everything else stay shared.
- Total parameters measure knowledge capacity; active parameters measure
  per-token cost. "8x7B" is ~47B total, ~13B active.
- Experts specialise by token statistics, not by subject.
- The price is memory (all experts resident), touchy training (load
  balancing, non-differentiable routing) and visible non-determinism.
- It decouples model size from cost per token, which is why frontier models
  can be huge and cheap at the same time.

*[Next: Chapter 17 — Making It Cheaper: Quantization, Speculative Decoding, Batching](17-making-it-cheaper.md)*
