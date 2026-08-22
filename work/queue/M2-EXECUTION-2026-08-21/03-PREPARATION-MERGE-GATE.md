# Documentation-only M2 preparation merge gate

Status: **NOT AUTHORIZED — CANDIDATE GATE FOR A SAVED STARTING POINT**

## Purpose

The intended merge creates a durable `master` starting point containing accepted M2 planning,
fresh executable work orders through M2 closeout, and conditional M3 preparation. It deliberately
contains no M2 implementation. This lets an experimental local coding LLM work on successor
branches without risking the saved baseline.

## Required pre-merge proof

All conditions must hold at one exact candidate head:

1. The branch descends from accepted `master` and contains the human Gate-B ratification.
2. `WO-0165` is active but explicitly held before implementation; `WO-0166` through `WO-0172` are
   ready specifications only and grant no later-slice authority.
3. The packet binds current source/member/routes, the checkpoint protocol, M2 sequence, M3 entry
   gate, and rollback model.
4. A SHA-256 preparation manifest covers every new preparation artifact and matches exact bytes.
5. The complete branch diff changes no `app/**`, `tests/**`, `migrations/**`, accepted ADR body,
   dependency, workflow, schema, SQL, or runtime file.
6. Repository-native install, ledger, PKL, disposition, scope, context-hygiene, manifest, ancestry,
   and `git diff --check` checks pass with fresh output.
7. Local, tracking, and live-remote candidate heads agree and the worktree is clean.
8. Ameen gives a new exact merge authorization after seeing the candidate commit, tree, manifest,
   changed paths, limitations, layman's summary, and impact.

## Merge effect

The merge would authorize only preservation of the documentation/governance starting point on
`master`. It would not authorize or claim:

- M2-I1 source/test implementation merely by being merged;
- M2-I2 SQL/DDL, schema, migration, or temporary/configured database activity;
- runtime composition, credentials, broker/network calls, orders, serving, promotion, or M3;
- acceptance of any local coding LLM output; or
- merge of an implementation branch.

## Post-merge launch rule

After the exact documentation merge is verified remotely, create
`codex/m2-i1-durable-codec-r1` from that exact `master` head. The first implementation checkpoint
must record the base SHA, regenerate the inventory in `02-CURRENT-SOURCE-INVENTORY.md`, and prove
the target modules/tests are still absent or reconcile the drift before RED work.

No implementation branch is created by this preparation candidate itself.
