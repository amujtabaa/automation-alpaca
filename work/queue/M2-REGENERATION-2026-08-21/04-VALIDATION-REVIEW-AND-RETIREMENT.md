# Validation, independent review, and exact retirement contract

Status: **CANDIDATE — EXECUTE BEFORE GATE-B CLAIM**

## Static acceptance checks

The candidate must pass all of these on its exact review commit:

1. Every manifest token is lowercase 64-character hexadecimal; every named candidate file exists,
   hashes exactly, is UTF-8 without BOM, uses LF, and ends in one newline.
2. `02-KEEP-REWRITE-DROP-NEW-MATRIX.md` has exactly 20 unique `O-*` rows and eight unique `N-*`
   rows. Every row has exactly one class from `KEEP`, `REWRITE`, `DROP`, `NEW`.
3. Accepted repository ADR hashes match the authority table and the ratification index records the
   accepted status of ADR-020 through ADR-024.
4. The original human form and current human overlay remain separately bound; the aggregate
   manifest still contains the original row and is not rewritten.
5. The six extracted files match their valid inner rows; the tar matches both independent correct
   64-character handoff bindings; the malformed 63-character tar row is reported, not repaired or
   silently accepted.
6. The `G|` stream independently reproduces 90 prefixed lines, one excluded header, 89 canonical
   rows, 12,724 UTF-8/LF bytes, and SHA-256 `95e826f2...`.
7. The successor descends from accepted master `177ea5f...`; c9 is not an ancestor; no c9 commit or
   file was imported.
8. No file outside WO-0164 allowed paths changed; `git diff --check`, AI-OS install, ledger, PKL,
   disposition, context, and work-order scope checks pass where applicable.
9. Negative text scans find no activation of `REV-0067`, `WO-0159` through `WO-0163`, D2-A, D4-A,
   Stage 3, ADR-025, old candidate hashes, provider comparison, specialist engagement, M2
   implementation, false PASS, promotion, or master merge.
10. Any unavoidable mention of an obsolete identity appears only in explicit negative provenance,
    reconciliation, or retirement scope and cannot be parsed as an active identity.

## Traceability map

| Candidate center | Primary authority | Frozen research/decision effect |
| --- | --- | --- |
| Fact truth and one writer | Safety core; ADR-020; ADR-022 | R01/R03/R10/R16 and S01/S02 preserve authority/refusal/failure gates |
| Direct lineage/controller/protection | ADR-020/021; accepted M1 handoff | R01/R03/R07/R08; no second controller, policy merge, or inferred lineage |
| Profile and market-source separation | Accepted ADR-024; ADR-023 | R02/R04/R15/R18; inherited Alpaca Paper only, no new provider selection |
| Atomic unit/claim/outbox | ADR-020/022; historical semantic clauses only | R01/R02/R03/R12/R15; timeout ambiguity and no blind retry |
| Cold restart | ADR-023 C01-C12; CR-01-CR-19 | R03/R04/R12/R15/R16; exact source capability/currentness and failure evidence |
| SQLite target and restore | Ratification index; architecture/testing PKL | R01/R10/R15/R16; sole beta store, no second hand-coded engine, target evidence `NOT_RUN` |
| Economic-fact quarantine | Completed human overlay | Prepare later policy/ADR; no execution-fact extension or silent cash mutation now |
| Numeric-risk hold | Completed human overlay; S02-F01 | Ameen owns future policy; no invented limit or readiness gain |
| Package/order sequence | Research roadmap plus human overlay | `PKG-MIN -> PKG-HARD -> conditional PKG-ADV`; no M9/FUTURE/provider comparison |
| Readiness/soak/expiry | Final research review and S02/S04 | `NOT_READY`, open findings, R16 not evaluated, experiments not run, costs unknown |

## Required failure-capable document mutations

Run each mutation in memory or an isolated temporary copy and prove the real validator rejects it;
restore exact candidate bytes after every case:

| Mutation | Required rejection |
| --- | --- |
| Remove one candidate file or manifest row | Exact inventory/hash gate fails |
| Change one manifest nibble or use a 63-character digest | Digest grammar or hash gate fails |
| Duplicate or omit one `O-*`/`N-*` row | Matrix identity/count/uniqueness gate fails |
| Give one matrix row two classes or an unknown class | Classification grammar fails |
| Mark ADR-024 conditional/unratified | Ratification/authority consistency gate fails |
| Treat embedded proposed ADR text as current status | Ratification-index consistency gate fails |
| Replace `NOT_RUN`, `NOT_EVALUATED`, `UNKNOWN`, or `NOT_READY` with PASS/zero/ready | Authority-laundering scan fails |
| Activate old WO/REV/ADR-025/D2-A/D4-A/Stage-3 identity | Stale-identity scan fails |
| Add provider comparison, Webull/M9 implementation, specialist engagement, or procurement | Human-decision and scope scan fails |
| Add SQL/DDL/parser/database/runtime/broker/credential/implementation authority | Forbidden-authority scan fails |
| Permit status/receipt/projection to change economics | Safety-fact invariant scan fails |
| Permit a second writer/store/controller/profile or history-fold startup | Architecture refusal scan fails |
| Omit strict `F > cursor`, no-cursor exception, baseline-first, buffered exclusion, or unsupported-source refusal | Cold-restart conjunction scan fails |
| Claim c9 ancestry/import or reuse a c9 candidate hash | Ancestry/stale-hash gate fails |

Passing prose without these negative controls is insufficient.

## REV-0069 independent seat

The review request freezes:

- exact base, candidate commit, tree, branch, and changed-file inventory;
- all candidate file hashes plus manifest hash;
- the current human-overlay hash and controlling research/ADR hashes;
- exact commands and decisive outputs for hashes, matrix, negative controls, ancestry, scope, and
  governance; and
- the malformed external tar-row defect and corrected proof path.

The reviewer reads the packet and current authority directly, re-runs the smallest failure-capable
checks, performs a bottom-up disproof, and writes findings only to `work/review/REV-0069/result.md`.
The author does not edit the review result. `ACCEPT` requires P0=0/P1=0; any semantic remediation
requires a new candidate manifest, commit, and focused fresh review. At most two remediation rounds
are allowed.

## Exact obsolete-branch retirement gate

Delete local and live-remote `codex/m2-planning-preflight-r1` only when all are freshly true:

1. the completed human decision remains exact and the active WO-0164 authority remains unchanged;
2. all five surfaces and the 89-row stream are verified as recorded;
3. the reconciliation and candidate are frozen and `REV-0069` independently returns `ACCEPT`,
   P0=0/P1=0;
4. no indispensable material exists only on the obsolete branch—every retained semantic item is
   present in accepted authority or this successor packet;
5. live local/remote obsolete refs still equal
   `c9b27dca6236606b3792dfc75c6418fd735be6cb`;
6. the obsolete ref is not checked out in any worktree, its worktree state has no unpreserved user
   changes, and the current successor worktree is clean;
7. the successor branch is committed, normally pushed, and proven to descend from accepted master
   and not c9;
8. an exact pre-delete inventory freezes every unrelated local branch, remote-tracking ref, and
   worktree; and
9. the user's recorded authorization for exact local/remote retirement remains the only deletion
   authority used.

Retirement executes only exact named local/remote deletion. It does not create a tag, bundle, or
replacement archive and does not prune, clean, rewrite, force-push, or touch another ref/worktree.

## Retirement evidence

After deletion, record:

- exact pre-delete local and live-remote target identities;
- exact successor branch/head/tree/base and remote presence;
- exact local target absence;
- exact live-remote target absence from a fresh non-mutating query;
- unchanged unrelated local/remote ref inventory;
- unchanged worktree inventory and final clean status; and
- accepted comparison/review hashes proving the old branch had no indispensable sole material.

If any check fails, leave the target untouched and return to the owning gate. No broad substitute
command is allowed.

## Terminal condition

Only after independent acceptance, exact retirement evidence, and atomic governance closeout may
the packet state become:

`READY_FOR_HUMAN_M2_REGENERATION_RATIFICATION — GATE B`

This state is planning evidence only. It does not authorize implementation or merge.
