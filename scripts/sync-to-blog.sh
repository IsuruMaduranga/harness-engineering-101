#!/usr/bin/env bash
# Build the mdBook and sync its static output into the blog repo, where it is
# served at isuruwijesiri.com/harness-engineering-101/. Cloudflare serves the
# committed static files, so no mdBook toolchain is needed in CI.
#
#   ./scripts/sync-to-blog.sh                      # default blog path
#   BLOG_REPO=/path/to/blog ./scripts/sync-to-blog.sh
#
# After it runs: cd into the blog repo, commit harness-engineering-101/, push.
set -euo pipefail

BOOK_REPO="$(cd "$(dirname "$0")/.." && pwd)"
BLOG_REPO="${BLOG_REPO:-/Users/isuruWij/me/IsuruMaduranga.github.io}"
DEST="$BLOG_REPO/harness-engineering-101"

if [ ! -d "$BLOG_REPO" ]; then
  echo "Blog repo not found: $BLOG_REPO (set BLOG_REPO=/path/to/blog)" >&2
  exit 1
fi

echo "Building mdBook in $BOOK_REPO ..."
( cd "$BOOK_REPO" && mdbook build )

# Pre-minify the CSS with a correct minifier, purely to cut the payload: mdBook
# ships readable CSS, and this roughly halves it. The blog serves these files
# verbatim - its own jekyll-minifier is configured to skip this directory,
# because that minifier corrupts calc(var(--x)) rules. See docs/findings.md in
# the blog repo; do not remove the `harness-engineering-101/*` exclude there.
echo "Pre-minifying book CSS ..."
find "$BOOK_REPO/book" -name '*.css' -print0 | while IFS= read -r -d '' f; do
  npx -y esbuild "$f" --minify --outfile="$f" --allow-overwrite >/dev/null 2>&1
done

echo "Syncing book output -> $DEST ..."
rm -rf "$DEST"
cp -R "$BOOK_REPO/book" "$DEST"

echo "Done."
echo "Next: cd \"$BLOG_REPO\" && git add harness-engineering-101 && git commit -m 'Update book' && git push"
