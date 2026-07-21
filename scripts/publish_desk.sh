#!/usr/bin/env bash
# Publish NQ gamma desk to GitHub Pages.
# Usage:
#   publish_desk.sh /path/to/nq_report_YYYYMMDD_HHMMSS ["optional commit message"]
set -euo pipefail

REPORT_DIR="${1:-}"
MSG="${2:-}"
SITE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
EXPORT="$SITE_DIR/scripts/export_latest.py"

if [[ -z "$REPORT_DIR" ]]; then
  echo "Usage: publish_desk.sh REPORT_DIR [commit message]" >&2
  exit 2
fi
if [[ ! -d "$REPORT_DIR/raw" ]]; then
  echo "ERROR: $REPORT_DIR/raw not found" >&2
  exit 1
fi
if [[ ! -f "$EXPORT" ]]; then
  echo "ERROR: missing $EXPORT" >&2
  exit 1
fi

export PATH="$HOME/.local/bin:$PATH"
cd "$SITE_DIR"

python3 "$EXPORT" "$REPORT_DIR" "$SITE_DIR"

# Ensure git identity for commits on this host
git config user.email >/dev/null 2>&1 || git config user.email "echo@futurecult.store"
git config user.name >/dev/null 2>&1 || git config user.name "Hermes Agent"

git add -A
if git diff --cached --quiet; then
  echo "No changes to publish."
  exit 0
fi

STAMP=$(date -u +%Y-%m-%dT%H:%MZ)
if [[ -z "$MSG" ]]; then
  SPOT=$(python3 -c "import json;print(json.load(open('data/latest.json'))['spot']['price'])" 2>/dev/null || echo "?")
  MSG="update NQ desk @ ${STAMP} (spot ${SPOT})"
fi

git commit -m "$MSG"
# Prefer gh-authenticated https remote
# NOTE: do NOT commit GitHub Actions workflows — OAuth token lacks `workflow` scope.
git push -u origin HEAD:main

# Enable classic Pages (branch main, root) if not already configured
if ! gh api repos/hyperlux/nq-gamma-desk/pages >/dev/null 2>&1; then
  gh api -X POST repos/hyperlux/nq-gamma-desk/pages \
    -H "Accept: application/vnd.github+json" \
    --input - <<'JSON' >/dev/null 2>&1 || true
{"source":{"branch":"main","path":"/"}}
JSON
fi

# Homepage link on repo
gh repo edit hyperlux/nq-gamma-desk --homepage "https://hyperlux.github.io/nq-gamma-desk/" >/dev/null 2>&1 || true

echo "Published. Site: https://hyperlux.github.io/nq-gamma-desk/"
echo "Repo:  https://github.com/hyperlux/nq-gamma-desk"
