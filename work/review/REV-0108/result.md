---
type: Review Result
rev_id: REV-0108
work_order_id: WO-0168d
reviewer_model: OpenAI Codex independent review seat
verdict: ACCEPT
date: 2026-08-27
---

# REV-0108 — independent findings-only result

## Verdict and exact counts

**ACCEPT.** No P0, P1, or P2 finding survived independent identity, source, mutation, regression,
scope, governance, and disproof passes. The exact successor closes the ordinary public
`sqlite3`/`sqlite3.*` wildcard-import gap identified by REV-0107 round two. This verdict closes
only WO-0168d's remediation review; it does not authorize DDL execution, a database, the separate
DDL intent review, or the human unlock.

- P0: **0**
- P1: **0**
- P2: **0**
- Separate out-of-model threat-class proposals: **0 newly demonstrated**

## Findings

None.

## Verified identities and ranges

- Repository: `https://github.com/amujtabaa/automation-alpaca.git`
- Branch: `codex/m2-wo0168d-hybrid-r1`
- Local `HEAD`, local remote-tracking ref, and a fresh read-only GitHub `ls-remote` query all
  resolved the published branch head to
  `9562a416032aeff156630cc953bbd672180c3feb`, tree
  `6279c9da4cf56991aba775d0bd128aa6db09e0bf`.
- Work-order base: `81c65a09fbdd3d67a4a46ccd1d22f3c9b395353a`, tree
  `7dfed0cb0dd68add1ca36704766ccfd7a65bff61`.
- REV-0107 round-two candidate: `198f7a0ecd812eb1863aba6bf0b8aa58666d69d3`, tree
  `7e073a4e2e5316553087d285154e0970cb7ad692`.
- REV-0108 successor candidate: `70dc59cb11a8a8f5b9e50c876fb7e5ed0945815c`, tree
  `f5ee0646d74047d373ce6b09728177453bd45c82`.
- Ancestry and both exact ranges were verified:
  `198f7a0ecd812eb1863aba6bf0b8aa58666d69d3..70dc59cb11a8a8f5b9e50c876fb7e5ed0945815c`
  and
  `81c65a09fbdd3d67a4a46ccd1d22f3c9b395353a..70dc59cb11a8a8f5b9e50c876fb7e5ed0945815c`.
  `git diff --check` passed for both ranges.
- The successor is an ancestor of published `HEAD`. Its only wrapper commit is
  `9562a416032aeff156630cc953bbd672180c3feb`, whose tracked diff adds
  `work/review/REV-0108/request.md` and appends exactly one final line to
  `work/ledger.jsonl`. There is no candidate-to-HEAD implementation, test, ADR, or other
  governance drift.
- The tracked worktree was clean before this result was created. Large pre-existing untracked
  scratch trees were observed and left untouched.

Requested SHA-256 identities reproduced exactly:

- `tests/execution_core/test_sqlite_boundary.py`:
  `8aa5eb3014000af3202d454e51a7e1bf635c4514cc017bf4e8f8e7201b5583ab`
- `app/execution_core/persistence/schema.py`:
  `5dc9fcbed9a60f0b39772093ac7842877a72dd9190de6df2fd579bb384b1d814`
- `tests/execution_core/approved_schema_digest.py`:
  `d88ba91c3c1d935ec2957d68eb4d3927a10865e40a9bf53a3ca1cb0384ac1e26`
- `docs/adr/ADR-026-interim-ddl-gate-threat-model.md`:
  `125a098860fc3e6ef8e7598ef2f7a56c3e30e5193e3ee50a8975a361e7121d86`
- `work/active/WO-0168d-m2-i3-5-hybrid-gate-simplification.md`:
  `65c15c164c4e718ba1cb402cb9c2e361d5ebe6b7e34e64877f650376e6749e8a`
- Immutable REV-0107 `result.md`:
  `680f11e0a5460eabb37163120c3b70737172d8ecd79561a8d789d3dee7b58c12`
- Immutable REV-0107 `result-r2.md`:
  `714a88cb269a0cba10c72458c9b233f6e8e73b952253bf45564b4634785e782d`

Static AST extraction without importing `schema.py` reproduced `SCHEMA_DDL` as exactly 178,755
UTF-8 bytes with SHA-256
`2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5` at the work-order base,
REV-0107 candidate, and REV-0108 successor; all three DDL values are byte-identical. The successor
schema Git blob is `ef332a0b97d28e0535ac53ea0e4d4e091991abad`, the expected digest matches those bytes, and
`DDL_EXECUTION_AUTHORIZED_BY_AMEEN` is the exact boolean `False`.

## Failure-capable evidence actually reproduced

- Runtime: Python **3.12.13**.
- Focused permitted suite:
  `\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider -q tests/execution_core/test_sqlite_boundary.py`
  produced **15 passed**, exit 0.
- A comparative predecessor/successor probe extracted only the four bounded detector functions
  from the REV-0107 candidate Git object. Against real source text, without executing any mutant:
  - real helper plus `from sqlite3 import *` and `Connection(database)`: predecessor accepted;
    successor rejected;
  - real held-suite source plus the same mutation and `allow_sqlite_import=True`: predecessor
    accepted; successor rejected;
  - real production source plus `from sqlite3.dbapi2 import *`, the name call, and
    `allow_sqlite_import=False`: predecessor accepted; successor rejected.
- The successor mutation probe was repeated against **all four** real held-suite files. Every
  wildcard mutant produced a `connection-import` violation. Both real production persistence
  files rejected the `sqlite3.dbapi2` wildcard mutant. Normal Python module namespaces exposed
  public `Connection` and `connect` names for both `sqlite3` and `sqlite3.dbapi2`; no connection
  was constructed.
- Prior regression classes were independently re-run against real or parsed source: explicit
  `connect`/`Connection` imports and aliases from `sqlite3` and `sqlite3.dbapi2`; local
  `Connection = sqlite3.Connection`; direct constructor use; assignment, default, decorator, and
  class-base executable references; conditional gate placement; an extra helper opener; module
  alias `.connect`; and a production mutation that preserved all four literal `sqlite3` tokens.
  Every prohibited mutant failed its owning structural control. Argument/variable/return
  annotation-only `sqlite3.Connection` remained admitted.
- Checked-in source remained clean: helper exactness returned true; all four held suites and both
  production persistence modules returned no structural violation. Independent AST inventory
  found **8** held-suite opening call sites, all calling
  `open_approved_sqlite_connection` (directness 1, repository 1, runtime-checkpoint 1, schema 5),
  with no direct checked-in `.connect`, executable `.Connection`, or dangerous direct import.
- Installer refusal was re-proved with a strict stand-in whose `__getattribute__` records and
  rejects every supplied-connection access. Positional-connection and keyword-connection calls
  using the known expected digest both raised the closed-gate `SchemaInstallError` with
  `touches=[]`; the application flag remained exactly `False`.
- Static quarantine checks reproduced `testpaths = ["tests"]`, no `tests_gated/**/__init__.py`,
  no link/reparse target in `tests_gated`, and five regular candidate Git blobs there. The four
  suites remain 99% Git renames plus the bounded gate-routing edits; the scanner body and
  `sys.settrace` machinery are absent from the retained 194-line kernel.
- Scope inspection found every path in the complete range admitted by WO-0168d. The authorized
  scanner deletion, four held-suite relocations, application gate, supporting tests, inherited
  regression edits, ADR/governance changes, CODEOWNERS, review records, and append-only ledger
  entries match the recorded authority. No DDL-byte, broker, credential, order, live-mode, or
  event-log-truth change appears in either reviewed range.
- Budgets reproduced: boundary test **363** plus helper/gate **36** = **399**
  nonblank/noncomment lines (limit 400); WO-0168d is **219** physical lines (limit 220). Ruff
  check and Ruff format-check passed on the successor Python file.

## Disproof pass

- **Wildcard closure:** the tentative concern that the one-token change merely made a canary pass
  did not survive. The exact REV-0107 detector accepted each real-source wildcard mutation; the
  exact successor detector rejected the same source. Root-package and `sqlite3.dbapi2` forms were
  both exercised, including every held suite and both production files.
- **Regression from the wildcard rule:** did not survive. The rule remains restricted to the
  already-declared public `sqlite3`/`sqlite3.*` `ImportFrom` family; prior explicit aliases,
  constructors, executable-reference positions, conditional gating, extra openers, module aliases,
  and count-preserving drift still fail. Annotation-only references remain clean.
- **Current checked-in bypass:** did not survive. All eight held opening sites route through the
  exact two-statement gate-then-connect helper, no second ordinary opener exists, and current
  held/production sources are structurally clean.
- **Installer authority:** did not survive as a concern. The known expected digest cannot reach
  supplied-connection access while the application-owned flag is false, for either ordinary call
  shape tested. DDL and installer identities remain frozen.
- **Quarantine, scope, governance, and budget:** no tentative concern survived the complete-range
  and bottom-up diff review. The gated files remain outside ordinary collection; authorized
  deletion/relocation is traceable; Core 20 cannot suppress evidence-backed findings about itself;
  and both budgets remain below their limits.
- **Out-of-model classes:** `_sqlite3`, reflective/dynamic-name construction, arbitrary `exec`,
  third-party drivers, and hostile-host mutation were not converted into blockers. No `_sqlite3`
  or third-party-driver use was found in the scoped source. The checked-in production dynamic
  lookup only classifies exceptions through an already-loaded `sys.modules` entry and acquires no
  connection; the held-suite `exec` text belongs to an import-inertness probe that was not imported
  or executed. Neither exposes a current product safety or data-integrity defect.

## Explicit NOT_RUN / unverified

- Nothing under `tests_gated/` was imported, collected, or executed.
- No SQLite connection was opened; no file or in-memory database was created; no DDL, schema
  installation, migration, catalog computation, or SQL-manifest computation ran; the human flag
  was not changed or monkeypatched.
- Full-repository pytest, conformance, the full ordinary `tests/execution_core` suite, and the
  inherited fill/protection regression tests were NOT_RUN. Their changed source and exact diffs
  were inspected, but author pass claims were not treated as reviewer execution evidence.
- Mypy, import-linter, the full AI-OS checker set, and remote GitHub branch-protection/CODEOWNERS
  enforcement were NOT_RUN or unverified. Python 3.11 was not separately exercised.
- No credentials, broker/network call, order, promotion, unlock, merge, commit, or push occurred.
  The only network operation was the read-only GitHub ref lookup required to verify published
  `HEAD`.

Verdict: **ACCEPT**

P0: **0**

P1: **0**

P2: **0**

Unverified: every item listed under **Explicit NOT_RUN / unverified** above.

[DONE] STATUS: VERIFIED
