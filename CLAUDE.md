# Harness Engineering 101

The book source. An mdBook of 16 chapters plus appendices, with a runnable toy
harness in plain Python. Rendered to static HTML and served on the blog.

## Commands

```bash
mdbook serve --open          # live preview at http://localhost:3000
mdbook build                 # static site into ./book
./scripts/sync-to-blog.sh    # build + copy book/ into the blog repo (see Publishing)
cd src/diagrams && python3 gen_all.py   # regenerate the quantitative PNGs
```

## Layout

- `src/*.md` — chapters and appendices (the book). `src/SUMMARY.md` is the TOC.
- `src/harness/` — the runnable toy harness, one file per stage.
- `src/diagrams/` — diagram generators and their PNGs.
- `book.toml` — mdBook config. `scripts/sync-to-blog.sh` — the publish script.

## Publishing

This repo is the source; the deployed book lives in the blog repo
(`/Users/isuruWij/me/IsuruMaduranga.github.io`, Cloudflare Pages →
isuruwijesiri.com/harness-engineering-101/), which serves committed static
HTML. **Editing `src/` does not update the live site on its own.** After any
content change, publish both repos:

1. `./scripts/sync-to-blog.sh` — rebuilds the book and copies it into the blog.
2. Commit and push this repo (`main`).
3. In the blog repo, commit `harness-engineering-101/` and push — that push is
   what goes live via Cloudflare.

The `v1.0.0` git tag tracks the current published edition; move it to the new
HEAD when you publish an edit that should be part of v1.

## Conventions

- Links from the book to code point to GitHub, not relative paths — the site
  serves raw `.py` as downloads. Inline diagram PNGs stay relative so they embed.
- Link to the intro page as `index.html` (mdBook builds `README.md` as
  `index.html`; a `README.md` link 404s). `SUMMARY.md` keeps `README.md`.
