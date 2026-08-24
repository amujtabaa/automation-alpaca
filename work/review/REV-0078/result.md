# REV-0078 independent review result

Date: 2026-08-24
Reviewer seat: Codex, independent findings-only review
Repository: `https://github.com/amujtabaa/automation-alpaca.git`
Author branch: `codex/claude-opus-m2-wo0168c-r1`
Review base: `344c32b`
Reviewed candidate: `5d3df2b6b69ff00e82e1d56db72a2993a8461dfd`
Candidate tree: `bd427a39f75239130a4e518c27cd6e8ddd2b9ec7`
Reviewed range: `344c32b..5d3df2b6b69ff00e82e1d56db72a2993a8461dfd`

## Verdict

**BLOCK — P0=1, P1=7, P2=3.**

The candidate has substantial good implementation and test work, but it is not eligible for the changed-DDL gate or WO-0168c closeout. The blocking causes are a crossed human gate, several accepted cross-family identity splices in checkpoint projection, one acquisition authority cross-scope splice, a bypassable query-plan control, incomplete mutation proof, out-of-scope paths, unresolved accepted-contract conflict, and a stale/noncanonical review request.

## Findings

### P0-1 — Changed DDL was installed and exercised before the exact human gate

- **Locations:** `work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md:16,115-128`; `work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md:93-149,198-214,228-270`; `tests/execution_core/test_persistence_repository.py:44-50`; `tests/execution_core/test_persistence_directness.py:28-34`; `tests/execution_core/test_persistence_runtime_checkpoint_sqlite.py:69-95`; `tests/execution_core/test_persistence_schema.py:32-34`.
- **Requirement:** the active work order prohibits every changed-DDL install and SQLite-bearing test until Ameen approves the exact candidate commit/tree, DDL SHA-256, UTF-8 byte count, and named fresh-file plan. It also prohibits in-memory databases.
- **Evidence (`reproduced-live` and repository record):** the gate record reports runs against changed DDL and says the installer ran against both `tmp_path` and `:memory:` databases before it requests authorization. The later amendment ratifies `_GATE_DIGEST` after those runs. Three other SQLite fixtures authorize installation using `schema_ddl_digest()` computed from the DDL being installed, so the caller and artifact approve themselves. The current artifact is 178,755 UTF-8 bytes with SHA-256 `2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5`; catalog digest `c717f6a6c84b37cb13773416c90b50d14f377e39928d7f9c626e769296e632d2`; `schema.py` blob `074cd47b49747b4fad740d736f7a0becebcfc682`. The original pre-execution packet was bound to the earlier `faa964e` candidate and did not bind this changed artifact by exact byte count and approved command list.
- **Impact:** the database evidence cannot satisfy the project's human-gated schema assurance. Post-hoc approval and self-derived approval tokens make a future accidental DDL change executable without a genuinely independent authorization.
- **Required resolution:** supersede the inaccurate gate record; explicitly mark the prior `tmp_path`/`:memory:` runs noncompliant and unusable as gate evidence; remove self-derived caller approval; and use one literal, externally transcribed approved digest. First resolve every static/pure finding below and freeze a new exact candidate. Then return its commit, tree, DDL SHA-256, UTF-8 bytes, catalog digest, SQL-manifest identity, and exact fresh-file-only commands to Ameen. Do not execute changed DDL until that new gate is explicitly approved.

### P1-1 — Same-key rows can splice foreign owner/effect/account relationships into an authenticated checkpoint

- **Locations:** `app/execution_core/persistence/checkpoint_codec.py:1984-1999,2062-2069,2178-2188,2230-2245,2502-2515,2938-2955`.
- **Requirement:** R15 requires missing, stale, cross-scope, and cross-family referenced rows to fail; R17 requires reached records to be deeply equal to the proof-selected relationship, not merely share a convenient scalar ID.
- **Evidence (`reproduced-live`):** isolated pure probes accepted: (1) a selected effect whose same-leg owner carried a foreign effect/observation relationship; (2) a selected root whose correlation came from a foreign effect/owner relation; (3) broker coverage from a foreign account with the same `root_fill_id`; and (4) reconciliation from a foreign effect when input/leg happened to match. The code checks `owner.leg_key`, `entry.root_key`, or only `root_fill_id`; reconciliation checks input plus leg/scope but not the selected effect/route relationship that admitted it.
- **Impact:** a checkpoint can seal internally authentic records that do not belong to one coherent selected execution history. Restoration would preserve the wrong economics or authority provenance under a legitimate selected key.
- **Required resolution:** propagate the complete proof-selected relation through each encoder and compare full keys and ownership coordinates: selected owner observation/effect/root relation; acquisition correlation route/effect/owner; full `RootFillKey` including broker/environment/account; and reconciliation effect/route plus leg/scope. Add same-key/different-associated-identity refusal mutants for every repaired family.

### P1-2 — Acquisition slots do not bind an authentic descriptor to the selected application/scope

- **Locations:** `app/execution_core/persistence/checkpoint_codec.py:3728-3769,3777-3817`.
- **Requirement:** R17 requires exact application/profile/scope cross-binding, and R20 permits descriptor history only after every reached current row is tied to the selected slot.
- **Evidence (`reproduced-live`):** a complete authority projection for a selected MSFT slot accepted an authentic descriptor permit for AAPL when the effect ID was used as the bridge. `_encode_runtime_checkpoint_acquisition_slot_value()` authenticates the row, while the outer loop verifies only `currentness.position_scope`; descriptor resolution later checks only `permit.effect_id` against the descriptor index.
- **Impact:** the checkpoint can attribute a real acquisition authorization for one symbol/account scope to another selected scope.
- **Required resolution:** carry the selected `(application_generation_id, position_scope, effect_id)` coordinates into slot/descriptor resolution and require the permit and active/currentness records to match all of them. Add authentic cross-scope and cross-generation negative controls.

### P1-3 — The bounded-query proof ignores a valid unaliased `INDEXED BY` source

- **Locations:** `tests/execution_core/test_persistence_runtime_checkpoint_sqlite.py:29-66,1439-1455`.
- **Evidence (`reproduced-live`):** `_base_table_plan_names("SELECT effect_id FROM venue_effect INDEXED BY ix_name", base_tables)` returns `{"INDEXED"}` instead of `{"VENUE_EFFECT"}` because `INDEXED` is parsed as an alias and is absent from `_SQL_KEYWORDS_AFTER_SOURCE`. A planner detail `SCAN VENUE_EFFECT ...` is then skipped at lines 1450-1452.
- **Impact:** an unbounded table/index scan can pass the very test intended to prove count-bounded direct selection.
- **Required resolution:** parse SQLite's `INDEXED BY` and `NOT INDEXED` source clauses explicitly while retaining the base-table name and any real alias. Add a failing mutation/negative control using an unaliased forced index and an intentionally unbounded plan.

### P1-4 — Four new refusal branches have no failure-capable tests despite the handoff's mutation claim

- **Locations:** `app/execution_core/persistence/checkpoint_codec.py:2414,2508,2857,2945`; `work/review/REV-0078/HANDOFF.md:161-162`.
- **Evidence (`reproduced-live` branch-deletion check and static search):** the suite does not directly exercise duplicate fill-reconciliation input on different legs, absent selected fill reconciliation, duplicate execution-reconciliation input on different scopes, or absent selected execution reconciliation. Deleting/bypassing those branches survives the current focused suite. The handoff says every new refusal is mutation-checked.
- **Impact:** missing/duplicate selected-state controls required by the work order can regress without a test failure, and the stated mutation evidence is not reproducible.
- **Required resolution:** add direct missing-row and duplicate-reference tests for both reconciliation families, demonstrate that removing each guard makes its named test fail, and correct the evidence claim to name the exact mutations and commands.

### P1-5 — Seven changed paths are outside the active work order's allowed paths

- **Locations:** `work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md:17-61` and the range's changed-path list.
- **Evidence (`reproduced-live`):** the canonical scope check rejects `tests/execution_core/test_persistence_directness.py`, `tests/execution_core/test_persistence_repository.py`, `tests/execution_core/test_persistence_write_capability.py`, `work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md`, and the three top-level `work/review/FINDING-*.md` files. The active list names none of them.
- **Impact:** the candidate cannot pass the repository's scope gate, and unrelated test/governance changes are not traceable to the recorded authority.
- **Required resolution:** either amend the active work order under valid authority to name each necessary path and rationale, or segregate/revert the out-of-scope changes. Re-run the canonical changed-path scope check against the exact final range.

### P1-6 — R15 and R16 conflict on whether unreachable historical manual rows are legal

- **Locations:** `work/queue/M2-EXECUTION-2026-08-21/26-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R15.md:52-62`; `work/queue/M2-EXECUTION-2026-08-21/27-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R16.md:7-9,35-49`; `app/execution_core/persistence/checkpoint_codec.py:3509-3545`; `work/review/REV-0078/HANDOFF.md:183`.
- **Evidence (`reasoned-only` from accepted text/code):** R16 says it does not replace R15 §3, where discovered manuals must equal both current-index map cardinalities and no older manual row is retained. R16 §2 nevertheless says `_manual_by_id` may retain older unreachable IDs that projection omits. The implementation follows the latter rule and the handoff acknowledges the unresolved conflict. Manual flatten is a human-gated safety surface, so the author cannot silently choose between accepted authorities.
- **Impact:** the final checkpoint contract is ambiguous: the same state is required to fail under R15 §3 and pass under R16 §2.
- **Required resolution / human decision:** explicitly supersede the conflicting R15 sentences. Recommended decision: adopt R16's reachable-current rule—checkpoint the one current manual reached from each selected scope and omit older unreachable `_manual_by_id` history, while retaining strict refusal of stale/cross-scope current links. In plain terms, save the current manual action, not every obsolete one. This keeps checkpoint creation possible with the append-only historical map; retaining R15's exact-map rule would require redesigning lifecycle/storage so old manual IDs are actually removed or archived.

### P1-7 — The author-owned review request does not freeze the candidate that was reviewed

- **Locations:** `.ai-os/core/15_CROSS_MODEL_REVIEW.md:23`; `work/review/REV-0078/request-r1.md:5-13,101-118`; `work/review/REV-0078/HANDOFF.md:12-19`.
- **Evidence (`reproduced-live`):** the canonical protocol requires `request.md`. REV-0078 contains `request-r1.md`; its latest amendment binds `344c32b..2082e4ed...`, tree `d4d3ddd...`. Actual head is `5d3df2b...`, tree `bd427a39...`, with six later commits including material repository/test changes. HANDOFF substitutes mutable `HEAD` for an immutable final identity.
- **Impact:** future reviewers cannot prove which artifact the author requested them to approve, particularly across changed-DDL and human-gated boundaries.
- **Required resolution:** author a canonical `request.md` that freezes the new post-remediation head/tree, exact base/range, commit list, changed paths, DDL identities, test evidence, and known limitations. Do not use mutable `HEAD` as the authority identity.

### P2-1 — Reconciliation superset code cites the wrong contract section

- **Locations:** `app/execution_core/persistence/checkpoint_codec.py:2482-2492,2922-2930`; corresponding assertions near `tests/execution_core/test_persistence_runtime_checkpoint_pure.py:3208`.
- **Evidence (`reasoned-only`):** R16 §2 classifies authority maps, not venue reconciliation indexes. R15 §2 is the controlling selected-reference rule. The implemented omission behavior may be defensible, but the cited authority is not.
- **Impact:** a future maintainer can extend the wrong “authenticated superset” exception to a family it never authorized.
- **Required resolution:** cite the exact governing R15/R20 text and state why unreachable append-only venue reconciliation history is omitted without weakening selected-reference completeness.

### P2-2 — Reproduction evidence names unsupported or incorrect commands/paths

- **Locations:** `work/review/REV-0078/HANDOFF.md:151-158`; `work/review/FINDING-preexisting-suite-floor-2026-08-24.md`.
- **Evidence (`reproduced-live`):** direct `python tests/r2_conformance_oracle.py` fails with `ModuleNotFoundError: No module named 'app'`; the supported pytest invocation passes. The floor record names `tests/test_import_boundary.py`, while the file is `tests/execution_core/test_import_boundary.py`.
- **Impact:** a fresh reviewer following the packet cannot reproduce the claimed evidence verbatim.
- **Required resolution:** record the exact working commands and paths that pass in the supported environment.

### P2-3 — The exact diff is not whitespace-clean

- **Location:** `work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md:274`.
- **Evidence (`reproduced-live`):** `git diff --check 344c32b..5d3df2b` reports a new blank line at EOF.
- **Impact:** the candidate does not satisfy a basic handoff hygiene check.
- **Required resolution:** remove the extra blank line and record a clean exact-range `git diff --check`.

## Verification evidence

Reproduced against the exact candidate above on CPython 3.12.13 unless noted:

- Focused checkpoint/schema/repository/directness/write-capability tests: **479 passed**, 0 failed, 0 skipped.
- Focused import-boundary checks: **6 passed**; the separate known suite-floor boundary test below remains red.
- `ruff check --no-cache` on changed Python paths: clean.
- `ruff format -n --check` on changed Python paths: clean.
- `mypy app/`: success, 95 source files.
- `lint-imports`: 6 contracts kept, 0 broken.
- Governance checks passing: install, version consistency (`0.9.2`), ledger, PKL, and work-order disposition.
- Work-order scope check: **failed** on the seven paths listed in P1-5.
- `tests/r2_conformance_oracle.py`: passes through pytest; direct script invocation from the packet fails as described in P2-2.
- `tests/test_wo0113_repair_scaling.py`: 13 passed.
- Broader non-stateful suite: started with 6,793 collected tests excluding the five stateful files; stopped after 34% because completion time was disproportionate to the already-blocking result. Exactly three failures appeared before the stop and no additional failure appeared through 34%.
- Direct rerun of those three documented floor tests: **3 failed** — both fill-position scaling assertions and `test_production_modules_cannot_reach_private_acceptance_closure_seams` (`checkpoint_codec.py:3045:AcceptanceProof`). The candidate's floor record attributes all three to base `344c32b`; this seat verified their candidate behavior but did not rerun the base commit.

Not verified in this seat: the five long stateful suites were not run; `check_fable_done.py` was not applicable without its required transcript argument; no configured database, migration, credentials, broker/network call, order path, runtime composition, or external conversation record was accessed.

## Gate disposition

Do not approve the current DDL identity and do not close WO-0168c. Claude may perform static/pure remediation inside corrected recorded scope, but no changed-DDL install or SQLite-bearing test should run. After all P0/P1 root corrections and a canonical exact-head request exist, obtain a fresh independent exact-head review. If that review reaches P0=0/P1=0, return the new immutable DDL gate packet to Ameen for the separately recorded fresh-file execution approval.
