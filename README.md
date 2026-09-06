# Harness Engineering 101

*The LLM is the brain. The harness is the body.*

A blog series about building AI agents from first principles, published as a
book with [mdBook](https://rust-lang.github.io/mdBook/).

**📖 Read it online: <https://isurumaduranga.github.io/harness-engineering-101/>**

Originally published on my blog:
<https://isuruwijesiri.com/blog/2026/harness-engineering-101/>. More writing at
[isuruwijesiri.com](https://isuruwijesiri.com).

An LLM API is stateless. Every turn, you send the entire conversation as a JSON
array and get text back. A *harness* is the program that builds, maintains, and
protects that array. Everything the field calls "agents" is a set of patches to
that one loop, and each patch exists because something concrete broke. This
series develops that one idea across 16 chapters, growing a ~300-line toy agent
in plain Python as it goes.

The full introduction and reading order are on the
[book's landing page](src/README.md).

## Repository layout

| Path | What it holds |
|---|---|
| `src/*.md` | The chapters and appendices (the book source) |
| `src/SUMMARY.md` | The book's table of contents |
| `src/harness/` | The runnable toy harness — one file per stage |
| `src/diagrams/` | Diagram generators and their generated PNGs |
| `book.toml` | mdBook configuration |
| `.github/workflows/deploy.yml` | Builds the book and deploys it to GitHub Pages |

## Building the book locally

```bash
cargo install mdbook mdbook-mermaid   # or: brew install mdbook (+ mdbook-mermaid binary)
mdbook serve --open                    # live-reloading preview at http://localhost:3000
mdbook build                           # static site into ./book
```

`mdbook-mermaid` renders the inline mermaid diagrams; without it those blocks
show as raw code.

## Regenerating the quantitative diagrams

```bash
cd src/diagrams && python3 gen_all.py   # Python 3.10+, matplotlib
```

## License

This repository is dual-licensed:

- **The prose** — every chapter and appendix (the `.md` files under `src/`) —
  is licensed under
  [Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International
  (CC BY-NC-ND 4.0)](https://creativecommons.org/licenses/by-nc-nd/4.0/). You
  may share it with credit, but not use it commercially or publish modified
  versions. Full text in [`LICENSE`](LICENSE).
- **The code** — the `.py` files under `src/harness/` and `src/diagrams/`, and
  code snippets reproduced from them in the chapters — is licensed under the
  [MIT License](LICENSE-CODE). Use it freely, with attribution.

© 2026 Isuru Wijesiri.
