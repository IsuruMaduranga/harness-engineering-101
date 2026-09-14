#!/usr/bin/env bash
# Build the LLMs 101 mdBook and sync its static output into the blog repo,
# where it is served at isuruwijesiri.com/llms-101/. Cloudflare serves the
# committed static files, so no mdBook toolchain is needed in CI.
#
#   ./scripts/sync-to-blog.sh                      # default blog path
#   BLOG_REPO=/path/to/blog ./scripts/sync-to-blog.sh
#
# After it runs: cd into the blog repo, commit llms-101/, push.
# NOTE: the blog's jekyll-minifier must exclude `llms-101/*` the same way it
# excludes `harness-engineering-101/*` (it corrupts calc(var(--x)) rules).
set -euo pipefail

BOOK_REPO="$(cd "$(dirname "$0")/.." && pwd)"
BLOG_REPO="${BLOG_REPO:-/Users/isuruWij/me/IsuruMaduranga.github.io}"
DEST="$BLOG_REPO/llms-101"

if [ ! -d "$BLOG_REPO" ]; then
  echo "Blog repo not found: $BLOG_REPO (set BLOG_REPO=/path/to/blog)" >&2
  exit 1
fi

echo "Building mdBook in $BOOK_REPO ..."
( cd "$BOOK_REPO" && mdbook build )

# mdBook copies every non-markdown file under src/ into the output. Drop the
# training artefacts so checkpoints and logs are not published.
echo "Pruning build artefacts ..."
rm -rf "$BOOK_REPO/book/gpt/__pycache__" "$BOOK_REPO/book/gpt/"*.pt "$BOOK_REPO/book/gpt/"*.log

echo "Pre-minifying book CSS ..."
find "$BOOK_REPO/book" -name '*.css' -print0 | while IFS= read -r -d '' f; do
  npx -y esbuild "$f" --minify --outfile="$f" --allow-overwrite >/dev/null 2>&1
done

echo "Syncing book output -> $DEST ..."
rm -rf "$DEST"
cp -R "$BOOK_REPO/book" "$DEST"

echo "Done."
echo "Next: cd \"$BLOG_REPO\" && git add llms-101 && git commit -m 'Update LLMs 101' && git push"
