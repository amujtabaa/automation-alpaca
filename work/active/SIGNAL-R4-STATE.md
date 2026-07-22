# Signal Seat R4 + malformed-lineage continuity state

Branch: `codex/signal-r4-store`

Setup baseline: `origin/master@9d60b74`. The requested local branch already existed at
`b253036` with zero unique commits; it was switched to and fast-forwarded without force or
history rewrite. Both work orders and accepted ADRs are present, the staging corpus is readable,
and REV-0039 / REV-0040 namespaces were free at activation.

## Operator decision block (pre-checked = ratified on paste; edit to override)

- [x] D-R4-1 **Slice correction (supersedes the WO-0128 slice map's 4-file R4 row):** R4's
      green obligation is exactly the three store-pure files —
      `tests/test_signal_seat_models.py`, `tests/test_signal_ingest_store.py`,
      `tests/test_signal_projector_forward_compat.py` — on BOTH stores.
      `tests/test_signal_quarantine_totality.py` imports the R5-owned
      `tests/signal_seat_helpers.py` app seam and CANNOT go green in R4: land its R4-owned
      symbols (`SIGNAL_TTL_MIN_SECONDS`/`SIGNAL_TTL_MAX_SECONDS` in `app.store.core`;
      `_SYMBOL_RE` already exists at `app/store/base.py:74`), paste collection evidence
      that its ONLY remaining red is the missing R5 seam, and never commit that file on
      this branch.
- [x] D-R4-2 **Constant placement follows the staged corpus**, not the archive: the six
      ingest-outcome constants + two TTL constants are importable from `app.store.core`
      exactly as the tests pin (archive kept them in `models.py` — do not follow it there).
- [x] D-R4-3 **Replay-parity registration ships in the same change** as the projector:
      `ReadModelProjection` gains a defaulted signals field, `project_read_models` folds via
      `project_signal_records`, `_describe_read_model_diff` extended.
- [x] D-R4-4 **Archive citations convert to archive-ref provenance** — never bare
      REV-0024/REV-0025 ids on master (id collision, plan §2): cite as
      `archive REV-00xx @ origin/archive/claude-wo-0001-install-checks-2x5ys8`.
- [x] D-R4-5 **Branch:** `codex/signal-r4-store` from current master; the three test files
      are pulled from the staging branch, byte-identical, never weakened.
- [x] D-R4-6 **Property-based corpus:** add `tests/test_signal_ingest_properties.py`
      (hypothesis, already pinned — no new dependency, no ADR) with the three tiers the WO
      specifies: planner invariants (A-3 exactness, skew boundaries, dedupe injectivity,
      echo-vs-conflict), outcome totality over the six constants, and metamorphic
      fold/replay equivalence — **PURE seams only, sync** (never drive async store methods
      under hypothesis; the house property idiom is sync-over-pure, and store round-trip
      parity is already example-pinned by the staged corpus). House idiom per
      `tests/test_wo0018_sellside_properties.py`; additive alongside the staged corpus,
      never a substitute; at least one property proven RED-capable via a mutation.
- **NOT pre-checked and NOT pre-checkable — THE SCHEMA GATE (Lane A only):** the fresh
  `signal_records` schema approval happens mid-session with the actual DDL in front of the
  operator (WO-0134 "THE SCHEMA GATE" section is the binding procedure). This block does NOT
  authorize any `app/store/sqlite.py` commit.

**Lane B (WO-0135 malformed-lineage record) — pre-ratified design:**

- [x] D-ML-1 **Mechanism = reuse.** Emit the durable record via the existing
      `store.create_submit_recovery(...)` seam at `app/monitoring.py:1502` — reusing the
      `SUBMIT_RECOVERY_NEEDS_REVIEW` event + `SubmitRecoveryRecord` ledger. **No new
      `ExecutionEventType`, no new table, no migration** → no mid-session gate. If reuse
      proves unsound at GATE, STOP and escalate (do NOT patch `app/store/**` or add a type).
- [x] D-ML-2 **Dedup identity** = `(local_order_id="lineage:<envelope.id>", broker_order_id="")`;
      pre-check `list_submit_recoveries()` (all statuses) for that pair and **skip create if
      any record exists in any status** — this is what makes it "one deduped needs_review" and
      what prevents the post-reconcile `RecoveryTransitionError` (war-game Hazard 2).
- [x] D-ML-3 **Scope fields = immutable envelope values only** (`symbol`, `side` SELL,
      `quantity=qty_ceiling`, `limit_price=None`, `client_order_id=envelope.id`,
      `session_id=None`) so the idempotent replay's `same_scope` always holds even as
      `remaining_quantity` drifts (Hazard 1). `remaining_quantity` + the ambiguity sets go in
      `extra_payload` only.
- [x] D-ML-4 **Reason code** = the string literal `"envelope_lineage_malformed"` kept in
      `app/monitoring.py` (NOT a new `app/models.py` constant) — keeps Lane B disjoint from
      Lane A's `models.py` edits.
- [x] D-ML-5 **Lifecycle** = resolves only via the operator's HUMAN_ATTESTED reconcile →
      `RECOVERY_OPERATOR_RECONCILED` (ADR-012, Accepted); the WO never re-flags a lineage the
      operator already dispositioned.
- [x] D-ML-6 **Log-quieting (bounded/optional)** = downgrade the `:1502` per-tick warning to
      first-detection-only; if it complicates the change, keep the warning and note it — never
      expand scope for it.

Already ratified, binding, never re-asked: ADR-009 A-3 constants (expires_at formula, ttl
[30, 86400], skew +30s/−24h, persisted-never-re-derived); D-SIG-1..9; D-SIG-7 in
particular — no multi-exit relaxation anywhere in R4 planning logic; injective
`(producer_id, signal_id)` dedupe; `payload_hash` conflict = audit-only, never a status
change. WO-0135 keeps the corrupt-lineage path **fail-closed** exactly as today (no venue
call, no guessed target) — the record is additive visibility only.

## Schema-gate approval record

`NEEDS-INPUT` — no SQLite approval is implied by the kickoff or prior archive decision. The exact
DDL package must be presented after R4 red evidence; the operator's response will be copied here
verbatim before any `app/store/sqlite.py` commit.

## Two-lane scoreboard

| Lane | Slice | Status | Commits | Notes |
| --- | --- | --- | --- | --- |
| A / WO-0134 | `app/models.py` | PENDING | — | Additive signal vocabulary only. |
| A / WO-0134 | `app/store/base.py` | PENDING | — | Result type + ABC trio. |
| A / WO-0134 | `app/store/core.py` planner | PENDING | — | Pure rewrite; constants in core. |
| A / WO-0134 | `app/store/memory.py` | PENDING | — | Signal state covered by `_atomic`. |
| A / WO-0134 | SCHEMA GATE | NEEDS-INPUT | — | No SQLite work/commit until explicit approval. |
| A / WO-0134 | `app/store/sqlite.py` | BLOCKED | — | Blocked only on the schema gate. |
| A / WO-0134 | projector + replay | PENDING | — | Same commit. |
| A / WO-0134 | green evidence | PENDING | — | Staged tests, properties, totality partial, full gates. |
| A / WO-0134 | REV-0039 staging | PENDING | — | Claude-seat request only. |
| B / WO-0135 | `app/monitoring.py` escalation | PENDING | — | Reuse gate VERIFIED on both stores before activation. |
| B / WO-0135 | idempotency + post-reconcile + scope pins | PENDING | — | Dual-store, replay, zero venue calls. |
| B / WO-0135 | green evidence | PENDING | — | Targeted then full gates. |
| B / WO-0135 | REV-0040 staging | PENDING | — | Claude-seat request only. |
