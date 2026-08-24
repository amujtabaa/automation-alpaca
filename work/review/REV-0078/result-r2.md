# REV-0078 independent review result — round 2

Date: 2026-08-24
Reviewer seat: Codex, independent findings-only review
Repository: `https://github.com/amujtabaa/automation-alpaca.git`
Author branch: `codex/claude-opus-m2-wo0168c-r1`
Review base: `344c32b`
Frozen implementation candidate: `ce5cb38d5b2fe38d957252df21d5f0a0889801fc`
Candidate tree: `5d2f7d2925c4f2d855fd1ae7161588420a600ec0`
Reviewed range: `344c32b..ce5cb38d5b2fe38d957252df21d5f0a0889801fc`
Canonical-request commit: `3b26c1cd636615cf0d85c13951eaebf099b88bdc` (documentation only after the candidate)

The original reviewer-owned `result.md` remains unchanged. This `result-r2.md` is the one additional review pass allowed by the packet protocol.

## Verdict

**BLOCK — P0=1, P1=6, P2=2.**

The remediation closes several R1 findings, but the exact changed-DDL gate is still mechanically open and bypassable before the separately required execution approval. Pure counterexamples also show that cross-family and acquisition-slot binding remain partial, blanket reconciliation omission accepts missing mandatory rows, the machine-readable scope gate still fails, and the bounded-plan/mutation proof is incomplete.

## Findings

### P0-1 — The exact changed-DDL execution gate remains open and has two approval sources

- **Locations:** `work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md:16,115-128`; `work/review/REV-0078/request.md:20-37,100-110`; `tests/execution_core/approved_schema_digest.py:1-15`; `tests/execution_core/test_persistence_schema.py:1-10,32-34,67-94`; `tests/execution_core/test_persistence_write_capability.py:1015-1050`.
- **Requirement:** changed DDL must remain non-executable until Ameen approves the exact candidate commit/tree, DDL identity/size, and named fresh-file commands. The R1 resolution required one externally transcribed approval source and a failure-capable anti-self-approval control.
- **Evidence (`reproduced-live`, no database):** the request calls `approved_schema_digest.py` the “single transcribed source,” but `test_persistence_schema.py` retains a second non-`None` `_GATE_DIGEST` and installs through `_require_gate_open()`. Its header still says there is standing authority to revise DDL and execute without another hash pause, contrary to the active work order and canonical request. The new AST control rejects only the literal spelling `approved_ddl_sha256=schema_ddl_digest()`: `digest = schema_ddl_digest(); install_schema(..., approved_ddl_sha256=digest)` produces no violation. The eight write-capability tests pass despite both bypasses. The current candidate has not yet received the separately requested execution approval.
- **Impact:** a SQLite-bearing suite can be run before the exact gate decision, and a helper/alias/local variable can restore self-approval while the claimed guard stays green. The disposition’s claim that P0-1 is fixed is not reproducible.
- **Required root correction:** separate static candidate identity from execution authorization. Route every installing fixture through one positive-provenance gate source and keep its execution state deny-by-default until the exact human decision. After approval, use one bounded unlock commit. Make the static control enumerate every `install_schema` call and require the exact central approval accessor/source; add helper, alias, local-computation, duplicate-literal, and alternate-source mutants. Do not run SQLite while making this correction.

### P1-1 — Cross-family binding still accepts foreign scope, leg, request, and reconciliation provenance

- **Locations:** `app/execution_core/persistence/checkpoint_codec.py:1982-2006,2074-2110,2437-2481,2571-2597`.
- **Requirement:** R15 §2 and R17 §1 require every reached row to equal its complete proof-selected relationship, including full keys and scope/lineage coordinates.
- **Evidence (`reproduced-live`, pure objects):** the exact candidate accepted (1) a selected owner with the same effect ID but a foreign request occurrence in its effect scope; (2) a selected root correlation carrying a foreign symbol, request occurrence, and a `VenueLegKey` from another account because only effect ID, order ID, and application generation are compared; and (3) a foreign-effect reconciliation when a closure names the same input before coverage. In case (3), `_reference()` retains the closure’s `effect=None`, never promotes the later known coverage effect, and therefore skips the effect comparison. This reviewer independently reproduced the foreign-account leg, foreign-symbol scope, and closure-first foreign-effect cases.
- **Impact:** an otherwise authentic checkpoint can seal mutually inconsistent selected effect, owner, correlation, and reconciliation provenance.
- **Required root correction:** compare the complete selected effect, owner, route, scope, full `VenueLegKey`, request occurrence, application/generation/profile, and observation relationships—not a chosen subset of scalar IDs. Duplicate input references must accumulate known coordinates (including promoting `None` to a later known effect) and reject every disagreement. Add the reproduced same-ID/different-associated-coordinate cases as direct controls.

### P1-2 — Acquisition slots can encode a descriptor/currentness different from the by-effect descriptor

- **Locations:** `app/execution_core/persistence/checkpoint_codec.py:3740-3798,3801-3838,3868-3925`.
- **Requirement:** R16 §2 makes current acquisition scope maps exact, and R17 requires exact application/scope cross-binding.
- **Evidence (`reproduced-live`, pure objects):** an authentic MSFT descriptor/active pair installed under the selected AAPL scope key was accepted while the by-effect map retained the authentic AAPL descriptor for the same effect ID. The slot and descriptor rows therefore carried different descriptor commitments. An authentic currentness row with a foreign application generation was also accepted because line 3830 checks only `position_scope`. The slot reference keeps only `(effect_id, position_scope)`, discarding the descriptor commitment needed to prove the by-scope and by-effect maps resolve to the same object.
- **Impact:** one checkpoint can contain slot, descriptor, and currentness rows that are each authentic but do not represent one acquisition authority.
- **Required root correction:** carry the slot descriptor commitment into descriptor resolution and require exact equality with the by-effect descriptor. Validate currentness application generation and its generation/binding coordinates against the selected slot and permit. Add cross-map descriptor-commitment and foreign-currentness-generation controls through the full slot encoder.

### P1-3 — Blanket omission accepts missing mandatory reconciliation evidence

- **Locations:** `app/execution_core/persistence/checkpoint_codec.py:2577-2586,3024-3032`; `app/execution_core/recovery.py:1237-1275`; `app/execution_core/venue.py:3661,6382-6397,12643-12653`.
- **Requirement:** R15 §2 permits unreferenced history to be omitted but requires missing selected referenced rows to fail.
- **Evidence (`reproduced-live`, pure objects and producer trace):** the new `continue` arms correctly allow an ordinary applied fill and initial bootstrap input to lack reconciliation, but they also accepted (1) broker coverage with a revision head and `mapping_exact=False` after its required revision reconciliation was removed, and (2) a refreshed bootstrap target whose distinct catch-up `checkpoint_input_id` had no execution-reconciliation outcome. The producers install those records atomically, and full venue validation requires the revision reconciliation.
- **Impact:** checkpoint creation can silently discard mandatory quarantine or registry-transition evidence and emit an apparently complete restart candidate.
- **Required root correction:** classify each reference by producer semantics. Initial applied-fill evidence and an initial bootstrap input may be optional; an inexact revision head and a distinct refreshed catch-up input must resolve or fail. Add mandatory-row deletion mutants for both families alongside the legitimate-absence controls.

### P1-4 — The released-path amendment is invisible to the canonical scope checker

- **Locations:** `work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md:17-61,139-161`; `.ai-os/scripts/check_work_order_scope.py:22-49`.
- **Evidence (`reproduced-live`):** the amendment lists paths only in a Markdown table, while the checker reads frontmatter `allowed_paths`. Against `344c32b..ce5cb38`, it still fails nine paths: `approved_schema_digest.py`; the repository, directness, and write-capability tests; gate records 35 and 36; and all three top-level `FINDING-*.md` files.
- **Impact:** the exact candidate fails the repository’s enforceable scope gate, contrary to the P1-5 disposition.
- **Required root correction:** add the nine authorized paths (or appropriate exact globs) to frontmatter `allowed_paths`, then rerun the canonical checker against the immutable range.

### P1-5 — The bounded-plan proof remains fail-open and omits contract-required negative controls

- **Locations:** `tests/execution_core/test_persistence_runtime_checkpoint_sqlite.py:29-66,1392-1525`; `work/queue/M2-EXECUTION-2026-08-21/14-WO-0168C-R4-SQL-MANIFEST.md:182-197`; `work/queue/M2-EXECUTION-2026-08-21/16-WO-0168C-R5-SQL-MANIFEST.md:367-378`.
- **Evidence (`reproduced-live` plus static contract comparison, no SQLite):** `INDEXED BY` now resolves, but valid SQL still resolves fail-open: a `RIGHT JOIN` reports `RIGHT` instead of the first table, `NATURAL JOIN` reports `NATURAL`, and a comma source omits the second table; `USING` is likewise accepted as an alias. A planner `SCAN` under any omitted real name is skipped. Separately, R4/R5 require at least 10,000 unrelated rows per populated base family, per-base alias/index assertions, hard-index removal failures, and reachable plan-level `NOT INDEXED` mutants. Those tests are not authored: the candidate has only a small foundation, a generic `SEARCH` assertion, and a string-parser `NOT INDEXED` case.
- **Impact:** the gate cannot prove either that current plans stay bounded under history or that its assertion fails for the intended unbounded regression.
- **Required root correction:** stop deriving safety-critical plan names with an expanding keyword denylist. Store authoritative base table/alias/index expectations beside each frozen query (or use a complete fail-closed parser), and drive one reusable plan predicate with the required scale, index-removal, and `NOT INDEXED` mutants. Author these tests now but execute them only after the DDL gate.

### P1-6 — The claimed nine-guard mutation sweep is incomplete

- **Locations:** `work/review/REV-0078/disposition-r1.md:24-35`; `app/execution_core/persistence/checkpoint_codec.py:2002-2006,2097-2109,2228-2234,2285-2297,2471-2481`.
- **Evidence (`reproduced-live`, pure mutation pass):** all 114 pure tests remained green when independently disabling seven new refusal branches: missing selected-owner effect, missing root route, missing route effect, same-leg/different-effect collision, broker coverage coordinate binding, human coverage coordinate binding, and human corroboration/root binding.
- **Impact:** material cross-family authenticity regressions survive the focused suite, so the request’s “nine caught mutants” completion claim is not reproducible.
- **Required root correction:** add one direct negative control per guard, vary every `RootFillKey` coordinate independently across fact/head/human/corroboration, and publish an exact guard-to-test mutation map with executable commands.

### P2-1 — The gate bundle’s current-status prose contradicts its superseding amendment

- **Location:** `work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md:3,201-205,277-305`.
- **Evidence (`static-reasoning`):** the opening status and database-activity section say no database action occurred, while Amendment 2 records changed-DDL runs against both `tmp_path` and `:memory:` databases and correctly marks them noncompliant.
- **Impact:** a reader can mistake superseded prose for the current audit truth.
- **Required root correction:** add a prominent supersession banner and make the top-level current status say that prior scratch runs occurred but are noncompliant and unusable.

### P2-2 — Evidence summaries are not literal Windows-reproducible commands

- **Locations:** `work/review/REV-0078/disposition-r1.md:38-47`; `work/review/REV-0078/HANDOFF.md:147-158`; `work/review/REV-0078/request.md:112-121`.
- **Evidence (`reproduced-live`):** `PYTHONPATH=. python ...` is POSIX assignment syntax and does not execute as written in PowerShell; `pytest ...checkpoint_sqlite.py` contains a placeholder; and `ruff check · mypy ...` is a result summary rather than a command.
- **Impact:** another Windows reviewer cannot reproduce the packet verbatim.
- **Required root correction:** record literal PowerShell commands with the exact interpreter path, test path/node ID, flags, and environment assignment.

## Verification evidence

Executed against the frozen candidate in an isolated worktree without opening SQLite:

- Candidate/tree/base, 29 commits, 22 changed paths: verified.
- `SCHEMA_DDL`: 178,755 UTF-8 bytes; SHA-256 `2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5`; catalog digest `c717f6a6c84b37cb13773416c90b50d14f377e39928d7f9c626e769296e632d2`.
- Runtime-checkpoint pure suite: **114 passed**.
- Write-capability/static gate suite: **8 passed**.
- Import-boundary suite: **6 passed**.
- Pure `INDEXED BY` parser control: **1 passed**.
- R2 conformance oracle: exit 0 with `PYTHONPATH` set correctly for PowerShell.
- Ruff check/format: clean on 11 changed Python files.
- Mypy: success on 95 source files.
- Import Linter: 6 contracts kept, 0 broken.
- Install, version (`0.9.2`), ledger, PKL, and disposition checks: passed.
- Exact-range `git diff --check`: clean.
- Canonical work-order scope check: **failed on nine paths** (P1-4).
- Focused pure counterexamples: foreign correlation leg/scope and closure-first foreign reconciliation all accepted; additional fresh lenses reproduced the owner, acquisition-slot/currentness, and mandatory-reconciliation cases above.

Intentionally not run: every SQLite-bearing test, schema installation, EXPLAIN plan, configured or in-memory database, migration, runtime composition, credentials, broker/network call, order path, stateful suite, broader repository suite, and 24-hour soak. The repository record of Ameen’s R16 manual-rule ratification was treated as governing authority; its external conversation provenance was not independently inspected.

## Gate disposition

Do not approve or execute the current DDL gate packet. Resolve every P0/P1 at the owning contract boundary using pure/static work only, keep the execution gate mechanically closed, and freeze a new exact candidate. Because this packet has now used its one additional critique round, the next independent exact-head review should use a fresh `REV-0079` packet and preserve both REV-0078 reviewer results unchanged. Only a new P0=0/P1=0 verdict should return the immutable DDL identities and named fresh-file commands to Ameen for execution approval.
