---
type: Work Order
title: "M1.5 broker-role and persistence-boundary alignment candidate"
status: REVIEW
work_order_id: WO-0156
wave: M1.5
model_tier: strong
risk: high
disposition: []
owner: Codex Cloud candidate seat
created: 2026-08-09
branch: work
base_sha: 5eea154f7fbdaa6d77519bdda0edd7ac706f9b5f
implementation_authority: USER_TASK_A_2026-08-09
---

# WO-0156 — M1.5 broker-role and persistence-boundary alignment candidate

`[FABLE • FULL • verification: DIRECT • task: M1.5 Task A candidate]`

## Fable gate

```yaml
fable_gate:
  goal: "Freeze a reviewable overlay decision that keeps Alpaca Paper as the sole beta mutating broker while making M2's durable identity provider-neutral and separating market-data provenance."
  assumptions:
    - claim: "The Task A checkout is the selected launch base."
      status: VERIFIED
      evidence: "git rev-parse HEAD returned 5eea154f7fbdaa6d77519bdda0edd7ac706f9b5f before edits."
    - claim: "ADR-024 is the next unused canonical ADR number."
      status: VERIFIED
      evidence: "The tracked docs/adr inventory ends at ADR-023."
    - claim: "Pure M1 is frozen and M2 remains inactive."
      status: VERIFIED
      evidence: "WO-0152 closeout and its handoff grant no persistence, runtime, broker, schema, or M2 authority."
  approach: "Audit accepted/current text, compare bounded alternatives, draft one schema-neutral overlay and M2 contract, map preservation/supersession at clause level, and freeze exact file hashes for independent review."
  alternatives_considered:
    - "Keep provider literals as permanent table constraints — rejected because it confuses the selected beta profile with the durable identity model."
    - "Build a general multi-broker runtime — rejected as unnecessary authority and safety risk."
    - "Rewrite ADR-020 through ADR-023 — rejected because completed M1 must remain unchanged."
  out_of_scope:
    - "app/**, tests/**, DDL, database creation, M2 implementation, runtime wiring, dependencies, CI changes, broker/network/API activity, credentials, adapters, routing, live trading, and project rename."
    - "Acceptance, exact-hash human ratification, PKL/ledger landing, or M2 activation."
  done_when:
    - behavior: "The candidate contains the audit, alternatives, proposed ADR, contract, roadmap obligations, review request, and exact hashes."
      test: "Static content, hash, scope, and whitespace checks."
      command: "python review packet checks; git diff --check"
    - behavior: "Independent review can issue a findings-only verdict without changing the candidate."
      test: "Review request names the exact immutable candidate paths and hashes."
      command: "sha256sum over the candidate manifest paths"
  blast_radius: "Documentation-only M1.5 candidate and review packet; no accepted authority changes."
  rollback: "Revert the candidate commit; no runtime or external state exists."
```

Docs-only TDD exception: Task A changes planning and proposed architecture records only. Static,
hash, lifecycle, and diff checks replace executable behavior tests.

## Allowed paths

- `work/active/WO-0156-m1-5-broker-persistence-alignment.md`
- `work/review/REV-0062/**`

## Candidate disposition

Task A stops at **READY FOR INDEPENDENT REVIEW**. The proposed ADR is not accepted, M2 is not
active, and no accepted ADR, PKL page, ledger row, application source, test, schema, workflow, or
broker surface is changed. Task C alone may land a human-ratified, independently accepted body and
perform the required lifecycle disposition.

```yaml
evidence:
  phase: FULL_SUITE
  command: "sha256sum candidate paths; git diff --check; AI-OS scope, disposition, ledger, and PKL checks"
  result: PASS
  decisive_output: "Six candidate hashes frozen; no forbidden path touched; static repository checks passed."
```

```yaml
fable_done:
  task: "M1.5 Task A candidate"
  done_when_results:
    - item: "The complete architecture candidate and independent review request are frozen."
      status: MET
      evidence: "REV-0062 contains the audit, matrix, proposed ADR, contract, roadmap, request, and candidate-manifest.sha256."
    - item: "Task A changes no accepted authority or executable surface."
      status: MET
      evidence: "Changed-path inspection is limited to WO-0156 and REV-0062."
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
  debt_check: "Independent review, exact-hash human ratification, Task C landing, and exact-head GitHub Actions remain mandatory."
  deferred:
    - "Independent review result and disposition."
    - "Human exact-hash ratification and accepted Task C landing."
    - "All M2 implementation and later milestone work."
  status: VERIFIED
```
