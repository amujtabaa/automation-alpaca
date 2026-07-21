---
type: Review Request
rev_id: REV-0035
title: WO-0114 — human-attested needs-review release valve and canonical fill ingestion
status: AWAITING_REVIEW
targets: [WO-0114, ADR-012, INV-096]
reviewer_seat: CLAUDE
human_gated_surfaces:
  - event-log truth and provenance vocabulary
  - submit-recovery state machine and quarantine release
  - operator fill ingestion and position truth
  - typed operator API and cockpit control
review_base_sha: 87aa950f375e91e116a3347e1cf13de0ea5bac88
head_sha: "Resolve codex/wo-0114 HEAD after the review-stage commit containing this packet"
commit_range: 87aa950f375e91e116a3347e1cf13de0ea5bac88..HEAD
branch: codex/wo-0114
created: 2026-07-20
---

# REV-0035 — independent review of WO-0114

## Context and immutable safety contract

This is internal correctness review of an Alpaca **paper-trading** system. No live trading,
credentials, schema migration, or venue call is in scope. The always-on rules remain:

- paper only; zero live mode;
- FastAPI/backend store is the source of truth;
- Streamlit calls only typed HTTP and owns no execution state;
- submitted is not filled and only canonical `FILL` facts move position quantity;
- the kill switch blocks new order intent;
- one single-writer engine owns execution decisions;
- ADR-001's broker-overfill latch is permanent and this change cannot release it.

The operator ratified exactly D-PD1-1 through D-PD1-4: hybrid-honest provenance,
`operator_reconciled`, API plus cockpit control, and separate fill-ingestion/release commands.
Ratification authorizes implementation, not acceptance. ADR-012 remains **Proposed** and no beta
reliance is permitted until Ameen accepts the ADR and this packet receives `ACCEPT` or
`ACCEPT-WITH-CHANGES`.

## Reviewer role — independent, spec first

You are the CLAUDE independent review seat, not the implementer. Re-derive behavior from the frozen
range; do not accept author reasoning, green counts, or in-process validation as certification.
Use this authority order:

1. `CLAUDE.md` safety core and `AGENTS.md` review rules.
2. The ratified D-PD1-1..4 block in the active WO/planning package.
3. Accepted ADR-001/008/010 and `docs/INVARIANTS.md` INV-090/091.
4. Proposed ADR-012 and INV-096 (verify they faithfully encode the ratification).
5. Production code and executable tests.

Create only `work/review/REV-0035/result.md`. Do not edit this request, the WO, ADRs, tests, or
implementation. Produce findings only. Each finding requires `file:line`, a concrete failing
sequence, why it matters, and what resolves it. End with exactly one verdict: **BLOCK**,
**ACCEPT-WITH-CHANGES**, or **ACCEPT**, and state anything not independently verified.

## Frozen review range

The packet is committed with the implementation, so resolve `codex/wo-0114` HEAD before review:

```powershell
git rev-parse 87aa950f375e91e116a3347e1cf13de0ea5bac88
git rev-parse codex/wo-0114
git diff --stat 87aa950f375e91e116a3347e1cf13de0ea5bac88..codex/wo-0114
git diff --name-status 87aa950f375e91e116a3347e1cf13de0ea5bac88..codex/wo-0114
git diff --check 87aa950f375e91e116a3347e1cf13de0ea5bac88..codex/wo-0114
git diff 87aa950f375e91e116a3347e1cf13de0ea5bac88..codex/wo-0114
```

Activation commit: `f991196`. Red-first checkpoint: `a3cd2a6`. The range contains only WO-0114
lane commits from the ULTRA batch base.

## What changed

- `app/models.py`: terminal recovery status/edge; release audit/lifecycle vocabulary; additive
  `OPERATOR` / `HUMAN_ATTESTED` provenance; strict typed command models.
- `app/store/core.py`: exact identity/evidence/parity helpers, canonical broker-leg fill sum,
  non-economic release event, and occurrence-scoped direct/envelope lifecycle consumers.
- `app/store/base.py`, `memory.py`, `sqlite.py`: typed command contracts; dual-store fill ingestion
  and atomic release; exact replay/conflict semantics; no SQLite DDL.
- `app/facade/**`, `app/api/routes_trading.py`: typed command boundary and 404/409/422 mapping.
- `cockpit/**`: full-echo fill/release controls through the typed API client only.
- ADR-012, ADR-008 amendment, INV-096/INV-090 cross-reference, and PKL rationale.
- WO-0114 tests, cockpit AppTest, hardening producer/consumer matrix, and the append-only interface
  totality pin.

Forbidden paths `app/adapters/**`, `app/reconciliation.py`, and `.github/workflows/**` are untouched.

## Required semantic audit

### 1. Release can never manufacture economic truth

Prove `reconcile_submit_recovery` writes no `Fill` and no `FILL`, cannot change position or envelope
remaining, and cannot call submit/cancel/replace/status APIs. Its only writes must be the exact
status, audit event, non-economic lifecycle event, and owner reconciliation in one rollback unit.
Search for alternate routes to `operator_reconciled`, especially generic `update_submit_recovery`,
raw route/store access, startup/reconciliation, and cockpit imports.

### 2. Identity, evidence, and exact broker-leg parity fail closed

Enumerate every echoed field, including required-null `client_order_id`, candidate/sell-intent/
envelope ids, and claim occurrence. Test missing/mismatched owners, ambiguous/missing envelope,
unknown recovery/order, nonterminal state, partial `FILLED`, blank evidence, and malformed/coercible
numeric input. Verify cumulative parity cannot count a fill from a different concrete broker leg;
legacy unscoped truth with multiple legs must conflict rather than guess.

### 3. Human provenance is never broker authority

Enumerate every `EventAuthority` / `EventSource` consumer affected by the additive values. A human
fill must fold position exactly once, but must not use the broker-only overfill exception, cross
position below zero, satisfy broker terminality, or become authority-weighted order status. The
release event must remain `ENGINE` / `LOCAL`. Confirm the enum additions require no schema-version
bump and `cleanup_status` requires no migration.

### 4. Atomicity, concurrency, and restart

Compare memory `_atomic` and SQLite `_tx` mutation order and rollback. Race two different
attestations and race the recovery driver. Verify exact repeat is byte/write-count neutral while a
different actor/reason/evidence/fact returns a 409-class conflict. Close/reopen SQLite between fill,
release, and both replays. Look for a check/write gap between fill ingestion and release, including
the envelope record-first bridge.

### 5. Contribution-only lifecycle closure

The release event names one durable submission-claim occurrence. Verify it cannot close a newer or
sibling claim/venue interval. After releasing one record, independently hold each predicate:
another open recovery, malformed envelope lineage, strict delegation, broker-working child,
TIMEOUT_QUARANTINE, and ADR-001 overfill latch. Exercise the existing WO-0108/0109 choke points:
envelope stage, final claim, direct-SELL single flight, and flatten—not a new local boolean.

### 6. Typed boundary and UI

Confirm both POST routes use `Depends(get_command_facade)`, require `X-Actor`, and map only typed
`FacadeError` outcomes. The cockpit must send the complete identity echo, render server-classified
409/422 outcomes, and import no store, broker, or Alpaca module. It must own no position/status
mutation and neither control may bypass FastAPI.

### 7. Docs and pin integrity

Compare ADR-012, ADR-008, INV-096/INV-090, and PKL text to code. Verify the hardening gate points to
executable producer/consumer sites, not declarations/comments. Ensure the update to
`test_fills_append_only.py` strengthens the contract by proving canonical delegation and does not
normalize a second fills-table writer.

## INV-096 fresh independent probe (required)

Do not merely rerun an authored pin. Construct this new scenario in a temporary reviewer harness:

1. On each store, create one local SELL order with two distinct submission-claim occurrences and
   two exact broker recovery legs, then place an independently open same-symbol envelope child.
2. Ingest operator evidence for only the older leg; mix one explicitly broker-scoped canonical fill
   with an unrelated legacy unscoped fill. Require ambiguity to block release until the unrelated
   fact is disambiguated—never allocate it optimistically.
3. Release the older leg and prove the newer claim/recovery plus sibling envelope still block stage,
   final claim, direct-SELL mint, and flatten. Assert position bytes do not change at release.
4. Release the final exact leg and prove only the recovery-derived contribution disappears; then
   append/retain an ADR-001 quarantine fact and prove all four rails remain blocked.
5. Close/reopen SQLite at each boundary and repeat the reads and exact-replay calls.

Record the actual harness, observable results, and any environmental limit in `result.md`.

## Producer/consumer table to verify

| Durable fact | Legitimate producer | Required consumers | Must never mean |
|---|---|---|---|
| `operator_reconciled` recovery status | `reconcile_submit_recovery` only | all `RECOVERY_OPEN_STATUSES` queries/indexes; full-history read remains | fill, broker cancel, ADR-001 clear, automatic reopen |
| `SUBMIT_RECOVERY_RECONCILED` audit | same transaction as status | operator audit/history and exact replay comparison | economic truth or authority |
| `SUBMIT_RECOVERY_OPERATOR_RECONCILED` lifecycle event | same transaction as status | direct-SELL and envelope occurrence projections | global terminal fact, position movement, broker authority |
| `OPERATOR/HUMAN_ATTESTED FILL` | `ingest_submit_recovery_fill` via canonical planners | position fold, envelope remaining/attribution, exact-leg cumulative parity | broker terminality, overfill exception, synthetic inference |
| `claim_occurrence` in both payloads | recovery creation audit / legacy causal lookup | occurrence-scoped lifecycle closure and replay identity | permission to close a later occurrence |

## Mutation requirements

At minimum, temporarily (without committing) and independently:

- remove cumulative parity comparison: the memory and SQLite contradiction nodes must turn red;
- omit one identity echo comparison: only that field's two store nodes must turn red;
- remove each lifecycle consumer of the release event: direct-SELL and envelope choke-point tests
  must distinguish the mutations;
- treat `HUMAN_ATTESTED` as broker-authoritative: capacity/negative-position pins must turn red;
- make the valve append a fill or alter position: byte-identical position pin must turn red.

Restore in place; do not use destructive checkout and do not commit reviewer mutations.

## Exact verification commands

Use OS temp for pytest scratch; do not create repo-root basetemp directories.

```powershell
$Py = (Resolve-Path .\.venv\Scripts\python.exe).Path
& $Py -m ruff check .
& $Py -m mypy app/
& .\.venv\Scripts\lint-imports.exe
git diff --check 87aa950f375e91e116a3347e1cf13de0ea5bac88..codex/wo-0114
& $Py -m pytest -q
& $Py -m pytest -q tests/r2_conformance_oracle.py tests/test_r2_conformance_oracle_claude.py
& $Py -m pytest -q tests/test_review_hardening_gates.py
& $Py -m pytest -q tests/test_wo0114_pd1_release_valve.py tests/test_wo0114_cockpit_release.py
```

Run Ruff format on the exact WO Python paths and require green. The repository-wide command
`ruff format --check .` has one pre-existing, out-of-range blocker:
`work/review/AUDIT-0002-priorwork/probe_review_integrity.py`. Reproduce and report it; do not edit
that prior review artifact as part of REV-0035.

## Author evidence to reproduce, not trust

- Full suite: **3,948 collected; 3,936 passed, 11 skipped, 1 xfailed; exit 0; 316.6 s**.
- WO/API/cockpit/hardening focused corpus: **86/86** (69 + 3 + 14).
- Conformance: **83 passed / 6 documented skips**; hardening: **14/14**.
- Static: Ruff check green; mypy **64 files**; import-linter **6 kept / 0 broken**; diff check green.
- Mutations: cumulative guard removed -> only **2 parity failures**; symbol echo skipped -> only
  **2 identity failures**; restored identity/parity corpus **22/22**.
- Additional red probe: partial `FILLED` plus missing claim occurrence -> **4/4 failed** before
  guards and **4/4 green** after.
- First full run found one stale append-only interface-totality pin. Root cause was a new command
  boundary omitted from the enumeration; the repair adds structural canonical-writer assertions.
  That file is **4/4** and the clean full rerun is the count above.

## Integration caveats (not implementation permission)

- `docs/00_START_HERE.md:394` still says the recovery set has three values and both automatic
  outcomes are terminal. It must later describe the fourth status and sole human-gated
  `needs_review -> operator_reconciled` edge.
- `docs/00_START_HERE.md:840` says a human clears `needs_review` without naming the separate
  canonical-fill plus full-identity/terminal/cumulative-parity contract. That replacement belongs
  to a separately authorized integration correction; WO-0114 correctly did not cross scope.
- The repository-wide Ruff-format blocker above is pre-existing and outside this WO.
- ADR-012 is Proposed; Ameen acceptance and this packet's independent verdict remain unverified.

## Expected result lifecycle

Write `result.md` with `rev_id: REV-0035`, `status: COMPLETE`, reviewer identity, exact reviewed
SHA/range, date, findings, and one final verdict. Do not create `disposition.md`, update the ledger,
close/move WO-0114, or authorize merge. Those actions belong to the implementer/operator only after
review and ADR acceptance.
