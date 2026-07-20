# REV-0030 — Independent Correctness Review Result (round 3, WO-0109)

**Reviewer:** Claude (independent review seat; implementer was Codex)
**Review date:** 2026-07-18
**Pinned branch/SHA:** `consolidate/r2-canonical` at `0236591`
**Commit range reviewed:** `7e59a9e..51dee57` (Clusters A–E; F is the doc/close-out commit)

## Verdict

**ACCEPT**

Every finding the REV-0029 round-2 review raised is closed, and — the point on which WO-0108 failed —
each new safety pin was independently **mutation-verified** to fail when its guard is removed. The
full native gate and both spec oracles are green, the performance gate now passes without any
threshold change, the branch scope is clean (no `.agents/.codex`), and two fresh amended-invariant
probes (new scenarios, not test reruns) confirm the P1-1 and INV-081 properties. The merge gate for
the R2 consolidation is cleared from the review side; the human-gated surfaces still require the
operator's explicit merge.

## Verification performed (reproduced, not accepted on the implementer's word)

**Gates (all reproduced green at `0236591`):**
`ruff check .`, `ruff format --check .`, `mypy app/`, `lint-imports`, full `pytest` suite (exit 0);
`python -m tests.performance.r2_scaling_gate` → `passed: true`, ratios runtime **1.05 ≤ 3.0** and
startup **7.03 ≤ 12.0** (were 4.02 / 20.37 in round 2), `RUNTIME_SCALE_LIMIT`/`STARTUP_SCALE_LIMIT`
unchanged — Cluster E optimized rather than loosened.

**Mutation verification (neuter the guard → the exact pin turns red; restored after each):**

| Guard neutered | Pin that turned red | Confirms |
|---|---|---|
| `expected_from` CAS in `transition_order` (`memory.py:3791`) | `test_stale_created_snapshot_cannot_cancel_claimed_buy[memory]` (`CANCELED is SUBMITTING`) | P0-1 fix is real |
| final-claim `needs_review_child_order_ids` consumer (`memory.py:3240`) | `test_same_envelope_prior_sibling_blocks_claim_after_stage[memory]` **and** `test_t1_3_needs_review_child_order_ids_has_distinct_executable_consumers[memory-final]` | NEW-P0-1 (inert pin) **and** NEW-P1-1 (substring gate) both fixed — the AST gate now catches consumer removal via real reachability analysis |
| monitoring correlation discovery branch (`monitoring.py:551`) | `…owner_keyed_hostile_lineage…[memory-correlation]` red while `[memory-order_owner]` stayed green | P1-1 correlation pin is now genuinely exclusive |

**Pins reproduced green:** P0-2 recovery exposure on flatten + final claim
(`test_flatten_blocks_terminal_local_buy_with_open_recovery`,
`test_final_sell_claim_blocks_terminal_local_buy_with_open_recovery`); P0-3 ingress rejection +
legacy referenced-scope (`test_recovery_ingress_rejects_scope_that_contradicts_order`,
`test_legacy_misscoped_direct_recovery_blocks_referenced_sell_scope`); P1-1 symbol-only diagnostic
(`test_p1_1_symbol_only_hostile_lineage_warns_without_cancel`); P1-2 comparator fidelity
(`test_stream_canonicalizer_preserves_execution_event_time`,
`…preserves_payload_expiry_time`).

**Fresh amended-invariant probes (new scenarios with distinct identities, PROC-0001):**
- **INV-090 — PASS.** A symbol-only malformed action (parent missing, correlation stranger, order
  owner stranger, only the referenced-order symbol = AAPL): the store's symbol projection quarantines
  it, monitoring's owner-scoped cancellation lineage **excludes** it, and `_cancel_envelope_working_
  order` issues **no** broker cancel (child untouched). Diagnostic vs cancellation authority are
  correctly separated.
- **INV-081 — PASS.** On SQLite, a same-symbol BUY in `CANCEL_PENDING` plus an open `needs_review`
  BUY recovery, **restarted**, then flattened: outcome `buys_open`, zero SELL minted. Recovery-aware
  exposure survives the persistence boundary.

## Per-finding closure

| Round-2 finding | Round-3 disposition |
|---|---|
| P0-1 stale-snapshot cancel | **closed-by-property** — atomic `expected_from` CAS; mutation-verified |
| P0-2 claim recovery-blind | **closed-by-property** — open BUY recoveries join the shared same-symbol exposure consumed by flatten + claim |
| P0-3 recovery-scope ingress | **closed-by-property** — ingress validates scope under lock; legacy rows stay visible under both declared and referenced scope |
| NEW-P0-1 inert sibling pin | **closed** — recovery now on a distinct prior sibling; mutation-verified |
| P1-1 monitoring blind spot + non-exclusive pin | **closed-by-property** — symbol-scoped diagnostic that never enters the cancel target set; exclusive owner-key fixtures, mutation-verified |
| P1-2 over-canonicalized parity | **closed** — comparator preserves `ts_event`/payload timestamps |
| NEW-P1-1 substring T1.3 gate | **closed** — AST reachable-use-site check; mutation-verified |
| P1-3 performance | **closed** — both ratios under unchanged limits via optimization |

## Not fully verified (scope of this review)

- **SQLite action-selector rewrite (Cluster E).** The split indexed selector (`parent OR ((event-owner
  OR order-owner) AND (event-symbol OR order-symbol))`, bind-limit chunking, dedupe, exclusion,
  sequence order) was verified by reproducing the R2 conformance oracle (61 passed), the Claude oracle
  (22 + 6 documented skips), and the full hostile-closure corpus — the tests that specifically target
  selector algebra — **not** by a line-by-line SQL audit. No divergence surfaced.
- **Doc/ADR wording** (INV-081/090, ADR-010 §3/§4) was read for accuracy against the fixes, not
  independently re-derived.
- No paper-broker sandbox call was made; all probes use the repo's mock adapter and both local stores.

## Note

Codex's handoff (`request.md`) modeled the review-hardening discipline it was reviewing me against in
round 2: an explicit independence framing, a "for every claimed mutation pin, can the guarded branch
be removed while the exact test turns red?" self-check invitation, and its own evidence flagged as
"claims to reproduce, not a substitute for review." That is the correction round 1 needed, applied.
