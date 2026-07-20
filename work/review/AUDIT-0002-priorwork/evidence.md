# AUDIT-0002 evidence

All commands below ran locally on Windows from
`C:\Users\amujt\dev\automation-alpaca`. No Alpaca credential was loaded, no
broker adapter was opened, and no repository-root pytest scratch directory was
created.

## E-01 — anchor and environment gate

```text
git rev-parse HEAD
9add18946380a0dab333263a19549d69c408a552

git diff --name-only 88833e3d..master -- app tests cockpit
<empty>

ALPACA_PAPER_API_KEY=ABSENT
ALPACA_PAPER_API_SECRET=ABSENT
APCA_API_KEY_ID=ABSENT
APCA_API_SECRET_KEY=ABSENT
```

```text
.venv\Scripts\ruff.exe check .
All checks passed!

.venv\Scripts\mypy.exe app/
Success: no issues found in 64 source files

.venv\Scripts\lint-imports.exe
Contracts: 6 kept, 0 broken

.venv\Scripts\python.exe -m pytest --collect-only -p no:cacheprovider
3873 tests collected in 2.03s

.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
[100%]
exit 0; 11 skipped; 1 xfailed; no FAILED/ERROR; 403.4s
```

Pytest used its normal OS-temporary base. The initial sandboxed attempt could
not scan the pre-existing Windows temp root (`WinError 5`); the same command was
re-run with access to OS temp and `-p no:cacheprovider`. No repo-local
`.pytest-tmp-*` directory was used.

## E-02 — closed-WO and ADR/invariant claim-link inventory

Command:

```text
.venv\Scripts\python.exe work/review/AUDIT-0002-priorwork/probe_claim_links.py
```

Decisive output:

```text
collection: 3873 tests collected in 1.95s
collected_node_count: 3873

ADR-001..ADR-009:
  missing_files=[] for every ADR
  uncollected_refs=[] for every ADR

INV-001..INV-089 (defined IDs):
  missing_files=[] for every explicit tests/... reference
  uncollected_refs=[] for every explicit tests/... reference
  zero explicit test paths: INV-051, INV-052, INV-074

INV-074 manual reconciliation:
  tests/test_import_boundaries.py:79 defines test_all_import_contracts_hold

35 physical completed-WO artifacts in the WO-0001..WO-0035 window:
  missing_files=[] for every explicit tests/... reference
  uncollected_refs=[] for every explicit tests/... reference
```

The zero-ref cases are materially different: INV-074 names a real test and
contract without repeating the path; INV-051 explicitly says it has no
dedicated test, and INV-052 says it is structural.

The same inventory found fourteen work-order records physically under
`work/completed/keep/` whose front matter is still draft/noncanonical (thirteen
with an empty disposition; WO-0030 has a disposition but noncanonical status):

```text
WO-0016 DRAFT                    disposition=[]
WO-0017 DRAFT                    disposition=[]
WO-0018 DRAFT                    disposition=[]
WO-0019 DRAFT                    disposition=[]
WO-0019a DRAFT-awaiting-gate     disposition=[]
WO-0020 DRAFT                    disposition=[]
WO-0021 DRAFT                    disposition=[]
WO-0024 DRAFT-awaiting-gate      disposition=[]
WO-0025 DRAFT-awaiting-gate      disposition=[]
WO-0026 DRAFT-awaiting-gate      disposition=[]
WO-0027 DRAFT-awaiting-gate      disposition=[]
WO-0028 DRAFT-recommended-first  disposition=[]
WO-0030 APPROVED-DONE            disposition=[RESULT_SUMMARY_KEPT]
WO-0031 APPROVED                 disposition=[]
```

The append-only ledger says `DISPOSED` for each of these IDs. The current
checker nevertheless returns green because it only evaluates four recognized
front-matter statuses:

```text
.venv\Scripts\python.exe .ai-os/scripts/check_work_order_disposition.py
DISPOSITION CHECK PASSED
```

## E-03 — fresh dual-store invariant probes

Command:

```text
.venv\Scripts\python.exe work/review/AUDIT-0002-priorwork/fresh_invariant_probes.py
```

Output, identical for memory and SQLite unless noted:

```text
INV-003/004 fill identity:
  statuses=[appended, duplicate, conflict]
  fill_rows=1; position_quantity=100; average_price=1.25
INV-025 same-status no-op:
  status=pending; new_events=0
INV-060 kill switch:
  OrderIntentBlockedError; orders_created=0
INV-061 strict bool:
  InvalidControlValueError; kill_switch=false
INV-087 one ACTIVE envelope per symbol:
  EnvelopeTransitionError; active_count=1
INV-089 valid fill price:
  InvalidFillError for NaN; remaining_quantity=100
INV-051/052 structural sample:
  app/store/memory.py awaits nested under async-with self._lock: []
  app/store/sqlite.py awaits nested under async-with self._lock: []
```

The structural sample supports the current implementation, but it is not a
maintained, failure-capable repository pin for INV-051/052.

## E-04 — runtime-only mutation checks

The packet plugin monkey-patches imported objects in a one-shot pytest process;
it edits no source or test file.

```text
run_mutation.py wo0007b_latest_wins \
  tests/test_wo0007b_stageb_projector.py::test_release_projects_created_not_submitting

FAILED: expected CREATED, got SUBMITTING
exit 1
```

```text
run_mutation.py wo0026_reduce_only \
  tests/test_rev0023_phase_a_pins.py::test_PIN_F1_sell_against_zero_position_never_reaches_venue[memory]

FAILED: expected outcome divergence, got blocked
exit 1
```

```text
run_mutation.py wo0032_all_memory_symbol_guards \
  tests/test_wo0032_per_symbol_mandate.py::test_second_active_envelope_same_symbol_is_refused[memory]

FAILED: DID NOT RAISE EnvelopeTransitionError
exit 1
```

Negative control: removing only
`_other_active_envelope_for_symbol_unlocked` leaves the WO-0032 pin green,
because the independent foreign-obligation projection still enforces the same
observable property. Removing both enforcement routes turns the exact pin red.

## E-05 — Tier-3 branch and queue topology

```text
git rev-parse origin/archive/claude-wo-0001-install-checks-2x5ys8
fc819517be64b10ecf831a9a6abd4fe6f9100e2f

git rev-list --count master..origin/archive/claude-wo-0001-install-checks-2x5ys8
47

git merge-base --is-ancestor origin/archive/claude-wo-0001-install-checks-2x5ys8 master
exit 1

rg SignalRecord|SignalProposal|SIGNAL_RECEIVED|routes_signals|signal_seat_enabled app cockpit tests .importlinter
NO_SIGNAL_IMPLEMENTATION_HITS
```

The archive line differs from master by 60 files, 8,556 insertions and 168
deletions, including the signal route, dual-store/event implementation, auth
boundary, launcher, tests, ADR/spec updates, and review packets. Therefore its
WO-0102 completion does not satisfy WO-0103/0104's dependency on current
master.

```text
git rev-parse origin/archive/collab-sol-0001
38180e1d594a961372b5854bfac9f097ac6910b1

git rev-list --count master..origin/archive/collab-sol-0001
1
```

The original five deliverables were re-landed by master commit `9c151eb`:
`MANIFEST.md`, `findings.md`, `sol_conformance_plugin.py`, and
`test_sol_policy.py` have byte-identical blob IDs; `sol_policy.py` is present
with the two-line post-intake amendment. This archive line is retained
provenance, not lost implementation.

## E-06 — Tier-4 mechanical inventory

Command:

```text
.venv\Scripts\python.exe work/review/AUDIT-0002-priorwork/probe_review_integrity.py
```

Decisive output across 25 `REV-*` directories and 13 standalone findings:

```text
REV-0019:
  result.md verdict=ACCEPT
  disposition.md verdict_received=ACCEPT-WITH-CHANGES
  disposition body contains an addendum explaining the overwritten result

REV-0023:
  result.md=yes; disposition.md=yes; request.md=no

REV-0024:
  request.md=yes; SUPERSEDED.md=yes; no result/disposition expected by marker

REV-0029:
  result.md=BLOCK; result-round2.md=BLOCK
  disposition.md title=IN PROGRESS
  no final round-2 disposition/supersession marker

REV-0030:
  result.md=ACCEPT; disposition.md=no; supersession marker=no
```

Nine standalone W3 finding files remain textually `Status: OPEN` even though
their named remediations landed: memory atomic rollback, multileg lifecycle,
redrive validation, reduce-only, refused-stale tranche latch, staged-order
preemption, supersession exposure, synthetic-fill bridge, and test integrity.
Two standalone findings are correctly `RESOLVED`; two are legitimately still
open/partially open (structural hold and grouped lifecycle/eventing debt).

## E-07 — scope proof before Lane-A commit

```text
git status --short
A  work/review/AUDIT-0002-priorwork/evidence.md
A  work/review/AUDIT-0002-priorwork/fresh_invariant_probes.py
A  work/review/AUDIT-0002-priorwork/mutation_plugin.py
A  work/review/AUDIT-0002-priorwork/probe_claim_links.py
A  work/review/AUDIT-0002-priorwork/probe_review_integrity.py
A  work/review/AUDIT-0002-priorwork/report.md
A  work/review/AUDIT-0002-priorwork/run_mutation.py

git diff --cached --stat
7 files changed, 1308 insertions(+)

git diff --cached --name-only
work/review/AUDIT-0002-priorwork/evidence.md
work/review/AUDIT-0002-priorwork/fresh_invariant_probes.py
work/review/AUDIT-0002-priorwork/mutation_plugin.py
work/review/AUDIT-0002-priorwork/probe_claim_links.py
work/review/AUDIT-0002-priorwork/probe_review_integrity.py
work/review/AUDIT-0002-priorwork/report.md
work/review/AUDIT-0002-priorwork/run_mutation.py

git diff --cached --name-only |
  .venv\Scripts\python.exe .ai-os\scripts\check_work_order_scope.py \
  work\queue\WO-0117-prior-work-audit-charter.md
SCOPE CHECK PASSED
```

No `app/**`, `tests/**`, `docs/**`, `pkl/**`, queue, active, workflow, or
AI-OS implementation file was edited by Lane A.

Final non-mutated spot-check after the mutation processes exited:

```text
pytest -q -p no:cacheprovider <WO-0007b node> <WO-0026 node> <WO-0032 node>
..... [100%]
5 passed
```
