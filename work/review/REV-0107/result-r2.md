---
type: Review Result
rev_id: REV-0107
round: 2
work_order_id: WO-0168d
reviewer_model: OpenAI Codex independent review seat
verdict: BLOCK
date: 2026-08-27
---

# REV-0107 round two — independent findings-only result

## Verdict and exact counts

**BLOCK.** The exact remediation candidate has **P0=0, P1=1, P2=0**. The three round-one
`Connection` alias/submodule mutants are now rejected, but an ordinary wildcard import from the
same SQLite import family still supplies `Connection` and `connect` while all named structural and
lexical controls remain green. REV-0107 still requires zero open P0/P1 before the separate DDL
intent review and human unlock gate.

- P0: **0**
- P1: **1**
- P2: **0**
- Separate out-of-model threat-class proposals: **0**

## Verified identities and scope

- Repository: `https://github.com/amujtabaa/automation-alpaca.git`
- Branch: `codex/m2-wo0168d-hybrid-r1`
- A read-only GitHub refs query and the local checkout both resolved the current published branch
  head to `e6bdd3727be0bf993e8618d459bd1e4bf6235a41`, tree
  `774856ffe462bfd3b904df108ca2d8d7b5292300`, whose sole parent is the remediation candidate.
- Full work-order base: `81c65a09fbdd3d67a4a46ccd1d22f3c9b395353a`, tree
  `7dfed0cb0dd68add1ca36704766ccfd7a65bff61`.
- Round-one implementation: `5cf52a846dcd34aaf6cae2d0f1338014ceabd536`, tree
  `68e2fb928f04732bdb03eaf996df8a3bdab2d177`.
- Round-two remediation candidate: `198f7a0ecd812eb1863aba6bf0b8aa58666d69d3`, tree
  `7e073a4e2e5316553087d285154e0970cb7ad692`.
- Ancestry and the exact ranges
  `81c65a09fbdd3d67a4a46ccd1d22f3c9b395353a..198f7a0ecd812eb1863aba6bf0b8aa58666d69d3`
  and
  `5cf52a846dcd34aaf6cae2d0f1338014ceabd536..198f7a0ecd812eb1863aba6bf0b8aa58666d69d3`
  were verified. The remediation range changes the boundary test plus the expected append-only
  ledger, gate amendment, and REV-0107 request/result/disposition records; it changes no
  application source or DDL.
- Candidate-to-published-head drift is exactly an added `work/review/REV-0107/request-r2.md` and
  one line appended at the end of `work/ledger.jsonl`. There is no candidate-to-head application,
  test, ADR, or other governance drift.
- Requested SHA-256 identities reproduced exactly:
  - `tests/execution_core/test_sqlite_boundary.py`:
    `438a63ac4f57becd725f02412c0987600f9a87f749acf67d5d3acee3f12dda9d`
  - unchanged `work/review/REV-0107/result.md`:
    `680f11e0a5460eabb37163120c3b70737172d8ecd79561a8d789d3dee7b58c12`
  - `work/review/REV-0107/disposition.md`:
    `fbc909d020db0cec0774db9ff16f1cf2ce1f9c3c8ab63a8578a5ff2e5c4d77d4`
  - unchanged `app/execution_core/persistence/schema.py`:
    `5dc9fcbed9a60f0b39772093ac7842877a72dd9190de6df2fd579bb384b1d814`
  - unchanged `tests/execution_core/approved_schema_digest.py`:
    `d88ba91c3c1d935ec2957d68eb4d3927a10865e40a9bf53a3ca1cb0384ac1e26`
- Static AST extraction, without importing or executing `schema.py`, reproduced `SCHEMA_DDL` as
  exactly 178,755 UTF-8 bytes with SHA-256
  `2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5`.
  The schema Git blob is `ef332a0b97d28e0535ac53ea0e4d4e091991abad`, the expected digest is the
  same SHA-256, and `DDL_EXECUTION_AUTHORIZED_BY_AMEEN` is the exact boolean `False`.
- Tracked files were clean at review start. Pre-existing untracked `.codex-temp/` and `.tmp/`
  directories were present and left untouched; they are outside every source root used by the
  boundary check.

## Finding

### [P1] Wildcard SQLite imports retain an ordinary name-call opener bypass

- Location: `tests/execution_core/test_sqlite_boundary.py:106` and
  `tests/execution_core/test_sqlite_boundary.py:157`
- Requirement: ADR-026 sections 1 and 2 require ordinary SQLite imports and direct public
  connection capability to be rejected, require the central helper to remain the sole ordinary
  opener, and require failure-capable import/alias canaries. REV-0107 round two requires the
  `sqlite3`/`sqlite3.*` import-family correction to reject dangerous `connect`/`Connection` direct
  imports without expanding into reflection or general dataflow.
- Evidence: **reproduced-live, static/no-I/O.** Python's normal wildcard-import namespace contains
  both `Connection` and `connect` for `sqlite3` and `sqlite3.dbapi2`. Three parsed real-source
  mutations were then probed without executing the mutated source:
  1. Appending `from sqlite3 import *` and a direct `Connection(database)` name-call opener to the
     real helper source made `_approved_connection_helper_is_exact(...)` return `True`.
  2. Appending the same ordinary import/opener to the real held-suite repository source made
     `_direct_connection_capability_violations(..., allow_sqlite_import=True)` and the lexical
     control both return `()`.
  3. Appending `from sqlite3.dbapi2 import *` and the name-call opener to the real production
     repository source made
     `_direct_connection_capability_violations(..., allow_sqlite_import=False)` and the lexical
     control both return `()`.
  Both `ImportFrom` checks match the SQLite module family but reject only aliases whose literal
  imported name is `connect` or `Connection`; an AST wildcard alias has the name `*`. The later
  `Connection(...)` is an ordinary name call and contains no `.Connection` attribute for the
  executable-reference rule to see.
- Impact: A plain import statement plus direct public constructor call can add a second opener to
  the helper or a held suite, or direct SQLite capability to production, while the focused
  boundary suite remains green. The checked-in candidate contains no wildcard import or current
  opener bypass, so this is a P1 failure-capability blocker rather than a P0 current
  execution/safety violation.
- Resolution: For every matched `sqlite3`/`sqlite3.*` `ImportFrom`, reject `*` alongside explicit
  `connect` and `Connection` in both the direct-capability and helper-exactness checks. Add finite
  canaries using real helper, held-suite, and production source for wildcard imports from
  `sqlite3` and `sqlite3.dbapi2`; no name dataflow, reflection, or arbitrary-Python model is needed.

## Required remediation and regression probes

- **Round-one helper alias:** real helper source plus `Connection = sqlite3.Connection` and a local
  name-call opener now makes helper exactness return `False`.
- **Round-one held-suite alias:** real held-suite source plus the same alias/opener now produces a
  `Connection` structural violation with `allow_sqlite_import=True`.
- **Round-one production submodule import:** real production source plus
  `from sqlite3.dbapi2 import Connection` and a name call now produces a direct-import violation
  with `allow_sqlite_import=False`.
- A direct `sqlite3.Connection(path)` call was rejected. Argument, variable, and return
  `sqlite3.Connection` annotations remained accepted, including when appended to the real helper.
- Assignment, default-value, decorator, and class-base executable `.Connection` references were
  each rejected.
- An added `import sqlite3.dbapi2 as db` in real production source was rejected.
- The prior conditional-gate and extra-helper `.connect` mutants invalidated helper exactness;
  module-alias and direct-import-alias mutants produced violations.
- A real-production count-preserving mutant retained exactly four `sqlite3` tokens and remained
  lexically admitted, but the structural control rejected both its added import and `.connect`.
- Checked-in helper exactness remained `True`; all four held-suite sources and both production
  persistence sources produced no current structural violation. This also confirmed that ordinary
  annotation-only `sqlite3.Connection` uses and non-connection SQLite exception attributes did not
  regress.
- No separate remediation regression survived beyond the incomplete wildcard-import coverage in
  the finding.

## Commands and evidence actually run

- Read the required authority and packet in the mandated order, including the `CLAUDE.md` safety
  core, WO-0168d, ADR-026, gate Amendments 7-10, REV-0106's two results and disposition, then the
  exact remediation diff, Amendment 11, candidate control/helper sources, and relevant static held
  and production source.
- Git identity/history: local branch/status/revision/tree/parent checks, a read-only
  `git ls-remote` published-head query, ancestry checks, full/remediation/wrapper range diffs,
  append-only ledger diff, SHA-256 checks, schema blob check, and `git diff --check` on both the
  remediation and full work-order candidate ranges.
- Focused permitted no-I/O suite:
  `.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider -q tests/execution_core/test_sqlite_boundary.py`
  -> **15 passed**, exit 0.
- Independent in-memory AST probes reproduced all required mutations and the wildcard finding
  against real source text. The mutated held-suite source was read as text only and was never
  imported, collected, or executed.
- A no-connection import probe confirmed normal wildcard imports expose `Connection` and `connect`
  from both `sqlite3` module spellings. It did not construct a connection.
- Ruff check and format check passed on the remediated boundary file. Budgets reproduced exactly:
  boundary test **364** plus helper **36** = **400** nonblank/noncomment lines; work order = **218**
  lines.

## Explicit NOT_RUN / unverified

- Nothing under `tests_gated/` was imported, collected, or executed.
- No SQLite connection or database (file or in-memory) was created; no DDL, schema installation,
  migration, catalog computation, or later work-order implementation ran; the human flag was not
  changed or monkeypatched `True`.
- Full-repository pytest, conformance, the full ordinary `tests/execution_core` suite, mypy,
  import-linter, and database-creating checks were NOT_RUN. Author claims for those checks were not
  treated as reviewer evidence.
- No application/broker network call, credential use, order, promotion, unlock, merge, commit, or
  push occurred. The only network access was the read-only GitHub ref query required to verify the
  current published branch head.
- GitHub branch-protection and live CODEOWNERS enforcement were not verified.

## Disproof pass

- **Round-one P1:** does not survive in its three required forms. The alias-acquisition
  `.Connection` attribute is now rejected before local-name call tracking is relevant, and the
  explicit `sqlite3.dbapi2` direct import is recognized.
- **Annotation-regression concern:** does not survive. Argument, variable, and return annotation
  subtrees remain admitted, while the same attribute in assignment/default/decorator/class-base
  expression positions is rejected. All checked-in held sources remain clean.
- **Prior structural regressions:** do not survive. Conditional gating, a second helper
  `.connect`, import aliases, and count-preserving production drift all failed their owning
  structural checks.
- **Wildcard-import finding:** survives. The mutations parse as ordinary `ImportFrom` plus direct
  `Name` calls, export the two connection capabilities under normal Python import semantics, use
  no reflection, dynamic-name construction, hostile host action, or general dataflow claim, and
  return clean results from both named controls on real-file mutations.
- **Current P0 concern:** does not survive. No wildcard or other checked-in bypass exists, the
  central helper remains exactly gate-then-connect, the human flag is still false, and application
  plus DDL identities are unchanged. The defect is in required future failure capability.
- Bottom-up reinspection found no additional authority, scope, DDL-identity, budget, product
  safety/data-integrity, or remediation-regression finding.

Verdict: **BLOCK**

P0: **0**

P1: **1**

P2: **0**

Unverified: held-suite execution; any SQLite/DDL/database/migration execution; full repository and
full ordinary execution-core suites; conformance; mypy; import-linter; remote branch protection and
CODEOWNERS enforcement.

[DONE] STATUS: VERIFIED
