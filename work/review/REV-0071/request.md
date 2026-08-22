---
type: Review Request
rev_id: REV-0071
title: M2-I2 schema and direct-current-proof foundation
status: IN_REVIEW
targets: [WO-0166]
human_gated_surfaces: [schema]
commit_range: 6a8477d51d38eb4575d88395e3b57493d03b6812..28c2c43deaaa5721c58c1a30d17d149486167de0
created: 2026-08-22
---

# REV-0071 — fresh M2-I2 adversarial review request

## Reviewer role and output boundary

Re-derive the exact candidate from repository bytes and fresh failure-capable evidence. Follow
`AGENTS.md`, `CLAUDE.md`, the active work order, and
`.ai-os/core/15_CROSS_MODEL_REVIEW.md`. Produce findings only; do not fix source, tests, or
governance. Each P0/P1 finding must identify exact file/line evidence, a counterexample or decisive
mutation, why it matters, the smallest root resolution, and whether it was reproduced live or
reasoned from source. `ACCEPT` requires P0=0 and P1=0.

The human decision owner explicitly authorized Codex to use direct verification plus multiple
fresh adversarial agents for this closeout instead of returning the candidate to Ox Alpha or a
separate external model. This packet records that authorized process honestly; it does not
mislabel an in-process adversarial agent as protocol-independent cross-model review.

## Exact reviewed identity

| Item | Exact value |
| --- | --- |
| Work order | `WO-0166` |
| Inherited Ox Alpha v4 commit | `6a8477d51d38eb4575d88395e3b57493d03b6812` |
| First Codex checkpoint | `b284beaa627f3a150148f007ea21b3764c651509` |
| Final candidate commit | `28c2c43deaaa5721c58c1a30d17d149486167de0` |
| Final candidate tree | `5420633c47daece2bb789b2fc85b19c76abeac6e` |
| Candidate branch | `codex/m2-i2-schema-direct-proof-codex-r1` |
| `SCHEMA_DDL` UTF-8 length | `72,373` bytes |
| `SCHEMA_DDL` SHA-256 | `46d486a01c9c2b93cd39024c7376df39a23e78ccf3f0d17b6239aa00b8423a66` |

All findings bind to the final candidate commit. Later review-artifact commits are not part of the
reviewed production/test tree.

## Exact candidate paths

```text
M app/execution_core/persistence/schema.py
M tests/execution_core/test_persistence_schema.py
M work/active/WO-0166-m2-i2-schema-direct-proof-foundation.md
```

## Required adversarial lenses

1. Canonical-fact-only durable economics and exact current-head authentication.
2. Application/profile/scope/generation ownership and secret-free external identity.
3. Fact/revision completeness, nonbranching lineage, and exact replacement behavior.
4. Effect/claim/owner/acceptance/closure authority, including every insert/update bypass.
5. Market stream, cursor, source profile, session, protection, and generation binding.
6. SQLite NULL/FK/trigger/recursive-trigger/upsert semantics and atomic installation.
7. Canonical origin/version constraints and failure-capable negative controls.
8. Direct-query plan coverage, public API exactness, inert import boundary, and work-order scope.

## New-invariant probe statement

No accepted `INV-*` registry entry was added or amended in this work order. The new schema-native
FR-1 through FR-8 constraints are nevertheless probed by fresh negative tests, mutation controls,
temporary-file execution, and the three adversarial lenses above.

## Author evidence to reproduce, not inherit

- 50 schema tests and 32 import-boundary tests passed independently.
- The complete 1,658-test `tests/execution_core` suite passed after an earlier full run exposed and
  forced removal of a forbidden production `sqlite3` import.
- Ruff/check-format, mypy over 91 source files, six import contracts, scope, and whitespace checks
  passed.
- Every schema test used a fresh pytest `tmp_path` file database; no configured/in-memory database,
  migration, runtime composition, credentials, broker/network call, order, promotion, or merge ran.

## Verdict boundary

An `ACCEPT` verdict clears only the user-authorized adversarial gate for this exact WO-0166
candidate. It does not activate M2-I3, authorize a configured database or migration, authorize any
runtime/broker/order surface, or authorize merge to `master`.
