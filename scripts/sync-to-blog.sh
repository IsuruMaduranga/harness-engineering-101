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

# Pre-minify the CSS. Cloudflare Auto Minify is stuck "on" for this zone (the
# settings API and Config Rules can't disable it) and its minifier corrupts
# mdBook's unminified CSS - it strips required spaces in `@media only screen
# and (...)`, invalidating the media block that offsets content past the
# sidebar, so the menu bar overlaps the sidebar. Cloudflare SKIPS files that are
# already minified (mdBook's own book.js is served untouched), so minifying the
# CSS ourselves with a correct minifier keeps the media queries valid and stops
# Cloudflare from touching it. See docs/findings.md in the blog repo.
echo "Pre-minifying book CSS (works around Cloudflare Auto Minify) ..."
find "$BOOK_REPO/book" -name '*.css' -print0 | while IFS= read -r -d '' f; do
  npx -y esbuild "$f" --minify --outfile="$f" --allow-overwrite >/dev/null 2>&1
done

echo "Syncing book output -> $DEST ..."
rm -rf "$DEST"
cp -R "$BOOK_REPO/book" "$DEST"

echo "Done."
echo "Next: cd \"$BLOG_REPO\" && git add harness-engineering-101 && git commit -m 'Update book' && git push"
