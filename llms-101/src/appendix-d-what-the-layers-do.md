# Appendix D: What the Layers Seem to Do

*LLMs 101, Appendix. [Series index](index.html) · [Prev](appendix-c-serving-systems.md) ·
[Next: Appendix E](appendix-e-life-after-attention.md)*

---

Everything in this book explained what the transformer *computes*. This
appendix is about what the computation *means*: what the layers are doing
with the vectors as they pass through. The field that studies this is
called interpretability, it is young, and its results should be held more
loosely than anything in the main chapters. But a few findings are solid
enough to change how you picture the model, and they connect to things you
saw in chapter 7's heatmaps.

> **The residual stream is a shared bus. Early layers do bookkeeping about
> tokens and positions, middle layers look up facts and build abstract
> features, late layers convert features into a next-token prediction.
> Individual attention heads have identifiable jobs, and the most important
> discovered so far is the pair that implements "copy what came after the
> last time I saw this."**

## The residual stream as a bus

Chapter 6 introduced the residual stream: the vector at each position that
every layer reads from and adds to. The productive way to picture it is
as a communication channel with many independent "wires" superimposed.
Attention heads and MLPs are components plugged into the bus; each reads a
few directions, writes a few directions, and leaves the rest alone. A
direction written by layer 3 can be read by layer 20 without anything in
between touching it. That's why a model can carry "this sentence is in
French" or "the subject is plural" from where it's detected to where it's
needed.

You can watch this with the **logit lens**: take the residual stream at
any layer, skip the remaining layers, apply the final norm and the
unembedding (chapter 3), and see what token the stream "would predict" if
the model stopped there. Early layers predict nonsense or copy the current
token. Somewhere in the middle the prediction snaps to something sensible,
and the last few layers refine it. The prediction is being *built up*
along the bus, not produced at the end.

## Heads with jobs

The two heads in chapter 7's figure were found by searching all 144 for
particular patterns, and both patterns are famous:

**Previous-token heads** (left panel, layer 4 head 11, weight 1.00 on the
token before). They copy information about position *i−1* into position
*i*'s stream. On their own they're dull. Combined with the next kind,
they're the most important discovered mechanism in transformers.

**Induction heads** (right panel is a close relative: layer 3 head 0 looks
from the second ` model` back to the first). The full induction circuit
needs two heads in sequence. A previous-token head in an early layer
writes "the token before me was X" into each position. Then a later head,
at a position whose current token is X, uses that written information as
its *key* to find the earlier position that came *after* an X, and copies
what it holds. Net effect: "the last time I saw ` model`, the next token
was ` reads`; predict ` reads`." This is how a model repeats a rare name
correctly the second time it appears, and it's the mechanism behind
chapter 9's in-context learning: a two-head circuit that generalises the
pattern-in-the-prompt. Induction heads appear abruptly during training,
and the moment they appear, the loss on repeated text drops in a visible
step.

Other heads with reliable jobs have been catalogued: heads that attend from
a verb to its subject, heads that track open brackets, heads that attend
to the first token as a sink (chapter 14) when they have nothing to do.

## Where the facts are

Chapter 6 asserted that the MLP is where facts live. The evidence is causal
tracing: run the model on "The Eiffel Tower is in", corrupt the input, then
restore the residual stream at one layer and one position at a time and
see which restoration recovers the answer "Paris." The recoveries cluster
in the *middle-layer MLPs at the subject's position*. That's where "Eiffel
Tower → Paris" is stored, and editing a specific small set of those MLP
weights changes the fact (the model will then say the Eiffel Tower is in
Rome, and reason consistently about it) without changing much else. The
key-value-memory picture of the MLP is not just an analogy; it's been used
to perform surgery.

## Superposition: more features than dimensions

A puzzle. The residual stream in GPT-2 has 768 dimensions, and the model
clearly represents far more than 768 distinct concepts. The resolution is
**superposition**: features are stored not one per dimension but as
directions in the space, and because most features are absent most of the
time, many more directions than dimensions can coexist with tolerable
interference. This is the same reason chapter 3's embeddings could encode
thousands of relationships in 768 numbers.

It also means individual neurons are mostly uninterpretable: one neuron
participates in many features. The 2023 to 2024 breakthrough was to train
a separate, much wider **sparse autoencoder** on the residual stream to
pull the superimposed features apart. The recovered features are strikingly
clean: one fires on mentions of the Golden Gate Bridge across languages and
images, one on code with a security vulnerability, one on the model
expressing uncertainty. Steering by adding a feature's direction into the
stream produces the behaviour: the widely reported demonstration was a
Claude that could not stop talking about the Golden Gate Bridge. Features
are real, they're directions, and there are millions of them.

## What this doesn't yet give you

Honesty about the state of the art. We can name some heads, locate some
facts, and extract some features. We cannot yet read out *why* a model
produced a particular answer in the way we can read a stack trace, and
chapter 11's caution stands: the thinking tokens a reasoning model writes
are not a transcript of these circuits firing. Interpretability is the
project of closing that gap, and as of this writing it's a project, not a
tool you can use in production. But the picture it gives, a bus of
superimposed features read and written by small specialised components, is
already more accurate than "a neural network figures it out," and it's the
picture to hold.

*[Next: Appendix E — Life After Attention](appendix-e-life-after-attention.md)*
