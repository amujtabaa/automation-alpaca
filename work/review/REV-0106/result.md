---
type: Review Result
rev_id: REV-0106
reviewer_model: OpenAI Codex (GPT-5)
verdict: BLOCK
date: 2026-08-27
---

## Verdict

**BLOCK.** Independent findings-only review of the frozen candidate found **P0=1, P1=2, P2=0**. The changed-DDL gate cannot proceed to an unlock or execution packet while the P0/P1 findings remain open.

Verified review identity:

- Reviewer: OpenAI Codex (GPT-5), fresh independent review seat; not the candidate author.
- Repository: `https://github.com/amujtabaa/automation-alpaca.git`
- Branch: `codex/m2-wo0168d-hybrid-r1`
- Base: `d0887585fdb479e83a74909e6d14f3375e0a0850`
- Candidate: `f20eddd4d060f7506bbbe563761bbf964731275f`
- Candidate tree: `36f4b028927110cf318c0f2f74108f7f083f8177`
- Authoritative range: `d0887585fdb479e83a74909e6d14f3375e0a0850..f20eddd4d060f7506bbbe563761bbf964731275f`
- Current branch head was `14110daaf8883142c01a8f5b7dec1d7707942b7b`; the only candidate-to-head tracked change was `work/review/REV-0106/request.md`. The candidate source tree therefore matched the working source reviewed.

## Findings

| ID | Severity | File:line | Evidence | Why it matters | Proposed action / Fix |
| --- | --- | --- | --- | --- | --- |
| REV-0106-F1 | P0 | `tests/execution_core/approved_schema_digest.py:16`; `app/execution_core/persistence/schema.py:4776` | **Reproduced, no SQLite/DDL.** With `DDL_EXECUTION_AUTHORIZED_BY_AMEEN is False`, calling `install_schema(Probe(), approved_ddl_sha256=EXPECTED_EXECUTION_DDL_SHA256)` reached `Probe.execute("PRAGMA foreign_keys")`. The stand-in raised immediately, before SQL could run. Source then shows `install_schema` would continue to `BEGIN IMMEDIATE` at line 4780 after the pragma check. The installer validates only equality between the caller-supplied digest and the DDL digest; it does not consume an independently authorized fact. | The public expected-identity constant alone is sufficient to cross the installer refusal and touch the supplied connection. This is an ordinary direct public-API call expressly inside ADR-026's threat model, and it contradicts the acceptance rule that a matching digest must never authorize changed-DDL execution. The current gated fixtures call the accessor correctly, but that does not close this load-bearing bypass. | Re-gate the required application-boundary change so `install_schema` (or the only reachable installing entry point) requires and verifies a separate authorization fact that cannot be satisfied by the expected digest. Add a no-I/O negative control proving that supplying `EXPECTED_EXECUTION_DDL_SHA256` while authorization is False refuses before connection access. |
| REV-0106-F2 | P1 | `tests/execution_core/test_sqlite_boundary.py:90` | **Reproduced mutation.** `_connection_gate_violations()` returned `()` for `import sqlite3 as db; def connection(path): return db.connect(path)`. `_is_direct_connect()` recognizes only an attribute call whose receiver is literally named `sqlite3`. The affected `tests_gated` files are lexically allowlisted, so the lexical control provides no fallback. | An ordinary alias import can add a direct gated-suite connection opener with no gate-first call while the named AST control stays green. The replacement therefore does not reliably detect the in-model direct-SQLite drift it claims to pin. | Resolve ordinary import aliases and direct import spellings (including `from sqlite3 import connect`) before classifying connection calls, and add mutation canaries for each supported direct-call shape. |
| REV-0106-F3 | P1 | `tests/execution_core/test_sqlite_boundary.py:21`; `tests/execution_core/test_sqlite_boundary.py:50` | **Reproduced mutation.** Passing a source mapping labeled `app/execution_core/persistence/repository.py` containing a newly added `sqlite3.connect(...)` to `_token_violations(..., _TOKEN_ALLOWLIST)` returned `()`. Lines 54-60 exempt every token occurrence in an allowlisted file, not only the justified boundary occurrence. | A new production SQLite import or connection in either whole-file production exemption is silently accepted. This directly fails the packet's requirement that lexical/AST allowlists not silently exempt new production SQLite access. | Replace whole-file production exemptions with symbol/occurrence-level structural pins or another bounded manifest that fails when a new SQLite-bearing occurrence is added to an allowed file. Add a mutation canary that inserts a second production occurrence under an existing allowed path. |

## Proposed Fixes Summary

1. Make the human authorization fact load-bearing at the installing API boundary; keep expected DDL identity insufficient by itself.
2. Extend the direct-connection detector to ordinary alias/direct-import forms and prove those forms with mutation canaries.
3. Narrow production lexical exemptions so new occurrences in an already-listed file fail closed.

## Counts and threat-class proposals

- P0: **1**
- P1: **2**
- P2: **0**
- Separate out-of-model threat-class proposals: **0**

## Commands and evidence actually run

- Identity/history: `git remote get-url origin`, branch/revision/tree/parent/ancestor/contains checks, candidate-to-head comparison, and `git diff --find-renames d0887585...f20eddd4`.
- Frozen identities: SHA-256 checks for ADR-026, Core 20, the gate accessor, boundary suite, and setup/anti-self-approval kernel; candidate schema blob check; static AST literal extraction confirmed `SCHEMA_DDL` as 178755 UTF-8 bytes with SHA-256 `2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5`. This extraction did not import or execute the schema module.
- Focused ordinary boundary evidence: `python -B -m pytest -p no:cacheprovider -q tests/execution_core/test_sqlite_boundary.py tests/execution_core/test_persistence_write_capability.py` -> **13 passed**.
- Reconciliation evidence: full ordinary `test_protection_stateful.py` -> **35 passed**; the two changed complete-node performance controls -> **2 passed**. Independent line-event measurements at 16 / 2,048 / 8,192 reproduced incoming `251051 / 252043 / 252173` and revision `256998 / 265219 / 265334`.
- Ordinary collection: default `pytest --collect-only` enumerated only `tests/**`; focused collection of `test_protection_stateful.py` found 35 tests. No `tests_gated` path was imported, collected, or run.
- Full ordinary suite: the first invocation was invalid as candidate evidence because the host's default pytest temp root was inaccessible and caused setup errors. A single clean rerun with a fresh explicit `--basetemp` and Hypothesis storage directory completed with exit 0 and 100%, expected skips, one xfail, and warnings only. It was not repeated.
- Safe failure probes: inert stand-in reproduction for F1; AST alias mutation for F2; allowlisted-production-source mutation for F3. None opened SQLite or executed DDL.
- Static/quality: `git diff --check d0887585...f20eddd4` passed; `ruff check` and `ruff format --check` passed on all ten changed Python files.
- Governance: `.ai-os/scripts/check_install.py`, `check_version_consistency.py`, `check_ledger.py`, and `check_work_order_disposition.py` all passed. The architecture/governance lens separately inspected ADR-026, Core 20 and its three routing edits, Amendments 7-8, CODEOWNERS, live-readiness policy, template, work-order/ledger changes, and the authoritative diff.

## Not verified

- Per the packet prohibition, no `tests_gated` test was imported, collected, or run; changed DDL was not executed; and no file or in-memory database was created in the execution-core lane.
- The catalog digest and R4/R5 SQL-manifest digests were not independently recomputed. Their locked text values were inspected; the schema blob, DDL bytes, and DDL digest were independently verified statically.
- `mypy`, `lint-imports`, the separate conformance oracle, PKL checker, and work-order scope checker were not rerun. The candidate changes no `app/**` file, and the completed ordinary suite plus focused probes were sufficient for this review's central claims.
- GitHub branch-protection settings and live CODEOWNERS enforcement were not verified from the local repository.

## Disproof pass

- **F1:** I tried to disprove the bypass by checking every changed gated call site and direct opener. They do call `require_approved_ddl_execution()` first, and the flag is False. The finding survives because the expected digest is exported as plain data and an ordinary direct `install_schema` call with that value reaches connection use without consulting the flag.
- **F2:** I tried the closest ordinary alternative spelling rather than reflection or dynamic-name evasion. A normal `sqlite3 as db` alias was not classified, and the enclosing gated file's lexical exemption supplies no second control. The finding survives.
- **F3:** I inserted the prohibited token under an already-justified production label. The detector returned no violation, confirming that the exemption is file-wide rather than pinned to the justified occurrence. The finding survives.
- The stale occurrence-replay concern did not survive: accepted occurrence identity includes `evaluation_time`, exact replay now preserves it, and changed context remains conflict-tested. The performance-cap concern did not survive the three-size measurements and failure-capable controls. No separate Core 20 suppression, routing, scope, hash, relocation, or budget finding survived the governance/implementation lenses.

[DONE] STATUS: VERIFIED
