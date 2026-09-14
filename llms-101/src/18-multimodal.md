# Chapter 18: Seeing and Hearing: Multimodal

*LLMs 101, Part III — Running the Brain.
[Series index](index.html) · [Prev](17-making-it-cheaper.md) ·
[Next: Reading a Model Card](19-reading-a-model-card.md)*

---

**The failure:** everything in this book has been a sequence of token ids
from a text tokenizer. An image isn't text. It's natural to assume a
"vision" model has a separate visual brain wired to the language one. The
body book said, in a paragraph, that it doesn't. Here's the mechanism:

> **An image is cut into patches, each patch is turned into a vector by a
> small encoder, and those vectors are dropped into the token sequence as
> if they were word embeddings.** The transformer that follows can't tell
> the difference and doesn't need to. Audio is the same with slices of a
> spectrogram instead of patches. "Multimodal" means the tokenizer got a
> second input format, not that the model got a second mind.

Once you see it this way, the odd behaviours (image token costs, trouble
reading small text, counting errors) are the text tokenizer's failures
from chapter 2, in a different medium.

## Patches are the tokenizer for pixels

Chapter 3 said the model works with vectors, and the embedding table is
what turns a token id into one. For an image, skip the id. Cut the picture
into a grid of small squares, 14 or 16 pixels on a side. Flatten each
square's pixel values into a long list of numbers and multiply by a learned
matrix to get a vector of the right width. Now you have a sequence of
vectors, one per patch, ordered left to right and top to bottom, with a
position signal added just as chapter 6 added one to words.

A 224 × 224 image at 16-pixel patches is 14 × 14 = 196 patches. That's a
sequence of 196 vectors, which is a sequence a transformer knows how to
read. Run it through a stack of blocks (attention, MLP, residuals, exactly
chapter 6, minus the causal mask because there's no "future" in an image),
and the output is 196 vectors that have each gathered context from the
whole picture. That's a **vision transformer**, and it's the same
architecture as everything else in this book.

Then the join. A small **projector**, one or two matrices, maps the vision
transformer's output vectors into the language model's embedding space, so
they have the same width and, after training, live in the same geometry
as word embeddings. Those projected vectors are inserted into the token
sequence at the point where the image appeared:

```
[ ␣Here ] [ ␣is ] [ ␣a ] [ ␣photo ] [ : ] [ img₁ ] [ img₂ ] ... [ img₁₉₆ ] [ ␣What ] [ ␣is ] [ ␣in ] [ ␣it ] [ ? ]
```

From that point on, the language model runs unchanged. Its attention heads
look at the image vectors the way they look at word vectors. The text
"what is in it?" attends into the patch vectors and finds a cat because,
during training, the vector the projector produces for cat-shaped patches
was pulled toward the region of space where the word ` cat` lives. There is
one sequence and one brain. The body book's line, "the model sees the way
it reads," is literal.

## Training the join

The vision encoder is usually trained first, on hundreds of millions of
image and caption pairs, with an objective that pulls the image's vector
toward its caption's vector and away from other captions (the CLIP recipe,
2021). That gives it a visual vocabulary aligned with language before it
ever meets the LLM. Then the projector, and often the whole stack, is
trained on image-plus-text conversations: describe this, answer questions
about this, read the text in this. The language model learns to treat the
new vectors as tokens with meaning; it doesn't need a new mechanism to do
so.

## Why an image costs what it costs

Providers bill an image as a number of tokens, and now you can compute
it. It's the number of patch vectors that get inserted, which depends on
the image's resolution and the patch size, usually with a pooling step that
merges neighbouring patches to keep the count sane. A 1024 × 1024 image at
14-pixel patches is over 5,000 raw patches; models pool that down to
somewhere between a few hundred and about 1,500 tokens. High-resolution
modes tile the image into several crops and encode each, so a detailed
screenshot can cost several thousand tokens, and it's occupying that much
of the context window (chapter 14) and that much of the KV cache (chapter
13) for the rest of the conversation. Sending a screenshot every turn of
an agent loop is expensive for the same reason a long tool result is.

## The failures are tokenizer failures

Chapter 2's lesson was that the model never sees letters, only chunks, and
everything blind about its behaviour followed from the chunking. Patches
are chunks of pixels, and the same failures follow:

- **Small text is hard to read** because a 16-pixel patch of 8-pixel type
  contains parts of several letters, the way a BPE token contains parts of
  several words. High-resolution tiling exists to make the patches smaller
  relative to the text.
- **Counting objects is unreliable** for the same reason counting letters
  in ` strawberry` is: the objects are spread across patch vectors that
  have already blended together by the time the language model reads them.
- **Fine spatial questions** ("is the cup left or right of the plate?")
  depend on the position signal added to the patches, and models are
  noticeably worse at them than at "what is this."

When a model gets these right, it's usually because the training data
included lots of examples of the task, not because the mechanism changed.

## Audio, video, and output

**Audio in** is the same recipe with a different slicing. Sound becomes a
spectrogram (frequency over time, an image-like grid), the grid is sliced
into short time windows, each window becomes a vector, an encoder runs, a
projector joins. A second of speech becomes a few dozen tokens. Many
products don't do this natively and instead run a separate speech-to-text
model first and feed the transcript in as ordinary text, which is cheaper
and usually good enough. That's the "more body than brain" pattern from
the body book, and you can tell them apart: a native model can answer
"what tone of voice was that?" and a transcript-fed one can't.

**Video** is sampled frames, each encoded as an image, with time positions
added. Frame rate and resolution are traded against token budget
aggressively, which is why video understanding is coarse.

**Output** in other modalities is a different story, and worth being
precise about. Speech output from a language model is typically done by
having the model emit *audio codec tokens*, ids from a learned vocabulary
of short sound fragments, which a decoder turns into a waveform; that's
next-token prediction over a different alphabet, and it fits this book. Most
image *generation*, though, uses a separate family of models (diffusion)
that isn't a next-token predictor at all, even when the product puts a
chat box in front of it. Some newer systems do generate images as tokens
autoregressively, but if you see a chatbot make a picture, don't assume the
transformer you've been reading about drew it.

## What you now know

- Images become sequences of patch vectors through a vision transformer
  and a projector, then join the text tokens in one sequence. One brain,
  one sequence.
- The encoder is pre-aligned with language via image-caption training;
  the join is trained on image conversations.
- Image token cost is patch count after pooling, and it occupies context
  and cache like any other tokens.
- Small text, counting and fine spatial questions fail for the same reason
  the strawberry problem does: chunking.
- Audio in is spectrogram slices; many products transcribe instead. Speech
  out is codec tokens. Image generation is usually a different kind of model.

That's the last mechanism. What remains is to turn everything into a
reading skill: given a model card full of numbers and adjectives, know
which chapter each one is pointing at.

*[Next: Chapter 19 — Reading a Model Card](19-reading-a-model-card.md)*
