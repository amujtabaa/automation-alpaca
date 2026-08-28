---
type: Work Order
title: M2-I3.5 hybrid gate simplification and suite restoration
status: REVIEW
work_order_id: WO-0168d
wave: M2-I3.5-R13-C-HYBRID
model_tier: strong
risk: critical
disposition: []
owner: Codex implementation seat; one fresh-context reviewer (REV-0106)
created: 2026-08-26
predecessor: WO-0168c superseded 2026-08-26 after REV-0105 BLOCK and ratified root simplification
branch: codex/m2-wo0168d-hybrid-r1
implementation_review_id: REV-0106
execution_authority: >
  Ameen Mujtabaa, 2026-08-26, in session, verbatim: "Ratified: hybrid points 1-10; scanner
  deletion approved; prohibition re-scoped per point 5. If there are any additional adjustments
  from the latest response you can integrate those too." The ratified plan is the hybrid in
  work/review/CONSULT-0001-wo0168c-architecture/memo-comparison.md plus the adjustments in this
  work order (expected-digest lifecycle, human unlock flag, two-tier quality standard,
  live-readiness checklist, meta-code tripwire). This grants ordinary reversible work inside the
  allowed paths, INCLUDING the human-gated deletion of the scanner body named in Scope 2. It does
  NOT authorize changed-DDL execution, running the relocated held suites, database creation in
  this lane, in-memory databases, migration, runtime composition, credentials, network, broker
  calls, orders, promotion, or merge to master.
  On 2026-08-27 Ameen additionally approved the four Codex handoff corrections: broaden the
  evidence-capable review contract, bind the unlock commit exactly, scope and independently
  review Core 20, and continue on a fresh branch in the main repository checkout.
  On 2026-08-27 Ameen further authorized, verbatim: "I authorize the bounded REV-0106-F1
  remediation of the application-side schema installer and supporting gate tests/governance
  records. The human authorization flag must be enforced before connection access. No DDL-byte
  change, held-suite execution, database creation, migration, or later work-order implementation
  is authorized. Obtain fresh exact-head review with zero open P0/P1 before proceeding to the
  separate DDL execution gate."
allowed_paths:
  - app/execution_core/persistence/schema.py
  - work/active/WO-0168d-m2-i3-5-hybrid-gate-simplification.md
  - work/completed/keep/WO-0168d-m2-i3-5-hybrid-gate-simplification.md
  - work/completed/keep/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md
  - work/ledger.jsonl
  - work/review/REV-0106/**
  - work/review/CONSULT-0001-wo0168c-architecture/**
  - work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md
  - work/queue/M2-EXECUTION-2026-08-21/37-WO-0168D-HYBRID-KICKOFF.md
  - tests/execution_core/test_persistence_write_capability.py
  - tests/execution_core/approved_schema_digest.py
  - tests/execution_core/test_sqlite_boundary.py
  - tests/execution_core/test_fill_position.py
  - tests/execution_core/test_protection_stateful.py
  - tests/execution_core/test_persistence_schema.py
  - tests/execution_core/test_persistence_repository.py
  - tests/execution_core/test_persistence_directness.py
  - tests/execution_core/test_persistence_runtime_checkpoint_sqlite.py
  - tests_gated/**
  - pyproject.toml
  - .github/CODEOWNERS
  - docs/LIVE_READINESS.md
  - docs/adr/ADR-026-interim-ddl-gate-threat-model.md
  - .ai-os/core/00_START_HERE.md
  - .ai-os/core/03_IN_USE_STRUCTURE.md
  - .ai-os/core/15_CROSS_MODEL_REVIEW.md
  - .ai-os/core/19_AUTONOMY_AND_ESCALATION.md
  - .ai-os/core/20_ASSURANCE_PROPORTIONALITY.md
  - .ai-os/templates/review-request.md
---

# Work Order: WO-0168d — hybrid gate simplification and suite restoration

`[FABLE • FULL • root-cause • smallest adequate mechanism • no DDL execution]`

## Why (one paragraph)

REV-0079…REV-0105 (27 packets, ~2 days) tried to prove, by static analysis, that no Python in 49
files could reach SQLite by any route. That claim is unbounded (arbitrary-Python semantics) and
review correctly kept refuting it — P0 counts rose 6→5→7 while pytest itself became NOT_RUN. Two
independent blinded consultations agreed on the root cause and on replacement. The load-bearing
protection was always the tiny runtime pair: a fail-closed pre-open fixture gate and an installer
that refuses before connection access. REV-0106 proved the installer checked only digest identity,
not authorization; Ameen authorized moving that same flag to the sensitive application boundary.
This order keeps the bounded pair, deletes the scanner, restores pytest, and makes review terminate.

## Ratified prohibition re-scope (point 5) — the interim rule from now on

PERMITTED again in this lane: importing project modules and `sqlite3` (imports do no I/O; root
`conftest.py` has always imported the SQLite store), repo-wide pytest excluding `tests_gated/`,
ruff/mypy/lint-imports/conformance oracle, and source inspection. STILL FORBIDDEN until Ameen's
gate-day unlock: executing any `tests_gated/` suite, installing/executing changed DDL, creating
any database file or in-memory database in the execution_core lane, migrations, runtime
composition, credentials, network, broker calls, orders, promotion, merge to master.

## Scope of work (all items in this branch; close-out ships with the finishing commit)

1. **Scanner deletion (human-gated; approved in execution_authority above).** Reduce
   `test_persistence_write_capability.py` to its healthy kernel: the WO-0168a setup-issuer
   direction controls, the no-I/O `_Connection` stand-in, and the REV-0078 anti-self-approval AST
   control (`approved_ddl_sha256=schema_ddl_digest()` spelling refused). Delete both 49-file
   scanners, the provenance/topology/binding-state models, all `sys.settrace` machinery, and the
   embedded snippet corpus. The uncommitted successor WIP remains preserved, untouched, in the
   old `automation-alpaca-worktrees/codex-m2-wo0168c` checkout; this fresh branch starts from the
   committed scanner baseline and must not reset or modify that old worktree. Git history, frozen
   review commits, and the preserved old checkout remain the evidence record.
2. **Held-suite quarantine by relocation.** `git mv` the four held suites
   (`test_persistence_schema.py`, `test_persistence_repository.py`, `test_persistence_directness.py`,
   `test_persistence_runtime_checkpoint_sqlite.py`) to `tests_gated/execution_core/` — outside
   `testpaths = ["tests"]`, no `__init__.py`, no symlinks. Fix their imports of
   `tests/execution_core` support modules (a small `tests_gated/execution_core/conftest.py` that
   extends `sys.path` is acceptable). Every installing fixture keeps calling the gate accessor as
   its first statement. Every helper or fixture that directly opens a connection calls the gate
   before any other call, so even a direct `pytest tests_gated/...` invocation refuses before a
   connection object exists.
3. **Boundary layer (new `tests/execution_core/test_sqlite_boundary.py`, ≤400 SLOC total for
   this item plus item 4).**
   (a) Lexical rule: outside an explicit justified allowlist, no file under `app/execution_core/`,
   `tests/execution_core/`, or `tests_gated/` may contain the tokens `sqlite3`, `app.store`, or
   `SqliteStateStore`. (b) AST pins: each `tests_gated` helper or fixture that directly opens a
   connection calls the gate accessor first; `install_schema` derives the digest, checks the
   application-owned human flag/expected identity, then checks the caller digest before connection
   access (source/AST proof only). (c) Canaries: disallowed tokens, ordinary aliases, added allowed-
   path occurrences, ungated fixtures, a closed application gate given the known digest, and a
   one-character digest mismatch all fail using no-I/O stand-ins.
4. **Gate lifecycle (ADEG §7.5 adaptation) at the installer boundary.** Rename
   `APPROVED_EXECUTION_DDL_SHA256` → `EXPECTED_EXECUTION_DDL_SHA256` and set it now to
   `2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5` (the identity assertion —
   reviewed with this candidate, NOT approval). `schema.py` owns that identity and
   `DDL_EXECUTION_AUTHORIZED_BY_AMEEN: Final[bool] = False`; `install_schema` enforces both before
   connection access. The pre-open test accessor reads the same facts and refuses while False.
   ONLY Ameen may authorize flipping the flag. The unlock commit must have the exact
   REV-0106-accepted head as its parent; its only source diff is the authorization flag changing
   `False` to `True`; and its message names the approved commands and attempt count. Before any
   execution, record the resulting unlock commit/tree and verify a clean worktree, local equals
   origin, and unchanged DDL digest, byte count, schema blob, and SQL-manifest identity. Agents
   never infer authorization from the expected digest or alter either constant without Ameen's
   explicit gate-day instruction. The DDL literal and caller-digest comparison stay unchanged.
5. **CODEOWNERS.** Create `.github/CODEOWNERS` assigning `@amujtabaa` to:
   `tests/execution_core/approved_schema_digest.py`, `tests/execution_core/test_sqlite_boundary.py`,
   `tests_gated/`, `app/execution_core/persistence/schema.py`, `.github/workflows/`, `.github/CODEOWNERS`.
6. **ADR-026 and scoped Core 20 governance** (`docs/adr/ADR-026-interim-ddl-gate-threat-model.md`,
   ≤2 pages, ships in the same
   commit): interim threat model (accidents and non-evasive agent mistakes in scope; deliberate
   evasion and host owner out of scope — such concerns are threat-class proposals routed to
   Ameen), the review stop rule below, the two-tier quality standard (live-grade invariants/data
   model now, paper-grade proof burden elsewhere, promotion via docs/LIVE_READINESS.md), and the
   meta-code tripwire. Narrow Core 20 and its routing text so it governs proportionate assurance
   design without suppressing evidence-backed contract, scope, regression, safety, or data-
   integrity findings. REV-0106 includes a separate governance lens for these `.ai-os` changes;
   Core 20 does not constrain findings about its own text. The ADR and project policy clear
   through the same packet, avoiding a second review bureaucracy.
7. **Verification.** Green: ruff, mypy, lint-imports, conformance oracle, and repo-wide pytest
   (which now excludes `tests_gated/` structurally) with the boundary suite passing, on this
   branch, evidence pasted. The four relocated suites are collected by nothing and run by nothing.

### In-flight inherited-baseline reconciliation

The first restored full-suite run reproduced ten failures against blobs identical to pre-work base
`d088758`: eight stale stateful replay fixtures still changed `evaluation_time` after the accepted
`d4bcf5c` contract bound it into occurrence identity, and two July performance caps predated M2's
accepted complete-node direct witnesses. Reconcile only those two test files: exact replay reuses
the exact occurrence, while changed delivery context remains a conflict in focused protection
tests; performance caps retain the non-linear-history kill and record 16/2,048/8,192 plateau
evidence. No product code or safety semantics change.

## Review contract (REV-0106) and stop rule

One fresh-context reviewer seat. Scope: the complete diff of this work order. The implementation
is judged against ADR-026's threat model; the Core 20/routing changes are judged independently
under `AGENTS.md` and doc 15, without using Core 20 to limit findings about itself. A P0/P1 may
block with reproducible evidence of any of: an unmet work-order acceptance criterion; scope or
authority violation; in-model boundary counterexample; a named control that cannot fail;
regression introduced by implementation or remediation; or product safety/data-integrity defect.
Concerns that require deliberate evasion outside ADR-026's threat model are recorded as threat-
class proposals for Ameen and do not block this interim gate. Maximum two rounds; round 2 examines
round-1 remediations and regressions caused by them. A round cap never forces acceptance: any
unresolved P0/P1 returns as an exact blocker and triggers re-diagnosis or human disposition.
`ACCEPT-WITH-CHANGES` may close this work order only when no P0/P1 remains; residual notes are P2
or explicitly accepted out-of-model risks. Product-code safety-invariant findings are never
capped by this rule.

## Budgets and tripwire

New boundary/gate code ≤400 SLOC; boundary checks complete in <60 s; this file stays ≤220 lines.
Standing tripwire: any proposal exceeding ~500 SLOC of meta-code (checkers of checkers, proof
machinery, provenance models) stops work and escalates to Ameen's decision queue instead of being
built. Exceeding a budget is a P1, not a reason to silently raise the budget.

## Done-when

1. Scope items 1–7 plus the bounded inherited-baseline reconciliation implemented with pasted
   evidence; old scanner WIP preserved in its prior
   worktree and absent from this fresh branch.
2. REV-0106 dispositioned ACCEPT or ACCEPT-WITH-CHANGES with zero unresolved P0/P1 findings.
3. Close-out ratchet in the finishing commit: status flip, disposition, ledger line, file move to
   `work/completed/keep/`, and gate-doc pointer refresh (35-WO-0168C-HUMAN-GATE-DDL.md).
4. Branch pushed; CI status reported honestly (known-red steps, if any, named with cause).

## Exclusions and precedence

No ADEG/EEP-1 external execution plane, Docker/VHDX/sandbox profiles, JSON record schemas,
attempt-slot state machines, or signatures — Ameen may promote these later via a new decision.
The DDL intent review and gate-day unlock are a separate human milestone, not this work order.
Queued M2/M3 work orders (WO-0168 i4, WO-0169, WO-0170, WO-0171, WO-0172) are unchanged; on any
conflict with the pre-2026-08-26 review regime, this work order and ADR-026 govern, and each
queued order is refreshed at activation. Frozen records (R1–R20 contracts, REV packets,
WO-0168c's amendment chain) are immutable evidence.

## Ameen's own task list (outside agent scope)

1. GitHub: enable branch protection on `master` requiring CI (needs GitHub Pro for a private
   repo) and CODEOWNERS review enforcement.
2. Schedule the DDL intent review (catalog/constraint level; the machinery binds exact bytes) —
   gate-day unlock happens only after it, via your one-line flag commit.
3. Optional: dispose stale `work/active/REMEDIATION-STATE.md` and `SIGNAL-R4-STATE.md` session
   files (both describe completed/dormant sessions).
