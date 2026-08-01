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

`[FABLE • FULL • verification: DIRECT + independent review • task: pure execution-fact kernel]`

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
    - "Accepted ADR-020/021 and the staged RESET-WO-01 uniquely require first-occurrence fill-family quantity truth, linked root replacement, pending non-tail basis, and exact negative overfill quarantine."
    - "Python 3.11 compatibility is enforced by mypy's 3.11 target and real 3.11 CI; local development is Python 3.12."
    - "The incumbent application and SQLite/event paths remain frozen evidence, not dependencies."
  approach: "Red-first immutable value/fact tests, named mutation pins, a test-owned exact arithmetic oracle, then the minimum pure implementation and stateful verification."
  out_of_scope: ["I/O or persistence", "broker/venue behavior", "human-attested ingestion", "status/retry/release/protection/serving", "runtime integration"]
  done_when: "Focused and full gates pass on Python 3.11/3.12, scope is exact, and an independent reviewer leaves no P0/P1."
  blast_radius: "New app.execution_core package and its isolated tests; no incumbent runtime consumer or schema."
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
fill/position, and stateful fill/position). No application, database, or broker code executed.

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
the now-coherent human-authority mutation fixtures. No production, broker, database, or runtime code
executed in this RED gate.

## Review, stop, and close-out

Stop if authority conflicts, representation needs adapter/persistence/query/recovery policy, exact
ordered folding is not determined, an implicit conversion is needed, either interpreter gate is
red/unavailable, incumbent store/event code is needed, or two P0/three same-root P1 findings emerge.

Completion requires exact scope, every mutation pin demonstrated failure-capable, focused/full
dual-version green evidence, no incumbent runtime/schema change, and independent blind review with
no unresolved P0/P1. Then move this WO to `work/completed/keep/`, append exactly one ledger row, and
record PKL impact in the same commit. No self-acceptance and no merge.
