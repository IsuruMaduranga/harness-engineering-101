#!/usr/bin/env python3
"""The real GPT-2 tokenizer, loaded from its two published files.

Same algorithm as v1_tokenizer.py, with two production details: a
reversible byte-to-printable-character mapping (so the vocab file is plain
JSON), and a Unicode-aware chunking regex. 50,257 tokens: 256 bytes,
50,000 merges, one end-of-text marker.

    python3 gpt2_tokenizer.py
"""
import json, os, regex

HERE = os.path.dirname(os.path.abspath(__file__))
GPT2_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "models", "gpt2"))   # filled by download_gpt2.py
CHUNK = regex.compile(
    r"'s|'t|'re|'ve|'m|'ll|'d| ?\p{L}+| ?\p{N}+| ?[^\s\p{L}\p{N}]+|\s+(?!\S)|\s+")


def _byte_to_unicode():
    """Map every byte to a printable character so tokens can live in JSON."""
    bs = list(range(33, 127)) + list(range(161, 173)) + list(range(174, 256))
    cs = bs[:]
    n = 0
    for b in range(256):
        if b not in bs:
            bs.append(b); cs.append(256 + n); n += 1
    return dict(zip(bs, map(chr, cs)))


class GPT2Tokenizer:
    def __init__(self, path=GPT2_DIR):
        self.encoder = json.load(open(os.path.join(path, "vocab.json")))
        self.decoder = {v: k for k, v in self.encoder.items()}
        merges = open(os.path.join(path, "merges.txt"), encoding="utf-8").read().split("\n")[1:-1]
        self.ranks = {tuple(m.split()): i for i, m in enumerate(merges)}
        self.b2u = _byte_to_unicode()
        self.u2b = {u: b for b, u in self.b2u.items()}
        self.eot = self.encoder["<|endoftext|>"]

    def _bpe(self, word):
        word = tuple(word)
        while len(word) > 1:
            pairs = [(self.ranks.get(p, 1e9), p) for p in zip(word, word[1:])]
            rank, (a, b) = min(pairs)
            if rank == 1e9:
                break
            out, i = [], 0
            while i < len(word):
                if i < len(word) - 1 and word[i] == a and word[i + 1] == b:
                    out.append(a + b); i += 2
                else:
                    out.append(word[i]); i += 1
            word = tuple(out)
        return word

    def encode(self, text):
        ids = []
        for chunk in CHUNK.findall(text):
            u = "".join(self.b2u[b] for b in chunk.encode("utf-8"))
            ids.extend(self.encoder[t] for t in self._bpe(u))
        return ids

    def decode(self, ids):
        text = "".join(self.decoder[i] for i in ids)
        return bytes(self.u2b[c] for c in text).decode("utf-8", errors="replace")

    def pieces(self, ids):
        """Human-readable token strings, for printing."""
        return [bytes(self.u2b[c] for c in self.decoder[i]).decode("utf-8", "replace") for i in ids]


if __name__ == "__main__":
    tok = GPT2Tokenizer()
    print("vocab size:", len(tok.encoder))
    for s in ["The harness is the body.", "strawberry", " strawberry",
              "How many r's are in strawberry?", "def call_llm(messages):",
              "The LLM is the brain.", "මොඩලය මොළයයි.", "1234567", "  indented"]:
        ids = tok.encode(s)
        assert tok.decode(ids) == s
        print(f"{s!r:36} -> {len(ids):3} tokens {tok.pieces(ids)}")
