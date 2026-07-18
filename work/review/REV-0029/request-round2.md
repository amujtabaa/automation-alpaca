# REV-0029 — request, ROUND 2: verify the WO-0108 remediation closed the BLOCK

> **Continuation of REV-0029 (same reviewer/session, round 2 — per the operator's 2026-07-18
> ratification).** Round 1 returned **BLOCK** with three execution-safety classes (P0-1/2/3), two
> mechanical defects (P0-4/5), and three P1s. P0-4, P0-5, and the P1-2 core were fixed in the
> disposition split (`321320c`); P0-1/2/3, P1-1, and the P1-2 extension were remediated under
> **WO-0108** (`work/active/WO-0108-rev0029-remediation.md`). This packet asks you to verify each
> class is closed **by property, not by the instance test that pins it** — the round-1 post-mortem
> found the failure was review-architecture, so this request deliberately avoids supplying "this is
> correct because…" framing. Enumerate the hazard's full producer/consumer boundary and either
> exhibit a surviving exploit or give a code-keyed unreachability argument. The merge gate reopens
> **only on your ACCEPT / ACCEPT-WITH-CHANGES**.

## Scope

- **Branch:** `consolidate/r2-canonical`.
- **Round-2 review diff:** `abfbae9..HEAD` — the round-1 clean tip through the remediation. Key
  commits: `321320c` (P0-4/5 + P1-2 core + doc corrections), `3b8f0bd` (P0-1), `a9c4960` (P0-3),
  `e4564ab` (P0-2), `188ed70` (P1-1), `37188a3` (P1-2 ext), plus the review-hardening gate commit.
- **Authority chain unchanged:** round-1 `result.md` + `disposition.md`; the four operator
  ratifications recorded in `disposition.md` §"remediation WO" and WO-0108's "Batched ratifications"
  (Policy A full needs_review submission quarantine; Policy B exit-preempts; PD-1 parked;
  same-Codex round 2).

## Turnkey verification (run all; every one green at HEAD)

```
ruff check . && ruff format --check . && mypy app/ && lint-imports
pytest -q                                              # full suite, both stores
pytest -q tests/r2_conformance_oracle.py               # Codex spec oracle (not default-collected)
pytest -q tests/test_r2_conformance_oracle_claude.py   # Claude spec oracle (6 NEEDS-INPUT skips)
pytest -q tests/test_review_hardening_gates.py         # the new Tier-1 mechanical gates
```

(The `.agents/`/`.codex/` trees are now git-ignored, so a literal `ruff check .` on a clean archive
sees only tracked source — the round-1 contamination cannot recur.)

## What to attack — closure BY PROPERTY (most important first)

For each class, the fix and its exact sites are named so you can find them; your task is to attack
the **boundary**, not confirm the instance. Where a claim is universally-quantified ("every
non-terminal status", "both stores", "every claim ordering"), verify the enumeration against a
fresh grep — never by sampling positives.

### P0-1 — flatten self-cross across cancel/late-fill

**Claim:** `FLATTEN_BLOCKING_BUY_STATUSES` (`app/store/core.py:788`) is now the full non-terminal
set (adds `SUBMITTING`/`CANCEL_PENDING`/`TIMEOUT_QUARANTINE` to the cancellable
`OPEN_BUY_STATUSES`). The store signals `FLATTEN_BUYS_OPEN` while ANY blocking BUY is non-terminal;
the facade retry cancels only the cancellable subset and fails closed (409) on venue-uncertain BUYs
(`app/facade/store_backed.py`), never blind-cancelling `SUBMITTING`/`TIMEOUT_QUARANTINE`.

**Enumerate & prove:** for EVERY `OrderStatus`, can a BUY in that status still fill after a flatten
mints its SELL? Name the gate that stops each, or exhibit the interleaving that reaches a
minted-SELL-beside-fillable-BUY state. Is `FLATTEN_BLOCKING_BUY_STATUSES == NON_TERMINAL` a property
the build enforces, or a coincidence a future status could break? (See the T1.1 gate below.)

### P0-2 — §5.3 self-cross across the Candidate→Order handoff and the final claim

**Claim (Policy B, "exit preempts"), both stores:** (a) a cross-side same-symbol rail evaluated as
the FINAL claim gate — `_cross_side_claim_block_reason` (`app/store/memory.py`, `sqlite.py`); a BUY
is blocked while any non-terminal exit SELL exists, a SELL exit blocked while a BUY is in
`MAY_EXECUTE_ORDER_STATUSES` (`app/policy.py:76` = `NON_TERMINAL − {CREATED}`). (b) flatten
(SUPERSEDE_AND_CREATE) + protection-open atomically stand down same-symbol PENDING/APPROVED BUY
candidates (`_stand_down_symbol_buy_candidates`, audited `candidate_transition reason=exit_preemption`).
(c) `create_order_for_candidate` refuses dispatch while a same-symbol exit may execute.

**Enumerate & prove:** list EVERY path by which a BUY and an exit SELL for one symbol can both reach
the venue — candidate pending/approved/dispatching, order created/claimed/working, both claim
orderings, manual flatten vs autonomous protection, the approval→dispatch await gap. For each, name
the layer (a/b/c) that closes it or exhibit the crossing. **Attack the asymmetry specifically:** the
exit "may execute" set includes `CREATED` but the BUY set excludes it — construct a race where a
`CREATED` BUY reaches the venue while an exit is live (claim orderings, concurrent claims), or prove
the claim rail blocks it in every ordering. Does the precedence (cross-side rail runs AFTER the
quarantine/session gates, so `symbol_quarantined`/`kill_switch` report first) ever let a crossing
BUY through?

### P0-3 — needs_review does not quarantine the sell side

**Claim (Policy A), both stores:** the envelope stage AND the final claim fail closed on same-lineage
`needs_review_child_order_ids`; direct-SELL dispatch/claim exposure scans widened from
`RECOVERY_UNRESOLVED` to `RECOVERY_OPEN_STATUSES`.

**Enumerate & prove:** every lane by which a second SELL can reach `SUBMITTING` beside an open
needs_review exposure — same-envelope vs fresh-owner, recovery latched before stage vs appearing
between stage and claim, both stores. Verify `needs_review_child_order_ids` has real rail consumers
(round 1 found ZERO): fresh-grep its producer and consumers (the T1.3 gate asserts producer +
both-store rails — check the enumeration is complete, not sampled).

### P1-1 — monitoring derived a narrower lineage than the store gates

**Claim:** `_validated_envelope_lineage` (`app/monitoring.py`) now discovers actions through the
store's OWNER-SCOPED identity universe — parent envelope + owner correlation (`correlation_id`) +
referenced-order owner (`order.sell_intent_id`) — matching `action_in_scope` (`app/store/memory.py`,
`sqlite.py`). An owner-keyed malformed action with a wrong/missing parent is now projected malformed
and fails the cancel closed with the R6 diagnostic instead of projecting clean-empty.

**Enumerate & prove:** the symbol key is deliberately EXCLUDED (per-envelope convergence is
owner-scoped; the store omits the symbol key when it keys by intent). Is that boundary sound — can a
malformed action the store quarantines by symbol-only (no correlation, no order-owner, no parent to
E) escape monitoring's owner-scoped universe and strand a live child with no diagnostic? Construct it
or prove it cannot arise for a per-envelope convergence. Verify the correlation-keyed AND
order-owner-keyed pins actually fail without the fix (mutation).

### P1-2 — close-parity fidelity + variants

**Claim:** the close-parity comparison is full canonicalized model dumps (`321320c`), and
`tests/test_wo0036_r2_close_and_recovery_ownership.py` now adds restart, retry (idempotent
re-close), and rollback-injection (mid-close failure → whole-close atomic rollback) variants on both
stores.

**Enumerate & prove:** does the canonicalization hide a real divergence (over-normalized ids/
timestamps)? Does the rollback-injection actually stage ≥1 event before failing (else it proves
nothing)? Is the single-atomic-unit claim true for close on BOTH stores?

## Tier-1 mechanical gates (new — verify they bite)

`tests/test_review_hardening_gates.py` (CI-blocking) encodes the deterministic gates round 1 showed
were missing: **T1.1** enum-total classification (`FLATTEN_BLOCKING == NON_TERMINAL`;
`MAY_EXECUTE == NON_TERMINAL − {CREATED}`; full-enum partition) and **T1.3** producer/consumer
(`needs_review_child_order_ids`, `MAY_EXECUTE_ORDER_STATUSES` each have a producer + both-store
consumers). Confirm each gate CAN fail: drop a status from a totality set, or a consumer reference,
and show the gate goes red. (T1.2 mutation-check + T1.4 N-run remain review-checklist per the
ratification.)

## New-invariant probe obligation (PROC-0001 #3)

INV/ADR entries AMENDED since round 1, each needing ≥1 fresh-probe line IN YOUR RESULT (a new
scenario against the invariant statement, not a rerun of its pinning test):
- **INV-090** (`docs/INVARIANTS.md`) — "no monitoring path derives a neighboring definition" is now
  asserted true (P1-1). Probe: a hostile lineage the store quarantines, checked against monitoring's
  projection directly.
- **INV-081 / ADR-010 §3/§4** — the P0-1/P0-2 self-cross corrections flipped from OPEN DEFECT to
  amended-and-closed. Probe: the §5.3 boundary under a fresh cancel/late-fill or candidate-handoff
  interleaving.

## Deliverable

Deposit `result-round2.md` with a verdict (`ACCEPT` / `ACCEPT-WITH-CHANGES` / `BLOCK`), per-finding
closure judgments (closed-by-property / instance-only / still-open + exploit or unreachability
argument), the fresh-probe lines, and any new findings. The builder will disposition per the loop in
`.ai-os/core/15_CROSS_MODEL_REVIEW.md`. Nothing beta-relevant relies on this trunk until ACCEPT.
