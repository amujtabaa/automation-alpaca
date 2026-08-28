---
type: Review Request
rev_id: REV-0107
round: 2
work_order_id: WO-0168d
status: AWAITING_REVIEW
review_mode: fresh-context findings-only remediation review
date: 2026-08-27
---

# REV-0107 round two — executable Connection alias remediation

## Reviewer contract

Use a fresh context. Read `AGENTS.md`, then this file, `request.md`, the reviewer-owned `result.md`,
and author-owned `disposition.md`. Reproduce the sole round-one P1 and inspect only its remediation
plus regressions it could introduce. You may also report any independently demonstrated product
safety/data-integrity, authority, scope, DDL-identity, or current-candidate P0/P1.

Create only `work/review/REV-0107/result-r2.md`. Do not edit any existing file, commit, or push.
Verdict is `BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`; include exact P0/P1/P2 counts and a disproof
pass. Zero open P0/P1 is required.

## Exact identities — verify, do not trust

- Branch: `codex/m2-wo0168d-hybrid-r1`
- Round-one implementation: `5cf52a846dcd34aaf6cae2d0f1338014ceabd536`, tree
  `68e2fb928f04732bdb03eaf996df8a3bdab2d177`
- Round-two remediation candidate: `198f7a0ecd812eb1863aba6bf0b8aa58666d69d3`, tree
  `7e073a4e2e5316553087d285154e0970cb7ad692`
- Remediation range: `5cf52a846dcd34aaf6cae2d0f1338014ceabd536..198f7a0ecd812eb1863aba6bf0b8aa58666d69d3`
- Full work-order base remains `81c65a09fbdd3d67a4a46ccd1d22f3c9b395353a`.
- Any later commit must change only this request and the append-only ledger. Verify that wrapper
  condition before accepting the candidate.

Key SHA-256 identities:

- remediated `tests/execution_core/test_sqlite_boundary.py`:
  `438a63ac4f57becd725f02412c0987600f9a87f749acf67d5d3acee3f12dda9d`
- unchanged round-one `result.md`:
  `680f11e0a5460eabb37163120c3b70737172d8ecd79561a8d789d3dee7b58c12`
- `disposition.md`:
  `fbc909d020db0cec0774db9ff16f1cf2ce1f9c3c8ab63a8578a5ff2e5c4d77d4`
- unchanged application `schema.py`:
  `5dc9fcbed9a60f0b39772093ac7842877a72dd9190de6df2fd579bb384b1d814`
- unchanged central opener module:
  `d88ba91c3c1d935ec2957d68eb4d3927a10865e40a9bf53a3ca1cb0384ac1e26`

DDL remains exactly 178,755 UTF-8 bytes, SHA-256
`2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5`, schema blob
`ef332a0b97d28e0535ac53ea0e4d4e091991abad`; the application-owned human flag remains exactly
`False`.

## Round-one P1 and remediation

Round one found that `Connection = sqlite3.Connection; Connection(path)` and
`from sqlite3.dbapi2 import Connection` could pass the structural controls. The correction is
deliberately syntactic and finite:

1. Gather AST nodes that belong to argument, variable, and return annotations.
2. Reject every `.Connection` attribute outside those deferred annotation nodes. This rejects the
   alias where it acquires the constructor, so no local-name dataflow model is needed.
3. Treat `sqlite3` and every ordinary `sqlite3.*` submodule as the same import family; dangerous
   `connect`/`Connection` direct imports are rejected.
4. Apply the executable-reference rule inside the exact helper-module check, so a second local
   alias opener invalidates helper exactness.
5. Add failure canaries for direct and locally aliased constructors, name calls, `sqlite3.dbapi2`
   import, and a second helper-module alias opener.

## Required probes

Re-run the exact three round-one failing mutations against the remediated functions:

- real helper source plus local `sqlite3.Connection` alias/opener;
- real held-suite source plus local alias/opener (`allow_sqlite_import=True`);
- production source plus `from sqlite3.dbapi2 import Connection` and a name call
  (`allow_sqlite_import=False`).

Also probe:

- a direct `sqlite3.Connection(path)` call;
- an annotation-only `sqlite3.Connection` reference (must remain allowed);
- assignment/default/decorator/class-base executable references (must fail if ordinary syntax);
- an added `import sqlite3.dbapi2 as db` in production;
- prior conditional-gate, extra-helper `.connect`, import-alias, and count-preserving mutants.

Do not expand into reflection, dynamic-name construction, hostile host behavior, or a general
Python dataflow claim; those remain outside ADR-026 unless they also prove an ordinary in-model
bypass.

## Authority and allowed evidence

No DDL-byte change, held-suite import/collection/execution, SQLite connection, database creation
(file or in-memory), schema installation, migration, full-repository pytest, conformance, unlock,
later work, credentials, network/broker call, order, promotion, or master merge is authorized.

Static parsing and no-I/O stand-ins are permitted. The focused command
`python -B -m pytest -p no:cacheprovider -q tests/execution_core/test_sqlite_boundary.py` is
permitted. Do not run anything under `tests_gated/`.

## Author evidence

- Focused no-I/O boundary suite: 15 passed.
- All ordinary `tests/execution_core`: 100%, exit 0.
- Ruff check/format: clean; mypy app: 95 files clean; import-linter: 6 kept/0 broken.
- AI-OS ledger/PKL/disposition and full work-order scope checks: pass.
- Boundary plus gate: exactly 400 nonblank/noncomment lines; work order: 218 lines.
- Round-one result hash unchanged; DDL identity and human flag unchanged.
- NOT_RUN: every prohibited action listed above.

End with explicit P0/P1/P2 counts and verdict. Acceptance does not authorize the separate DDL
intent review or human unlock.
