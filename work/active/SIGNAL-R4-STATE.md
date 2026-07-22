# Signal Seat R4 + malformed-lineage continuity state

Branch: `codex/signal-r4-store`

Setup baseline: `origin/master@9d60b74`. The requested local branch already existed at
`b253036` with zero unique commits; it was switched to and fast-forwarded without force or
history rewrite. Both work orders and accepted ADRs are present, the staging corpus is readable,
and REV-0039 / REV-0040 namespaces were free at activation.

Activation commit: `7f918b4`.

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

`APPROVED` — the exact archive-shape DDL plus the master-specific fail-closed `_migrate`
shape/unique-key guard was presented in-session after RED evidence on 2026-07-22.

Operator response, copied verbatim before any `app/store/sqlite.py` change or commit:

> The DDL plus guard looks fine as far as I'm concerned. You may proceed.

Approval scope is exactly the presented `signal_records` DDL, status/symbol indexes, exact
column-shape guard, and `UNIQUE(producer_id, signal_id)` guard. It does not broaden either lane.

## Lane A final gate-disposition record

Operator response, copied verbatim on 2026-07-22:

```text
Approved: Grant a bounded WO-0134 formatting/whitespace exception covering only the three mandatory staging blobs and the seven Ruff findings proven byte-identical to origin/master. The three staged hashes must remain unchanged, all implementation-owned non-staged files must pass Ruff formatting, and no additional finding is waived. Formatting normalization is separate work.
Accept .venv\Scripts\python.exe -m pytest -p no:cacheprovider -q tests/r2_conformance_oracle.py as satisfying the R2 oracle gate. The unchanged oracle passes all 61 cases; the direct-script spelling is an import-context defect and should be corrected separately.
```

The exception waives no semantic test, implementation-owned formatting failure, additional Ruff
finding, or future hash drift. The direct-script import-context defect remains separate work.

## Lane B final blocker-disposition record

Operator response, copied verbatim on 2026-07-22:

```text
Keep WO-0135 BLOCKED. Do not weaken ADR-012 or implement a replacement mechanism in this session. Stage REV-0040 for Claude to verify the reuse blocker and assess, as a non-authoritative proposal, whether a purpose-built malformed-lineage operator-review record is the appropriate next design direction. Any exact schema, event vocabulary, lifecycle, operator command, new WO, or implementation requires subsequent planning and explicit human approval.
```

WO-0135 remains in `work/active/` with its Fable/blocker state `BLOCKED`; no replacement design or
implementation is authorized by this record.

## Two-lane scoreboard

| Lane | Slice | Status | Commits | Notes |
| --- | --- | --- | --- | --- |
| A / WO-0134 | `app/models.py` | VERIFIED | `ba1594d` | Additive enum/entity/event vocabulary; `test_signal_seat_models.py`: 6 passed. |
| A / WO-0134 | `app/store/base.py` | VERIFIED | `4d9779d` | Result type + ABC trio; typed injected clock. |
| A / WO-0134 | `app/store/core.py` planner | VERIFIED | `4d9779d` | Pure rewrite; constants in core; 9-property corpus green and A-3 mutation killed. |
| A / WO-0134 | `app/store/memory.py` | VERIFIED | `4d9779d` | Signal state covered by `_atomic`; all 16 memory ingest cases green. |
| A / WO-0134 | SCHEMA GATE | APPROVED | `6947966` | Operator approval copied verbatim above; exact presented package only. |
| A / WO-0134 | `app/store/sqlite.py` | VERIFIED | `b87d464` | Approved DDL + guards, mapper, and atomic ingest/read methods; focused rollback and malformed-schema tests green. |
| A / WO-0134 | projector + replay | VERIFIED | `4d9779d` | Same change; staged pure + memory projector tests and 108 replay regressions green. |
| A / WO-0134 | green evidence | VERIFIED / BOUNDED EXCEPTION | `b87d464`, `d79bd6e`, `f8c6048`, `a6468a1` | Signal R4 suite: 66 passed across both stores; full pytest, Ruff check, mypy, import-linter, operator-accepted canonical R2 oracle, and repair-scaling pass. The formatting/whitespace exception is limited to the three exact staged blobs and seven byte-identical baseline Ruff findings. |
| A / WO-0134 | REV-0039 staging | STAGED / READY | `d79bd6e`, `f8c6048`, `a6468a1` | Claude-seat request is frozen at `b87d464`; operator gate decisions are recorded and WO-0134 is REVIEW. |
| B / WO-0135 | `app/monitoring.py` escalation | BLOCKED | `249f9be`, `5e86fd0` | Creation/dedup works, but the pre-ratified lifecycle is unreachable; operator directed no implementation or ADR-012 weakening. |
| B / WO-0135 | idempotency + post-reconcile + scope pins | BLOCKED | `249f9be`, `5e86fd0` | Typed attestation rejects empty broker id; both stores reject the missing-order lineage before ADR-012 release. |
| B / WO-0135 | green evidence | BLOCKED | `249f9be`, `5e86fd0` | GATE stop condition fired before RED test/source work; blocker state explicitly retained. |
| B / WO-0135 | REV-0040 staging | STAGED / READY-BLOCKER | `5be2996`, `5e86fd0` | Claude verifies the blocker and may assess a purpose-built record only as a non-authoritative proposal. |

## Full-gate evidence (2026-07-22)

- `VERIFIED` — `.venv\Scripts\python.exe -m ruff check .`: `All checks passed!`
- `VERIFIED / BOUNDED EXCEPTION` — `.venv\Scripts\python.exe -m ruff format --check .`: Ruff would reformat the
  three mandatory byte-identical staged Signal tests and seven files unchanged from
  `origin/master`; 276 files were already formatted. Formatting either set would violate the
  staged-corpus contract or unrelated-baseline scope. All nine implementation-owned, non-staged
  Python files pass the same format check.
- `VERIFIED` — the seven non-Signal formatter findings are byte-identical to `origin/master`, and
  the three Signal findings retain staging blob ids `a4de2669...`, `9513d50e...`, and
  `a3ed1b5d...`.
- `VERIFIED / BOUNDED EXCEPTION` — `git diff --check origin/master...HEAD` reports only a trailing blank line in each
  of those same three exact staged blobs. Editing them would violate D-R4-5; no implementation or
  evidence file contributes a whitespace error.
- `VERIFIED` — `.venv\Scripts\python.exe -m mypy app/`: no issues in 70 source files.
- `VERIFIED` — `.venv\Scripts\lint-imports.exe`: 6 contracts kept, 0 broken. The initial
  `python -m lint_imports` spelling was not an executable module; the repository's installed
  entry point is the passing canonical invocation.
- `VERIFIED` — `.venv\Scripts\python.exe -m pytest -p no:cacheprovider -q`: 4,275 nodes
  collected, exit 0, progress reached 100% (including the repository's existing skips/xfail).
- `VERIFIED / ACCEPTED CANONICAL INVOCATION` — `.venv\Scripts\python.exe tests/r2_conformance_oracle.py` fails before collection
  with `ModuleNotFoundError: No module named 'app'` because direct file execution roots imports at
  `tests/`. The repository/CI canonical invocation,
  `.venv\Scripts\python.exe -m pytest -p no:cacheprovider -q tests/r2_conformance_oracle.py`,
  is `VERIFIED` with 61 passing cases.
- `VERIFIED` — `.venv\Scripts\python.exe -m pytest -p no:cacheprovider -q
  tests/test_wo0113_repair_scaling.py`: 13 passed.
- `VERIFIED` — post-disposition boundary recheck: all three staging hashes remain exact; all nine
  implementation-owned non-staged Python files report `already formatted`; all seven waived Ruff
  baseline files remain byte-identical to `origin/master`.

## NEEDS-INPUT

- None for this session. WO-0135 is deliberately BLOCKED; any next mechanism requires subsequent
  planning and explicit human approval.
