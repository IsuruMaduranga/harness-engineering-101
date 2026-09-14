# Appendix E: Life After Attention

*LLMs 101, Appendix. [Series index](index.html) · [Prev](appendix-d-what-the-layers-do.md) ·
[License](license.md)*

---

Chapter 5 gave attention's price: the score grid is quadratic in sequence
length, and chapter 13 added that the KV cache grows linearly and lives in
the scarcest memory. Chapter 4 explained what attention replaced: a
recurrent network with a fixed-size state, which was cheap and forgot
things. This appendix is the research that asks whether you can have
recurrence's cost with attention's memory, and what the answer looks like
so far.

> **Every alternative to attention trades exact recall of the distant past
> for constant cost per token.** Linear attention and state-space models
> are recurrent networks with better-designed states. They win on long
> sequences where you don't need to look up one specific old token, and
> lose where you do. The current answer is hybrids that interleave a few
> full-attention layers with many cheap ones.**

## Linear attention: drop the softmax and it becomes an RNN

Look at chapter 5's formula, softmax(QKᵀ)V, and imagine removing the
softmax. Then the output for position *i* is Qᵢ · (Σⱼ Kⱼᵀ Vⱼ) over all
earlier *j*: a query dotted with a *running sum* of key-value outer
products. That running sum is a fixed-size matrix (d × d) that you update
by adding one term per token. You never need the old keys and values
again; you need the sum. Constant memory, constant time per token, and the
sum is exactly an RNN state.

The catch is that the softmax was doing something. It let a query put
nearly all its weight on one key, which is what exact retrieval needs.
Without it, the running sum blurs every past token together, and the
model's ability to find the one name it saw ten thousand tokens ago
degrades. **Linear attention** variants (2020 onward) add feature maps and
decay terms to sharpen the blur, and they close some of the gap on
language modelling loss while staying behind on recall-heavy tasks.

## State-space models: the RNN redesigned

**Mamba** (2023) and its relatives take the recurrent view seriously and
engineer the state well. Each token updates a fixed-size state through a
learned linear transformation, with the twist that the transformation's
parameters are themselves computed from the current token ("selective":
the model decides per token how much to remember and how much to forget).
Training is parallelised with a scan algorithm, so it doesn't inherit the
RNN's serial training problem from chapter 4. Inference is one state update
per token, no cache growth, no quadratic anything.

On raw language-modelling loss, state-space models match transformers of
the same size. On tasks that need copying an exact token from far back (a
phone number mentioned earlier, a variable name from the top of a file),
they're measurably worse, because a fixed-size state has to compress the
whole past and something is lost. Chapter 4's forgetting problem didn't go
away; it got a much better memory manager.

## Compressing the cache instead

A different line keeps attention and attacks the cache. **Multi-head latent
attention** (DeepSeek, 2024) projects each token's keys and values into a
small shared latent vector, caches only that, and reconstructs K and V from
it on the fly. It's grouped-query attention's idea (chapter 13) pushed
further: the cache shrinks several-fold more, quality holds, and full
softmax attention is preserved. This is the pragmatic branch: keep the
mechanism that works, make its memory cheaper.

**Sparse attention** is the other pragmatic branch: let each query look at
a fixed number of keys chosen by a cheap heuristic (recent tokens plus a
few learned or retrieved anchors) instead of all of them. Sliding windows
from chapter 14 are the simplest case.

## Hybrids: where it's landed

By 2025 the working answer in released models is mixing. Interleave a
state-space or linear-attention layer for most of the stack, and keep a
full-attention layer every few blocks so exact retrieval is still possible
somewhere. Jamba (2024) did it openly; several frontier labs are believed
to do something similar. The economics are straightforward: if six of
every seven layers have no growing cache, the memory per token falls by
most of a factor of seven, the context can be far longer for the same
hardware, and the one-in-seven attention layers keep the needle tests
passing.

## How to read a new architecture claim

When the next paper says it has replaced attention, ask the chapter 4
question: **what is the state, and how big is it?** If the state is fixed
in size, the model is a recurrent network with a good design, it will be
cheap on long sequences, and it will be worse at retrieving an exact token
from the distant past. If the state grows with the sequence, it's a form
of attention with a cheaper cache, and the question is how much was lost
in the compression. If it claims both constant state and perfect recall,
read the recall benchmark very carefully. The trade-off in this appendix
is not an engineering shortfall waiting to be fixed. It's the same
information-theoretic fact chapter 4 met in the RNN: a fixed-size summary
cannot hold an unbounded past.

*[License](license.md) · [Series index](index.html)*
