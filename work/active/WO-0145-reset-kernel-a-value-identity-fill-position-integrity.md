---
type: Work Order
title: "Reset kernel A: value identity and fill-position integrity"
status: ACTIVE
work_order_id: WO-0145
wave: RESET-M1A
model_tier: strong
risk: high
disposition: []
owner: Codex implementation seat
created: 2026-07-31
branch: codex/arch-reset-2026-07-r1
base_sha: 74799d322476117c8403c9ab39a72dffd61a0716
staged_source: work/queue/ARCH-RESET-2026-07/11-first-work-order.md
activation_ci: "GitHub Actions run 30678810342 (#673): Python 3.11 job 91311451600 SUCCESS; Python 3.12 job 91311451583 SUCCESS"
---

# WO-0145 — Reset kernel A: value identity and fill-position integrity

`[FABLE • FULL • verification: DIRECT • task: pure execution-fact kernel]`

## Activation and authority

Ameen gave standing explicit consent for implementation and in-flight remediation, then instructed,
“Carry on; be ambitious.” That authority is applied only after WO-0144 closed, REV-0047 addendum 01
returned `ACCEPT`, and exact-head CI at `74799d322476117c8403c9ab39a72dffd61a0716`
passed Python 3.11 and 3.12. It activates only this bounded WO, its I/O-free production kernel, its
tests, in-scope fixes,
branch CI/review preparation, and eventual close-out. It does not activate RESET-WO-02 or later work.

Credentials are unavailable. Verification must force `BROKER_ADAPTER=mock`. No credential discovery
or use, Alpaca Paper call, account activity, broker I/O, persistent application-database change,
runtime wiring, legacy deletion/cleanup, or merge is authorized. Future Paper use requires explicit
credential, account, and activity authorization. A later explicit re-gate authorizes only the existing
R2 and full-coverage suites, including SQL/DDL performed by existing fixtures against disposable
test-only SQLite databases, plus branch push for unchanged Python 3.11/3.12 CI and WO-0145
evidence/close-out. The prohibited R1 DDL execution remains inadmissible and supplies no design,
validity, test, or acceptance evidence here.

## Fable gate

```yaml
fable_gate:
  goal: "Build the exact, immutable, deterministic fill-family semantic center without wiring it into the incumbent runtime."
  assumptions:
    - claim: "ADR-020, ADR-021, ADR-022, and staged RESET-WO-01 define the controlling M1A semantics."
      status: VERIFIED
      evidence: "Accepted authority is recorded in the reset ratification and immutable staged work order."
    - claim: "Standing human authority covers WO-0145 implementation and in-scope remediation without widening any exclusion."
      status: VERIFIED
      evidence: "The activation section records the original authority and both explicit in-flight re-gates."
    - claim: "The kernel can be verified without incumbent runtime, broker, persistence, UI, clock, network, or nondeterministic dependencies."
      status: VERIFIED
      evidence: "The isolated execution_core and import-boundary tests exercise the pure kernel; authorized pytest filesystem, source-read, basetemp, and subprocess activity is disclosed separately."
    - claim: "The exact final change will pass the database-bearing R2 and full-coverage gates."
      status: VERIFIED
      evidence: "After explicit test-database authorization, R2 passed 61/61 and the full suite passed 4,767 tests at 93.184302% branch coverage with BROKER_ADAPTER=mock."
    - claim: "The exact final change will pass Python 3.11 and Python 3.12 branch CI."
      status: UNVERIFIED
      evidence: "Python 3.11 is unavailable locally and the exact final head has not been pushed."
  approach: "Use RED-first immutable transition tests, independent arithmetic oracles, live mutation pins, minimum pure implementation, repository static gates, and independent exact-head review."
  alternatives_considered:
    - "Reuse Spine v2 or R6 implementation — rejected because those implementations remain read-only evidence until separately replaced."
    - "Wire the kernel into the incumbent runtime — rejected because integration belongs to a later reset work order."
    - "Run SQLite-bearing tests or branch CI now — rejected pending separate explicit authorization."
  out_of_scope:
    - "Broker calls, credentials, account activity, or Alpaca Paper activity"
    - "Persistent application databases, schema/migration changes, or database execution outside the explicitly authorized existing disposable test fixtures"
    - "Runtime wiring, adapters, serving, UI, status, retry, release, or protection behavior"
    - "Legacy deletion or cleanup"
    - "Merge or activation of RESET-WO-02 or later work"
  done_when:
    - behavior: "All required fill-family, lineage, quantity, basis, integrity, hydration, and import-boundary behaviors pass."
      test: "Focused execution_core test suite"
      command: ".\\.venv\\Scripts\\python.exe -m pytest -q tests/execution_core/test_values.py tests/execution_core/test_fill_position.py tests/execution_core/test_fill_position_stateful.py tests/execution_core/test_import_boundary.py -p no:cacheprovider --basetemp <fresh-path>"
    - behavior: "Every named production mutant fails while live, passes after restoration, and leaves no production diff."
      test: "Named deterministic and stateful mutation pins"
      command: "Apply each documented mutant, run its named node with a fresh cache-disabled basetemp, inverse-patch it, and rerun the same node."
    - behavior: "Repository static, import-contract, AI-OS, ledger, disposition, and contamination checks pass on the exact tree."
      test: "Repository static gates"
      command: "Run Ruff, mypy app, six import contracts, and all applicable AI-OS checkers."
    - behavior: "R2 and full branch-coverage pytest pass with BROKER_ADAPTER=mock."
      test: "Database-bearing gates after separate authorization"
      command: ".\\.venv\\Scripts\\python.exe -m pytest -q tests/r2_conformance_oracle.py; .\\.venv\\Scripts\\python.exe -m pytest --cov=app --cov-branch --cov-report=term-missing"
    - behavior: "The exact head passes unchanged Python 3.11 and Python 3.12 CI."
      test: "GitHub Actions after separate push authorization"
      command: "Push the exact head and inspect both unchanged CI jobs."
    - behavior: "Independent exact-head review reports no unresolved P0 or P1."
      test: "Independent review seat"
      command: "Review the final exact diff and fresh evidence without relying on implementation-seat conclusions."
  blast_radius: "Only app/execution_core, its isolated tests, and WO-0145 close-out records; no incumbent runtime consumer or schema."
  rollback: "Revert only the bounded WO-0145 commits while leaving incumbent runtime, repositories, worktrees, and preserved artifacts untouched."
```

## Context packet

1. `AGENTS.md` and the `CLAUDE.md` safety core.
2. ADR-020; ADR-021 fill/integrity clauses; ADR-022 sequencing/governance.
3. ADR-001; ADR-008 fill provenance; ADR-012 fill-authority separation.
4. `docs/SPINE_EXECUTION_ARCHITECTURE_v2.md` INV-1/4/5/7/9.
5. Reset packet `02-target-architecture.md`, `03-domain-specification.md`, and immutable staged
   `11-first-work-order.md`.
6. `app/position.py` and named legacy arithmetic/identity tests, read-only and re-derived.
7. D-7(a) evidence at Git object `39a6ed8b9a7562f61afc9ec5c0f9fad2c3918c80`, read with
   `git show`; its R6 paths are absent here and R6 implementation is not target authority.
8. `pkl/project/goals.md`, `pkl/architecture/testing-model.md`, and `pkl/log.md`.

## Scope

```yaml
allowed_paths:
  - app/execution_core/values.py
  - app/execution_core/identity.py
  - app/execution_core/fills.py
  - app/execution_core/position.py
  - app/execution_core/__init__.py
  - tests/execution_core/test_values.py
  - tests/execution_core/test_fill_position.py
  - tests/execution_core/test_fill_position_stateful.py
  - tests/execution_core/test_import_boundary.py
  - work/active/WO-0145-reset-kernel-a-value-identity-fill-position-integrity.md
  - work/completed/WO-0145-reset-kernel-a-value-identity-fill-position-integrity.md
  - work/completed/keep/WO-0145-reset-kernel-a-value-identity-fill-position-integrity.md
  - work/ledger.jsonl
  - pkl/log.md
activation_only_paths:
  - README.md
  - docs/04_IMPLEMENTATION_PLAN.md
  - docs/adr/ARCH-RESET-2026-07-RATIFICATION.md
  - pkl/project/goals.md
forbidden_paths:
  - app/store/**
  - app/events/**
  - app/broker/**
  - app/monitoring.py
  - app/main.py
  - app/server.py
  - app/api/**
  - ui/**
  - docs/adr/**
  - .github/**
```

The ratification index is the sole `docs/adr/**` activation-only exception. Reviewer-owned
`work/review/REV-0048/**` artifacts follow the cross-model-review contract and are outside the
implementation diff. The manifest-covered staged work order is never edited.

## Frozen M1A design decisions

- `Quantity` rejects bool/non-integer/negative values. `PriceUnits` is an exact integer;
  `PriceScale` is a finite positive `Decimal`; economic price is `units × scale`.
- Tick metadata is explicit. Compatibility requires numeric scale equality, equal positive tick
  units, and aligned reported units. There is no global scale, float conversion, or implicit rescale.
- Frozen exact identities cover broker, environment, account, symbol, order, root fill, and source
  event. Dedupe key is `(broker, environment, account, source_event_id)`.
- Normalized facts contain no receive timestamp. Full-payload equality includes fact kind, complete
  scope, root/predecessor, quantity, price, scale, and tick. Bust quantity is structurally zero and
  may retain optional reported price metadata; absent metadata is not itself incompatibility, while
  explicitly incompatible metadata withholds basis.
- Integrity is a monotonic `Flag`: `CONSISTENT=0`, fact conflict, reconciliation required, and
  overfill quarantine may coexist and are only ORed. Overfill never clears.
- Every first observation, including rejected lineage, enters the immutable seen-fact index with its
  original classification. Exact replay reports that classification and zero delta; changed replay
  preserves the first fact, adds conflict, and applies zero economics.
- `SeenFactIndex` is one immutable registry per `(broker, environment, account)`, shared across that
  account's position symbols. Its exact account owner, first observations, root reservations, and
  per-position overfill summaries participate in commitment and value identity. Mixed-account
  insertion is rejected.
- `SeenFact` commits the exact position on which an observation was evaluated. Applied
  classifications require evaluation scope to equal fact position scope; reconciliation
  observations may record a misroute. Same-position identical retries are exact no-ops;
  cross-position identical retries reconcile, and changed cross-position retries conflict and
  reconcile. A fact rejected on another position never later applies merely because it is routed to
  its fact symbol.
- A fresh source event reusing a root-fill key is reconciliation-required. A revision applies only
  to a broker-authoritative root's current head under exact complete scope.
- `PositionState` stores ordered root keys and aligned current-head IDs; the immutable root-head
  index stores full heads. Any mismatch fails closed with zero economics. Current heads are never
  independently mutable or silently trusted.
- Every valid revision replaces one head at its original root sequence and applies exact signed
  quantity delta. A non-tail revision always withholds basis and never calls/caches the slow fold.
- An available tail revision uses an exact pre-tail fold input. If that input or compatible metadata
  is unavailable, the valid fact/head/quantity still applies and basis becomes pending.
- The separate slow helper binds root order and head IDs, uses exact rational arithmetic and the
  accepted long-only fold, and returns derived, incompatible-metadata, or inconsistent-snapshot.
  Its candidate never has current authority.
- Hydration replays the complete account observation order through isolated per-position snapshots,
  then returns the selected position bound to the account-registry high-water. Historical non-tail
  proof is exact-compared whenever any proof cache is supplied. A wholly absent proof cache is an
  allowed representation, but a later affected revision remains basis-pending.
- `PositionState.integrity_floor`, exact `RootHeadIndex` scope and signed economics, and
  `SeenFactIndex` owner/reservation/summary state participate in value equality as well as
  commitments. Extrinsic snapshot bindings remain intentionally outside value equality.

## Required behavior and tests

- First BUY, partial SELL, flat, exact replay, changed replay, SELL overfill, correction, bust, and
  every missing/stale/branched/out-of-order/root/scope lineage rejection have named examples.
- Decisive examples: BUY 10@100 then BUST is qty/basis 0; correction to 7@101 is qty 7/basis 707;
  BUY 10@100, SELL 5, non-tail correction to 7@101 is qty 2/pending and slow candidate 202, not
  207; BUY 10, SELL 8, BUST BUY is qty -8 with permanent quarantine.
- Broker-authoritative incompatible price metadata and negative quantity always update exact
  quantity/head truth; they are never rejected, clamped, hidden, or relabeled. Residual SELL cap is
  `max(raw_quantity, 0)` without altering raw state.
- Human-attested input is structurally excluded; human roots cannot be corrected/busted. No
  acknowledgement, status, or non-fill-family shape can enter the transition.
- A synchronous Hypothesis `RuleBasedStateMachine` covers roots, revision chains, duplicates,
  conflicts, lineage failures, incompatible metadata, and overfill. Independent ordered-fold
  quantity/basis/head invariants run after every step; rare paths also have deterministic examples.
- Named RED-capable pins cover the historical and extended mutation matrices below: quantity,
  basis, lineage, integrity, account-wide source/root identity, exact evaluation scope, hydration,
  proof, authority, fail-closed recovery, per-position overfill summary, commitment, and equality.
- A failing sentinel proves the fast non-tail path never invokes slow derivation. Complete
  transitions repeat deterministically, inputs/predecessors remain immutable, and import/AST tests
  exclude incumbent `app.*`, SQLite, web/UI/SDK/network, dynamic import, production I/O, clock,
  UUID, random, logging, and sleep dependencies from the production execution-core modules. The
  pytest harness still performs authorized filesystem, source-read, basetemp, and subprocess I/O.

## Commands and gates

Local development is Python 3.12.13; Python 3.11 is not installed locally.

```powershell
$env:BROKER_ADAPTER = 'mock'
.\.venv\Scripts\python.exe -m pytest -q tests/execution_core/test_values.py tests/execution_core/test_fill_position.py tests/execution_core/test_fill_position_stateful.py tests/execution_core/test_import_boundary.py --basetemp .pytest_tmp_wo0145_focused
.\.venv\Scripts\python.exe -m ruff check app/execution_core tests/execution_core
.\.venv\Scripts\python.exe -m ruff format --check app/execution_core tests/execution_core
.\.venv\Scripts\python.exe -m mypy app/execution_core
```

Before close-out, run repository-wide Ruff, mypy, six import contracts, and all AI-OS checks. Run
the database-bearing R2 oracle and full branch-coverage pytest only after separate database-test
authorization, with broker forced to mock and fresh basetemps. Push only after separate push/CI
authorization; unchanged GitHub Actions must then pass both 3.11 and 3.12 jobs. Those jobs run
`ruff check .`, `mypy app/`, `lint-imports`, AI-OS checks, `python -m pytest -q
tests/r2_conformance_oracle.py`, and `pytest --cov=app --cov-branch --cov-report=term-missing`. Do not
claim R6's absent Ruff `target-version=py311` or syntax-string test; the enforceable gate is mypy
target 3.11 plus real Python 3.11 CI.

### RED evidence — 2026-07-31

The four required test modules were authored before `app/execution_core` existed. Ruff check and
format check passed. The combined focused command above, using fresh basetemp
`.pytest_tmp_wo0145_red_root` and disabled cache, failed during collection on exactly three expected
`ModuleNotFoundError: No module named 'app.execution_core'` errors (`test_values`, deterministic
fill/position, and stateful fill/position). No production runtime, broker, database, network, or
application-I/O path ran. Authorized pytest collection and filesystem activity occurred; collection
stopped before `app.execution_core` could import.

```yaml
evidence:
  phase: RED
  command: ".\\.venv\\Scripts\\python.exe -m pytest -q tests/execution_core/test_values.py tests/execution_core/test_fill_position.py tests/execution_core/test_fill_position_stateful.py tests/execution_core/test_import_boundary.py -p no:cacheprovider --basetemp .pytest_tmp_wo0145_red_root"
  result: FAIL
  decisive_output: "Collection stopped with exactly three expected ModuleNotFoundError failures because app.execution_core did not yet exist."
```

### P0 stop and explicit re-gate — 2026-07-31

The first independent GREEN review triggered this work order's mandatory stop condition by finding
three P0 snapshot/scope defects: position scope was not bound to broker/environment/account; the
position, root-head, seen-fact, and integrity inputs were not one coherently bound snapshot; and an
unbound pre-tail fold input could publish incorrect authoritative basis. It also found P1 gaps in
priced-bust metadata consistency, historical-length-independent fast-path complexity, predecessor
provenance, human-head exclusion, and failure-capable test evidence. All agents stopped and the
uncommitted working copy was preserved at committed HEAD
`49ec1f0863cebf5651b381662d9157312213cf00`.

Ameen then explicitly authorized: "Authorize WO-0145 re-gating and in-scope remediation of the
disclosed P0/P1 findings, preserving all existing broker, credential, database, runtime-wiring,
merge, deletion, and cleanup exclusions." This re-opens only the existing allowed paths for RED-first
remediation and verification. It does not widen this work order or authorize any excluded activity.

The remediation tests were then completed before production remediation. Both deterministic and
stateful arithmetic oracles were independently recast as proportional long-lot ledgers. A root-seat
focused run with `BROKER_ADAPTER=mock`, cache provider disabled, and fresh basetemp
`.pytest_tmp_wo0145_remediation_red_root_2` collected 115 tests and produced exactly 99 passes plus
16 expected failures. Those failures pin priced-bust metadata parity; three complete position-scope
dimensions; predecessor presence; mixed position/root/seen snapshots; exact replay against a stale
snapshot; monotonic integrity binding; forged pre-tail input; two pending-cache invariants; human
head exclusion; historical-length-independent fast work; and all three immutable index-update paths.
The slope pin measured 664 traced line events at 16 roots and 53,496 at 2,048 roots. An earlier
attempt with `--cache-clear` never reached collection because a pre-existing `.pytest_cache` Windows
ACL denied pytest's cache hook; it is environment evidence only and was not counted as RED evidence.

```yaml
evidence:
  phase: RED
  command: ".\\.venv\\Scripts\\python.exe -m pytest -q tests/execution_core/test_values.py tests/execution_core/test_fill_position.py tests/execution_core/test_fill_position_stateful.py tests/execution_core/test_import_boundary.py -p no:cacheprovider --basetemp .pytest_tmp_wo0145_remediation_red_root_2"
  result: FAIL
  decisive_output: "115 tests collected: 99 passed and 16 intended remediation pins failed."
```

```yaml
fable_fix:
  symptom: "The first implementation did not bind complete position scope, snapshot components, or authoritative pre-tail basis proof."
  root_cause: "Independently supplied components and fold input lacked one verifiable scope and commitment boundary."
  evidence: "Independent review found three P0 defects; the first remediation RED gate produced 16 intended failures."
  fix: "Added PositionScope binding, component commitments, coherent snapshot construction, provenance checks, exact tail-proof binding, and history-independent index updates."
  regression_test: "The 16 first-remediation deterministic and stateful pins documented above."
  red_green_verified: true
  attempt: 1
```

### Second P0 stop and standing in-flight re-gate — 2026-07-31

After the first remediation reached 115 focused passes, fresh review triggered the stop threshold
again. `ExecutionSnapshot.bind_verified` could bind an applied seen fact without matching root
economics, bind an overfill snapshot with a cleared integrity latch, and bind an unverified forged
tail-prefix basis proof. Removing the human-authority protections also survived all then-named human
tests, proving that mutation pin ineffective. Work stopped with a clean tree at checkpoint
`eee6c68` after required mutants (a) duplicate count and (b) overfill clamp were killed and restored.

Ameen then explicitly authorized the second re-gate and "any other issues or refinements found in
flight," while preserving every existing scope exclusion. This is standing authority for further
RED-first remediation within this work order's existing allowed paths. A new authorization remains
required for scope expansion or any excluded broker, credential, database, runtime-wiring, merge,
deletion, or cleanup activity.

The second remediation tests were then completed before further production edits. Ruff formatted
the focused deterministic test file and its check passed. A root-seat run with
`BROKER_ADAPTER=mock`, cache provider disabled, and fresh basetemp
`.pytest_tmp_wo0145_second_red_2` produced 16 named expected failures and six selected positive
controls. The failures independently pin orphan and unclosed applied observations, missing or
reconciliation-classified revision ancestry, replay-classification forgery, historical overfill and
reconciliation latch clearing, the non-reconstructable conflict floor, forged tail economics and
prefix commitments, inexact and erased priced-bust metadata, tail/floor commitment coverage, public
human-root hydration, and stale-bound tail-cache tampering. Positive controls retained valid
revision-chain hydration, rejected-observation hydration with its required latch, conservative
integrity supersets, fully absent tail proof degrading the next valid revision to typed pending, and
the now-coherent human-authority mutation fixtures. No production runtime, broker, database,
network, or application-I/O path ran. Authorized pytest filesystem, source-read, basetemp, and
subprocess activity occurred while the selected tests exercised only the pure kernel.

The minimum remediation then made all 22 selected second-round tests green. The full focused gate
collected and passed 134 tests with `BROKER_ADAPTER=mock`, cache disabled, and fresh basetemp
`.pytest_tmp_wo0145_second_focused_1`. Focused Ruff check, Ruff format check, and mypy over
`app/execution_core` also passed. Hydration is an explicit slow chronological replay of immutable
first observations; it compares exact current root/economic/metadata state, reconstructs any active
tail proof, permits a fully absent proof to degrade future revision basis to pending, and requires
supplied integrity to contain both replay-derived restrictions and the state-carried committed
monotonic floor. The replay is audit-only and does not enter the normal fact-application fast path.

```yaml
fable_fix:
  symptom: "Hydration admitted unmatched applied observations, cleared required integrity, accepted forged tail proof, and the human-authority mutation survived its original fixture."
  root_cause: "Commitment comparison did not reconstruct chronological semantics, integrity lacked a committed monotonic floor, and the human fixture was not coherently bound."
  evidence: "The second-remediation selection produced 16 intended failures and six positive controls; the repaired focused suite subsequently passed."
  fix: "Added chronological replay, exact classification/economic/metadata comparison, committed integrity floor, reconstructed tail proof, absent-proof degradation, and coherent human fixtures."
  regression_test: "Second-remediation hydration tests, deterministic revision-integrity pin, human-authority pins, and live hydration mutants."
  red_green_verified: true
  attempt: 2
```

### Actual mutation evidence — 2026-07-31

Every mutation below was applied to production source, run against a fresh cache-disabled basetemp,
then immediately inverse-patched. The same killing node was rerun green after restoration, and the
final production diff against GREEN checkpoint `949d861` was empty. Required mutants (a) duplicate
count and (b) overfill clamp had already been killed and restored before the second stop. This pass
killed:

- (c) reject negative root truth; (d) clear prior integrity on both root and revision application;
  (e) append rather than replace revision quantity; (f) accept a stale/non-head predecessor; (g)
  remove the human-authority revision guard for both correction and bust; (h) publish a slow
  non-tail candidate; (i) retain prior available basis when the exact tail proof is absent; (j)
  reject incompatible authoritative root metadata; (k) call the slow fold from the fast non-tail
  path; and (l) omit revision-induced negative quarantine.
- Replay/hydration mutants omitting current-root closure, replay-derived overfill/reconciliation
  restrictions, the committed conflict floor, exact first classification, exact basis metadata,
  priced-bust metadata, static tail-prefix reconstruction, tail presence/value commitment,
  integrity-floor commitment, and public human-root exclusion.

Mutation (d) initially survived all deterministic examples at the revision seam but was killed by
the stateful oracle. While that mutant remained live, a named deterministic
`test_applied_revision_preserves_prior_combined_integrity` was added and failed red; after restoring
production it passed green. Historical-overfill and reconciliation hydration fixtures were also
materialized with a clean committed floor so their pins independently require chronological replay,
rather than passing through the already-carried runtime floor. The post-mutation focused run passed
all 135 tests with fresh basetemp `.pytest_tmp_wo0145_post_mutation_focused_1`; no counted mutant
from that historical wave remained live. This makes no claim about production changes added later.

#### Reproducible required mutation matrix

The historical summary is superseded for reproducibility at its recorded checkpoints by the exact
matrix below. Every row used `BROKER_ADAPTER=mock`, `-q --tb=line -p no:cacheprovider`, the exact node
shown, and the exact fresh basetemp shown. After the recorded exit-1 failure, the literal edit was
inverse-patched and the same node was rerun at the `_restored` basetemp with exit 0. Its GREEN
production baseline was `949d861fd3c54f744e14a31f97ebdb7fc42deb26`. R01-R20 were run during the
working tree that culminated at `05960e14840ec0d40692201d506e4db21c3e5b68`; the preserved record
does not identify one immutable pre-mutation SHA for every R-row, so those rows are retained as
historical node/basetemp evidence rather than one-SHA reproduction evidence. No production runtime,
broker, database, network, or application-I/O path ran. Authorized test-harness filesystem,
source-read, basetemp, mutation-patch, and subprocess activity occurred.

| ID | Exact live production edit | Exact killing node / basetemp | Decisive exit-1 output | Exact inverse / restored result |
|---|---|---|---|---|
| a | `position.py:_unchanged_transition quantity_delta=0 -> 1` | `tests/execution_core/test_fill_position.py::test_exact_duplicate_is_noop_and_reports_original_classification`; `.pytest_tmp_wo0145_mut_a_duplicate_count` | `assert 1 == 0` | `1 -> 0`; `_restored`; `1 passed` |
| b | root `next_raw_quantity = q + delta -> max(q + delta, 0)` | `tests/execution_core/test_fill_position.py::test_direct_sell_overfill_is_exact_not_clamped_rejected_or_flattened`; `.pytest_tmp_wo0145_mut_b_overfill_clamp` | `ValueError: cannot bind structurally divergent position/root state` | restore exact signed sum; `_restored`; `1 passed` |
| c | insert early reconciliation when root `next_raw_quantity < 0` | `tests/execution_core/test_fill_position.py::test_direct_sell_overfill_is_exact_not_clamped_rejected_or_flattened`; `.pytest_tmp_wo0145_mut_c_reject_negative_root` | expected `APPLIED`, got `RECONCILIATION_REQUIRED` | remove early return; `_restored`; `1 passed` |
| d1 | root `next_integrity = integrity -> CONSISTENT` | `tests/execution_core/test_fill_position.py::test_covering_buy_establishes_only_long_remainder_basis_and_keeps_latch`; `.pytest_tmp_wo0145_mut_d1_root_integrity_clear` | overfill latch absent | restore `integrity`; `_restored`; `1 passed` |
| d2 | revision `next_integrity = integrity -> CONSISTENT` | `tests/execution_core/test_fill_position.py::test_applied_revision_preserves_prior_combined_integrity`; `.pytest_tmp_wo0145_mut_d2_revision_integrity_clear` | expected combined integrity, got `CONSISTENT` | restore `integrity`; `_restored`; `1 passed` |
| e | revision `q + signed_change -> q + revised_quantity.value` | `tests/execution_core/test_fill_position.py::test_revision_substitutes_head_at_original_sequence_without_append`; `.pytest_tmp_wo0145_mut_e_revision_append` | structural quantity/root divergence | restore signed replacement delta; `_restored`; `1 passed` |
| f | remove both current-head-ID and proven-predecessor guards | `tests/execution_core/test_fill_position.py::test_stale_predecessor_after_deep_chain_is_rejected`; `.pytest_tmp_wo0145_mut_f_accept_stale_predecessor` | stale revision changed quantity/head instead of zero economics | restore both guards; `_restored`; `1 passed` |
| g | remove `head.authority is not BROKER_AUTHORITATIVE` revision guard | `tests/execution_core/test_fill_position.py::test_human_attested_root_cannot_be_corrected_or_busted` and `tests/execution_core/test_fill_position_stateful.py::test_property_human_attested_root_cannot_be_corrected_or_busted`; `.pytest_tmp_wo0145_mut_m30_human_authority` | both fixtures applied human revisions | restore authority guard; `_restored`; `2 passed` |
| h | for non-tail revision publish `derive_ordered_basis_candidate(...).cost_basis` | `tests/execution_core/test_fill_position.py::test_non_tail_correction_commits_two_pending_and_slow_candidate_202_not_207`; `.pytest_tmp_wo0145_mut_h_publish_slow_candidate` | expected `APPLIED_BASIS_PENDING`, got `APPLIED_AVAILABLE` | remove candidate publication; `_restored`; `1 passed` |
| i | revision `next_basis = None -> position.cost_basis` | `tests/execution_core/test_fill_position.py::test_bind_verified_allows_missing_tail_proof_then_revision_becomes_pending`; `.pytest_tmp_wo0145_mut_i2_retain_basis_without_proof` | expected pending authority, got `AVAILABLE` | restore `None`; `_restored`; `1 passed` |
| j | reject root when `_metadata_accepts(...)` is false | `tests/execution_core/test_fill_position.py::test_incompatible_first_fill_applies_quantity_truth_but_withholds_basis`; `.pytest_tmp_wo0145_mut_j_reject_incompatible_root` | both cases expected `APPLIED`, got reconciliation | remove rejection; `_restored`; `2 passed` |
| k | call `_fold_ordered_heads(root_heads)` on every non-tail revision | `tests/execution_core/test_fill_position.py::test_fast_non_tail_revision_never_calls_slow_derivation`, `tests/execution_core/test_fill_position.py::test_fast_non_tail_revision_line_events_are_independent_of_history_length`, and `tests/execution_core/test_fill_position_stateful.py::test_property_fast_non_tail_revision_never_invokes_or_exposes_slow_candidate`; `.pytest_tmp_wo0145_mut_m29b_direct_slow_fold` | both sentinels fired; slope grew from `100888` to `4592439` line events | remove call; `_restored`; `3 passed` |
| l | remove revision-negative overfill OR | `tests/execution_core/test_fill_position_stateful.py::test_property_revision_induced_negative_is_exact_and_permanently_quarantined`; `.pytest_tmp_wo0145_mut_l_revision_negative_quarantine` | negative revision lacked `OVERFILL_QUARANTINE` | restore OR; `_restored`; `1 passed` |

#### Reproducible third-remediation mutation matrix

| ID | Exact live production edit | Exact killing node / basetemp | Decisive exit-1 output | Exact inverse / restored result |
|---|---|---|---|---|
| R01 | remove `_apply_root_fill` `seen_facts.contains_root` guard | `tests/execution_core/test_fill_position.py::test_rejected_first_observation_still_reserves_root_fill_key` and `tests/execution_core/test_fill_position_stateful.py::test_property_rejected_root_key_remains_reserved`; `.pytest_tmp_wo0145_mut_m13b_root_guard_both` | both later fills became `APPLIED` | reinsert guard; `_restored`; `2 passed` |
| R02 | reserve roots only for `BrokerFillFact`, not correction/bust | `tests/execution_core/test_fill_position.py::test_rejected_revision_reserves_root_against_later_fill`; `.pytest_tmp_wo0145_mut_m17_all_fact_roots` | correction and bust roots both admitted later fills | restore unconditional fact-family reservation; `_restored`; `2 passed` |
| R03 | encode observed roots by `root_fill_id` only | `tests/execution_core/test_fill_position.py::test_seen_fact_commitment_covers_observed_root_reservations`; `.pytest_tmp_wo0145_mut_m18_account_scoping` | different-account key incorrectly returned `True` | restore full `RootFillKey` encoding; `_restored`; `1 passed` |
| R04 | omit `_observed_roots.commitment` from seen-index v2 commitment | `tests/execution_core/test_fill_position.py::test_seen_fact_commitment_covers_observed_root_reservations`; `.pytest_tmp_wo0145_mut_m14_seen_commitment` | forged/unforged commitments became equal | restore map commitment; `_restored`; `1 passed` |
| R05 | `SeenFactIndex.__eq__` compares entries only | `tests/execution_core/test_fill_position.py::test_seen_fact_commitment_covers_observed_root_reservations`; `.pytest_tmp_wo0145_mut_m15_seen_equality` | behaviorally different indexes compared equal | restore observed-map equality; `.pytest_tmp_wo0145_mut_m15_seen_equality_restored_2`; `1 passed` |
| R06 | hydration closure compares entries but not seen-index commitment | `tests/execution_core/test_fill_position.py::test_bind_verified_rejects_unclosed_observed_root_reservations`; `.pytest_tmp_wo0145_mut_m16_hydration_closure` | forged empty reservation map did not raise | restore commitment comparison; `_restored`; `1 passed` |
| R07 | omit `position.integrity_floor` from incoherent recovery | `tests/execution_core/test_fill_position.py::test_incoherent_snapshot_preserves_position_integrity_floor`; `.pytest_tmp_wo0145_mut_m19_incoherent_floor` | committed overfill disappeared | restore floor union; `_restored`; `1 passed` |
| R08 | remove all component-binding fallback recovery | `tests/execution_core/test_fill_position.py::test_incoherent_snapshot_recovers_integrity_from_shared_binding`; `.pytest_tmp_wo0145_mut_m20_binding_fallback` | binding-carried overfill disappeared | restore three binding reads; `_restored`; `1 passed` |
| R09 | remove changed-observation conflict OR | `tests/execution_core/test_fill_position.py::test_incoherent_changed_replay_latches_fact_conflict`; `.pytest_tmp_wo0145_mut_m21_changed_conflict` | `EXECUTION_FACT_CONFLICT` absent | restore exact inequality guard; `_restored`; `1 passed` |
| R10 | raise conflict for every existing observation | `tests/execution_core/test_fill_position.py::test_incoherent_exact_replay_does_not_invent_fact_conflict`; `.pytest_tmp_wo0145_mut_m22_exact_no_conflict` | exact replay invented conflict | restore payload inequality predicate; `_restored`; `1 passed` |
| R11 | return incoherent position without ORing `next_integrity` into its floor | `tests/execution_core/test_fill_position.py::test_incoherent_changed_replay_latches_fact_conflict`; `.pytest_tmp_wo0145_mut_m23_durable_floor` | returned floor remained `CONSISTENT` | restore floor promotion; `_restored`; `1 passed` |
| R12 | skip rejection of retained current-tail proof when position proof is absent | `tests/execution_core/test_fill_position.py::test_bind_verified_rejects_retained_head_proof_without_position_proof`; `.pytest_tmp_wo0145_mut_m24_absent_tail_validation` | invalid hydration did not raise | restore fully-absent check; `_restored`; `1 passed` |
| R13 | retain prefix-head commitment on a pending root fill | `tests/execution_core/test_fill_position.py::test_pending_root_clears_tail_proof_and_hydrates`; `.pytest_tmp_wo0145_mut_m25_pending_root_proof` | active head commitment remained nonempty | restore conditional empty proof; `_restored`; `1 passed` |
| R14 | disable pending active-tail proof clearing | `tests/execution_core/test_fill_position.py::test_pending_tail_revision_clears_active_proof_and_hydrates` and `tests/execution_core/test_fill_position.py::test_non_tail_revision_clears_current_tail_proof_and_hydrates`; `.pytest_tmp_wo0145_mut_m26_final_active_tail_clear` | both active tails retained proof | restore active-tail clearing block; `_restored`; `2 passed` |
| R15 | erase revised historical non-tail proof unconditionally | `tests/execution_core/test_fill_position.py::test_non_tail_revision_clears_current_tail_proof_and_hydrates`; `.pytest_tmp_wo0145_mut_m28_final_historical_proof` | historical prefix commitment became empty | restore head proof preservation; `_restored`; `1 passed` |
| R16 | omit `head.price` from replayed root-head semantics | `tests/execution_core/test_fill_position.py::test_bind_verified_rejects_root_head_semantics_not_in_seen_replay`; `.pytest_tmp_wo0145_mut_m31_head_semantics` | forged price did not raise | restore price comparison; `_restored`; `1 passed` |
| R17 | omit tail `prefix_heads_commitment` comparison | `tests/execution_core/test_fill_position.py::test_bind_verified_rejects_tail_head_proof_not_in_seen_replay`; `.pytest_tmp_wo0145_mut_m32_tail_heads_commitment` | forged heads commitment case did not raise | restore comparison; `_restored`; `2 passed` |
| R18 | omit both tail `prefix_proof_commitment` comparisons | `tests/execution_core/test_fill_position.py::test_bind_verified_rejects_tail_head_proof_not_in_seen_replay`; `.pytest_tmp_wo0145_mut_m33_tail_proof_commitment` | forged proof commitment case did not raise | restore both comparisons; `_restored`; `2 passed` |
| R19 | reject every priced bust during hydration | `tests/execution_core/test_fill_position.py::test_bind_verified_accepts_priced_bust_and_preserves_compatibility`; `.pytest_tmp_wo0145_mut_m34b_priced_bust_positive` | valid priced bust raised `ValueError` | remove blanket rejection; `_restored`; `1 passed` |
| R20 | remove `PositionScope` from public `__all__` | `tests/execution_core/test_import_boundary.py::test_public_import_is_side_effect_free_and_complete`; `.pytest_tmp_wo0145_mut_m36_public_exports` | exact declared surface mismatch | reinsert export; `_restored`; `1 passed` |

One exploratory tail-proof mutation—always preserving the revised head proof—remained green because
the later active-tail clearing block was behaviorally equivalent. It was not counted as killed or
as acceptance evidence. Instead, the redundant constructor branch was removed permanently and the
four active/historical proof controls passed at `.pytest_tmp_wo0145_tail_refactor_green_1`.

```yaml
evidence:
  phase: REFACTOR
  command: "Apply each of the 33 exact live edits above, run its exact cache-disabled node selection and basetemp, inverse-patch it, and rerun at the recorded restored basetemp."
  result: PASS
  decisive_output: "All 33 counted mutants exited 1 at the named assertion and all exact inverse restorations exited 0; the one behaviorally equivalent survivor was disclosed and adopted as a simplifying refactor rather than counted."
```

### Third review stop and standing-authority RED gate — 2026-07-31

Fresh independent semantic, scope, and test reviews then reproduced two further P0 defects. An
incoherent snapshot transition could drop committed overfill and changed-replay conflict evidence,
and a rejected first observation did not reserve its account-scoped root key against a later fresh
fill. Review also found P1 proof gaps in exact public-surface coverage, direct slow-fold sentinels,
stateful human-authority coherence, hydration branch controls, fully absent tail proof, priced-bust
positive hydration, non-tail history scaling, canonical Fable records, and reproducible mutation
evidence. The standing in-flight authorization covers RED-first remediation of all of these findings
without changing any scope exclusion.

All third-round tests and evidence refinements were authored before production remediation. With
`BROKER_ADAPTER=mock`, cache disabled, and fresh basetemp
`.pytest_tmp_wo0145_third_red_complete_3`, the exact selected gate expanded to 22 cases through two
parameterizations and produced exactly 12 intended failures plus 10 positive-control passes. The
failures pin rejected fill/correction/bust root reservation; observed-root behavior, equality,
commitment, and hydration closure; monotonic floor recovery and persistence; changed-replay
conflict; fully absent tail proof; proof clearing for pending root and non-tail revision outputs; and
the stateful rejected-root property. Positive controls passed exact incoherent replay without false
conflict, exact head semantics/proof rejection, priced-bust hydration/compatibility, direct slow-fold
sentinels, bounded non-tail history work, coherent human-authority guards, and exact public exports.
No production runtime, broker, database, network, or application-I/O path ran. Authorized pytest
filesystem, source-read, basetemp, and subprocess activity occurred while the pure kernel ran.

```yaml
evidence:
  phase: RED
  command: >-
    .\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
    tests/execution_core/test_fill_position.py::test_rejected_first_observation_still_reserves_root_fill_key
    tests/execution_core/test_fill_position.py::test_rejected_revision_reserves_root_against_later_fill
    tests/execution_core/test_fill_position.py::test_seen_fact_commitment_covers_observed_root_reservations
    tests/execution_core/test_fill_position.py::test_bind_verified_rejects_unclosed_observed_root_reservations
    tests/execution_core/test_fill_position.py::test_incoherent_snapshot_preserves_position_integrity_floor
    tests/execution_core/test_fill_position.py::test_incoherent_snapshot_recovers_integrity_from_shared_binding
    tests/execution_core/test_fill_position.py::test_incoherent_changed_replay_latches_fact_conflict
    tests/execution_core/test_fill_position.py::test_incoherent_exact_replay_does_not_invent_fact_conflict
    tests/execution_core/test_fill_position.py::test_bind_verified_rejects_root_head_semantics_not_in_seen_replay
    tests/execution_core/test_fill_position.py::test_bind_verified_rejects_tail_head_proof_not_in_seen_replay
    tests/execution_core/test_fill_position.py::test_bind_verified_rejects_retained_head_proof_without_position_proof
    tests/execution_core/test_fill_position.py::test_bind_verified_accepts_priced_bust_and_preserves_compatibility
    tests/execution_core/test_fill_position.py::test_pending_root_clears_tail_proof_and_hydrates
    tests/execution_core/test_fill_position.py::test_non_tail_revision_clears_current_tail_proof_and_hydrates
    tests/execution_core/test_fill_position.py::test_fast_non_tail_revision_never_calls_slow_derivation
    tests/execution_core/test_fill_position.py::test_fast_non_tail_revision_line_events_are_independent_of_history_length
    tests/execution_core/test_fill_position_stateful.py::test_property_rejected_root_key_remains_reserved
    tests/execution_core/test_fill_position_stateful.py::test_property_fast_non_tail_revision_never_invokes_or_exposes_slow_candidate
    tests/execution_core/test_fill_position_stateful.py::test_property_human_attested_root_cannot_be_corrected_or_busted
    tests/execution_core/test_import_boundary.py::test_public_import_is_side_effect_free_and_complete
    --basetemp .pytest_tmp_wo0145_third_red_complete_3
  result: FAIL
  decisive_output: "22 selected cases: 12 intended failures and 10 positive-control passes."
```

```yaml
fable_fix:
  symptom: "Incoherent transitions could lose integrity evidence; rejected observations did not reserve root identity; review also exposed tail-proof and proof-quality gaps."
  root_cause: "The fail-closed path neither committed all recoverable flags nor detected changed replay; SeenFactIndex lacked a committed observed-root map; inactive tail proof was not fully cleared or rejected."
  evidence: "Independent review reproduced both P0s and the third-round selected RED gate failed at all 12 intended seams."
  fix: "Added a persistent commitment-bound observed-root index and hydration closure; made incoherent integrity durable and changed-replay-aware; and cleared or rejected inactive current-tail proof."
  regression_test: "The 22-case third-round selection documented above."
  red_green_verified: true
  attempt: 3
```

The minimum third remediation made the unchanged selected gate pass all 22 cases with fresh
basetemp `.pytest_tmp_wo0145_third_green_1`. The complete focused suite then passed all 153 tests
with fresh basetemp `.pytest_tmp_wo0145_third_focused_1`. Focused Ruff check, Ruff format check, and
mypy over all five isolated source files also passed. The observed-root lookup and update remain
history-independent persistent-map operations; exact account scope is part of the key. Hydration
replays and commitment-compares the reservation map, and fail-closed transitions commit recovered
and newly raised flags into the immutable position floor. Pending outputs now carry no active
current-tail proof, while historical non-tail head metadata remains untouched.

```yaml
evidence:
  phase: GREEN
  command: "The exact 22-case third-round node selection above with --basetemp .pytest_tmp_wo0145_third_green_1"
  result: PASS
  decisive_output: "22 passed."
```

```yaml
evidence:
  phase: GREEN
  command: ".\\.venv\\Scripts\\python.exe -m pytest -q -p no:cacheprovider tests/execution_core/test_values.py tests/execution_core/test_fill_position.py tests/execution_core/test_fill_position_stateful.py tests/execution_core/test_import_boundary.py --basetemp .pytest_tmp_wo0145_third_focused_1"
  result: PASS
  decisive_output: "153 passed."
```

### Tail-proof refinement RED/GREEN — 2026-07-31

Mutation planning separated active-tail invalidation from historical head provenance. The active
tail must lose both proof fields whenever basis becomes pending, but a revised non-tail head may
retain its immutable original-prefix proof because it is no longer the active authority seam. The
strengthened two-node gate first produced one intended failure and one positive pass at
`.pytest_tmp_wo0145_proof_refinement_red_1`; the minimum conditional preservation then passed both
nodes at `.pytest_tmp_wo0145_proof_refinement_green_1`. Live mutation then proved the constructor
condition duplicated the later active-tail clearing block, so the equivalent branch was removed;
all four active/historical proof controls passed at `.pytest_tmp_wo0145_tail_refactor_green_1`. The
integrity-floor fixture was also unbound so it now pins the committed floor independently of binding
fallback.

```yaml
fable_fix:
  symptom: "Pending-proof clearing also erased historical non-tail prefix provenance."
  root_cause: "Revision proof clearing was conditioned only on basis availability, not on whether the revised head remained the active tail."
  evidence: "The strengthened non-tail hydration test failed on erased historical proof while the isolated floor control passed."
  fix: "Preserve revised-head proof in the constructor and use the single later active-tail block to clear proof whenever basis is pending."
  regression_test: "test_non_tail_revision_clears_current_tail_proof_and_hydrates"
  red_green_verified: true
  attempt: 4
```

### Post-matrix exact-tree verification — 2026-07-31

After all 33 counted mutants were inverse-restored and the equivalent tail-proof branch was
simplified, the complete focused suite passed all 154 tests at fresh basetemp
`.pytest_tmp_wo0145_post_matrix_focused_1`. Repository-wide Ruff, mypy over 82 source files, all six
import contracts, install/version/ledger/PKL/disposition/Fable/scope checks, and the contamination
guard all passed. Local execution used Python 3.12.13; `py -0p` exposed only a separate Python 3.14
launcher entry and no local Python 3.11 interpreter.

```yaml
evidence:
  phase: GREEN
  command: ".\\.venv\\Scripts\\python.exe -m pytest -q -p no:cacheprovider tests/execution_core/test_values.py tests/execution_core/test_fill_position.py tests/execution_core/test_fill_position_stateful.py tests/execution_core/test_import_boundary.py --basetemp .pytest_tmp_wo0145_post_matrix_focused_1"
  result: PASS
  decisive_output: "154 passed."
```

```yaml
evidence:
  phase: REFACTOR
  command: "ruff check .; ruff format --check app/execution_core tests/execution_core; mypy app; lint-imports; AI-OS install/version/ledger/PKL/disposition/Fable/scope checks; contamination guard"
  result: PASS
  decisive_output: "Ruff clean; Ruff format check passed for 9 files; mypy clean over 82 files; 6 contracts kept and 0 broken; all AI-OS checks and contamination guard passed."
```

```yaml
evidence:
  phase: FULL_SUITE
  planned_command_not_executed: ".\\.venv\\Scripts\\python.exe -m pytest -q tests/r2_conformance_oracle.py; .\\.venv\\Scripts\\python.exe -m pytest --cov=app --cov-branch --cov-report=term-missing"
  execution: NOT_RUN
  result: BLOCKED
  decisive_output: "Static inspection established that both gates instantiate SQLite; current authority still excludes database execution."
```

### Account-identity and integrity review rounds - 2026-07-31

Fresh review after `05960e14840ec0d40692201d506e4db21c3e5b68` found one further P0 and
related P1 defects. The first-observation registry was position-local even though source-event and
root identity are account-scoped. Evaluation position was not committed separately from fact
position, so exact and changed cross-symbol retries could lose reconciliation semantics. Fail-closed
recovery could lose overfill evidence held only by a negative visible component or unbound history,
and account-global overfill history needed an exact-position summary to avoid cross-symbol leakage.
A foreign-account registry could raise instead of returning typed zero-economics reconciliation.
Historical non-tail proof comparison and value equality were also narrower than committed state.

Standing in-flight authority covered RED-first remediation without widening any exclusion. Round 4
selected seven cases: four intended failures and three controls, then 7/7 green. Round 5 selected
nine cases: five intended failures and four controls, then 9/9 green. Round 6 recorded four focused
repair checks green; because the preserved record lacks its exact pre-fix failing run, it is not
claimed as a RED/GREEN proof. Round 7 produced 3/3 intended failures, then 3/3 green. The later full
focused candidate passed 173 cases before the final construction-boundary and mutation-gap pins were
added. Final exact-tree evidence is recorded separately below.

```yaml
fable_fix:
  symptom: "Cross-symbol source/root reuse and evaluation-scope misroutes were not closed account-wide."
  root_cause: "SeenFactIndex lacked an immutable account owner, and SeenFact did not commit the position on which the fact was evaluated."
  evidence: "Rounds 4, 5, and 7 produced the recorded intended failures; the extended live-mutation matrix independently killed every account/evaluation omission."
  fix: "Made the registry account-owned; reserved source/root identity across symbols; committed evaluation scope; replayed account order through isolated per-position snapshots; and made cross-position retries reconciliation or conflict-plus-reconciliation."
  regression_test: "Cross-symbol source/root collision, exact/rejected misroute, evaluation-scope commitment, mixed-account construction, and hydration-routing pins."
  red_green_verified: true
  attempt: 5
```

```yaml
fable_fix:
  symptom: "Incoherent recovery, historical proof, and value identity could omit safety-relevant evidence."
  root_cause: "Recovery and equality/proof comparisons were narrower than committed state."
  evidence: "The focused rounds and extended mutants failed at component bindings, negative evidence, overfill history, foreign-account containment, proof comparison, and value identity."
  fix: "Recovered all trusted same-account bindings, visible negatives, and per-position overfill history; returned typed reconciliation for foreign registries; exact-compared historical proof unless wholly absent; and aligned value equality with commitments."
  regression_test: "Binding, negative-component, overfill-history/non-leak, foreign-account, historical-proof/all-absent-proof, and value-identity pins."
  red_green_verified: true
  attempt: 6
```

A final proof audit found four test-evidence P1s rather than new production defects: the original
classification fixture did not isolate the early diagnostic, foreign-registry binding contamination
was not failure-capable, pending-overfill summary construction lacked its own branch pin, and root
signed-quantity equality lacked an independent corruption fixture. Test checkpoints
`b78a652698e039652e7ca6dc3994ca9b10077551` and
`c2b881a62b4ef2a34899dbcb2f0aa8906421f17c` added the missing failure-capable pins. E01 and
E30-E32 failed live and passed after exact restoration; no production source changed for this proof
gap.

```yaml
fable_fix:
  symptom: "Four safety claims lacked isolated failure-capable mutation evidence."
  root_cause: "Earlier fixtures either exercised a redundant downstream barrier or omitted one classification, cross-scope binding, or equality branch."
  evidence: "The added test-only checkpoints made E01 and E30-E32 fail at their intended assertions and pass after restoration."
  fix: "Added non-overfill classification, foreign-bound overfill, pending-overfill summary, and signed-quantity corruption fixtures."
  regression_test: "E01 and E30-E32 in the extended matrix."
  red_green_verified: true
  attempt: 7
```

Targeted independent account-identity and value-identity reviews both returned `ACCEPT` on production
checkpoint `5ce26480ad260b8483f79999143d6e1f084ae37e`; no P0/P1 remained in those reviewed seams.
A final exact-tree blind review still follows the complete extended matrix and refreshed gates.

#### Extended post-account-scope mutation matrix

E01-E29 used immutable test/production baseline
`b78a652698e039652e7ca6dc3994ca9b10077551`; E30-E32 used baseline
`c2b881a62b4ef2a34899dbcb2f0aa8906421f17c`. Every live edit was applied alone except the explicitly
compound redundant-authority E04, run with `-q --tb=line -p no:cacheprovider` at the named fresh
basetemp, inverse-patched, and rerun green at the same stem plus `_restored`. Production diff was
empty after every restoration. No production runtime, broker, database, network, or application-I/O
path ran; authorized filesystem, source-read, basetemp, mutation-patch, and subprocess activity did.
In the table, a selector beginning `::` is exact shorthand for
`tests/execution_core/test_fill_position.py::`.

| ID | Exact live production edit | Exact killing node / basetemp | Decisive failure |
|---|---|---|---|
| E01 | Remove hydration `original_classification` comparison | `tests/execution_core/test_fill_position.py::test_bind_verified_rejects_available_fact_reclassified_basis_pending`; `.pytest_tmp_wo0145_m36_exact_classification_v2` | expected early classification error; late seen-closure error occurred |
| E02 | Omit exact `basis_price_metadata` replay comparison | `::test_bind_verified_rejects_inexact_basis_price_metadata` and `::test_bind_verified_rejects_erased_priced_bust_metadata`; `.pytest_tmp_wo0145_m37_basis_metadata` | both forged hydrations did not raise |
| E03 | Use only `position.integrity_floor` as required hydration integrity | `::test_bind_verified_rejects_historical_overfill_integrity_reset` and `::test_bind_verified_rejects_reconciliation_integrity_reset`; `.pytest_tmp_wo0145_m38_replay_integrity` | both cleared histories did not raise |
| E04 | Remove public human-head guard and omit authority from replay semantics | `::test_bind_verified_rejects_human_attested_root`; `.pytest_tmp_wo0145_m39_combined_human_authority` | human root did not raise |
| E05 | Omit fallback `position.binding` | `::test_incoherent_snapshot_recovers_integrity_from_each_component_binding[position]`; `.pytest_tmp_wo0145_m40_position_binding` | conflict flag disappeared |
| E06 | Omit fallback `root_heads.binding` | `::test_incoherent_snapshot_recovers_integrity_from_each_component_binding[root_heads]`; `.pytest_tmp_wo0145_m41_root_binding` | conflict flag disappeared |
| E07 | Omit fallback `seen_facts.binding` | `::test_incoherent_snapshot_recovers_integrity_from_each_component_binding[seen_facts]`; `.pytest_tmp_wo0145_m42_seen_binding` | conflict flag disappeared |
| E08 | Remove negative visible position/root overfill guard | `::test_incoherent_negative_component_conservatively_latches_overfill`; `.pytest_tmp_wo0145_m43_negative_components` | both parameterizations lost quarantine |
| E09 | Disable historical non-tail proof mismatch rejection | `::test_bind_verified_rejects_changed_historical_non_tail_proof`; `.pytest_tmp_wo0145_m44_historical_proof` | forged and erased proof did not raise |
| E10 | Reject all historical proof mismatch, including wholly absent cache | `::test_bind_verified_accepts_fully_absent_multi_head_proof_cache`; `.pytest_tmp_wo0145_m45_all_absent_proof` | valid proofless hydration raised |
| E11 | Omit seen-history overfill consumption | `::test_incoherent_snapshot_recovers_overfill_from_unbound_seen_history`; `.pytest_tmp_wo0145_m46_seen_overfill_consumption` | quarantine disappeared |
| E12 | Make overfill query account-global instead of position-scoped | `::test_incoherent_account_history_does_not_leak_overfill_between_symbols`; `.pytest_tmp_wo0145_m47_overfill_nonleak` | AAPL history contaminated MSFT |
| E13 | Add a new observation to a foreign-account registry | `::test_incoherent_foreign_account_registry_reconciles_without_exception`; `.pytest_tmp_wo0145_m48_foreign_registry_add` | mixed-account `ValueError` escaped |
| E14 | Omit registry owner from commitment | `::test_seen_registry_value_identity_carries_account_owner`; `.pytest_tmp_wo0145_m49_owner_commitment` | different owners committed equally |
| E15 | Omit registry owner from equality | `::test_seen_registry_value_identity_carries_account_owner`; `.pytest_tmp_wo0145_m50_owner_equality` | different owners compared equal |
| E16 | Omit evaluation position from `SeenFact` commitment | `::test_seen_fact_commits_reconciliation_evaluation_scope`; `.pytest_tmp_wo0145_m51_evaluation_commitment` | different evaluation positions committed equally |
| E17 | Remove APPLIED fact/evaluation-scope construction guard | `::test_seen_registry_rejects_mixed_or_forged_evaluation_scope`; `.pytest_tmp_wo0145_m52_applied_scope_validation` | forged APPLIED scope did not raise |
| E18 | Remove mixed evaluation-account insertion guard | `::test_seen_registry_rejects_mixed_or_forged_evaluation_scope`; `.pytest_tmp_wo0145_m53_mixed_account_validation` | mixed account did not raise |
| E19 | Remove foreign-position first-observation retry branch | `::test_account_registry_rejects_cross_symbol_source_event_collision`, `::test_account_registry_rejects_cross_symbol_exact_replay_misroute`, and `::test_rejected_misroute_cannot_apply_when_later_routed_to_fact_symbol`; `.pytest_tmp_wo0145_m54_duplicate_scope_guard` | all three returned incomplete retry semantics |
| E20 | Bypass account-wide first-observation lookup | `::test_account_registry_rejects_cross_symbol_source_event_collision`; `.pytest_tmp_wo0145_m55_account_source_reservation` | duplicate insertion escaped as `ValueError` instead of typed transition |
| E21 | Omit account-wide root-reservation apply guard | `::test_account_registry_rejects_cross_symbol_root_fill_collision`; `.pytest_tmp_wo0145_m56_account_root_guard` | second capital mutation became `APPLIED` |
| E22 | Bypass observed-root reservation construction | `::test_account_registry_rejects_cross_symbol_root_fill_collision`, `::test_rejected_first_observation_still_reserves_root_fill_key`, and both parameters of `::test_rejected_revision_reserves_root_against_later_fill`; `.pytest_tmp_wo0145_m57_root_reservation_construction` | four cases lost reservation behavior |
| E23 | Hydrate by fact position instead of evaluation position | `::test_rejected_misroute_cannot_apply_when_later_routed_to_fact_symbol`; `.pytest_tmp_wo0145_m58_hydration_evaluation_scope` | classification was not reproducible |
| E24 | Omit per-position overfill summary from commitment | `::test_seen_registry_commitment_carries_overfill_summary`; `.pytest_tmp_wo0145_m59_overfill_summary_commitment` | forged/authentic commitments matched |
| E25 | Omit per-position overfill summary from equality | `::test_seen_registry_commitment_carries_overfill_summary`; `.pytest_tmp_wo0145_m60_overfill_summary_equality` | forged/authentic indexes compared equal |
| E26 | Exclude `PositionState.integrity_floor` from equality | `::test_position_value_identity_carries_integrity_floor`; `.pytest_tmp_wo0145_m61_position_floor_equality` | clean/quarantined positions compared equal |
| E27 | Compare `RootHeadIndex.entries` only | `::test_empty_root_index_value_identity_carries_exact_scope`; `.pytest_tmp_wo0145_m62_root_scope_equality` | different scopes compared equal |
| E28 | Disable per-position overfill-summary construction | `::test_seen_registry_commitment_carries_overfill_summary` and `::test_incoherent_snapshot_recovers_overfill_from_unbound_seen_history`; `.pytest_tmp_wo0145_m63_overfill_summary_construction` | both lost the summary/latch |
| E29 | Default reconciliation evaluation scope to fact scope | `::test_seen_fact_commits_reconciliation_evaluation_scope` and `::test_rejected_misroute_cannot_apply_when_later_routed_to_fact_symbol`; `.pytest_tmp_wo0145_m64_reconciliation_evaluation_record` | both recorded MSFT instead of evaluated AAPL |
| E30 | Trust a foreign registry's snapshot binding | `::test_incoherent_foreign_account_registry_reconciles_without_exception`; `.pytest_tmp_wo0145_m65_foreign_binding_contamination` | foreign overfill contaminated local integrity |
| E31 | Omit `APPLIED_PENDING_OVERFILL` summary construction | `::test_incoherent_snapshot_recovers_pending_overfill_from_seen_history`; `.pytest_tmp_wo0145_m66_pending_overfill_summary` | pending overfill summary disappeared |
| E32 | Omit signed quantity from `RootHeadIndex` equality | `::test_root_index_value_identity_carries_signed_quantity`; `.pytest_tmp_wo0145_m67_root_signed_quantity_equality` | different signed economics compared equal |

All E01-E32 selections passed immediately after their exact inverse restoration. E01's older
overfill-classification fixture initially survived because summary/closure checks independently
rejected the forgery; the added non-overfill fixture pins the earlier diagnostic seam while the late
closure remains defense in depth. For E04, either human-authority guard alone survived because the
other guard still rejected; the disclosed compound edit proved the complete bypass. Invalid or
non-counted historical attempts remain excluded from totals: wrong-arity fold, `NameError`
priced-bust, wrong basis occurrence, the equivalent proof survivor, and a single redundant human
guard. The historical 33 plus this first extended 32 give 65 counted live edits, all
inverse-restored before the eighth review below.

### Eighth review P1 and scope-isolation fix - 2026-07-31

The final blind review found one new P1: incoherent recovery trusted a foreign-position root
binding and negative root quantity, and a same-account other-symbol seen-registry binding, without
requiring the binding/root position to equal the local position. Economics still failed closed at
zero, but foreign `OVERFILL_QUARANTINE` could be imported and permanently committed into the local
position floor. The RED gate at `.pytest_tmp_wo0145_eighth_red_cross_scope_integrity` produced 3/3
intended failures: same-account other-symbol root, foreign-account root, and other-symbol bound seen
registry. The minimum fix admitted component binding and visible root evidence only for exact local
position scope. The repaired gate plus seven same-scope/foreign-account controls passed 10/10 at
`.pytest_tmp_wo0145_eighth_green_cross_scope_integrity`.

```yaml
fable_fix:
  symptom: "Fail-closed recovery could import and permanently latch integrity from a foreign position."
  root_cause: "Component bindings and visible root negativity were treated as trusted evidence without exact binding/root position-scope equality."
  evidence: "Three cross-scope RED cases imported OVERFILL_QUARANTINE; the repaired 10-case selection preserved local reconciliation without leakage and retained all same-scope recovery."
  fix: "Gate position/root/seen binding integrity on exact binding position scope, gate root bindings and signed quantity on exact root-index position scope, and retain account/position-scoped seen-history recovery."
  regression_test: "Foreign-account and other-symbol root non-leak, other-symbol seen-binding non-leak, and per-component binding-scope mismatch pins."
  red_green_verified: true
  attempt: 8
```

The fix was committed at `d12dec0`; the exact component-binding proof pins were committed at
`e73d4ec31efdacfdd1b367f292b0d54ebfdf288e`, which is the baseline for E33-E36. Each live edit was
applied alone, run with the same cache-disabled mutation protocol, inverse-patched, and rerun green.

| ID | Exact live production edit | Exact killing node / basetemp | Decisive failure |
|---|---|---|---|
| E33 | Trust `position.binding` without exact binding position scope | `::test_incoherent_component_binding_scope_mismatch_does_not_leak_overfill[position]`; `.pytest_tmp_wo0145_m68_position_binding_scope` | foreign quarantine entered local integrity |
| E34 | Trust `root_heads.binding` without exact binding position scope | `::test_incoherent_component_binding_scope_mismatch_does_not_leak_overfill[root_heads]`; `.pytest_tmp_wo0145_m69_root_binding_scope` | foreign quarantine entered local integrity |
| E35 | Trust same-account `seen_facts.binding` without exact binding position scope | `::test_incoherent_other_symbol_seen_binding_does_not_leak_overfill`; `.pytest_tmp_wo0145_m70_seen_binding_scope` | other-symbol quarantine entered local integrity |
| E36 | Trust negative root quantity without exact root-index position scope | both parameters of `::test_incoherent_foreign_root_index_does_not_leak_overfill`; `.pytest_tmp_wo0145_m71_foreign_root_negative` | both foreign roots contaminated local integrity |

All four selections passed after restoration. Removing only the additional root-component-scope
predicate from binding recovery remains behaviorally redundant while the exact binding-scope guard
is present; it is disclosed and not counted. The complete campaign therefore contains 69 counted
live edits (33 historical plus 36 extended), all restored before final verification.

### Final allowed exact-tree verification - 2026-07-31

The exact source/test tree at immutable checkpoint
`e73d4ec31efdacfdd1b367f292b0d54ebfdf288e`, together with this documentation-only evidence
reconciliation, passed the complete focused gate: 182/182 cases at fresh cache-disabled basetemp
`.pytest_tmp_wo0145_final_focused_2`. Repository-wide Ruff passed; Ruff format check reported all
nine execution-core source/test files already formatted; mypy passed all 82 `app` source files;
Import Linter kept all six contracts with zero broken; install, version, ledger, PKL, disposition,
Fable, and exact WO scope checks passed; and the tracked-tooling contamination guard was clean.

```yaml
evidence:
  phase: GREEN
  command: ".\\.venv\\Scripts\\python.exe -m pytest -q tests/execution_core/test_values.py tests/execution_core/test_fill_position.py tests/execution_core/test_fill_position_stateful.py tests/execution_core/test_import_boundary.py -p no:cacheprovider --basetemp .pytest_tmp_wo0145_final_focused_2 --tb=line"
  result: PASS
  decisive_output: "182 passed (72 + 72 + 38 progress cases)."
```

```yaml
evidence:
  phase: REFACTOR
  command: "ruff check .; ruff format --check app/execution_core tests/execution_core; mypy app; lint-imports --no-cache; AI-OS install/version/ledger/PKL/disposition/Fable/scope checks; contamination guard"
  result: PASS
  decisive_output: "Ruff clean; 9 files already formatted; mypy clean over 82 files; 6 contracts kept and 0 broken; all AI-OS checks, exact WO scope, and contamination guard passed."
```

No production runtime, broker, credential, account activity, database, SQL/DDL, network, application-I/O,
runtime-wiring, merge, deletion, or cleanup activity occurred. Authorized test-harness filesystem,
source-read, basetemp, mutation-patch, and subprocess activity occurred. R2/full branch coverage,
local Python 3.11, push, and dual-version CI remain deferred to separately authorized future gates.

The independent final reviewer re-derived the repaired source/test checkpoint
`e73d4ec31efdacfdd1b367f292b0d54ebfdf288e`, reran 182/182 focused tests plus repository
Ruff/format/mypy, reviewed the current evidence reconciliation, and returned `ACCEPT` with no
unresolved P0/P1. That pass did not execute the 69 mutations independently and did not run the
database-bearing, Python 3.11/dual-version CI, broker, runtime, or network gates; those limits remain
explicit rather than being treated as acceptance evidence.

### Authorized database-test and coverage re-gate - 2026-08-01

Ameen explicitly authorized WO-0145 to run the existing R2 conformance and full branch-coverage
suites with `BROKER_ADAPTER=mock`, including SQL/DDL executed by existing fixtures only against
disposable test SQLite databases. The same re-gate authorizes in-scope remediation and branch push
only for unchanged Python 3.11/3.12 CI and WO-0145 evidence/close-out. It does not authorize broker
credentials, Alpaca activity, persistent application-database changes, runtime wiring, PR, merge,
deletion, cleanup, or activation of a later work order.

The first full-coverage attempt timed out at 99% and is environment evidence only. The completed
baseline then passed all 4,758 executable tests but failed the unchanged 93% floor at exactly
92.568306% (`18,634 / 20,130` covered line/branch elements). Static coverage analysis found that the
deficit was concentrated in real malformed-input and immutable-boundary guards in the allowed
execution-core modules. Nine test-only cases were added for exact composite identity types,
root-head economics/proofs, immutable index operations, account-registry ownership, hydration state,
and public operation types. No production code, exclusion, skip, threshold, or denominator changed.

```yaml
fix:
  symptom: "The full behavior suite passed, but the unchanged 93% branch-coverage gate failed at 92.568306%."
  root_cause: "Real defensive execution-core branches lacked direct failure-capable public-surface tests."
  evidence: "The completed pre-fix full run reported 4,758 passed, 11 skipped, 1 xfailed, and 92.57% coverage."
  fix: "Added nine in-scope test cases covering 124 previously unexecuted line/branch elements without modifying production or coverage configuration."
  regression_test: "The 191-case focused gate and the complete 4,767-test branch-coverage gate."
```

The exact changed source/test tree passed 191/191 focused cases at
`.pytest_tmp_wo0145_coverage_focused_1`. Repository Ruff and format checks passed; mypy passed all 82
`app` files; Import Linter kept all six contracts; every install/version/ledger/PKL/disposition/Fable
and exact-scope checker passed; and the contamination guard remained clean. Independent findings-only
review reproduced all nine new tests plus the affected 180-test subset and returned `ACCEPT` with no
P0/P1, while correctly deferring the full suite and dual-version CI to their own gates.

The exact post-fix R2 oracle passed 61/61 at `.pytest_tmp_wo0145_r2_authorized_2`. The authoritative
full suite at `.pytest_tmp_wo0145_full_coverage_authorized_3` passed 4,767 tests with 11 skips, one
expected failure, 18 warnings, and 93.184302% coverage in 1,034.26 seconds. Exact totals were 13,978
covered lines of 14,748 statements and 4,780 covered branches of 5,382. The preserved coverage-data
artifact `.coverage_wo0145_full_authorized_3` has SHA-256
`82803610fbc66665a7aaf1966a348e8584c57df30925fe6140a72b3b356c951c`.

```yaml
evidence:
  phase: GREEN
  command: ".\\.venv\\Scripts\\python.exe -m pytest -q tests/r2_conformance_oracle.py -p no:cacheprovider --basetemp .pytest_tmp_wo0145_r2_authorized_2 --tb=line"
  result: PASS
  decisive_output: "61/61 R2 conformance cases passed with BROKER_ADAPTER=mock."
```

```yaml
evidence:
  phase: GREEN
  command: ".\\.venv\\Scripts\\python.exe -m pytest --cov=app --cov-branch --cov-report=term-missing -p no:cacheprovider --basetemp .pytest_tmp_wo0145_full_coverage_authorized_3 --tb=line"
  result: PASS
  decisive_output: "4,767 passed, 11 skipped, 1 xfailed; required 93% reached at 93.184302%."
```

Authorized existing fixtures executed test-only SQL/DDL against their disposable SQLite databases.
No broker credential, Alpaca account, Paper activity, network broker path, persistent application
database, schema/migration change, or runtime wiring was used. The prohibited R1 DDL incident and its
result were not cited, reused, or relied upon for any WO-0145 conclusion. Coverage and basetemp
artifacts are preserved and remain uncommitted because cleanup and deletion remain excluded.

## Review, stop, and close-out

Stop if authority conflicts, representation needs adapter/persistence/query/recovery policy, exact
ordered folding is not determined, an implicit conversion is needed, either interpreter gate is
red/unavailable, incumbent store/event code is needed, or two P0/three same-root P1 findings emerge.

Completion requires exact scope, every mutation pin demonstrated failure-capable, focused/full
dual-version green evidence, no incumbent runtime/schema change, and independent blind review with
no unresolved P0/P1. Then move this WO to `work/completed/keep/`, append exactly one ledger row, and
record PKL impact in the same commit. No self-acceptance and no merge.

```yaml
fable_done:
  task: "WO-0145 reset kernel A: value identity and fill-position integrity"
  done_when_results:
    - item: "All focused kernel behavior passes on the exact current tree."
      status: MET
      evidence: "The authorized post-coverage source/test tree passed all 191 focused tests at .pytest_tmp_wo0145_coverage_focused_1."
    - item: "Every required mutation pin is demonstrated failure-capable and restored green with durable evidence."
      status: MET
      evidence: "The historical 33 and extended 36 rows record 69 live edits with nodes/basetemps, decisive failures, inverse restoration, and restored green; historical baseline limits and redundant/invalid survivors are disclosed rather than miscounted."
    - item: "Repository-wide static gates pass on the exact current tree."
      status: MET
      evidence: "Repository Ruff, 9-file format check, mypy over 82 app files, six import contracts, all applicable AI-OS checks, exact WO scope, and contamination guard passed after the coverage remediation."
    - item: "R2 and full branch-coverage suites pass."
      status: MET
      evidence: "Under the explicit disposable-test-database re-gate, R2 passed 61/61 and the full suite passed 4,767 tests at 93.184302% with BROKER_ADAPTER=mock."
    - item: "Python 3.11 and Python 3.12 CI pass on the exact head."
      status: BLOCKED
      evidence: "Push and unchanged dual-version CI are now authorized; the exact checkpoint has not yet been pushed."
    - item: "Independent exact-head review has no unresolved P0 or P1."
      status: MET
      evidence: "The prior exact-source reviewer accepted e73d4ec; the coverage-delta reviewer independently reproduced all nine new cases and the affected 180-test subset, then returned ACCEPT with no unresolved P0/P1."
    - item: "Allowed paths and all broker, credential, database, runtime, merge, deletion, and cleanup exclusions remain respected."
      status: MET
      evidence: "The tracked diff remains within allowed paths. Only explicitly authorized existing fixtures used disposable test SQLite/SQL/DDL; no persistent application database, broker, credential, account activity, network, runtime wiring, merge, deletion, or cleanup occurred."
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
  debt_check: "Open in-scope defects and unexecuted proof obligations are listed explicitly; none is waived."
  deferred:
    - "Authorized exact-head Python 3.11 and Python 3.12 branch CI pending checkpoint push and run inspection."
  status: BLOCKED
```
