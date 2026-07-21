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
git push -u origin HEAD:main

# Enable pages if needed (idempotent)
gh api repos/hyperlux/nq-gamma-desk/pages >/dev/null 2>&1 || \
  gh api -X POST repos/hyperlux/nq-gamma-desk/pages \
    -f build_type=workflow \
    -f source[branch]=main \
    -f source[path]=/ 2>/dev/null || \
  gh api -X POST repos/hyperlux/nq-gamma-desk/pages \
    --input - <<'JSON' >/dev/null 2>&1 || true
{"build_type":"legacy","source":{"branch":"main","path":"/"}}
JSON

# Ensure pages from main root via actions or legacy
if [[ ! -f .github/workflows/pages.yml ]]; then
  mkdir -p .github/workflows
  cat > .github/workflows/pages.yml <<'YAML'
name: Deploy GitHub Pages
on:
  push:
    branches: [main]
  workflow_dispatch:
permissions:
  contents: read
  pages: write
  id-token: write
concurrency:
  group: pages
  cancel-in-progress: true
jobs:
  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/configure-pages@v5
      - uses: actions/upload-pages-artifact@v3
        with:
          path: .
      - id: deployment
        uses: actions/deploy-pages@v4
YAML
  git add .github/workflows/pages.yml
  git commit -m "ci: GitHub Pages deploy workflow" || true
  git push origin HEAD:main || true
fi

echo "Published. Site: https://hyperlux.github.io/nq-gamma-desk/"
echo "Repo:  https://github.com/hyperlux/nq-gamma-desk"
