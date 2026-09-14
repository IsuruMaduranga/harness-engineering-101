#!/usr/bin/env python3
"""Build corpus.txt: the full text of Harness Engineering 101, in reading
order, as one plain-text file. This is the training data for the toy GPT.

About 180 KB. Tiny by any real standard, which is the point of chapter 9.

    python3 make_corpus.py
"""
import os, re

HERE = os.path.dirname(os.path.abspath(__file__))
BOOK_SRC = os.path.normpath(os.path.join(HERE, "..", "..", "..", "src"))
OUT = os.path.join(HERE, "corpus.txt")

summary = open(os.path.join(BOOK_SRC, "SUMMARY.md")).read()
files = re.findall(r"\]\(([^)]+\.md)\)", summary)
files = [f for f in files if f != "license.md"]

parts = []
for name in files:
    text = open(os.path.join(BOOK_SRC, name)).read()
    # drop mermaid diagrams: they are code for a renderer, not prose
    text = re.sub(r"```mermaid.*?```", "", text, flags=re.S)
    parts.append(text.strip() + "\n")

corpus = "\n".join(parts)
open(OUT, "w").write(corpus)
print(f"{len(files)} chapters, {len(corpus):,} characters, "
      f"{len(corpus.split()):,} words -> corpus.txt")
