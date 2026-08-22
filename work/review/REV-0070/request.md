---
type: Review Request
rev_id: REV-0070
title: M2-I1 immutable durable value and profile codec contract
status: AWAITING_REVIEW
targets: [WO-0165]
human_gated_surfaces: []
commit_range: abcefca80d1a16ae86f7982d27ba6212a9504bfa..35721bf5a980639a18ab12e0383f9f382716ed28
created: 2026-08-21
---

# REV-0070 — independent M2-I1 review request

## Reviewer role and output boundary

You are the independent adversarial review seat, separate from the Ox Alpha local-LLM
implementation seat. Re-derive the candidate from repository bytes and fresh failure-capable
evidence. Follow `AGENTS.md`, `CLAUDE.md`, the active work order, and
`.ai-os/core/15_CROSS_MODEL_REVIEW.md`.

Produce findings only in `work/review/REV-0070/result.md`; do not fix source, tests, governance,
or preparation files. Use `P0`, `P1`, and `P2`. Each finding must identify exact file/line evidence,
why it matters, and the smallest resolution. End with `BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`
and P0/P1/P2 totals. `ACCEPT` requires P0=0 and P1=0.

## Exact reviewed identity

| Item | Exact value |
| --- | --- |
| Work order | `WO-0165` |
| Accepted base commit | `abcefca80d1a16ae86f7982d27ba6212a9504bfa` |
| Accepted base tree | `e52f5e6345049388db1544a164ae99f30e057724` |
| Candidate commit | `35721bf5a980639a18ab12e0383f9f382716ed28` |
| Candidate tree | `a8e95f1d2b0eff31f0709eaa6f7b87c3c653b82a` |
| Candidate parent | `0e97461c65d3594a8b62734d13ba6ba207b8b49a` |
| Candidate branch | `codex/m2-i1-durable-codec-r1` |
| Preparation-manifest SHA-256 at the accepted base | `ec7809b0cdcf17b0e0800ce3b5dd5b7d08145fb25aae974f1e5c923582436d68` |

All conclusions must bind to the candidate commit, not any later review-artifact commit.

## What is under review

The candidate adds the pure, schema-neutral M2-I1 durable codec and immutable ADR-024 profile
contracts, directly necessary tests and import-boundary pins, and the implementation-start
governance records. The exact base-to-candidate path inventory is:

```text
A app/execution_core/durable_codec.py
A app/execution_core/profiles.py
A tests/execution_core/test_durable_codec.py
M tests/execution_core/test_import_boundary.py
A tests/execution_core/test_profiles.py
M work/active/WO-0165-m2-i1-durable-codec-contract.md
M work/queue/M2-EXECUTION-2026-08-21/02-CURRENT-SOURCE-INVENTORY.md
A work/queue/M2-EXECUTION-2026-08-21/04-I1-ACTIVATION-CHECKPOINT.md
```

No SQL/DDL, database creation or access, runtime composition, credentials, broker/network calls,
orders, promotion, M2-I2 or later implementation, or merge to `master` is authorized.

## Read order

1. `AGENTS.md` and the safety core in `CLAUDE.md`.
2. `work/active/WO-0165-m2-i1-durable-codec-contract.md`.
3. `docs/adr/ADR-024-broker-roles-execution-connection-profile.md` and only the linked M1 owners.
4. The two new production modules and their three changed test files.
5. The changed implementation-start governance records and the preparation merge gate.

## Required adversarial lenses

1. Verify every concrete exact M1 identity and required composite/value owner has exactly one
   canonical atom shape and exact owning-type round trip.
2. Attempt malformed version/tag/count/order/type/text/integer/decimal/fraction constructions and
   forged decode paths. Refuse every noncanonical form without silent repair.
3. Verify the public API contains exactly the eight names frozen by WO-0165 and no extra public
   helper, registry, schema object, plugin surface, or runtime facade.
4. Re-derive ADR-024 framing, field order, domain separation, origin/token/version/text/hex rules,
   digest self-exclusion, profile separation, and independent literal known answers.
5. Check that tests exercise the real decisive path and can fail under representative mutations.
6. Check purity, import boundaries, Python 3.11/3.12 compatibility, typing, and unchanged M1 owners.
7. Reconcile every changed governance path against the active work order's post-baseline
   read-only/checkpoint boundary, including any conflicting older preparation instruction.
8. Confirm no human-gated runtime, database, broker, credential, order, promotion, or merge surface
   changed or ran.

## Author evidence to reproduce, not inherit

The implementation seat reported 273 focused tests passing, 1,589 execution-core tests passing
with one skip on CPython 3.12.13, Ruff and mypy clean, repository governance checks clean, and no
database/broker/credential activity. Re-run the smallest failure-capable evidence. Record
environment-caused limitations rather than laundering them into candidate failures or passes.

## Verdict boundary

An `ACCEPT` verdict clears only WO-0165's independent review gate. It does not close the work order
by itself, activate M2-I2, authorize schema/database/runtime work, or authorize merge to `master`.
