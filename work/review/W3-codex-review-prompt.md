# W3 Codex Review Prompt — Execution Envelope wave (ADR-010, WO-0016..0021)

Paste to Codex with repo access on the authoritative env (Python 3.12.13), pinned to the W3
integration branch tip commit `f092ca7` (`feat/execution-envelope`) on a clean, single-commit checkout. Do not share
Phase A results before the verdict.

---

You are the independent adversarial review seat for `automation-alpaca` (per `AGENTS.md`). You are
reviewing the Execution Envelope wave: `docs/adr/ADR-010-execution-envelope.md` and its
implementation (work orders WO-0016..0021 in `work/queue/`, code under `app/`, tests under
`tests/`). This wave delegates bounded autonomous sell-side execution (submit/cancel/replace)
under a human-approved envelope — it amends how the human-gated order-submission and
cancel/replace surfaces are satisfied, so your review is the policy-mandatory independent gate.

Your job is to find where the implementation, the tests, or ADR-010 itself is wrong, incomplete,
or weaker than claimed. Re-derive; do not trust WO close-out claims, comments, or test names.
Run your own reproductions and paste decisive output for every finding and every cleared gate.

Hard rails to independently verify (each is a gate; attempt to falsify before clearing):

H1  No reachable venue action violates: floor price, qty ceiling (fills-only decrement), cooldown
    floor, lifetime replace budget, max outstanding=1, TTL, allowed session phases, SELL-only,
    reduce-only. Construct hostile snapshots and interleavings; check both stores.
H2  Hard-rail violations freeze (BREACHED/EXHAUSTED, terminal-pending-human) — never clamp.
    Soft bounds clamp AND log. Verify the classification matches ADR-010 §2 exactly.
H3  Kill switch ⇒ all envelopes FROZEN before any further plan/write; the HALTED/kill check is
    atomic with durable writes — enumerate every await in the approval unit and engine seam and
    attempt the REV-0019-F-001 construction (kill in a post-check window leaving artifacts).
H4  Manual flatten preempts envelopes atomically and first; try to race an envelope reprice
    against flatten in both stores; assert event ordering in the log.
H5  Write-time validation is genuinely independent of plan-time; inject a stub policy emitting a
    below-floor plan ⇒ FROZEN + ENVELOPE_PLAN_DIVERGENCE, zero venue calls.
H6  Stale/NaN/±Inf/negative/crossed/out-of-range data ⇒ fail-closed + per-envelope stale-data
    disposition; verify none of these can reach sizing (W2-STALE/W2-RISK standard).
H7  Timeout/ambiguous broker response on submit or replace legs ⇒ TIMEOUT_QUARANTINE with
    deterministic client_order_id, no blind resubmit, envelope paused while quarantined; budget
    accounting cannot double-spend across crash-restart (single-transaction atomicity, sqlite).
H8  Remaining qty changes only on deduped fill events; race fills against cancel-acks.
H9  Supersession atomic: no instant with two ACTIVE envelopes per intent under concurrency.
H10 Replay parity: envelope state reconstructs identically from the event log; memory/sqlite
    agree on final state for your scenarios; provenance per ADR-008 on every action event.
H11 Boundary contracts hold: alpaca-py only in the adapter; UI holds no envelope state;
    single-writer preserved; import-linter contract for app/sellside/ actually enforces it.

Also review as design, not just code:
- ADR-010 internal consistency and its interaction with ADR-001/002/003/008 — flag any
  under-specified edge (e.g., partial fill while FROZEN, supersession with a resting order,
  session-boundary/DST math, restart semantics of cooldown/budget derived from history).
- Test quality: for each WO-0021 property/scenario, could it ever fail? Flag weakened assertions,
  unreachable hypothesis strategies, missing dual-store variants, unproven red-green regressions.
- Unrequested additions and scope drift in the diffs (findings, per Fable review discipline).

Verdict: BLOCK / ACCEPT-WITH-CHANGES / ACCEPT. Findings ranked P0-P3 with reproduction command +
pasted decisive output. State explicitly which gates you cleared by independent re-derivation and
which you could not exercise (and why). Deliver as `work/review/REV-00XX/result.md` content.
