# Appendix A: Backprop by Hand

*LLMs 101, Appendix. [Series index](index.html) · [Epilogue](21-epilogue-train-your-own.md) ·
[Next: Appendix B](appendix-b-training-at-scale.md)*

---

Chapter 8 said `loss.backward()` computes the gradient of the loss with
respect to every weight and asked you to trust it. This appendix does the
computation by hand once, on a model so small the whole thing fits on a
napkin, and checks the answer against PyTorch. If you take one thing from
it: **backpropagation is the chain rule from calculus, applied
mechanically, backwards through the operations of the forward pass.**
There's no other idea in it.

## The smallest language model that has a gradient

A bigram model, chapter 1, as a matrix instead of a counting table. The
vocabulary has five tokens. The model is a 5 × 5 matrix `W`. Given current
token `x`, the scores for the next token are row `x` of `W`. Softmax the
row and you have probabilities. The loss is the negative log probability of
the true next token `y`. Three lines:

```python
logits = W[x]                                  # row x of W
probs = np.exp(logits) / np.exp(logits).sum()  # softmax
loss = -np.log(probs[y])                       # surprise at the true next token
```

Now the question training asks: if I change one entry of `W` slightly, how
does `loss` change? That's the gradient, and we need it for all 25 entries.

## The chain rule, twice

The loss depends on `probs`, which depends on `logits`, which depends on
`W`. The chain rule says: multiply the sensitivities along the chain.

**Step 1: loss with respect to logits.** This is the one derivative worth
memorising in all of deep learning, because softmax followed by
negative-log-likelihood collapses to something absurdly clean:

> ∂loss / ∂logits[j] = probs[j] − (1 if j == y else 0)

In words: the gradient on each score is *the probability the model gave
it, minus one for the correct answer*. If the model gave the true token
0.2, its gradient is 0.2 − 1 = −0.8: push that score up, hard. If it gave a
wrong token 0.5, the gradient is +0.5: push it down. Every training signal
in this book, at the last layer, is this vector. Deriving it takes half a
page of algebra with logs and exponentials; the result is the line above.

**Step 2: logits with respect to W.** `logits` is row `x` of `W`, copied.
So the gradient on row `x` of `W` is exactly the gradient on `logits`, and
every other row's gradient is zero: those entries weren't used, so changing
them changes nothing.

```python
d_logits = probs.copy(); d_logits[y] -= 1   # probs - onehot(y)
d_W = np.zeros_like(W); d_W[x] = d_logits    # only the row that was used
```

That's the whole backward pass. Two lines for a two-operation forward
pass. Then the nudge, `W - step * d_W`, and one training step is done.

## Checking it

[`gpt/appendix_a_backprop.py`](https://github.com/IsuruMaduranga/harness-engineering-101/blob/main/llms-101/src/gpt/appendix_a_backprop.py)
runs those lines and then asks PyTorch for the same gradient with autograd:

```
probs before: [0.209 0.292 0.089 0.256 0.153]  loss 1.875
gradient on row x: [ 0.209  0.292  0.089  0.256 -0.847]
probs after one step: [0.191 0.256 0.087 0.229 0.238]  loss 1.438
hand-computed gradient matches torch autograd: yes
```

The true token had probability 0.153 and gradient −0.847. One step of size
0.5 moved it to 0.238 and cut the loss from 1.88 to 1.44. The other four
probabilities all went down, in proportion to how much undeserved mass
they had. `torch` agrees to floating-point precision.

## What changes in a real network

Nothing conceptual. A transformer's forward pass is a few hundred
operations instead of two: matrix multiplies, additions, softmaxes, layer
norms, GELUs. Each has a known local derivative. Autograd records the
sequence of operations as they run (the "tape"), then walks it backwards,
multiplying each operation's local derivative by the gradient arriving from
above, exactly as we did with softmax then row-select. Two things make it
worth having a framework do it:

- **Bookkeeping.** A matrix multiply `y = x @ W` has gradient `dW = x.T @
  dy` and `dx = dy @ W.T`. Fine once; error-prone across 300 operations
  with 12 kinds of shape.
- **Memory.** The backward pass needs the forward pass's intermediate
  values (the `probs` above, for instance). For a big model that's most of
  the training memory, and frameworks manage it (or recompute it, a trick
  called activation checkpointing) so you don't have to.

Residual connections (chapter 6) look different from this angle, too.
`x = x + f(x)` has gradient `dx = dy + (gradient through f)`. The `dy` term
passes straight through untouched, which is why a hundred stacked blocks
still deliver a usable gradient to the bottom layer. Without the `+`, the
gradient would be a product of a hundred local derivatives, each less than
one, and it would vanish. The residual is a gradient highway. That's the
mechanical reason "add, don't replace" made depth possible.

## What you now know

- The gradient of softmax-plus-log-loss with respect to the scores is
  `probs − onehot(true)`. That vector is the training signal at the top of
  every language model.
- Backprop is the chain rule walked backwards through the forward pass's
  operations. Autograd records the operations and does the walk.
- Residual connections pass the gradient straight through, which is why
  deep stacks train.

*[Next: Appendix B — Training at Scale](appendix-b-training-at-scale.md)*
