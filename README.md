# Harness Engineering 101

*The LLM is the brain. The harness is the body.*

*Version 1.1, October 2026.*

A blog series about building AI agents from first principles, published as a
book.

**📖 Read it online: <https://isuruwijesiri.com/harness-engineering-101/>**

An LLM API is stateless. Every turn, you send the entire conversation as a JSON
array and get text back. A *harness* is the program that builds, maintains, and
protects that array. Everything the field calls "agents" is a set of patches to
that one loop, and each patch exists because something concrete broke. This
series develops that one idea across 16 chapters, growing a ~300-line toy agent
in plain Python as it goes.

I use the same ideas in [One Code](https://github.com/IsuruMaduranga/one-code),
an open-source coding agent built on [pi](https://github.com/earendil-works/pi).

The rendered book reads best online at the link above. If you'd rather read
the source here on GitHub, follow the chapters in order below. The full
introduction is on the [book's landing page](src/README.md).

## Reading order

Every chapter has the same shape: the failure, the minimal patch, what the
patch costs.

### Part I — The Wire (nothing is magic)

| # | Chapter | The failure it patches |
|---|---------|------------------------|
| 1 | [It's Just a JSON Array](src/01-its-just-a-json-array.md) | "How do I even talk to this thing?" |
| 2 | [The Brain: A Next-Token Black Box](src/02-the-brain.md) | "Why does it behave like that?" |
| 3 | [Tools: JSON Mapped to Functions](src/03-tools.md) | The brain can't touch the world |
| 4 | [The Agent Loop](src/04-the-agent-loop.md) | One tool call isn't enough |
| 5 | [Caching: Why Order Matters](src/05-caching.md) | Resending the array gets expensive |

### Part II — Running Long (the array under pressure)

| # | Chapter | The failure it patches |
|---|---------|------------------------|
| 6 | [Context Is a Budget, Not a Bag](src/06-context-is-a-budget.md) | The window fills up |
| 7 | [Subagents: Fork the Context](src/07-subagents.md) | One array can't hold all the work |
| 8 | [Steering the Running Loop](src/08-steering.md) | The brain drifts mid-task |
| 9 | [Background Work and Time](src/09-background-work-and-time.md) | The loop is synchronous; the world isn't |

### Part III — The Ecosystem (naming what you already understand)

| # | Chapter | The failure it patches |
|---|---------|------------------------|
| 10 | [Every Framework Is a Wrapper Around Chapter 1](src/10-frameworks-are-wrappers.md) | Abstraction anxiety |
| 11 | [Extending the Body: MCP, Skills, Deferred Loading, Hooks](src/11-extending-the-body.md) | Capabilities don't fit in the array |
| 12 | [Debugging the Array](src/12-debugging-the-array.md) | You can't fix the prompt you can't see |

### Part IV — Trust, Domains, and Data

| # | Chapter | The failure it patches |
|---|---------|------------------------|
| 13 | [Reflexes and Guardrails](src/13-reflexes-and-guardrails.md) | The loop will do something dumb |
| 14 | [Case Study: Coding Agents](src/14-coding-agents.md) | How specialized does the body need to be? |
| 15 | [RAG Was a Harness Pattern All Along](src/15-rag.md) | A thousand names for one idea |

### Epilogue

- [Build Your Own](src/16-epilogue-build-your-own.md): the complete toy harness, annotated

### Appendix — Advanced Topics

Standalone pieces. Read them when you need them.

- [A. One Harness, Many Brains](src/appendix-a-one-harness-many-brains.md): model routing, prompt tiers, cost engineering
- [B. Worktrees and Isolation](src/appendix-b-worktrees-and-isolation.md): giving parallel agents separate copies of the world
- [C. Modes and Plan Mode](src/appendix-c-modes-and-plan-mode.md): harness-enforced operating states (coding-specific)
- [D. Retries, Rate Limits, and Streaming](src/appendix-d-retries-rate-limits-streaming.md): the unglamorous plumbing, plus how streaming works on the wire

## Repository layout

| Path | What it holds |
|---|---|
| `src/*.md` | The chapters and appendices (the book source) |
| `src/SUMMARY.md` | The book's table of contents |
| `src/harness/` | The runnable toy harness, one file per stage |
| `src/diagrams/` | Diagram generators and their generated PNGs |
| `book.toml` | mdBook configuration |
| `scripts/sync-to-blog.sh` | Builds the book and mounts it into the blog for serving |

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

- **The prose** (every chapter and appendix, the `.md` files under `src/`) is
  licensed under
  [Creative Commons Attribution-NonCommercial-NoDerivatives 4.0 International
  (CC BY-NC-ND 4.0)](https://creativecommons.org/licenses/by-nc-nd/4.0/). You
  may share it with credit, but not use it commercially or publish modified
  versions. Full text in [`LICENSE`](LICENSE).
- **The code** (the `.py` files under `src/harness/` and `src/diagrams/`, and
  code snippets reproduced from them in the chapters) is licensed under the
  [MIT License](LICENSE-CODE). Use it freely, with attribution.

© 2026 Isuru Wijesiri.
