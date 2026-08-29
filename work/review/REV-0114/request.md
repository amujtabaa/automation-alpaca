---
type: Review Request
rev_id: REV-0114
work_order_id: WO-0168
status: AWAITING_REVIEW
review_mode: fresh-context findings-only static changed-DDL review
date: 2026-08-29
allowed_paths:
  - work/review/REV-0114/result.md
forbidden_paths:
  - app/**
  - tests/**
  - tests_gated/**
  - work/review/REV-0114/request.md
  - work/review/REV-0114/ddl-static-manifest.md
---

# REV-0114 — WO-0168 consolidated changed-DDL static review

## Boundary

Use a fresh context and re-derive the candidate from the exact diff and governing contract. Produce
findings only. Do not fix, commit, push, or edit the request or manifest. The reviewer response
belongs in `result.md`.

This is a **static-only** review. Do not import or invoke `sqlite3`, connect to SQLite, create any
database, install DDL, collect or execute anything under `tests_gated/`, migrate, unlock the human
flag, implement a later work order, promote, or merge. Permitted evidence is source/contract proof,
Git object inspection, hashing, Python compilation, literal/AST extraction without connection
access, and no-I/O pure checks.

## Exact identities — verify, do not trust

- Repository: `https://github.com/amujtabaa/automation-alpaca.git`.
- Branch: `codex/m2-wo0168-atomic-uow-r1`.
- Human-authorized source parent:
  `bedb1105fc7165da799c3fd025f3291af8bb69cd`, tree
  `6c15f5420b873e746753ae0783131a00e45532c2`.
- Source candidate: `b7bf7d2d4f5356a3977fd68cc1dc6cfcdf0dbaae`, tree
  `3c1eab6ad18c6865e9cbf4e5b33dd343bd3b036c`.
- Candidate parent is exactly the human-authorized source parent above.
- Review diff: `bedb1105fc7165da799c3fd025f3291af8bb69cd..b7bf7d2d4f5356a3977fd68cc1dc6cfcdf0dbaae`.
- `SCHEMA_DDL`: 190,705 UTF-8 bytes at SHA-256
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`.
- `EXPECTED_EXECUTION_DDL_SHA256` equals that digest.
- `DDL_EXECUTION_AUTHORIZED_BY_AMEEN`: exact boolean `False`.
- `schema.py` blob: `164de10ad9fef6ce37324840aff59b5b68c07d2a`; file SHA-256
  `cde0e1e33b7c78e22a854c192ea4b3b83d64c5d11dd538b3ccf23a6e234dc60d`.
- Held WO-0168 test blob: `6057cc263677735201ad8e59105444c796e0613f`; file SHA-256
  `05a9b10e691a9979902d0ea939819326dcb4c3da96dbfe6cce923936c4f8fd5f`.
- Active WO-0168 blob: `01bdd2eac20379e6b586ab5298d72daadbd48a59`; file SHA-256
  `01361d218bc37f4b01a54825875d4424ddc9661b7a0e7e0e9a437fc0916bbdf3`.
- Static manifest blob: `de8a49dc34df7c990d1b983db0681172f21b19f7`; SHA-256
  `c855b1ee04c6c4a60bdfb25123dba66677161123b1650feb3d75bbbed3ceec41`.
- Static DDL inventory: 28 tables, 30 indexes, 152 triggers, zero views; the fixed splitter
  returns 210 complete statements.

Any commit after the source candidate is packet-hosting governance only. Review the exact source
candidate above, not an inferred branch `HEAD`.

## Changed paths in the review diff

- `app/execution_core/persistence/schema.py`
- `tests_gated/execution_core/test_persistence_unit_of_work_sqlite.py`
- `work/active/WO-0168-m2-i4-atomic-unit-of-work-effects.md`
- `work/review/REV-0114/ddl-static-manifest.md`

## Human authority

Ameen Mujtabaa authorized one bounded changed-DDL remediation from the exact source parent. It may
implement only the consolidated schema corrections in active WO-0168, update the expected digest
while keeping the human flag exactly `False`, complete directly necessary held tests and compact
governance, and obtain this fresh static review with zero open P0/P1. No SQLite connection,
database creation, DDL installation, held-suite execution, migration, later work order, promotion,
or merge is authorized.

## Contract to re-derive

1. **One immutable owner, at most one exact route.** `acquisition_root_route` references the
   root-independent exact owner key. A rootless owner may acquire one route; a prebound owner may
   route only to that same root; a second route for the exact owner key is refused. The route-to-
   root foreign key remains exact.
2. **Dormant admission is flat-only.** NORMAL effect and claim admission may use dormant protection
   only with a `CONSISTENT`, zero-quantity controller, exact controller head and protection version,
   and all six active stream coordinates `NULL`. Active NORMAL and HARD_BAIL behavior remains
   unchanged; positive, negative, and stale dormant admission remains refused.
3. **First positive activation is exact and one-way.** A NORMAL all-null to all-non-null protection
   activation may occur with positive quantity only for a `CONSISTENT` controller, its exact live
   acquisition generation, and exact head. Positive active-to-active transfer and active-to-
   dormant release remain refused; quarantined and negative activation remain refused; flat
   `CONSISTENT` transfer/release remains accepted under ADR-021.
4. **One late owner, one immediate advance.** The late-owner trigger advances controller head and
   version immediately. INVALIDATION skips its own controller advance only when it exactly names
   that retained late owner. Ordinary invalidation still advances.
5. **Catch-up requires complete exact evidence.** NORMAL protection may catch up at the exact final
   `UNRESOLVED_VENUE_QUARANTINED` head only with unchanged authority class and all six stream
   coordinates, at least one exact late-owner INVALIDATION against an INVALIDATED effect, and no
   retained late owner in that scope lacking its own exact matching evidence. INSERT, stale-head,
   transfer, and every other quarantine class remain closed.

## Threat model and required review probes

Treat malformed but foreign-key-valid rows, stale versions/heads, same-scope cross-owner evidence,
prior evidence reused after a later owner, and partial predicate removal as in-model. For each
contract item:

1. Trace every child/parent key and guard predicate and identify any route that permits the wrong
   root, a second root, a positive/negative dormant effect, stale admission, positive transfer,
   double controller advance, skipped ordinary advance, or catch-up with outstanding evidence.
2. Map the staged held controls to the exact predicates. A control is adequate only if removing or
   broadening the load-bearing predicate would make its assertion fail for the intended reason.
3. Check the first-activation exception does not become a general nonflat-transfer exception and
   does not weaken the separate exact-current-controller trigger.
4. Check the invalidation skip uses the exact effect/owner/observation identity and that older
   evidence cannot authorize catch-up after a newer late owner advances the head.
5. Check the new parent foreign key has an exact SQLite-valid unique parent key and that the new
   partial index supports the late-owner scope/evidence predicates without changing query
   semantics.
6. Verify no source/test/governance drift beyond the four paths, no flag-true value, and no claim
   that static review proves executable SQLite semantics.

No `INV-*` identifier is added or amended by this candidate. The five scenarios above are the
fresh probes for the newly frozen WO-0168 relational contract.

## Author evidence — reproduce only when allowed

- Full pure suite (held tests excluded by location): 1,985 collected, reached 100%, exit 0.
- Focused pure tests: 107 passed across SQLite boundary fakes, import boundary, and UOW tests.
- Ruff check and format check: clean on changed Python files.
- mypy: success across 96 application files.
- Import Linter: 6 contracts kept, 0 broken.
- Install, version, ledger, PKL, disposition, work-order scope, compilation, digest/flag,
  statement-splitting, and `git diff --check`: passed.
- `tests_gated/**`: **NOT COLLECTED / NOT RUN**.
- SQLite/database/DDL execution: **NOT RUN**.

## Finite stop rule

This is one fresh review round. A P0/P1 must cite a contract clause or demonstrate a concrete
in-model bypass, non-failing control, regression, scope violation, or safety/data-integrity defect.
Style, alternate-design preference, speculative scale concerns, and out-of-model threats are P2/P3
or proposals, not blockers. If a confirmed P0/P1 is returned, the implementation seat may apply
one root remediation and request one correction-only verification; do not broaden the review into
an architectural redesign. `ACCEPT` requires zero open P0/P1.

## Response contract

For each finding provide priority, exact `file:line`, governing clause, evidence level, concrete
impact, smallest complete root resolution, and a disproof pass. End exactly with:

```text
Verdict: BLOCK | ACCEPT-WITH-CHANGES | ACCEPT
P0: <count>
P1: <count>
P2: <count>
Unverified: <items or none>
```

State explicitly that no SQLite/database/DDL/held-suite execution occurred.
