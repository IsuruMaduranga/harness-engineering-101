#!/usr/bin/env python3
"""Toy GPT v0: a bigram model. The whole "LLM" is a counting table.

Given the current character, what usually comes next? Count every pair in
the corpus, turn the counts into probabilities, and sample. No neural
network, no learning in any interesting sense. But it already has the
exact shape of every language model: sequence in, probability for every
next token out, pick one, append, repeat.

    python3 v0_bigram.py
"""
import random
from collections import Counter, defaultdict

random.seed(0)
text = open("corpus.txt").read()

# --- 1. "train": count what follows what --------------------------------
following = defaultdict(Counter)            # following['t']['h'] = how often 'h' follows 't'
for a, b in zip(text, text[1:]):
    following[a][b] += 1

def next_token_distribution(context):
    """The one function every LLM is: sequence in, probabilities out.
    A bigram model only looks at the last token of the sequence."""
    counts = following[context[-1]]
    total = sum(counts.values())
    return {ch: n / total for ch, n in counts.items()}

# --- 2. the sampling loop lives OUTSIDE the model ----------------------
def sample(probs, temperature=1.0):
    chars = list(probs)
    weights = [p ** (1 / temperature) for p in probs.values()]
    return random.choices(chars, weights)[0]

def generate(prompt, n=300, temperature=1.0):
    out = prompt
    for _ in range(n):
        probs = next_token_distribution(out)   # model
        out += sample(probs, temperature)       # serving layer
    return out

if __name__ == "__main__":
    print(f"corpus: {len(text):,} characters, {len(following)} distinct")
    probs = next_token_distribution("t")
    top = sorted(probs.items(), key=lambda kv: -kv[1])[:5]
    print("after 't', most likely next:", [(c, round(p, 2)) for c, p in top])
    for t in (1.0, 0.5):
        print(f"\n--- temperature {t} ---")
        print(generate("The harness", temperature=t))
