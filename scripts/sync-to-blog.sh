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

echo "Syncing book output -> $DEST ..."
rm -rf "$DEST"
cp -R "$BOOK_REPO/book" "$DEST"

echo "Done."
echo "Next: cd \"$BLOG_REPO\" && git add harness-engineering-101 && git commit -m 'Update book' && git push"
