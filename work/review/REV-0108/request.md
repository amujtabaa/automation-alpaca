---
type: Review Request
rev_id: REV-0108
work_order_id: WO-0168d
status: AWAITING_REVIEW
review_mode: fresh-context findings-only exact-successor review
date: 2026-08-27
---

# REV-0108 — terminal public-SQLite import-family review

## Seat and output

Use a fresh independent context. Read `AGENTS.md`, then this request and the required records below.
Create only `work/review/REV-0108/result.md`; do not edit any existing file, commit, or push.

Report findings with file:line, reproduced or source-grounded evidence, impact, and smallest root
correction. Include a disproof pass, explicit NOT_RUN items, exact P0/P1/P2 counts, and final
`BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`. Acceptance requires zero open P0/P1.

## Exact identities — verify, do not trust

- Repository: `https://github.com/amujtabaa/automation-alpaca.git`
- Branch: `codex/m2-wo0168d-hybrid-r1`
- Work-order base: `81c65a09fbdd3d67a4a46ccd1d22f3c9b395353a`, tree
  `7dfed0cb0dd68add1ca36704766ccfd7a65bff61`
- REV-0107 round-two candidate: `198f7a0ecd812eb1863aba6bf0b8aa58666d69d3`, tree
  `7e073a4e2e5316553087d285154e0970cb7ad692`
- REV-0108 successor candidate: `70dc59cb11a8a8f5b9e50c876fb7e5ed0945815c`, tree
  `f5ee0646d74047d373ce6b09728177453bd45c82`
- Successor range: `198f7a0ecd812eb1863aba6bf0b8aa58666d69d3..70dc59cb11a8a8f5b9e50c876fb7e5ed0945815c`
- Complete range: `81c65a09fbdd3d67a4a46ccd1d22f3c9b395353a..70dc59cb11a8a8f5b9e50c876fb7e5ed0945815c`
- Any later commit must add only this request and one append-only ledger line. Verify that wrapper
  condition before accepting the successor.

SHA-256 identities:

- `tests/execution_core/test_sqlite_boundary.py`:
  `8aa5eb3014000af3202d454e51a7e1bf635c4514cc017bf4e8f8e7201b5583ab`
- unchanged `app/execution_core/persistence/schema.py`:
  `5dc9fcbed9a60f0b39772093ac7842877a72dd9190de6df2fd579bb384b1d814`
- unchanged `tests/execution_core/approved_schema_digest.py`:
  `d88ba91c3c1d935ec2957d68eb4d3927a10865e40a9bf53a3ca1cb0384ac1e26`
- `docs/adr/ADR-026-interim-ddl-gate-threat-model.md`:
  `125a098860fc3e6ef8e7598ef2f7a56c3e30e5193e3ee50a8975a361e7121d86`
- WO-0168d:
  `65c15c164c4e718ba1cb402cb9c2e361d5ebe6b7e34e64877f650376e6749e8a`
- immutable REV-0107 results:
  `result.md` = `680f11e0a5460eabb37163120c3b70737172d8ecd79561a8d789d3dee7b58c12`;
  `result-r2.md` = `714a88cb269a0cba10c72458c9b233f6e8e73b952253bf45564b4634785e782d`.

DDL remains exactly 178,755 UTF-8 bytes with SHA-256
`2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5`, schema blob
`ef332a0b97d28e0535ac53ea0e4d4e091991abad`, and application-owned human flag exactly `False`.

## Why this successor exists

REV-0107 round two confirmed every round-one executable-alias/submodule correction, then found that
`from sqlite3 import *` and `from sqlite3.dbapi2 import *` supply public `Connection`/`connect`
names while the import rule checked only explicitly named aliases. REV-0107 exhausted two rounds.

The successor changes the already-bounded public import-family rule from
`{connect, Connection}` to `{*, connect, Connection}` in both the direct-capability and exact-helper
checks. It replaces the explicit submodule constructor canary with a wildcard submodule canary and
adds a real helper wildcard canary. It adds no dataflow, reflection, provenance, or general Python
analysis. Boundary plus gate is 399 nonblank/noncomment lines.

## Required read order

1. `AGENTS.md` and the safety core in `CLAUDE.md`.
2. WO-0168d and ADR-026.
3. Amendments 7–12 in the DDL gate record.
4. `work/review/REV-0106/{result.md,result-r2.md,disposition.md}`.
5. `work/review/REV-0107/{request.md,result.md,disposition.md,request-r2.md,result-r2.md}`.
6. Both Git ranges above and candidate source/tests.

## Required failure probes

Against real candidate source text, without executing mutations:

1. Append `from sqlite3 import *` plus `Connection(database)` to the helper; exactness must fail.
2. Append the same to each representative held-suite source with `allow_sqlite_import=True`; the
   direct-capability control must fail.
3. Append `from sqlite3.dbapi2 import *` plus the name call to production source with
   `allow_sqlite_import=False`; the control must fail.
4. Re-run explicit `connect`/`Connection` imports (including aliases and `sqlite3.dbapi2`), local
   `Connection = sqlite3.Connection`, direct constructor, assignment/default/decorator/class-base
   executable references, conditional gate, extra helper opener, module alias, and count-preserving
   production mutants.
5. Verify annotation-only `sqlite3.Connection` remains admitted and every checked-in held/production
   source remains clean.
6. Independently prove the installer still refuses the known digest before supplied-connection
   access while the application flag is False.

## Finite threat boundary

The in-scope ordinary module family is Python's public `sqlite3` package and its `sqlite3.*`
submodules. Dynamic-name construction, reflection, `exec`/`eval`, deliberate use of internal
extension modules such as `_sqlite3`, third-party drivers, editing the guard during an authorized
run, and a malicious host owner are outside this interim in-process mechanism. Record them as
nonblocking threat-class proposals unless checked-in code uses them or they independently expose a
current product safety/data-integrity defect. Do not regrow the retired arbitrary-Python scanner.

## Authority and evidence limits

Ameen authorized only the application installer/gate remediation and fresh zero-P0/P1 review. No
DDL-byte change, held-suite import/collection/execution, SQLite connection, file or in-memory
database, schema installation, migration, full-repository pytest, conformance, unlock, later work,
credentials, network/broker call, order, promotion, or master merge is authorized.

Permitted: source/AST parsing, no-I/O stand-ins, static commands, and
`python -B -m pytest -p no:cacheprovider -q tests/execution_core/test_sqlite_boundary.py`.

Author evidence: focused 15 passed; all ordinary `tests/execution_core` 100% exit 0; Ruff and format
clean; mypy 95 files; import-linter 6 kept/0 broken; AI-OS and full branch scope checks pass;
boundary+gate 399/400, WO 219/220; DDL and flag identities unchanged. Reproduce selectively and do
not infer acceptance from these claims.

Acceptance closes only this remediation work order. It does not authorize the separate DDL intent
review or human unlock.
