#!/usr/bin/env bash
# Fetches the published JSON tree into ../out at build time.
#
# The nightly GitHub Action force-pushes out/ to a branch called `data` as a
# single commit. Vercel has no database and no Python, so this is how the site
# gets its numbers. While the repository is public no credentials are needed;
# set DATA_TOKEN in Vercel (a fine-grained token with read-only Contents access
# to this one repository) before making it private, and the authenticated API
# is used instead.
#
# Locally it does nothing: you already have an out/ from running the pipeline.
set -euo pipefail

REPO="${DATA_REPO:-joeylampasona/web-app}"
BRANCH="${DATA_BRANCH:-data}"
WEB_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ -n "${VERCEL:-}" ]; then
  # Inside the Next.js root: anything above it may not survive the upload.
  TARGET="$WEB_ROOT/out"
else
  TARGET="$(cd "$WEB_ROOT/.." && pwd)/out"
fi

if [ -z "${VERCEL:-}" ] && [ -f "$TARGET/meta.json" ]; then
  echo "fetch-data: using the local out/ tree — nothing to fetch."
  exit 0
fi

echo "fetch-data: pulling $REPO@$BRANCH into $TARGET"
mkdir -p "$TARGET"

if [ -n "${DATA_TOKEN:-}" ]; then
  # The API's tarball redirects to a short-lived signed URL; -L follows it and
  # curl drops the Authorization header on the way, which is what we want.
  status=$(curl -sL -o /tmp/data.tar.gz -w '%{http_code}' \
    -H "Authorization: Bearer $DATA_TOKEN" \
    -H "Accept: application/vnd.github+json" \
    "https://api.github.com/repos/$REPO/tarball/refs/heads/$BRANCH")
else
  status=$(curl -sL -o /tmp/data.tar.gz -w '%{http_code}' \
    "https://codeload.github.com/$REPO/tar.gz/refs/heads/$BRANCH")
fi

if [ "$status" != "200" ]; then
  echo ""
  echo "fetch-data: could not download the data branch (HTTP $status)."
  echo ""
  echo "  Two things cause this:"
  echo "    1. The nightly job has never run, so the branch does not exist yet."
  echo "       Run it once by hand: Actions -> Nightly scan -> Run workflow."
  if [ -n "${DATA_TOKEN:-}" ]; then
    echo "    2. DATA_TOKEN is set but cannot read $REPO: expired, or missing"
    echo "       read access to Contents on this repository."
  else
    echo "    2. The repository is private and DATA_TOKEN is not set."
  fi
  echo ""
  echo "  Refusing to build a site with no data in it."
  exit 1
fi

tar xzf /tmp/data.tar.gz --strip-components=1 -C "$TARGET"
rm -f /tmp/data.tar.gz

if [ ! -f "$TARGET/meta.json" ]; then
  echo "fetch-data: the data branch has no meta.json. Refusing to build."
  exit 1
fi

python3 - "$TARGET/meta.json" <<'PY' 2>/dev/null || true
import json, sys
meta = json.load(open(sys.argv[1]))
print(f"fetch-data: {meta['universe_count']:,} names, as of {meta['as_of']}, "
      f"source {meta['data_source']}")
PY
