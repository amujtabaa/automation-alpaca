---
type: Review Disposition
rev_id: REV-0038
verdict_received: ACCEPT-WITH-CHANGES
disposition_status: RESOLVED
date: 2026-07-22
remediated_by: "edc8998 (F1 payload-guard pins, tests-only)"
implementation_sha: "b99d8c0"   # WO-0131 fix; F1 pins edc8998; re-verified at 57fcf3f
---

# Disposition — REV-0038

REV-0038 (reviewer: Claude, independent of the Codex builder) reviewed WO-0131's envelope
replay FSM-legality enforcement and returned **ACCEPT-WITH-CHANGES**: the fix independently
verified correct (original defect reproduced pre-fix; the exhaustive 90-pair transition matrix
re-derived and matched exactly; mutations kill), with one required change — **F1**, additive
payload `from`/`to` mismatch pins for the pre-existing guards.

**F1 remediated by `edc8998`** (tests-only, 4 new nodes) and independently re-verified by the
Claude seat at `57fcf3f`: re-applying the review's surviving mutation (b) now turns exactly
`test_status_event_payload_from_must_match_projected_status[project-envelopes]` and
`[project-read-models]` RED (previously 106-green); the `to`-guard pins are independently
failure-capable; restore → 110 passed; parity + both oracles 193 passed / 6 documented skips.

F2 (event-vocabulary/edge pairing) and F3 (3.11 env) remain recorded as non-blocking notes.
**REV-0038 disposition: RESOLVED.**
