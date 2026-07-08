#!/usr/bin/env bash
# Wire a GitHub repo → Coolify webhook for push-triggered auto-deploy.
#
# Use this on EVERY new Coolify app that was created via the
# /applications/private-deploy-key endpoint, since that flow gives
# Coolify clone access but NO push-notification path. Without a webhook,
# `git push` will land on GitHub but Coolify won't know to redeploy.
#
# See gotcha G29 in coolify-gotchas.md for the diagnosis pattern.
#
# Usage:
#   setup-github-webhook.sh <app-name> <github-owner>/<repo>
# Example:
#   setup-github-webhook.sh example <GITHUB_OWNER>/Example App
#
# Requires:
#   - COOLIFY_API_BASE + COOLIFY_NEW_TOKEN in env (source the credentials file)
#   - gh CLI authenticated with repo admin scope
#   - node (for JSON parsing)
#
# Idempotent: GitHub rejects duplicate webhooks with the same URL on the
# same repo with HTTP 422, which this script reports cleanly rather than failing.

set -e

APP_NAME="${1:?usage: setup-github-webhook.sh <app-name> <owner>/<repo>}"
REPO="${2:?usage: setup-github-webhook.sh <app-name> <owner>/<repo>}"

: "${COOLIFY_API_BASE:?must be set — source the credentials file}"
: "${COOLIFY_NEW_TOKEN:?must be set — source the credentials file}"

WEBHOOK_URL="${COOLIFY_API_BASE%/api/v1}/webhooks/source/github/events/manual"

echo "[1/4] resolving app UUID for '$APP_NAME'..."
UUID=$(curl -sS -H "Authorization: Bearer $COOLIFY_NEW_TOKEN" \
  "$COOLIFY_API_BASE/applications" | \
  node -e "const d=JSON.parse(require('fs').readFileSync(0,'utf8'));const m=d.find(a=>a.name==='$APP_NAME');process.stdout.write(m?m.uuid:'');")

if [ -z "$UUID" ]; then
  echo "  ERROR: no Coolify app named '$APP_NAME'"
  exit 1
fi
echo "  uuid=$UUID"

echo "[2/4] fetching per-app webhook secret..."
SECRET=$(curl -sS -H "Authorization: Bearer $COOLIFY_NEW_TOKEN" \
  "$COOLIFY_API_BASE/applications/$UUID" | \
  node -e "const d=JSON.parse(require('fs').readFileSync(0,'utf8'));process.stdout.write(d.manual_webhook_secret_github||'');")

if [ -z "$SECRET" ]; then
  echo "  ERROR: app has no manual_webhook_secret_github (unexpected for a private-deploy-key app)"
  exit 1
fi
echo "  secret prefix: ${SECRET:0:12}..."

echo "[3/4] creating GitHub webhook on $REPO..."
HOOK_RESP=$(gh api -X POST "repos/$REPO/hooks" \
  -f name=web \
  -F active=true \
  -f "events[]=push" \
  -F "config[url]=$WEBHOOK_URL" \
  -F "config[content_type]=json" \
  -F "config[secret]=$SECRET" 2>&1) || true

HOOK_ID=$(echo "$HOOK_RESP" | node -e "try{const d=JSON.parse(require('fs').readFileSync(0,'utf8'));process.stdout.write(d.id?String(d.id):'');}catch(e){}")

if [ -z "$HOOK_ID" ]; then
  if echo "$HOOK_RESP" | grep -q "Hook already exists"; then
    echo "  already exists (idempotent) — looking up existing hook id..."
    HOOK_ID=$(gh api "repos/$REPO/hooks" --jq '.[] | select(.config.url == "'"$WEBHOOK_URL"'") | .id' | head -1)
    echo "  id=$HOOK_ID"
  else
    echo "  ERROR creating hook:"
    echo "$HOOK_RESP" | head -10
    exit 1
  fi
else
  echo "  created: id=$HOOK_ID"
fi

echo "[4/4] firing test ping..."
sleep 1
gh api -X POST "repos/$REPO/hooks/$HOOK_ID/pings" >/dev/null 2>&1
sleep 1
STATUS=$(gh api "repos/$REPO/hooks/$HOOK_ID" --jq '.last_response | "\(.status):\(.code) — \(.message)"')
echo "  last_response: $STATUS"

if [[ "$STATUS" == active:200* ]]; then
  echo ""
  echo "DONE — push to $REPO will now trigger Coolify deploy of app '$APP_NAME'."
else
  echo ""
  echo "WARNING — webhook created but ping response was '$STATUS' (expected 'active:200')."
  echo "Likely causes: Coolify down, network issue, or per-app secret mismatch."
fi
