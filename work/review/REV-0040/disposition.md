---
type: Review Disposition
rev_id: REV-0040
verdict_received: ACCEPT
disposition_status: RESOLVED
date: 2026-07-22
outcome: WO-0135 ABANDONED (reuse unsound; successor is a future purpose-built-record WO)
implementation_sha: "249f9be (doc-only blocker record); re-verified at 58b4296"
---

# Disposition — REV-0040

REV-0040 (reviewer: Claude, independent of the Codex implementer) was a **blocker-verification**
packet, not an implementation review: Codex's read-only GATE judged the pre-ratified WO-0135 reuse
design unsound and stopped per the WO's stop condition, shipping no Lane B code. The review returned
**ACCEPT** — the implementer correctly identified a real blocker and responded exactly per contract.

Independently reproduced from current code (both stores, pinned 3.12 venv):

- Reuse contract items 1–2 (create + dedup) **hold** — one record, one `SUBMIT_RECOVERY_NEEDS_REVIEW`
  event, same id, `claim_occurrence is None`, restart-stable.
- Item 3 (operator resolution) is **structurally impossible**: the typed attestation requires a
  non-empty `broker_order_id` (`app/models.py:1038`) while the store reconcile requires a real order,
  trustworthy owner/envelope lineage, and a durable submission-claim occurrence
  (`app/store/core.py:2998-3001` via `memory.py:4367` / `sqlite.py:6112`) — a synthetic record holds
  none, and a `SUBMIT_PENDING` claim can only be minted for a real `CREATED` order, so the gap is
  permanent, not incidental.
- Item 4 (post-reconcile pin) therefore cannot be constructed through the approved boundary.

**Reviewer's new corroborating finding (F1):** the synthetic record would additionally enter the
symbol's SELL-exposure rails and **permanently block `flatten_position` for that symbol** — a second,
independent unsoundness the ratified war-game missed. This strengthened the STOP.

**Outcome:** Ameen abandoned WO-0135 (2026-07-22). The reuse of the submit-recovery ledger is the
wrong vessel; its guards are load-bearing for real recoveries sharing the `""` unknown-id sentinel,
so widening ADR-012 to admit synthetic identities is rejected as a P0-class bypass. The corrupt-lineage
path stays fail-closed (REV-0037 P2-1 was advisory).

**Successor direction (non-authoritative planning input, decides nothing):** a purpose-built
malformed-lineage operator-review record (its own event vocabulary, projector, read model, typed
operator command, and ADR) is the recommended end-state; a re-derivable read-model/cockpit surface is
a defensible low-risk interim. This becomes a fresh, gated WO when Signal Seat R5+/the recovery surface
is next worked, inheriting this packet's assessment.

Per P-1, the reviewer-authored `result.md` was not edited; this disposition is a separate record.
**REV-0040 disposition: RESOLVED (blocker confirmed; WO-0135 ABANDONED).**
