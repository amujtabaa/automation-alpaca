---
type: Review Result
rev_id: REV-0107
work_order_id: WO-0168d
reviewer_model: OpenAI Codex independent review seat
verdict: BLOCK
date: 2026-08-27
---

# REV-0107 — independent findings-only result

## Verdict and exact counts

**BLOCK.** The exact implementation candidate has **P0=0, P1=1, P2=0**. The checked-in
installer and central opener are closed and correctly ordered, but the required structural
failure control accepts an ordinary locally aliased `sqlite3.Connection` opener. REV-0107 requires
zero open P0/P1 before the separate DDL intent and human unlock gate.

- P0: **0**
- P1: **1**
- P2: **0**
- Separate out-of-model threat-class proposals: **0**

## Verified identities

- Repository: `https://github.com/amujtabaa/automation-alpaca.git`
- Branch: `codex/m2-wo0168d-hybrid-r1`
- Review-time `HEAD`: `adbb8d85a0ffbbe294a4f4e1b4358e6f7df442eb`, tree
  `759a4356b62388d35ae43e0daffc2ee3c2934864`
- Work-order planning base: `81c65a09fbdd3d67a4a46ccd1d22f3c9b395353a`, tree
  `7dfed0cb0dd68add1ca36704766ccfd7a65bff61`
- REV-0106 terminal record head: `f0a6121908d8cfadeeb9de6ff2d5f4d94238f6ec`, tree
  `b2c596ce5179305fba26ac093197de1be1ba9119`
- Implementation candidate: `5cf52a846dcd34aaf6cae2d0f1338014ceabd536`, tree
  `68e2fb928f04732bdb03eaf996df8a3bdab2d177`
- Both requested ranges and ancestry were verified:
  `81c65a09fbdd3d67a4a46ccd1d22f3c9b395353a..5cf52a846dcd34aaf6cae2d0f1338014ceabd536`
  and
  `f0a6121908d8cfadeeb9de6ff2d5f4d94238f6ec..5cf52a846dcd34aaf6cae2d0f1338014ceabd536`.
- The candidate is the direct parent of review-time `HEAD`. Candidate-to-HEAD tracked drift is only
  `work/ledger.jsonl` and `work/review/REV-0107/request.md`; there is no candidate-to-HEAD
  implementation, test, ADR, or AI-OS drift.
- Candidate SHA-256 identities reproduced exactly:
  - `app/execution_core/persistence/schema.py`:
    `5dc9fcbed9a60f0b39772093ac7842877a72dd9190de6df2fd579bb384b1d814`
  - `tests/execution_core/approved_schema_digest.py`:
    `d88ba91c3c1d935ec2957d68eb4d3927a10865e40a9bf53a3ca1cb0384ac1e26`
  - `tests/execution_core/test_sqlite_boundary.py`:
    `c62d9a0c8d3917090d7efe17ebecb4fd1e2f24b758589af961f1e47c2d9dbe93`
  - `docs/adr/ADR-026-interim-ddl-gate-threat-model.md`:
    `3782009e924625a0c3fb18ca3f86c2feaa5796a1d4bd9b1462faa8645bf83763`
  - `work/active/WO-0168d-m2-i3-5-hybrid-gate-simplification.md`:
    `72a9f1c9d503097bd0af79e9b00f484c2f5a71dacacf0464b2eaa82b51f3a456`
- Static AST extraction, without importing or executing `schema.py`, reproduced `SCHEMA_DDL` as
  178,755 UTF-8 bytes with SHA-256
  `2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5`.
  Those bytes are identical at the planning base and candidate. The candidate schema Git blob is
  `ef332a0b97d28e0535ac53ea0e4d4e091991abad`, and
  `DDL_EXECUTION_AUTHORIZED_BY_AMEEN` is the exact boolean `False`.

## Findings

### [P1] Executable `Connection` aliases evade both structural opener controls

- Location: `tests/execution_core/test_sqlite_boundary.py:90`,
  `tests/execution_core/test_sqlite_boundary.py:97`,
  `tests/execution_core/test_sqlite_boundary.py:140`, and
  `tests/execution_core/test_sqlite_boundary.py:147`
- Requirement: REV-0107 requires the structural controls to kill ordinary import aliases, direct
  `Connection(...)`, and an extra helper-module opener. WO-0168d items 2–3 and ADR-026 section 2
  require the central helper to remain the sole ordinary opener and require held suites and
  production persistence modules to contain no other ordinary direct connection capability.
- Evidence: **reproduced-live, static/no-I/O.** Three parsed source mutations were never executed:
  1. Appending `Connection = sqlite3.Connection` plus
     `def bypass_connection(database): return Connection(database)` to the real helper-module
     source made `_approved_connection_helper_is_exact(...)` return `True`; the lexical control
     also returned `()`.
  2. Appending the same two lines to the real
     `tests_gated/execution_core/test_persistence_repository.py` source made
     `_direct_connection_capability_violations(..., allow_sqlite_import=True)` and the lexical
     control both return `()`.
  3. Appending `from sqlite3.dbapi2 import Connection` plus the same direct
     `Connection(database)` opener to the real production repository source made
     `_direct_connection_capability_violations(..., allow_sqlite_import=False)` and the lexical
     control both return `()`.
  The detector recognizes only `ImportFrom` whose module is exactly `sqlite3`, any `.connect`
  attribute, and a call whose callee is directly an attribute named `Connection`. It does not
  recognize an executable `sqlite3.Connection` reference assigned to a local name followed by a
  direct name call, and the helper exactness check has the same gap. The whole-file lexical
  allowlist is intentionally non-semantic, so it supplies no fallback.
- Impact: A plain, non-reflective edit can add a second helper-module or held-suite opener that
  constructs a SQLite connection before the human gate while every named boundary test remains
  green. The production submodule form also violates the no-SQLite-import rule while passing the
  same controls. No such bypass exists in the checked-in candidate, so this is a P1
  failure-capability blocker rather than a P0 current execution/safety violation.
- Resolution: Extend the bounded structural rule to reject executable, non-annotation
  `sqlite3.Connection` references and direct calls through their ordinary local bindings, and
  recognize ordinary `sqlite3` submodule imports. Apply the same finite rule to the helper,
  held-suite, and production checks. Add canaries using the locally aliased constructor plus an
  extra opener and the `sqlite3.dbapi2` direct-import form; no general Python dataflow or
  reflection model is needed.

## Commands and evidence actually run

- Read the required authority in order: `AGENTS.md`, the `CLAUDE.md` safety core, WO-0168d,
  ADR-026, gate Amendments 7–10, REV-0106 `result.md`, `result-r2.md`, and `disposition.md`, then
  candidate source/tests, both Git ranges, and the changed AI-OS review/scope rules.
- Git identity/history: remote URL, branch, commit/tree/parent inspection, three ancestry checks,
  both requested range diffs, candidate-to-HEAD drift, full-range scope, and `git diff --check`.
- Static candidate-object probe: recomputed all five requested SHA-256 values, schema blob, DDL
  bytes/digest, expected digest, and exact false authorization flag. A separate base/candidate AST
  comparison proved byte-identical DDL, unchanged `install_schema` signature, unchanged `__all__`,
  inert standard-library-only imports, and no top-level expression call.
- Focused no-I/O boundary suite:
  `python -B -m pytest -p no:cacheprovider -q tests/execution_core/test_sqlite_boundary.py` ->
  **14 passed**, exit 0.
- Installer no-I/O probe: a stand-in whose `__getattribute__` records and rejects every connection
  access was supplied through positional-connection, keyword-connection, matching-known-digest,
  non-string-digest, and invalid positional-digest call shapes. Valid calls raised the closed-gate
  `SchemaInstallError`, the invalid positional shape raised `TypeError`, and every probe recorded
  `touches=[]`.
- Held-suite source inventory: parsed all four files without importing them. Seven checked-in
  connection-opening call sites were found, all targeting `open_approved_sqlite_connection`; no
  direct `.connect`, called `.Connection`, direct imported `connect`/`Connection`, or name-called
  `connect`/`Connection` exists in the candidate held files.
- Required mutation probes: conditional gate placement, module-alias `.connect`, direct imported
  `connect`, direct imported `Connection`, extra direct `.connect` helper opener, direct
  `sqlite3.Connection(...)` helper opener, and count-preserving production drift were rejected.
  The local-constructor-alias and SQLite-submodule mutations documented in the finding were
  accepted.
- Focused inherited-baseline regression evidence: the two changed line-event tests in
  `test_fill_position.py` both passed, exit 0.
- Ruff check and format check passed on the six successor Python files. AI-OS install, version,
  ledger, PKL, and disposition checks passed. The work-order scope checker passed for both the
  exact candidate range and the full base-to-HEAD range.
- Static quarantine checks confirmed `testpaths = ["tests"]`, no `__init__.py` under
  `tests_gated`, no symlink in that tree, and regular Git blobs for its five files.
- Budgets reproduced: boundary plus gate = **376** nonblank/noncomment lines; work order =
  **218** lines. The scanner kernel is 194 lines and the 11,849-line scanner body is deleted.

## Explicit NOT_RUN / not verified

- Nothing under `tests_gated/` was imported, collected, or executed.
- No SQLite connection or database (file or in-memory) was created; no DDL, schema installation,
  migration, catalog computation, or later work-order implementation ran; the human flag was not
  changed or monkeypatched `True`.
- Full-repository pytest, the conformance oracle, and the full ordinary `tests/execution_core`
  suite were NOT_RUN. Evidence was limited to the permitted 14-test no-I/O boundary suite and two
  selected ordinary line-event tests.
- Mypy and import-linter were NOT_RUN. Their author-reported results were not treated as reviewer
  evidence.
- GitHub branch-protection settings and live CODEOWNERS enforcement were not remotely verified.

## Disproof pass

- **Tentative installer P0:** did not survive. The candidate computes the actual DDL digest, checks
  the application-owned false human authorization and expected identity, then checks the caller
  digest before connection inspection. Every ordinary no-I/O call-shape probe recorded zero
  connection touches. The DDL bytes and installer public shape are unchanged.
- **Prior conditional-gate defect:** did not survive. The helper exactness rule requires two exact
  executable statements and rejected the conditional-gate mutant.
- **Prior count-preserving-drift defect:** did not survive in its reproduced form. Lexical
  allowlisting made no semantic claim, while the production structural check rejected an ordinary
  added `import sqlite3` plus `sqlite3.connect(...)` despite preserved token count.
- **Current held-suite routing concern:** no checked-in bypass survived static inventory; all seven
  opener sites use the central helper. This disproves a current P0 but does not cure a required
  control that accepts an in-model future mutant.
- **P1 alias finding:** survives. The accepted mutations use no dynamic name construction,
  reflection, hostile host action, or arbitrary-language proof claim. They are ordinary assignments
  or imports followed by direct `Connection(...)`, expressly inside REV-0107's required mutation
  lens. Both the semantic and lexical controls returned clean results on the real-file mutations.
- Bottom-up reinspection found no additional scope, DDL, safety-invariant, collection, governance,
  budget, or inherited-test regression finding.

Verdict: **BLOCK**

P0: **0**

P1: **1**

P2: **0**

Unverified: held suites; any SQLite/DDL/database/migration execution; full repository and full
ordinary execution-core suites; conformance; mypy; import-linter; remote branch protection and
CODEOWNERS enforcement.

[DONE] STATUS: VERIFIED
