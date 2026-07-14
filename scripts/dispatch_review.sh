#!/usr/bin/env bash
# Dispatch a review packet to the local Codex CLI with explicit model/effort.
# Usage: scripts/dispatch_review.sh REV-NNNN [effort] [model]
#   effort: minimal | low | medium | high | xhigh   (default: high)
#   model:  passed to `codex -m`; omit for the CLI's configured default
# Billing: uses whatever auth `codex login` established — ChatGPT sign-in = plan
# allotment, OPENAI_API_KEY = API credits. Check with `codex login status`.
set -euo pipefail

REV="${1:?usage: dispatch_review.sh REV-NNNN [effort] [model]}"
EFFORT="${2:-high}"
MODEL="${3:-}"

REQ="work/review/$REV/request.md"
OUT="work/review/$REV/result-raw.md"
[ -f "$REQ" ] || { echo "ERROR: $REQ not found (run from the repo root, on the branch carrying the packet)"; exit 1; }
command -v codex >/dev/null 2>&1 || { echo "ERROR: codex CLI not found. Install: npm i -g @openai/codex ; then: codex login"; exit 1; }

SHA=$(git rev-parse --short HEAD)
echo "== Dispatching $REV | frozen HEAD: $SHA | effort: $EFFORT | model: ${MODEL:-<CLI default>}"

PROMPT="You are the independent review seat for this repository (read AGENTS.md '## Review guidelines' and prompts/INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md and follow them: re-derive from the repo, findings only, do not modify files).

Execute the review request in $REQ exactly as written — answer its numbered questions and end with an explicit verdict token from its vocabulary (ACCEPT / ACCEPT-WITH-CHANGES / BLOCK, with enumerated findings).

BEGIN your output with YAML frontmatter attesting what actually ran:
---
type: Review Result
rev_id: $REV
reviewer_model: <the exact model you are>
reasoning_effort: <the effort setting in use>
environment: <python/tool versions if you ran anything>
reviewed_commit: $SHA
date: $(date +%F)
---
A result without this attestation does not clear the gate."

# --sandbox read-only: the reviewer must not modify the tree (findings only).
# If your codex version rejects a flag, consult `codex --help`; flags current
# as of the codex-plugin-cc release. model_reasoning_effort falls back to
# 'high' automatically if the chosen model doesn't support '$EFFORT'.
codex exec \
  --sandbox read-only \
  -c model_reasoning_effort="\"$EFFORT\"" \
  ${MODEL:+-m "$MODEL"} \
  "$PROMPT" | tee "$OUT"

echo
echo "== Raw output saved to $OUT"
echo "== Finish the loop:"
echo "   1. Verify the attestation frontmatter is present and truthful; finalize as work/review/$REV/result.md"
echo "   2. git add work/review/$REV/ && git commit -m \"review: $REV result (\$(head -20 $OUT | grep -i verdict || echo 'see result'))\" && git push"
echo "   3. Write disposition.md (your verdict decision) — any Claude session will handle gate effects + ledger from there."
