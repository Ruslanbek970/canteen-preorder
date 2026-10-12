#!/bin/sh
# Dev entrypoint: node_modules lives in a named volume, so reinstall when package-lock.json changes
# (otherwise new dependencies from a `git pull` would be missing).
set -e
STAMP=node_modules/.package-lock.md5
CURRENT=$(md5sum package-lock.json | cut -d' ' -f1)
if [ ! -f "$STAMP" ] || [ "$(cat "$STAMP")" != "$CURRENT" ]; then
  echo "package-lock.json changed, running npm install..."
  npm install --no-audit --no-fund
  echo "$CURRENT" > "$STAMP"
fi
exec npm run dev -- --host 0.0.0.0
