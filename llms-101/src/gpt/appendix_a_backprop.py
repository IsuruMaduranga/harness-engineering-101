#!/usr/bin/env python3
"""Appendix A: backpropagation by hand on the smallest possible language
model, checked against PyTorch's autograd.

The model: a bigram model as a matrix. Token id in, one-hot it, multiply by
W (vocab x vocab), softmax, read off the probability of the true next
token. Three lines of forward pass, three lines of backward pass.

    python3 appendix_a_backprop.py
"""
import numpy as np, torch

V = 5                                              # a five-token vocabulary
rng = np.random.default_rng(0)
W = rng.standard_normal((V, V)) * 0.5              # the only parameter: a 5x5 matrix
x, y = 2, 4                                        # current token 2, true next token 4

# ---- forward: three lines --------------------------------------------------
logits = W[x]                                      # row x of W: one score per next token
probs = np.exp(logits) / np.exp(logits).sum()      # softmax
loss = -np.log(probs[y])                           # surprise at the true next token

# ---- backward: three lines (the chain rule, applied twice) ----------------
d_logits = probs.copy(); d_logits[y] -= 1          # d loss / d logits = probs - onehot(y)
d_W = np.zeros_like(W); d_W[x] = d_logits          # only row x was used, so only row x gets a gradient
step = 0.5
W_new = W - step * d_W                             # the nudge

# ---- check against autograd -----------------------------------------------
Wt = torch.tensor(W, requires_grad=True)
lt = -torch.log_softmax(Wt[x], dim=0)[y]
lt.backward()
assert np.allclose(Wt.grad.numpy(), d_W), "hand gradient disagrees with autograd"

np.set_printoptions(precision=3, suppress=True)
print("probs before:", probs, f" loss {loss:.3f}")
print("gradient on row x:", d_logits)
logits2 = W_new[x]; probs2 = np.exp(logits2) / np.exp(logits2).sum()
print("probs after one step:", probs2, f" loss {-np.log(probs2[y]):.3f}")
print("hand-computed gradient matches torch autograd: yes")
