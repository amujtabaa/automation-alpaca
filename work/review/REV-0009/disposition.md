---
type: Review Disposition
rev_id: REV-0009
verdict_received: ACCEPT-WITH-CHANGES
disposition_status: RESOLVED
date: 2026-07-10
---

# Disposition — REV-0009 (STORE-IMPL, dual-store parity)

Reviewer: GPT-5 Codex, verdict **ACCEPT-WITH-CHANGES**. The single finding is the already-known
REV-0006-F-001 (sqlite flatten atomicity); verified independently on Python 3.12.3 and cross-checked
for any *other* dual-store divergence.

## Findings

- [x] **REV-0006-F-001 (flatten atomicity)** → **CONFIRMED (known item, already REMEDIATED).** At the
  frozen base, sqlite `flatten_position` committed create+approve (`sqlite.py`) then dispatched in a
  **separate** transaction, so a hard crash between them stranded an APPROVED MANUAL_FLATTEN intent
  with no order; the in-memory store was already atomic (one `_atomic()` block wrapping create→approve→
  dispatch). **Refinement (widens the finding, not a new defect):** the create path was actually up to
  **four** sequential commits (supersede-cancel, supersede-expire, create+approve, dispatch), not the
  "supersede+create+approve in one tx" the packet implied — a wider crash window; the named
  APPROVED-no-order gap is unchanged. **Already fixed** on the dev branch (commit `27bbffb`, F-001:
  whole SUPERSEDE_AND_CREATE branch folded into one `_tx()`) and **independently cleared by REV-0019**.

- [x] **Adversarial dual-store parity scan (completeness)** → **NO other divergence.** Every sqlite
  method opening >1 `_tx()` in a single lock hold was compared to its memory counterpart:
  `create_order_for_candidate`, `append_fill`, `close_session`, and the
  `transition_order`/`quarantine`/`reconcile` family (via `_apply_order_evented_plan_locked`) all use
  **mutually-exclusive** branches or a **single** write transaction — atomic, matching memory.
  `flatten_position` was the *sole* method with a sequential multi-commit decomposition. Codex's single
  finding is complete.

## Disputed Items
- None. The finding is accurate; the four-commit refinement is a wording note for the REV-0009 packet.

## Verification
- Re-derived the sqlite decomposition and the memory single-`_atomic()` at the frozen base;
  in-code corroboration at `app/store/core.py:1085-1087`. Confirmed the F-001 fix + REV-0019 clearance.

## Follow-up
- **STORE-IMPL gate CLEARS** — the one finding is remediated (F-001, REV-0019-cleared) and no further
  parity divergence exists.
- Ledger updated (`work/ledger.jsonl`: REV-0009 outcome).
