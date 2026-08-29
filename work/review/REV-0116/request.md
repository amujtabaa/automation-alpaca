---
type: Review
review_id: REV-0116
work_order_id: WO-0169
review_mode: fresh-context static pre-implementation architecture review
status: REVIEW
authoritative_candidate: 974198587791454f7fc3ea5dbe0a8d640d22c9ce
---

# REV-0116 — WO-0169 cold startup preflight

Perform one fresh, findings-only pre-implementation review. Re-derive the contract rather than
trusting its prose, but stop at the finite questions below. Do not edit, commit, push, open SQLite,
create a database, install DDL, run held suites, or implement source.

## Exact binding

- Repository: `https://github.com/amujtabaa/automation-alpaca.git`.
- Branch: `codex/m2-wo0169-startup-cold-recovery-r1`.
- Accepted predecessor: WO-0168 closeout
  `c390c1b1de7ee0f88f6c8a3b4419e8fa122aec51`, tree
  `de844054db45d03c73889d986185cab651cbc386`.
- Activation candidate: `974198587791454f7fc3ea5dbe0a8d640d22c9ce`.
- Candidate tree: `e83ff0caeb84c6dfdd7310af7558467e19ec71fb`.
- Active WO blob: `8f3678df71c2ca72eff1b72f52205a2fb54d2089`; file SHA-256
  `40da7dc99fe6e7d8b52f02021918b5fcaac59a5d6700ea7b7a0125d52f89896a`.
- Controlling ADR-023 R1 SHA-256:
  `9a61d4f952079b5f78da7a8f1a17f70dc3099d20fb359596923c5938cc421eaf`, accepted by the
  separate ratification index despite the immutable embedded proposed wording.
- DDL is inherited unchanged at 190,705 bytes / SHA-256
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`; no DDL change is proposed.

## Minimal read order

1. `AGENTS.md` safety/review rules.
2. `work/active/WO-0169-m2-i5-startup-reconciliation-cold-recovery.md` completely.
3. ADR-023 and only its acceptance/R1 sections in
   `docs/adr/ARCH-RESET-2026-07-RATIFICATION.md`.
4. `work/completed/keep/WO-0168-m2-i4-atomic-unit-of-work-effects.md` terminal contract.
5. Only the relevant current seams in `persistence/unit_of_work.py`, `repository.py`,
   `operations.py`, `checkpoint_codec.py`, and `protection.py`.

## Threat model and finite questions

In scope: trusted application startup after crash/restart; accidental stale/forged local proof;
second-owner/lease loss; unknown prior dispatch outcome; source replay/buffering/fence ambiguity;
crash at each phase; history growth; and fake/injected capability misbehavior. Out of scope: host or
trusted-source compromise, real lock/adapter implementation, credentials/network, warm-exact
optimization, DDL, M3, and broad redesign of accepted M1/M2 predecessors.

1. Is the cold-only choice compatible with ADR-023 and sufficient to deny service rather than
   accidentally claiming warm authority?
2. Does owner evidence gate the first connection/query/stream access and remain process-lifetime
   authority through the final serving transition?
3. Can current repository/checkpoint seams prove identity, scope totality, effects/claims/owners/
   acceptance/closure, and bounded history without a new DDL table or hidden scan?
4. Is the private startup-invalidation UOW bridge a valid system lifecycle transition that keeps
   the public eight-operation union frozen, persists owner/checkpoint state atomically, and grants
   no external-input receipt/effect/dispatch bypass? If not, identify the exact accepted clause it
   violates and the smallest root correction.
5. Does targeted effect reconciliation forbid blind resend and require complete exact coverage
   before service?
6. Do subscription acknowledgement, source-authoritative `F`, strict retained-cursor advance,
   exclusion of `<=F`, baseline-at-`F`, and post-commit verification preserve every controlling
   ADR-023 cold-restart ordering rule?
7. Are the public types/ports and allowed paths the minimum coherent implementation surface, with
   no generic callback/registry/framework or missing necessary path?
8. Are CR-01 through CR-19 independently failure-capable and sufficient for the named acceptance
   criteria, including crash and unrelated-history stress?

Report only demonstrated contract/architecture/safety/scope defects. Do not promote preferences or
alternate feature ideas to findings without a reproducible counterexample or exact accepted-clause
conflict. End:

```text
Verdict: BLOCK | ACCEPT-WITH-CHANGES | ACCEPT
P0: <count>
P1: <count>
P2: <count>
Unverified: <exact list or NONE>
```

`ACCEPT` requires zero open P0/P1. This preflight stops after one result; any accepted finding is
reconciled once at the contract boundary before implementation.
