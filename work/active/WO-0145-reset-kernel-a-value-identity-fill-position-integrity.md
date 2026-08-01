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
passed Python 3.11 and 3.12. It activates only this bounded I/O-free WO, its tests, in-scope fixes,
branch CI/review preparation, and eventual close-out. It does not activate RESET-WO-02 or later work.

Credentials are unavailable. Verification must force `BROKER_ADAPTER=mock`. No credential discovery
or use, Alpaca Paper call, account activity, broker I/O, persistence/schema/SQL/DDL/database work,
runtime wiring, legacy deletion/cleanup, or merge is authorized. Future Paper use requires explicit
credential, account, and activity authorization. The prohibited R1 DDL execution remains inadmissible
and supplies no design, validity, or test evidence here.

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
      evidence: "The isolated execution_core and import-boundary tests exercise only the pure kernel."
    - claim: "The exact final change will pass the database-bearing R2 and full-coverage gates."
      status: UNVERIFIED
      evidence: "Static inspection established that those commands instantiate SQLite, which remains excluded."
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
    - "Persistence, schema, SQL, DDL, database engines, migrations, or fixtures that instantiate a database"
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
- Named RED-capable pins kill all staged mutants: duplicate count; overfill clamp/reject; integrity
  clear; positive revision append; non-head acceptance; human revision; pending candidate exposure;
  missing exact-basis-or-pending result; incompatible-price rejection; slow-helper fast call; and
  revision-induced negative without quarantine.
- A failing sentinel proves the fast non-tail path never invokes slow derivation. Complete
  transitions repeat deterministically, inputs/predecessors remain immutable, and import/AST tests
  exclude incumbent `app.*`, SQLite, web/UI/SDK/network, dynamic import, I/O, clock, UUID, random,
  logging, and sleep dependencies.

## Commands and gates

Local development is Python 3.12.13; Python 3.11 is not installed locally.

```powershell
$env:BROKER_ADAPTER = 'mock'
.\.venv\Scripts\python.exe -m pytest -q tests/execution_core/test_values.py tests/execution_core/test_fill_position.py tests/execution_core/test_fill_position_stateful.py tests/execution_core/test_import_boundary.py --basetemp .pytest_tmp_wo0145_focused
.\.venv\Scripts\python.exe -m ruff check app/execution_core tests/execution_core
.\.venv\Scripts\python.exe -m ruff format --check app/execution_core tests/execution_core
.\.venv\Scripts\python.exe -m mypy app/execution_core
```

Before close-out, run repository-wide Ruff, mypy, six import contracts, all AI-OS checks, the R2
oracle, and full branch-coverage pytest with broker forced to mock and fresh basetemps. Push the
exact head; unchanged GitHub Actions must pass both 3.11 and 3.12 jobs. Those jobs run `ruff check
.`, `mypy app/`, `lint-imports`, AI-OS checks, `python -m pytest -q tests/r2_conformance_oracle.py`,
and `pytest --cov=app --cov-branch --cov-report=term-missing`. Do not claim R6's absent Ruff
`target-version=py311` or syntax-string test; the enforceable gate is mypy target 3.11 plus real
Python 3.11 CI.

### RED evidence — 2026-07-31

The four required test modules were authored before `app/execution_core` existed. Ruff check and
format check passed. The combined focused command above, using fresh basetemp
`.pytest_tmp_wo0145_red_root` and disabled cache, failed during collection on exactly three expected
`ModuleNotFoundError: No module named 'app.execution_core'` errors (`test_values`, deterministic
fill/position, and stateful fill/position). No production runtime, broker, database, or I/O path
executed; collection stopped before `app.execution_core` could import.

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
the now-coherent human-authority mutation fixtures. No production runtime, broker, database, or I/O
path executed; the selected tests exercised only the pure `app.execution_core` kernel in-process.

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
all 135 tests with fresh basetemp `.pytest_tmp_wo0145_post_mutation_focused_1`; no mutant remained.

#### Reproducible required mutation matrix

The earlier summary is superseded for reproducibility by the exact matrix below. Every row used
`BROKER_ADAPTER=mock`, `-q --tb=line -p no:cacheprovider`, the exact node shown, and the exact fresh
basetemp shown. After the recorded exit-1 failure, the literal edit was inverse-patched and the same
node was rerun at the `_restored` basetemp with exit 0. No database, broker, runtime, or I/O path ran.

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
Only the pure kernel ran in-process; no runtime, broker, database, or I/O path executed.

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
  decisive_output: "Ruff clean; 9 files formatted; mypy clean over 82 files; 6 contracts kept and 0 broken; all AI-OS checks and contamination guard passed."
```

```yaml
evidence:
  phase: FULL_SUITE
  command: ".\\.venv\\Scripts\\python.exe -m pytest -q tests/r2_conformance_oracle.py; .\\.venv\\Scripts\\python.exe -m pytest --cov=app --cov-branch --cov-report=term-missing"
  result: BLOCKED
  decisive_output: "Static inspection established that both gates instantiate SQLite; current authority still excludes database execution."
```

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
      evidence: "The post-matrix exact tree passed all 154 focused tests."
    - item: "Every required mutation pin is demonstrated failure-capable and restored green with durable evidence."
      status: MET
      evidence: "The exact 33-row matrix records every live edit, node, exit-1 assertion, inverse edit, and restored exit-0 result; one equivalent survivor was disclosed and simplified."
    - item: "Repository-wide static gates pass on the exact current tree."
      status: MET
      evidence: "Repository Ruff, mypy, six import contracts, all applicable AI-OS checks, scope, and contamination guard passed after the matrix."
    - item: "R2 and full branch-coverage suites pass."
      status: BLOCKED
      evidence: "Those gates instantiate SQLite and database execution remains excluded."
    - item: "Python 3.11 and Python 3.12 CI pass on the exact head."
      status: BLOCKED
      evidence: "Local Python 3.11 is unavailable and pushing would start excluded database-bearing CI."
    - item: "Independent exact-head review has no unresolved P0 or P1."
      status: NOT_MET
      evidence: "The latest review returned blocking P0 and P1 findings; re-review is pending."
    - item: "Allowed paths and all broker, credential, database, runtime, merge, deletion, and cleanup exclusions remain respected."
      status: MET
      evidence: "Scope review found the implementation diff exact and no excluded activity occurred."
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
  debt_check: "Open in-scope defects and unexecuted proof obligations are listed explicitly; none is waived."
  deferred:
    - "Database-bearing R2 and full-coverage validation pending separate explicit database-test authorization."
    - "Exact-head Python 3.11 and Python 3.12 branch CI pending separate push and CI authorization."
    - "Independent re-review pending third remediation and fresh verification."
  status: BLOCKED
```
