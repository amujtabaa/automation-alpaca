---
type: Review Request
rev_id: REV-0106
title: WO-0168d hybrid DDL gate simplification and governance review
status: AWAITING_REVIEW
targets: [WO-0168d, ADR-026, Core 20]
human_gated_surfaces: [changed-DDL execution gate, schema/DB execution policy]
commit_range: d0887585fdb479e83a74909e6d14f3375e0a0850..f20eddd4d060f7506bbbe563761bbf964731275f
created: 2026-08-27
---

# REV-0106 — independent exact-candidate review

## Your role and frozen identity

You are the **independent findings-only review seat**, intentionally separate from the author.
Follow `AGENTS.md`, `.ai-os/core/15_CROSS_MODEL_REVIEW.md`, and
`prompts/INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md`. Re-derive claims from the frozen diff; do not
trust this request's summary. Do not fix code, edit this request, or push. Deposit only
`work/review/REV-0106/result.md` using the repository result template.

- Repository: `https://github.com/amujtabaa/automation-alpaca.git`
- Branch: `codex/m2-wo0168d-hybrid-r1`
- Review base: `d0887585fdb479e83a74909e6d14f3375e0a0850`
- Candidate commit: `f20eddd4d060f7506bbbe563761bbf964731275f`
- Candidate tree: `36f4b028927110cf318c0f2f74108f7f083f8177`
- Authoritative diff: `d0887585fdb479e83a74909e6d14f3375e0a0850..f20eddd4d060f7506bbbe563761bbf964731275f`
- Request-document commits after the candidate are documentation-only and are not part of the
  implementation candidate.

Verify those identities before reviewing. Stop and report an identity mismatch rather than
silently reviewing another tree.

## What changed

WO-0168d replaces a non-converging roughly 12,000-line arbitrary-Python static scanner with the
ratified bounded hybrid gate:

1. Keep the fail-closed runtime authorization accessor and the installer's exact-digest refusal.
2. Relocate the four SQLite/changed-DDL suites to `tests_gated/execution_core/`, outside normal
   pytest collection, while preserving a gate-first rule before every direct connection.
3. Add a small lexical/AST boundary suite and negative canaries.
4. Separate expected DDL identity from Ameen's still-False execution authorization flag.
5. Add CODEOWNERS, ADR-026, live-readiness policy, and a narrowed Core 20 assurance policy.
6. Reconcile two inherited stale test contracts without changing product code: occurrence replay
   now reuses the exact accepted occurrence identity, and bounded complete-node witness costs use
   measured plateau-aware caps.

No `app/**` path changed. The changed-DDL gate remains closed. The four held suites have not been
run, changed DDL has not been executed, and no database was created in the execution-core lane.

Run for the full context:

```text
git diff --find-renames d0887585fdb479e83a74909e6d14f3375e0a0850..f20eddd4d060f7506bbbe563761bbf964731275f
```

## Required read order

1. `AGENTS.md` and `.ai-os/core/15_CROSS_MODEL_REVIEW.md`.
2. `work/active/WO-0168d-m2-i3-5-hybrid-gate-simplification.md`.
3. `docs/adr/ADR-026-interim-ddl-gate-threat-model.md`.
4. `.ai-os/core/20_ASSURANCE_PROPORTIONALITY.md`, plus its routing changes in
   `.ai-os/core/00_START_HERE.md`, `.ai-os/core/03_IN_USE_STRUCTURE.md`, and
   `.ai-os/core/19_AUTONOMY_AND_ESCALATION.md`.
5. Amendments 7 and 8 in
   `work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md`.
6. `tests/execution_core/approved_schema_digest.py`,
   `tests/execution_core/test_sqlite_boundary.py`, and
   `tests/execution_core/test_persistence_write_capability.py`.
7. The four relocated suites under `tests_gated/execution_core/`, by source inspection only.
8. The bounded baseline reconciliations in `test_fill_position.py` and
   `test_protection_stateful.py`.

## Required independent lenses

### A. Implementation and gate integrity

Judge the implementation against WO-0168d and ADR-026. Check at least:

- normal pytest cannot collect any `tests_gated/` test;
- direct invocation of a gated installing fixture would encounter the False authorization gate
  before opening a connection (prove by source/AST; do not invoke the gated test);
- expected identity cannot self-authorize execution;
- the digest-off-by-one control and anti-self-approval control can fail;
- lexical/AST allowlists are explicit and do not silently exempt new production SQLite access;
- the scanner deletion did not remove a protection the ratified replacement promises to retain;
- the two inherited test reconciliations preserve accepted product semantics and retain
  failure-capable controls;
- budgets are met: boundary plus gate code at most 400 SLOC, boundary checks under 60 seconds,
  work order at most 220 lines, and no new meta-code design over roughly 500 SLOC.

### B. Governance and architecture

Review ADR-026 and all `.ai-os` changes independently under `AGENTS.md` and doc 15. **Core 20 may
not be used to restrict findings about Core 20 itself.** Check whether the new policy is properly
scoped, consistently routed, preserves human-gated safety authority, and cannot suppress valid
contract, scope, regression, safety, or data-integrity findings. Treat a governance defect as a
normal finding; do not defer it merely because the implementation tests are green.

## Threat model and finite stop rule

- **In scope:** accidents, ordinary coding mistakes, and non-evasive agent mistakes within the
  repository's normal workflow; unmet work-order criteria; authority/scope violations; in-model
  boundary counterexamples; non-failing named controls; remediation regressions; product safety
  or data-integrity defects; and governance text that weakens any of those protections.
- **Out of scope:** a collaborator deliberately editing around visible controls, malicious host
  ownership, and a requirement to prove arbitrary Python can never reach SQLite. Record such a
  concern as a clearly labeled threat-class proposal for Ameen; it does not block this interim
  gate unless it also demonstrates an in-scope contract, safety, data-integrity, or governance
  defect.
- **Acceptance criteria:** the closed requirements in WO-0168d, ADR-026, the repository safety
  core, and Amendments 7-8. A matching DDL hash, a review verdict, or an agent-written record must
  never authorize changed-DDL execution.
- **Permitted evidence:** reproducible non-gated runtime evidence, source/contract proof, AST or
  lexical counterexamples, mutation evidence, diff/history proof, or another failure-capable form
  appropriate to the claim.
- **Round cap:** at most two review rounds in this packet. Round two examines accepted round-one
  remediations and regressions they introduce. The cap never forces acceptance. An unresolved
  P0/P1 remains an exact blocker and triggers re-diagnosis or human disposition.
- `ACCEPT-WITH-CHANGES` may close WO-0168d only with zero open P0/P1. Residual P2 notes or
  explicitly labeled out-of-model threat proposals are permitted.

Added/amended INV entries: none; fresh-probe obligation: N/A.

## Safety boundary for review commands

Permitted: read-only Git/source inspection; the ordinary pytest suite (which structurally
excludes `tests_gated/`); the focused ordinary boundary tests; ruff, mypy, lint-imports,
conformance, and governance checks if proportionate.

**Forbidden during this review:** running or collecting any `tests_gated/` test; importing or
executing changed DDL to validate it; creating a file or in-memory database in the execution-core
lane; migrations; runtime composition; credentials; network or broker calls; orders; promotion;
merge; force-push; or edits outside reviewer-owned `result.md`.

## Author evidence to reproduce or challenge

All evidence below was collected at candidate `f20eddd4…`; it is evidence input, not authority:

- Focused boundary: `13 passed`.
- Focused accepted protection reconciliation: `24 passed`.
- Two complete-node performance controls: `2 passed`.
- Full ordinary suite: exit 0 and 100%; independent collection counter: `6512` tests collected.
  Expected skips and one xfail remained; `tests_gated/` was not collected.
- Ruff check and format check: clean on every changed Python path.
- mypy: success over `app/` (`95` source files).
- lint-imports: `6` contracts kept, `0` broken.
- conformance oracle: exit 0, `100%`.
- AI Project OS install, version (`v0.9.2`), ledger, PKL, disposition, and scope checks: pass.
- `git diff --check`: pass.
- First restored full-suite run had 10 inherited-baseline failures. The author isolated eight to
  stale `evaluation_time` replay fixtures after accepted occurrence-identity change `d4bcf5c`,
  and two to July caps that predated M2 complete-node direct witnesses. The final full run above
  is the decisive run; review whether the reconciliations are root-contract corrections rather
  than weakened tests.
- Measured line-event witnesses at history sizes 16 / 2,048 / 8,192:
  incoming `251051 / 252043 / 252173`; revision `256998 / 265219 / 265334`. The post-2,048 growth
  is `+130 / +115`, while the revised controls still reject the former roughly 53,000-event
  history scan.

## Locked source identities (do not execute to verify)

- `SCHEMA_DDL` SHA-256: `2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5`
- `SCHEMA_DDL` UTF-8 bytes: `178755`
- `app/execution_core/persistence/schema.py` Git blob:
  `537c6740746611dc18299aa4f7f3a5921774609c`
- `_SCHEMA_CATALOG_SHA256`:
  `c717f6a6c84b37cb13773416c90b50d14f377e39928d7f9c626e769296e632d2`
- R4 SQL manifest SHA-256:
  `99aab5f40d43ea5dacce78e77ea47cad250cb9618223d9036a071d8a2704ed39`
- R5 SQL manifest SHA-256:
  `4e69ea8bfb077cf0cbbf844b94d58a817ee096e8f802822d0a266c72a5e84525`

Relevant frozen file SHA-256 values:

- ADR-026: `3d830df76737236e8f9fd396a331e9ffaa3dff1434d547531f5f8ae3ef9a4bdc`
- Core 20: `2810312c4e48cf0d91c197b16fcf48b51e26ab0824fad8fc6371fbfa9c648470`
- gate accessor: `b76731150ea93da40212376dd64c669641155a27048554e3eef06a3bef8e596e`
- boundary suite: `5512a7eaa990d2d7fa10dfef475905b7d3c426f04090652d9a5fea584ba26521`
- setup/anti-self-approval kernel:
  `dab6baa49bbe46eebe4249b884d10b3cbf12cd11eb2ecfba8cfb5534232daaad`

## Response contract

Create `work/review/REV-0106/result.md` with:

1. verified commit/tree/range and reviewer identity;
2. verdict: `ACCEPT`, `ACCEPT-WITH-CHANGES`, or `BLOCK`;
3. findings only, each with severity, tight `file:line`, reproduced or reasoned evidence, why it
   matters, and what resolves it;
4. explicit P0/P1/P2 counts and separate threat-class proposals;
5. commands actually run and anything not verified;
6. a disproof pass explaining which central claims you tried to falsify;
7. `[DONE] STATUS: VERIFIED` only if the stated review work and evidence are complete. This marker
   does not mean the implementation is accepted unless the verdict says so.

Do not edit `request.md`, implementation, ADR, policy, work order, ledger, or gate record.
