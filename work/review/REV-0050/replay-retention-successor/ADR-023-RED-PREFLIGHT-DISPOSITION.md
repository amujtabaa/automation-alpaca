# ADR-023 replacement RED critical pre-flight and disposition

Date: 2026-08-04

Target: `f528b5dd59a415413e010bb6015364d0094512c4`

Authority: accepted ADR-023 SHA-256
`898DA71EA959ED8B6F343DA23795E3E52D7DB94D8BAD255FDAC13475CED0F259`

Scope: read-only static pre-build review of the replacement RED map. No tests, application code,
database, SQL/DDL, network, broker, Alpaca, runtime, merge, deletion, or cleanup activity occurred.

## Initial result

Verdict: **ACCEPT-WITH-CHANGES**

- P0: 0
- P1: 4
- P2: 2

The reviewer found:

1. a causality conflict between production remaining unchanged, absent target interfaces, and the
   requirement that every deep semantic control prove independent failure capability;
2. an incomplete classifier matrix that omitted exact-current replay/conflict precedence while
   baseline-required;
3. collapsed exhaustion coverage that did not isolate all three triggers or non-triggering maximum
   secondary watermarks;
4. Python 3.11 grammar/AST compatibility deferred too late;
5. a shallow boundedness proof that could miss a reachable `_PersistentKeyMap`; and
6. recovery-fence wording that risked claiming M2 runtime provenance in M1.

## Accepted root disposition

No interface-only production scaffold or authority widening will be used. The replacement contract
must instead couple each production-facing semantic assertion/table/oracle to executable test-local
positive and single-rule-negative controls. Current production may fail at its explicit missing
ADR-023 structural prerequisite, but evidence must label that path
`STRUCTURALLY RED — SEMANTIC PATH NOT REACHED`. The mechanically shared oracle must independently
reject its named test-local mutant before freeze, and every material rule must later receive a
named production mutation fail/restore control after GREEN.

The RED map now additionally requires:

- the full serving/baseline-required/exhausted route/projection/epoch/coordinate/identity table,
  including exact-current precedence and exact disposition/alert/state deltas;
- independent strict-coordinate-max, committed-epoch-max, and increment-from-max exhaustion cases,
  plus maximum evaluation/source-time non-trigger controls and terminal behavior;
- pre-freeze Python 3.11 grammar and used-AST-API compatibility;
- recursive exact-type boundedness that rejects `_PersistentKeyMap` and any reachable variable-
  cardinality market collection, with a map-reintroduction mutant; and
- negative public/call-graph controls against caller-authored baseline, recovery-fence,
  subscription, or restart-provenance authority. Runtime fence provenance remains M2-only.

## Follow-up determination

The reviewer confirmed this bounded resolution satisfies ADR-023's pre-production “RED controls
must prove” language if the immutable candidate verifies the mechanically coupled controls, labels
unreached production semantics honestly, and has zero new P0/P1. Under those conditions the
reviewer would return pre-build `ACCEPT` for the RED contract only. It would not accept production,
M2 recovery-fence provenance, WO-0148 closeout, or any later slice.

## Post-repair material delta addendum

The replacement controls were implemented with application code unchanged. Successive functional-
conformance passes found eleven material P1 classes in total: four commitment/invalidation/scaling
gaps, three bounded-annotation/constructor/helper-binding gaps, and four retained-field,
authenticity, repeated-reset, and state-leaf gaps. Every finding was reproduced, repaired at its
owning test boundary, and retained as a failure-capable control. No P0 was found.

The final materiality-scoped current-worktree review returned **ACCEPT**, P0=0, P1=0, P2=0. It
confirmed the exact canonical 15-argument state commitment, complete optional-cursor authenticity
mutations, two authenticated branch-reset cycles in both bounded histories, the deterministic exact
state inventory, the fixed state-leaf allowlist, the 12-case invalidation projection matrix, and
the canonical SHA/constructor/four-binding seals.

Fresh classification is 504 tests: 410 intentional production-facing failures, 94 executable
controls passing, zero errors, and zero skips. The separately preserved predecessor corpus passes
745/745. Exact commands, hashes, static/governance results, and boundaries are recorded in
`ADR-023-RED-PRE-FREEZE-EVIDENCE.md`.

This addendum accepts only the current-worktree pre-freeze contract. Production semantics remain
`STRUCTURALLY RED — SEMANTIC PATH NOT REACHED`. An immutable candidate commit and fresh independent
exact-commit ACCEPT with zero unresolved P0/P1 remain mandatory before any production edit.
