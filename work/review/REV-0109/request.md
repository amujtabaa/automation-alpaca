---
type: Review Request
rev_id: REV-0109
title: Frozen M2 DDL intent, catalog, and bounded execution-plan review
status: AWAITING_REVIEW
targets: [WO-0168c DDL gate, WO-0168d, ADR-026]
human_gated_surfaces: [schema/DDL execution, temporary file database creation]
review_target_commit: 70dc59cb11a8a8f5b9e50c876fb7e5ed0945815c
review_target_tree: f5ee0646d74047d373ce6b09728177453bd45c82
created: 2026-08-28
round: 1 of 2 maximum
---

# REV-0109 — frozen M2 DDL intent and execution-gate review

## Your role and exact boundary

You are the independent review seat. Re-derive the schema intent from the frozen contracts and
the exact source object below. Produce findings only in `result.md`; do not edit this request or
any source, test, contract, ADR, or governance file.

This is a **static catalog/constraint and bounded execution-plan review**. It does not authorize
importing `schema.py`, collecting or running `tests_gated/`, opening SQLite, creating a file or
in-memory database, installing DDL, computing a live catalog, migrating data, changing the human
flag, or implementing a later work order. Source reading, Git-object inspection, AST/literal
extraction without import, hashing, and other no-I/O static checks are permitted.

## Exact candidate and identities — verify; do not trust

- Repository: `https://github.com/amujtabaa/automation-alpaca.git`
- Published preparation branch: `codex/m2-wo0168d-hybrid-r1`
- Exact source candidate reviewed and accepted by REV-0108:
  - commit: `70dc59cb11a8a8f5b9e50c876fb7e5ed0945815c`
  - tree: `f5ee0646d74047d373ce6b09728177453bd45c82`
- The packet is hosted by later documentation-only closeout history. The valid future unlock must
  branch from the exact source candidate above; packet/closeout commits are not unlock parents.
- `app/execution_core/persistence/schema.py`:
  - Git blob: `ef332a0b97d28e0535ac53ea0e4d4e091991abad`
  - file SHA-256: `5dc9fcbed9a60f0b39772093ac7842877a72dd9190de6df2fd579bb384b1d814`
- `SCHEMA_DDL` static literal:
  - UTF-8 bytes: `178755`
  - SHA-256 and `EXPECTED_EXECUTION_DDL_SHA256`:
    `2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5`
- `_SCHEMA_CATALOG_SHA256` expected after installation:
  `c717f6a6c84b37cb13773416c90b50d14f377e39928d7f9c626e769296e632d2`
- `DDL_EXECUTION_AUTHORIZED_BY_AMEEN`: exact boolean `False`.
- R4/R5 SQL-manifest SHA-256 identities:
  - `99aab5f40d43ea5dacce78e77ea47cad250cb9618223d9036a071d8a2704ed39`
  - `4e69ea8bfb077cf0cbbf844b94d58a817ee096e8f802822d0a266c72a5e84525`
- Static mechanical inventory to reproduce independently: 28 tables, 29 indexes, 148 triggers,
  and no view declaration.

## Read order

1. `AGENTS.md`, especially the safety core and independent-review rules.
2. `docs/adr/ADR-026-interim-ddl-gate-threat-model.md`.
3. `work/completed/keep/WO-0168d-m2-i3-5-hybrid-gate-simplification.md`, only its current
   authority, review contract, unlock lifecycle, and exclusions.
4. `work/completed/keep/WO-0166-m2-i2-schema-direct-proof-foundation.md`, for the accepted M2-I2
   schema semantics.
5. `work/queue/M2-EXECUTION-2026-08-21/16-WO-0168C-R5-SQL-MANIFEST.md` and the exact R6 overlay in
   `17-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R6.md`; R7–R20 state that they do not alter SQL or
   DDL, with R20 the final checkpoint-contract overlay.
6. The exact candidate's `app/execution_core/persistence/schema.py`, read as source only.
7. The four files under `tests_gated/execution_core/`, read as source only, solely to judge whether
   the proposed execution can expose the catalog/constraint failures under review.
8. `work/review/REV-0108/result.md`, only to verify the accepted source and closed gate state; do
   not inherit its conclusions about DDL intent, which REV-0108 did not review or execute.

## Closed review questions

Review only these questions:

1. **Catalog identity and install contract.** Does the static DDL define one coherent fresh-file
   catalog, and do the installer checks keep digest, empty-target, foreign-key, recursive-trigger,
   schema-version, and exact-catalog verification distinct and fail closed?
2. **M2-I2 durable authority.** Do keys, foreign keys, uniqueness, checks, and triggers encode the
   accepted profile/application/scope/generation, execution-fact/head, effect/claim/acceptance/
   closure, protection, stream, cursor, and direct-current-proof rules without an impossible
   ordinary path or an evident bypass?
3. **Checkpoint and I4 substrate.** Do payload/current-head atomicity, required indexes, durable
   input identity, semantic keys, decision receipts, outcomes, and broker-outbox rows match the
   frozen non-serving checkpoint and future unit-of-work substrate without creating serving or
   broker authority?
4. **Manifest consistency and boundedness.** Are the current DDL indexes and catalog objects
   consistent with the frozen R4/R5 SQL manifests plus R6's vector-count-only correction, and is
   any required direct lookup evidently missing or contradicted?
5. **Failure-capable held evidence.** By source inspection, do the four held suites use fresh
   `tmp_path` file databases, route opening through the accepted gate, avoid configured and
   `:memory:` databases, exercise both acceptance and refusal paths, and appear capable of
   detecting syntax, catalog, constraint, trigger, directness, repository, and checkpoint faults?
6. **Bounded gate plan.** Is the proposed two-attempt plan below narrow enough to authorize without
   silently authorizing DDL repair, weakened tests, configured data, migration, or later work?

Do not reopen the retired claim that arbitrary Python cannot reach SQLite. A concrete product
schema, constraint, test-evidence, or gate-lifecycle defect remains fully in scope.

## Proposed post-review human gate — review the plan, do not execute it

If this review closes with zero open P0/P1 and Ameen separately approves, Codex will:

1. create a fresh branch from exact candidate
   `70dc59cb11a8a8f5b9e50c876fb7e5ed0945815c`;
2. make one unlock commit whose only source change flips
   `DDL_EXECUTION_AUTHORIZED_BY_AMEEN: Final[bool] = False` to `True`;
3. publish that commit, record its commit/tree, verify a clean tracked worktree and local equals
   origin, then re-verify every identity above before any connection access; and
4. run at most two attempts of the exact held-suite command, each against a distinct fresh
   `--basetemp` directory:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider --tb=short -q --basetemp=.codex-ddl-gate-run/rev-0109-attempt-1 tests_gated/execution_core/test_persistence_schema.py tests_gated/execution_core/test_persistence_directness.py tests_gated/execution_core/test_persistence_repository.py tests_gated/execution_core/test_persistence_runtime_checkpoint_sqlite.py
```

Attempt 2 is the identical command with only
`--basetemp=.codex-ddl-gate-run/rev-0109-attempt-2` changed. It may run only when:

- attempt 1 was interrupted/environmental with no source change; or
- a failure is proven to be test-fixture/test-expectation-only and the correction is confined to
  the five files already under `tests_gated/execution_core/`, preserves or strengthens assertions,
  adds no skip/xfail/broad exception, and receives one fresh static diff check before rerun.

Any DDL byte, `schema.py`, manifest, expected/catalog digest, application/fixture gate, production
repository, or contract change stops this authorization. Any product/schema defect, ambiguity in
failure attribution, second failed attempt, configured path, migration need, or broader scope also
stops. The result returns to Ameen; it does not automatically activate WO-0168.

## Threat model and finite stop rule

- In scope: accidental or non-evasive schema mistakes; contradictory or bypassable durable-state
  constraints; impossible valid writes; missing required rejection; stale/mismatched identities;
  insufficient failure-capable tests; and scope or authorization defects.
- Out of scope: a malicious host owner, deliberate reflective/dynamic guard evasion, hostile
  interpreter replacement, external sandboxing, live trading, credentials, network/broker calls,
  configured databases, migrations, promotion, and later work-order implementation. Record a
  newly supported out-of-model concern as a human threat-class proposal, not an automatic block.
- Permitted evidence: static Git/source/contract proof, no-import AST/literal extraction, hashing,
  and failure-capability reasoning from test source. SQLite execution and live catalog evidence are
  deliberately unavailable until the separate human act.
- A P0/P1 must identify a concrete acceptance/scope violation, in-model counterexample, incapable
  control, manifest/contract contradiction, product data-integrity defect, or unsafe gate plan.
  Preference and speculative hardening are P2 or proposals.
- Maximum two rounds. Round two may examine only confirmed round-one remediations and regressions
  they introduce. The cap never forces acceptance; an unresolved P0/P1 returns for root
  re-diagnosis or human disposition, not a third review packet.

## New-invariant probe obligation

No `INV-*` entry is added or amended by this packet. Fresh invariant-probe lines are therefore not
applicable. Existing safety and durable-state invariants remain binding and may support findings.

## Response contract

Create `work/review/REV-0109/result.md`. For every finding give `file:line`, governing requirement,
evidence level (`reproduced-live` for static commands actually run, `static-reasoning`, or
`unverified`), concrete impact, and the smallest complete resolution. End with:

```text
Verdict: BLOCK | ACCEPT-WITH-CHANGES | ACCEPT
P0: <count>
P1: <count>
P2: <count>
Unverified: <items or none>
```

`ACCEPT` requires zero open P0/P1. State explicitly that no SQLite/database/DDL execution occurred.
