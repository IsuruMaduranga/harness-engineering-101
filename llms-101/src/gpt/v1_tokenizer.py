#!/usr/bin/env python3
"""Toy GPT v1: a byte-pair-encoding (BPE) tokenizer, trained from scratch.

Start with 256 tokens (one per byte). Repeatedly find the most common
adjacent pair in the training text and merge it into a new token. Stop
when the vocabulary is as big as you want. That is the entire algorithm
behind every modern LLM tokenizer, including GPT-2's and Claude's.

    python3 v1_tokenizer.py
"""
import re
from collections import Counter

# GPT-2's chunking rule: split text into words / numbers / punctuation runs
# first, so merges never cross a word boundary. (Leading space stays with
# the word, which is why " strawberry" and "strawberry" are different.)
CHUNK = re.compile(r"'s|'t|'re|'ve|'m|'ll|'d| ?\w+| ?\d+| ?[^\s\w]+|\s+(?!\S)|\s+")


def train(text, vocab_size):
    """Return the ordered list of merges (pair -> new token id)."""
    chunks = Counter(CHUNK.findall(text))                  # unique chunks + counts
    words = {tuple(c.encode("utf-8")): n for c, n in chunks.items()}
    merges = {}
    for new_id in range(256, vocab_size):
        pairs = Counter()
        for word, n in words.items():
            for a, b in zip(word, word[1:]):
                pairs[(a, b)] += n
        if not pairs:
            break
        best = max(pairs, key=pairs.get)                   # most frequent pair
        merges[best] = new_id
        words = {_merge(w, best, new_id): n for w, n in words.items()}
    return merges


def _merge(word, pair, new_id):
    out, i = [], 0
    while i < len(word):
        if i < len(word) - 1 and (word[i], word[i + 1]) == pair:
            out.append(new_id); i += 2
        else:
            out.append(word[i]); i += 1
    return tuple(out)


class Tokenizer:
    def __init__(self, merges):
        self.merges = merges                               # (a, b) -> id
        self.vocab = {i: bytes([i]) for i in range(256)}
        for (a, b), i in merges.items():
            self.vocab[i] = self.vocab[a] + self.vocab[b]

    def encode(self, text):
        ids = []
        for chunk in CHUNK.findall(text):
            word = tuple(chunk.encode("utf-8"))
            while len(word) > 1:                            # apply merges in training order
                pairs = [(self.merges.get(p, 1e9), p) for p in zip(word, word[1:])]
                rank, pair = min(pairs)
                if rank == 1e9:
                    break
                word = _merge(word, pair, self.merges[pair])
            ids.extend(word)
        return ids

    def decode(self, ids):
        return b"".join(self.vocab[i] for i in ids).decode("utf-8", errors="replace")


if __name__ == "__main__":
    text = open("corpus.txt").read()
    tok = Tokenizer(train(text, vocab_size=512))
    ids = tok.encode(text)
    print(f"vocab 512: {len(text):,} chars -> {len(ids):,} tokens "
          f"({len(text)/len(ids):.2f} chars/token)")
    print("first merges:", [tok.vocab[i] for i in range(256, 266)])
    print("longest tokens:", sorted(tok.vocab.values(), key=len)[-8:])
    for s in ["The harness is the body.", "strawberry", " strawberry",
              "The LLM is the brain.", "මොඩලය මොළයයි."]:
        e = tok.encode(s)
        print(f"{s!r:32} -> {len(e):3} tokens {[tok.vocab[i] for i in e]}")
        assert tok.decode(e) == s
