---
type: Review Result
rev_id: REV-0106
round: 2
reviewer_model: OpenAI Codex independent review seat
verdict: BLOCK
date: 2026-08-27
---

# REV-0106 round two — independent findings-only result

## Verdict and exact counts

**BLOCK.** The frozen remediation candidate has **P0=0, P1=2, P2=0**. F1 is
resolved and the alias-specific F2 defect is resolved, but one newly identified gate-order defect
and one incomplete F3 remediation remain open. Under the packet's finite-stop contract, an open P1
is an exact blocker for re-diagnosis or human disposition; the review cap does not force acceptance.

- P0: **0**
- P1: **2**
- P2: **0**
- Separate out-of-model threat-class proposals: **0**

## Verified identities

- Repository: `https://github.com/amujtabaa/automation-alpaca.git`
- Branch: `codex/m2-wo0168d-hybrid-r1`
- Original review base: `d0887585fdb479e83a74909e6d14f3375e0a0850`
- Original candidate: `f20eddd4d060f7506bbbe563761bbf964731275f`
- Round-two remediation candidate: `a5c95ca271c99f79ecfd045468072274107f6ead`
- Round-two candidate tree: `fdbdbe0934a08e97d542945d28b937bdc67708ea`
- Candidate schema Git blob: `ef332a0b97d28e0535ac53ea0e4d4e091991abad`
- Review-time `HEAD`: `c5fb5c3edd0117fa0bd88fb6cd98bae6974c984e`, a descendant of the
  remediation candidate. `a5c95ca..HEAD` changes only the work order, ledger, REV-0106 disposition,
  and `request-r2.md`; `app/**`, `tests/**`, and `tests_gated/**` have no candidate-to-HEAD drift.
- The listed SHA-256 values were reproduced for `schema.py`
  (`5dc9fcbed9a60f0b39772093ac7842877a72dd9190de6df2fd579bb384b1d814`),
  `approved_schema_digest.py`
  (`68338cde85bd0467728f6cb318bd083c34c0a131459534a585c88947edff0d20`),
  `test_sqlite_boundary.py`
  (`211b44139b6ba445abfa8602d0bbeaa6d826826c9ea944b885d89ce9190e6b7a`), ADR-026
  (`4db26a999efd4c2f751c7c6a15b25423e94ae61df034cec15fa01c3603109ea0`), and
  the current required-read WO-0168d
  (`624ad8656923c2b7cab09ebf1ab3ee5eb426fdd8be68d1e67e408b631b589f73`).
- Static AST extraction from the candidate Git blob, without importing or executing the module,
  produced `178755` UTF-8 `SCHEMA_DDL` bytes and SHA-256
  `2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5`.
  The extracted DDL is byte-identical to the original candidate's DDL.
- The application-owned authorization flag is statically `False`; there is one source definition.
  The expected identity is the DDL SHA above. The installed-catalog constant remains
  `c717f6a6c84b37cb13773416c90b50d14f377e39928d7f9c626e769296e632d2`.
- The R4/R5 manifest files independently hash to
  `99aab5f40d43ea5dacce78e77ea47cad250cb9618223d9036a071d8a2704ed39` and
  `4e69ea8bfb077cf0cbbf844b94d58a817ee096e8f802822d0a266c72a5e84525`.
- `install_schema` retains its positional/keyword signature and frozen `__all__`. Static module
  inspection found only inert standard-library imports and no top-level call expression.

## Findings

### New defect

### REV-0106-R2-F1 — [P1] The gate-order pin accepts a gate that does not dominate connection access

- Location: `tests/execution_core/test_sqlite_boundary.py:234`
- Requirement: WO-0168d lines 107-110 and ADR-026 lines 41-51 require every direct connection
  opener to call the pre-open gate first so a direct invocation refuses before a connection object
  exists. ADR-026's finite threat model includes ordinary edits that bypass a named gate.
- Evidence: **reproduced-live, static/no-I/O.** An in-memory source mutation of the real
  `tests_gated/execution_core/test_persistence_directness.py` fixture added an optional
  `enforce_gate: bool = False` parameter and placed the existing gate call under
  `if enforce_gate:`. It did not add or remove any controlled token. Both
  `_connection_gate_violations(mutant, path)` and the exact-token `_token_violations(...)` returned
  `()`. The detector flattens calls by source location and accepts the first syntactic call as the
  gate; it does not require that call to execute on every path reaching `sqlite3.connect`.
- Impact: The default direct fixture invocation reaches `sqlite3.connect` without invoking the
  pre-open guard while both named controls remain green. That can create the database before the
  installer-owned gate has an opportunity to refuse. The current checked-in fixtures remain
  correctly gated, so this is a failure-capable control gap rather than evidence that this candidate
  executed DDL or created a database.
- Resolution: Make the bounded AST pin require an unconditional gate as the first executable
  statement on every path that can reach a direct connection, and add a canary for a conditional,
  non-dominating gate. A finite statement-shape rule for these four held files is sufficient; no
  general Python control-flow analyzer is required.

### Incomplete / bypassable fix

### REV-0106-R2-F2 — [P1] Total token counts do not make F3 occurrence-bounded

- Location: `tests/execution_core/test_sqlite_boundary.py:91`
- Requirement: `request-r2.md` lines 82-83 and WO-0168d lines 113-120 require an added production
  token occurrence under an already justified path to fail and require the manifest not to hide a
  new occurrence.
- Evidence: **reproduced-live, static/no-I/O.** A parsed in-memory mutation of the real
  `app/execution_core/persistence/repository.py` added an ordinary `import sqlite3`, replaced an
  existing justified comment occurrence with `sqlite3.connect("candidate.db")`, and removed a
  different obsolete comment occurrence. The source remained valid Python; its token-count vector
  remained exactly `(4, 0, 0)`; `_token_violations(...)` returned `()`. No mutated source was
  executed. The implementation records only per-file totals, not the identity or structure of each
  justified occurrence.
- Impact: A direct production import and connection can replace previously justified non-capability
  occurrences while the exact-count test stays green. This leaves round-one F3 incomplete under the
  packet's ordinary-import/direct-use threat model.
- Resolution: Pin the finite justified occurrences by stable structural identity (for example,
  bounded AST/string occurrence records) rather than only aggregate counts, and add a
  count-preserving replacement canary using an allowed production path.

### Remediation regressions introduced by the fixes

None found beyond the incomplete F3 mechanism above. The F1 application change preserves DDL bytes,
installer API shape, `__all__`, import inertness, the still-closed flag, and the separate unlock
governance. The F2 alias additions do not create a false positive for the tested ordinary aliased
gate-first forms.

## Commands and evidence actually run

- Git identity/history: remote, branch, candidate/tree/blob `rev-parse`, ancestry checks,
  `f20eddd4..a5c95ca` name/status/stat/log/diff inspection, `a5c95ca..HEAD` drift inspection,
  per-remediation-commit diffs, and `git diff --check`.
- Static identity probe: Python `ast` plus `git cat-file blob` recomputed candidate file hashes,
  extracted and compared both DDL literals, inspected constants/imports/API shape, and never imported
  the schema module for the DDL proof.
- Focused permitted tests:
  `.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider -q tests/execution_core/test_sqlite_boundary.py tests/execution_core/test_persistence_write_capability.py`
  -> **18 passed**.
- Independent F1 no-I/O probe: a stand-in overriding `__getattribute__` received a direct
  `install_schema(..., approved_ddl_sha256=EXPECTED_EXECUTION_DDL_SHA256)` call. Result:
  `SchemaInstallError("HUMAN-GATE pending...")`, with `connection_touches=[]`.
- F2 probes: ordinary `import sqlite3 as db`, `from sqlite3 import connect`, and
  `from sqlite3 import connect as open_db` were detected; function-alias and module-alias gate-first
  forms were accepted. The conditional-gate mutation above returned no violation.
- F3 probes: additive drift was killed by the focused canary; the count-preserving real-production
  mutation above returned no violation.
- Static quality: Ruff check passed; Ruff format check reported all three changed Python files
  formatted; mypy passed **95 source files**; lint-imports kept **6 contracts, 0 broken**.
- Scope/API/governance: the remediation range changes ten paths, all admitted by WO-0168d; the F1
  commit changes only the three authorized source/test files; the human approval precedes that
  commit; Amendment 9, ADR-026, and WO-0168d retain the separate DDL intent/unlock gate.
- One initial custom static-probe one-liner failed at Python parsing because of command-line quoting.
  It executed no repository code and produced no evidence; the corrected static probe is the result
  reported above.

## Not verified

- No `tests_gated` module was imported, collected, or run. No DDL was executed or installed; no file
  or in-memory database was created; the conformance oracle and broader database-creating suites
  were not run; the authorization flag was never set or monkeypatched `True`.
- The full ordinary `tests/execution_core` suite and full repository suite were not rerun. Evidence
  was limited to the permitted focused 18-test set and static checks because the two findings are
  independently failure-capable without database execution.
- The installed catalog digest was not recomputed from a database. Only its unchanged source
  constant was verified; recomputation would require forbidden DDL/database execution.
- The AI-OS install/version/ledger/PKL/disposition checker set and remote GitHub branch-protection /
  CODEOWNERS enforcement were not rerun or remotely verified. The relevant local authority text and
  exact remediation scope were inspected directly.

## Disproof pass

- **Round-one F1:** The candidate computes the actual digest, checks the application-owned false
  authorization and expected identity, then checks the caller digest before connection inspection.
  The stricter stand-in observed zero attribute/method touches. The round-one F1 finding does not
  survive.
- **Round-one F2:** All required ordinary SQLite import spellings were detected, including a direct
  import alias, and ordinary aliased gate-first forms remained accepted. The alias-specific F2
  finding does not survive. R2-F1 is distinct: a syntactically first gate can be conditional and
  non-dominating.
- **Round-one F3:** A simple additive occurrence is now rejected. A count-preserving mutation on the
  actual allowed production file remained invisible while adding ordinary direct SQLite capability,
  so F3 survives as the incomplete-fix finding R2-F2.
- **R2-F1 disproof attempt:** The same mutation was checked against both the AST and lexical controls;
  both returned no violation, and the default path skips the guard before the direct connection.
  Installer-owned authorization cannot prevent the connection object/database from being created
  first. The finding survives at P1.
- **R2-F2 disproof attempt:** The mutant parsed successfully, retained the exact expected count
  vector, used no reflection or dynamic-name construction, and introduced ordinary `import sqlite3`
  plus direct `sqlite3.connect`. The finding remains inside ADR-026's finite threat model and
  survives at P1.
- **Other remediation regressions:** Candidate/source hashes, DDL identity, flag state, single-fact
  ownership, source order, API shape, scope, and governance were rechecked bottom-up. No additional
  P0/P1/P2 finding survived.

[DONE] STATUS: VERIFIED
