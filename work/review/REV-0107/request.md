---
type: Review Request
rev_id: REV-0107
work_order_id: WO-0168d
status: AWAITING_REVIEW
review_mode: fresh-context findings-only exact-candidate review
date: 2026-08-27
---

# REV-0107 — central SQLite opener and installer gate review

## Seat and artifact contract

Act as the independent reviewer. Re-derive the candidate from repository evidence; do not rely on
author claims. Write findings only to `work/review/REV-0107/result.md`. Do not edit this request,
implementation, governance, tests, or prior review records. Do not commit or push.

Verdict must be `BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT` and include exact P0/P1/P2 counts.
Acceptance requires zero open P0 and zero open P1. Each finding needs file:line, reproducible or
source-grounded evidence, impact, and the smallest root correction.

## Exact identities — verify, do not trust

- Repository: `https://github.com/amujtabaa/automation-alpaca.git`
- Branch: `codex/m2-wo0168d-hybrid-r1`
- Work-order planning base: commit `81c65a09fbdd3d67a4a46ccd1d22f3c9b395353a`, tree
  `7dfed0cb0dd68add1ca36704766ccfd7a65bff61`
- REV-0106 terminal record head: `f0a6121908d8cfadeeb9de6ff2d5f4d94238f6ec`, tree
  `b2c596ce5179305fba26ac093197de1be1ba9119`
- Implementation candidate: commit `5cf52a846dcd34aaf6cae2d0f1338014ceabd536`, tree
  `68e2fb928f04732bdb03eaf996df8a3bdab2d177`
- Full work-order range: `81c65a09fbdd3d67a4a46ccd1d22f3c9b395353a..5cf52a846dcd34aaf6cae2d0f1338014ceabd536`
- Re-diagnosed successor range: `f0a6121908d8cfadeeb9de6ff2d5f4d94238f6ec..5cf52a846dcd34aaf6cae2d0f1338014ceabd536`
- Any later committed change must be review-request/ledger documentation only. Verify that before
  treating the implementation candidate as exact.

Candidate file SHA-256 identities:

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

Frozen DDL identity (must remain static-only):

- `SCHEMA_DDL`: 178,755 UTF-8 bytes
- SHA-256: `2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5`
- `schema.py` Git blob: `ef332a0b97d28e0535ac53ea0e4d4e091991abad`
- `DDL_EXECUTION_AUTHORIZED_BY_AMEEN`: exactly `False`

## Authority and prohibitions

Ameen authorized only bounded REV-0106-F1 remediation of the application installer and supporting
gate tests/governance. The human flag must be enforced before connection access. No DDL-byte
change, held-suite execution, database creation (file or in-memory), migration, later work-order
implementation, unlock, credentials, network/broker call, order, promotion, or master merge is
authorized.

The reviewer may read and parse held-suite source but MUST NOT import, collect, or execute anything
under `tests_gated/`. Do not run the full repository suite or conformance oracle because they create
databases. Runtime reproduction must use no-I/O stand-ins or monkeypatches and ordinary
`tests/execution_core` only.

## Why REV-0107 exists

REV-0106 round two returned BLOCK P0=0/P1=2/P2=0. It confirmed that the application installer now
enforces the still-False human flag before touching its supplied connection. Its remaining controls
were still bypassable: a conditional gate fooled flattened call ordering, and aggregate token
counts admitted count-preserving production drift. REV-0106 exhausted its two-round cap.

The candidate removes both brittle mechanisms instead of extending them:

1. `open_approved_sqlite_connection` is the sole ordinary held-suite opener. Its exact executable
   body is unconditional gate call, then `sqlite3.connect(database)`.
2. All four held suites route their opens through that helper and contain no direct `.connect`,
   `Connection(...)`, or `from sqlite3 import connect/Connection` capability.
3. Production schema/repository files cannot import SQLite or contain direct ordinary connection
   capability. The helper module is pinned to exactly one unaliased SQLite import and exactly one
   connection attribute, inside the exact helper.
4. Lexical allowlisting only governs token location; it no longer claims semantic protection.
   Structural tests independently kill aliases, `Connection(...)`, conditional gating, an added
   helper-module bypass, and count-preserving lexical drift.
5. `install_schema` still independently computes actual DDL identity, enforces the app-owned human
   authorization and expected identity, checks caller digest, and only then accesses the supplied
   connection.

## Required read order

1. `AGENTS.md` and the safety core in `CLAUDE.md`.
2. `work/active/WO-0168d-m2-i3-5-hybrid-gate-simplification.md`.
3. `docs/adr/ADR-026-interim-ddl-gate-threat-model.md`.
4. Amendments 7–10 in
   `work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md`.
5. `work/review/REV-0106/result.md`, `result-r2.md`, and `disposition.md`.
6. Candidate source/tests and both Git ranges above.
7. Relevant `.ai-os` review/scope rules changed in the full work-order range.

## Required review lenses

1. **Installer authority:** prove the known expected digest cannot make `install_schema` access its
   supplied connection while the human flag is False. Check all ordinary public call shapes in the
   accepted threat model.
2. **Pre-open dominance:** prove the exact central helper gates unconditionally before constructing
   a connection and no second ordinary opener exists in its module.
3. **Held-suite routing:** statically inspect all four held suites for every connection-opening site
   and ordinary SQLite constructor spelling. Do not execute or import them.
4. **Failure capability:** independently mutate conditional gate placement, ordinary import aliases,
   direct `Connection(...)`, an extra helper-module opener, and count-preserving production drift.
   A named control that accepts its in-model mutant is blocking.
5. **Scope and regression:** inspect the complete work-order diff for unauthorized DDL/source scope,
   weakened product semantics, test collection leaks, or governance text that suppresses legitimate
   scope, safety, regression, contract, or data-integrity findings.
6. **Budgets:** boundary plus gate must remain at most 400 nonblank/noncomment lines; work order at
   most 220 lines; no retired large scanner or equivalent analyzer may regrow.
7. **Threat boundary:** deliberate dynamic-name/reflection evasion and a malicious host owner are
   outside ADR-026. Record such concerns as nonblocking proposals unless they also demonstrate an
   ordinary in-model bypass or a product safety/data-integrity defect.

## Author evidence — reproduce selectively

- Focused no-I/O boundary suite: 14 passed.
- All ordinary `tests/execution_core`: 100%, exit 0.
- Ruff check and format: clean on six changed Python files.
- mypy: success on 95 application files.
- import-linter: 6 kept, 0 broken.
- AI-OS install/version/ledger/PKL/disposition and full branch scope checks: pass.
- Boundary plus gate: 376 nonblank/noncomment lines; work order: 218 lines.
- Static DDL extraction: exact byte count/digest above; authorization flag False.
- NOT_RUN by authority: held suites, full repository pytest, conformance oracle, any DDL/SQLite
  execution, database creation, migration, and all later work.

## Result format

Create only `work/review/REV-0107/result.md` with:

- verified commit/tree/ranges and candidate hashes;
- commands/probes actually run and explicit NOT_RUN items;
- findings ordered P0, P1, P2 with evidence and root resolution;
- disproof pass for each tentative P0/P1;
- exact P0/P1/P2 counts and final verdict.

Do not infer acceptance from green author evidence. Conversely, do not reopen the retired arbitrary-
Python proof problem outside ADR-026's declared threat model.
