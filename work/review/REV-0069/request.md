---
type: Review Request
rev_id: REV-0069
title: Fresh M2 documentation-only Gate-A regeneration
status: AWAITING_REVIEW
targets: [WO-0164, M2-REGENERATION-2026-08-21]
human_gated_surfaces: [M2 persistence planning, future schema and database planning, obsolete branch retirement]
commit_range: 177ea5fcd959b9e7d7d5a3172070f90f89ece963..fd7a5ec0319547145acb6a349d95fd5ce99f604c
created: 2026-08-21
---

# REV-0069 — independent clean-room review request

## Your role and output boundary

You are the independent adversarial review seat. You did not author this candidate. Re-derive the
result from the exact current authority and candidate bytes; do not continue the author's reasoning
or treat author-recorded validation as proof. Follow `AGENTS.md`, `CLAUDE.md`, and the
`adversarial-reviewer` protocol. Produce findings only and do not implement fixes.

Write only `work/review/REV-0069/result.md`. Do not edit this request, the candidate, work order,
ledger, ADR, PKL, source, test, schema, or any other file. Use `P0`, `P1`, and `P2`; every finding
must give an exact file:line, evidence level (`reproduced-live` or `reasoned-only`), why it matters,
and the smallest resolution. Separate unverified checks. End with exactly one verdict:
`BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`, followed by P0/P1/P2 totals. `ACCEPT` requires
P0=0/P1=0.

## Exact reviewed identity

| Item | Exact value |
| --- | --- |
| Accepted base commit | `177ea5fcd959b9e7d7d5a3172070f90f89ece963` |
| Accepted base tree | `99338a7832509645f17ed4f51c511e7dffb6c41f` |
| Activation commit | `d1380e0529a95ae04997c24c6d793d00ca765ec2` |
| Candidate commit | `fd7a5ec0319547145acb6a349d95fd5ce99f604c` |
| Candidate tree | `cb88dddeb8bd50cfd5e921030a7012456695ac73` |
| Candidate branch | `codex/m2-regeneration-gate-a-r1` |
| Candidate manifest | `work/queue/M2-REGENERATION-2026-08-21/AUTHORITY-MANIFEST.sha256` |
| Candidate manifest SHA-256 | `e59b2d70f1511a741372a3ee01d0c8feb07d68ea60a0e583a64b300da0f83d4c` |
| Obsolete comparison commit | `c9b27dca6236606b3792dfc75c6418fd735be6cb` — non-authoritative, not an ancestor |
| Completed human overlay SHA-256 | `32adab8c1e4e3d92610ef1e33628f1ef5e1664d873c91db190ab44b4aff39947` |

The candidate manifest covers exactly five semantic files and excludes itself to avoid a hash
cycle. Verify its recorded hashes rather than trusting this request.

## Read order

1. `AGENTS.md` and `CLAUDE.md`.
2. `work/active/WO-0164-m2-regeneration-gate-a.md`.
3. `docs/adr/ARCH-RESET-2026-07-RATIFICATION.md`; ADR-020 through ADR-024; and
   `pkl/architecture/architecture-map.md`, `pkl/architecture/testing-model.md`.
4. The five manifest-covered files in `work/queue/M2-REGENERATION-2026-08-21/`.
5. The completed human overlay at
   `G:/dev-hdd/Automation_Alpaca_Research_Program_v1.1.0/11_Run_Artifacts_PENDING/CODEX_CONTINUATION_2026-08-20/frozen/AGGREGATE/11_HUMAN_DECISION_PACKET.md`.
6. Only if needed to disprove a comparison claim, the exact quarantined tar and handoff paths named
   in the candidate. Do not use obsolete c9 prose as accepted authority.

## Changed-file boundary

The exact base-to-candidate change inventory should be eight paths: active WO-0164, append-only
ledger activation, five candidate files, and the self-excluded manifest. No source, test, ADR, PKL,
schema, migration, dependency, workflow, runtime, database, broker, or credential file may differ.

Use:

```text
git diff --name-status 177ea5fcd959b9e7d7d5a3172070f90f89ece963..fd7a5ec0319547145acb6a349d95fd5ce99f604c
git diff --check 177ea5fcd959b9e7d7d5a3172070f90f89ece963..fd7a5ec0319547145acb6a349d95fd5ce99f604c
git merge-base --is-ancestor 177ea5fcd959b9e7d7d5a3172070f90f89ece963 fd7a5ec0319547145acb6a349d95fd5ce99f604c
git merge-base --is-ancestor c9b27dca6236606b3792dfc75c6418fd735be6cb fd7a5ec0319547145acb6a349d95fd5ce99f604c
```

Expected ancestry exits are 0 for accepted master and 1 for c9. Reproduce them.

## Required adversarial lenses

1. **Authority routing:** verify accepted ADR status comes from the ratification index, including
   accepted ADR-024, while embedded proposed/draft labels remain provenance. Research and human
   acceptance must add no implementation, readiness, trading, merge, or promotion authority.
2. **Safety truth:** only first-occurrence canonical `FILL` and valid predecessor-linked,
   broker-authoritative `TRADE_CORRECT`/`TRADE_BUST` revisions may change economics. Status,
   receipts, projections, and acknowledgements must not. One writer and existing pure semantic
   owners must survive.
3. **Architecture:** attempt to find a second engine/store/writer/controller/profile, history-fold
   startup, caller-built authority, split transaction, blind retry, mutable profile, or hidden
   currentness inference. Check all accepted ADR-020 through ADR-024 conjunctions, not isolated
   slogans.
4. **Cold restart:** verify strict post-ack `F > retained cursor`, exact no-cursor exception,
   baseline-first at `F`, buffered `<=F` exclusion, source-authoritative fence, invalidation,
   unsupported-source non-serving, and terminal exhaustion remain one coherent sequence.
5. **Schema-neutrality:** find any SQL/DDL, parser/execution claim, selected relation/trigger/index,
   SQLite pragma, configured database access, migration, runtime composition, or implementation
   authority hidden in the planning language.
6. **Research reconciliation:** verify the 20 `O-*` rows and 8 `N-*` rows are unique, total for the
   bounded comparison, and each has exactly one legal class. Check that every retained old semantic
   item traces to current accepted authority rather than c9 authority.
7. **Human decisions:** verify non-trade financial facts remain excluded/quarantined pending later
   policy; numeric risk remains unselected and human-owned; `PKG-MIN -> PKG-HARD -> conditional
   PKG-ADV`; no comparison, specialist, procurement, or provider selection is introduced.
8. **Evidence honesty:** every experiment/runtime/schema/restore/soak/R16 claim must remain
   `NOT_RUN`, `NOT_EVALUATED`, `UNKNOWN`, or `NOT_READY` as applicable. Author static checks cannot
   substitute for runtime evidence.
9. **Comparison defect:** independently examine whether the input manifest's tar row is malformed
   at 63 hexadecimal characters, whether two separate frozen handoffs bind the actual 64-character
   digest, and whether all six valid inner rows plus the 89-row stream can be reproduced. Reject any
   unrecorded waiver or authority gain.
10. **Retirement safety:** attempt to disprove that every useful c9 semantic item is preserved in
    accepted authority or the successor. Review the exact retirement gate for ref targeting,
    worktree cleanliness, successor publication, unrelated-ref stability, and post-delete absence.
    Do not delete either branch during review.

Perform a bottom-up disproof pass after the first findings pass: actively construct the strongest
counterexample to each would-be `ACCEPT` conclusion and say which checks could not be reproduced.

## Author evidence to reproduce, not inherit

The author reports:

- manifest grammar/inventory/hash/UTF-8/LF checks passed for five rows;
- matrix totals are 20 old plus 8 new, with `KEEP=8`, `REWRITE=6`, `DROP=6`, `NEW=8`;
- 18 isolated in-memory mutations were rejected, covering manifest omission/truncation, matrix
  duplication/omission/invalid classes, ADR-024 status laundering, false readiness, stale identity,
  provider/specialist work, SQL, unsafe economics, second writer, cold-sequence omission, and c9
  ancestry/hash reuse;
- the quarantined contract's canonical stream reproduced at exactly 89 rows and SHA-256
  `95e826f2ce22aa3125ce258a457ea22ea9f7dc529be2d7386b11c324d3cda5ed`;
- `check_install.py`, `check_ledger.py`, `check_pkl.py pkl`,
  `check_work_order_disposition.py`, `check_work_order_scope.py`, and `git diff --check` passed; and
- context hygiene reported zero violations and eight pre-existing advisory size findings.

Re-run the smallest failure-capable checks. A validator that only notices changed hashes is not
sufficient for semantic mutations. Record actual commands/results and exact hashes reviewed.

Full pytest, Ruff, mypy, import-linter, configured-database checks, broker/network checks, and runtime
tests are intentionally not review requirements for this documentation-only candidate and must not
be represented as PASS.

## New-invariant probe declaration

Accepted `INV-*` entries added or amended by this candidate: **none**. This packet proposes no
accepted invariant or ADR change. Nevertheless, fresh mutation probes are required for the safety,
cold-restart, authority-status, matrix-totality, and no-implementation pins above; record at least
one independently executed rejection in each applicable family.

## Verdict boundary

`ACCEPT` means only that this exact documentation-only Gate-A packet is fit to reach the recorded
retirement gate and then stop at
`READY_FOR_HUMAN_M2_REGENERATION_RATIFICATION — GATE B`. It does not authorize M2 implementation,
schema/DDL, a database, broker/credential activity, provider selection, promotion, or merge to
`master`.
