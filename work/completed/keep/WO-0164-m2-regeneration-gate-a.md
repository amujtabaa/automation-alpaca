---
type: Work Order
title: Fresh M2 authority reconciliation, Gate-A regeneration, and obsolete-branch retirement
status: CLOSED
work_order_id: WO-0164
wave: M2-REGENERATION-GATE-A
model_tier: strong
risk: high
disposition: [RESULT_SUMMARY_KEPT, ARCHIVED]
owner: Codex
created: 2026-08-21
branch: codex/m2-regeneration-gate-a-r1
review_id: REV-0069
execution_authority: Ameen Mujtabaa activated this documentation-only successor in the Codex task on 2026-08-21, authorized fresh identities, one bounded quarantined-evidence inspection, and exact local/remote retirement of codex/m2-planning-preflight-r1 only after its recorded gate; no M2 implementation or master merge is authorized.
---

# Work Order: Fresh M2 Gate-A regeneration and obsolete-branch retirement

`[FABLE • FULL • verification: DIRECT plus INDEPENDENT • task: documentation-only M2 authority reconciliation, regeneration planning, and exact obsolete-branch retirement]`

## Goal

Produce one fresh, hash-bound M2 Gate-A planning candidate from accepted `master` and the ratified
research overlay, obtain independent P0=0/P1=0 review, retire only the exact obsolete M2 branch
after its gate, and stop at human Gate B without implementing M2.

## Context packet

Read only these first:

- `AGENTS.md`
- `CLAUDE.md`
- `docs/adr/ARCH-RESET-2026-07-RATIFICATION.md`
- `docs/adr/ADR-020-current-state-execution-kernel.md`, `docs/adr/ADR-021-position-protection-liquidity-execution.md`, `docs/adr/ADR-022-reset-beta-scope-cutover-governance.md`, `docs/adr/ADR-023-bounded-market-occurrence-authority.md`, and `docs/adr/ADR-024-broker-roles-execution-connection-profile.md`
- `pkl/architecture/architecture-map.md` and `pkl/architecture/testing-model.md`
- `G:/dev-hdd/Automation_Alpaca_Research_Program_v1.1.0/11_Run_Artifacts_PENDING/CODEX_CONTINUATION_2026-08-20/frozen/AGGREGATE/11_HUMAN_DECISION_PACKET.md`
- `G:/dev-hdd/Automation_Alpaca_Research_Program_v1.1.0/11_Run_Artifacts_PENDING/CODEX_CONTINUATION_2026-08-20/handoffs/M2_REGENERATION_2026-08-21/01_M2_DISPOSITION_AND_RETIREMENT.md`
- `G:/dev-hdd/Automation_Alpaca_Research_Program_v1.1.0/11_Run_Artifacts_PENDING/CODEX_CONTINUATION_2026-08-20/handoffs/M2_REGENERATION_2026-08-21/02_SUCCESSOR_WORK_ORDER_DRAFT.md`
- `G:/dev-hdd/Automation_Alpaca_Research_Program_v1.1.0/11_Run_Artifacts_PENDING/CODEX_CONTINUATION_2026-08-20/post_research_reconciliation_input/m2-planning-preflight-r1-c9b27dc/README.md` and its adjacent `INPUT_MANIFEST.sha256`

## Fable gate

```yaml
fable_gate:
  goal: "Regenerate a documentation-only M2 Gate-A candidate from accepted authority and ratified research, independently accept it, and retire only the obsolete c9 branch."
  assumptions:
    - claim: "The human research decision is validly complete."
      status: "VERIFIED at overlay SHA-256 32adab8c1e4e3d92610ef1e33628f1ef5e1664d873c91db190ab44b4aff39947"
    - claim: "Accepted master is 177ea5fcd959b9e7d7d5a3172070f90f89ece963 with tree 99338a7832509645f17ed4f51c511e7dffb6c41f."
      status: "VERIFIED locally and by non-mutating live-remote query before activation"
    - claim: "All five comparison surfaces are available and hash-verifiable."
      status: "TO VERIFY before semantic use"
    - claim: "The obsolete branch contains no indispensable unpreserved material."
      status: "TO VERIFY through one bounded comparison plus independent review"
  approach: "Hash-verify the five surfaces; classify each M2-relevant old item KEEP/REWRITE/DROP/NEW against accepted authority and frozen research; derive a new candidate from accepted master; freeze and independently review; retire the exact obsolete branch; stop at Gate B."
  out_of_scope:
    - "Application, test, migration, schema, SQL/DDL, runtime, configured database, dependency, or CI behavior changes"
    - "Broker, credential, provider, vendor, account, procurement, order, serving, or capital activity"
    - "M1/M1.5 reopening, c9 resume/merge/cherry-pick, old candidate-hash reuse, REV-0067, or master merge"
  done_when:
    - "All five surfaces are exact-byte and hash-bound; the 89-row stream count and full digest are independently reproduced"
    - "Every bounded old M2 item is classified exactly once as KEEP, REWRITE, DROP, or NEW with authority evidence"
    - "A fresh M2 Gate-A candidate and external manifest receive independent ACCEPT with P0=0/P1=0"
    - "The successor is proven to descend from accepted master and not from c9"
    - "The exact obsolete local and live-remote branches are absent after retirement, with no unrelated ref/worktree change"
    - "Governance records close atomically at READY_FOR_HUMAN_M2_REGENERATION_RATIFICATION — GATE B"
  blast_radius: "Documentation/governance records, one fresh planning branch, one review packet, read-only quarantined comparison evidence, and exact retirement of one named obsolete branch."
```

## Allowed paths

```yaml
allowed_paths:
  - work/active/WO-0164-m2-regeneration-gate-a.md
  - work/completed/keep/WO-0164-m2-regeneration-gate-a.md
  - work/queue/M2-REGENERATION-2026-08-21/**
  - work/review/REV-0069/**
  - work/ledger.jsonl
  - pkl/architecture/architecture-map.md
```

Read-only external authority and evidence are limited to the exact research/handoff paths in the
context packet and the single manifest-bound quarantined tar after its hash gate passes.

## Forbidden paths and actions

```yaml
forbidden_paths:
  - app/**
  - tests/**
  - migrations/**
  - .github/workflows/**
  - pyproject.toml
  - constraints.txt
  - docs/adr/**
```

- No application/server startup, configured-database access, SQL/DDL, broker/API/network activity,
  credentials, procurement, orders, capital, or provider/vendor/platform/model selection.
- No c9 resume, merge, branch parent, wholesale cherry-pick, candidate-hash reuse, REV-0067,
  force-push, history rewrite, broad prune/clean, master merge, or unrelated ref/worktree change.
- Do not edit the original aggregate manifest or treat the post-freeze human overlay as covered by
  its original decision-packet row.

## Required behavior

- [x] Preserve original decision-packet SHA-256 `0ff73c46...` and bind the ratified overlay
  `32adab8c...` separately.
- [x] Verify the quarantined tar and input manifest before listing or extraction.
- [x] Acquire exact bytes for WO-0158b, the 89-row authority stream/inventory, the cold-restart
  contract, ADR-023, and ADR-024; reproduce the stream count and digest independently.
- [x] Reconcile only M2-relevant authority once using `KEEP / REWRITE / DROP / NEW`.
- [x] Preserve every `NOT_RUN`, `NOT_EVALUATED`, refusal, negative finding, and
  `NOT_READY / HOLD_ALL_PROMOTION` state.
- [x] Produce a new documentation-only candidate from accepted current authority without reusing
  c9 candidate hashes or treating old prose as accepted.
- [x] Freeze all candidate inputs/outputs under an external SHA-256 manifest and obtain separate
  independent `REV-0069` review. Any semantic edit requires rehash and re-review.
- [x] Retire only `codex/m2-planning-preflight-r1` after every gate in the recorded retirement
  document passes; verify exact local/live-remote absence and unrelated-ref stability.
- [x] Stop at `READY_FOR_HUMAN_M2_REGENERATION_RATIFICATION — GATE B`.

## Validation

- [x] SHA-256 verification for every controlling input, comparison surface, candidate file, and
  review result.
- [x] Independent reproduction of the canonical `G|` stream: exactly 89 rows and digest
  `95e826f2ce22aa3125ce258a457ea22ea9f7dc529be2d7386b11c324d3cda5ed` or a recorded failure.
- [x] Static traceability: every candidate statement maps to current accepted authority or a frozen
  Rxx/Sxx decision/hold.
- [x] Negative scan rejects stale c9 candidate hashes, REV-0067 activation, implementation
  authority, false PASS language, provider selection, and promotion gain.
- [x] Git ancestry proves the successor descends from accepted master and does not descend from c9.
- [x] `git diff --check` and repository-native AI Project OS install/scope/disposition checks pass.

## Review and remediation

- `REV-0069` is review-only and uses the `adversarial-reviewer` protocol in a fresh seat.
- The author does not review their own work. Findings only are deposited in `result.md`.
- At most two semantic remediation rounds are allowed. A third same-root P1 or unresolved P0
  returns to the human without branch retirement.

## In-flight FIX-01 — malformed quarantined-tar manifest row

```yaml
fable_fix:
  symptom: "The first INPUT_MANIFEST.sha256 token is 63 hexadecimal characters and cannot equal any SHA-256 digest."
  root_cause: "The row omits one `b` at offset 46 relative to the actual tar digest; the manifest file itself remains exact-hash-bound and must not be rewritten."
  evidence: "Manifest token f163ac6cca5a1dbebdf17d585bb9dfa3e2bd4197f048fbafa1364ac69ab4604 (63 chars); actual tar and independently frozen 01/03 handoff binding f163ac6cca5a1dbebdf17d585bb9dfa3e2bd4197f048fbbafa1364ac69ab4604 (64 chars)."
  fix: "Preserve the malformed external manifest as negative evidence; gate the container against the identical 64-character digest independently recorded in both frozen handoff artifacts, then verify every extracted surface against its valid 64-character entry row."
  regression_test: "Reject non-64-character SHA tokens, require the tar to match both independent handoff bindings, and require all six manifest-bound inner-file digests plus the 89-row stream digest to reproduce."
  red_green_verified: true
  attempt: 1
```

## Autonomy and escalation

- Ordinary reversible documentation/governance work inside `allowed_paths` is authorized.
- The user pre-authorized exact local and remote obsolete-branch retirement only after the recorded
  gate; no repeat permission is required when the gate is proven.
- Relevant in-flight root corrections may proceed only when documentation-only, reversible, and
  necessary to this exact outcome. Material architecture, implementation, external, credential,
  financial, or other-ref scope remains excluded.

## Acceptance criteria

- [x] Required behavior and validation are freshly evidenced.
- [x] Independent review is `ACCEPT` with P0=0/P1=0.
- [x] Scope is limited to allowed paths and no forbidden path changed.
- [x] Obsolete branch retirement evidence is complete and exact.
- [x] PKL update explicitly not required because no accepted architecture changed.
- [x] Work order, ledger, disposition, result retention, and move close atomically.

## Completion disposition

- [x] RESULT_SUMMARY_KEPT
- [x] ARCHIVED
- [x] PKL update not required; accepted architecture state did not change

## Completion evidence

- Fresh candidate manifest SHA-256:
  `e59b2d70f1511a741372a3ee01d0c8feb07d68ea60a0e583a64b300da0f83d4c`.
- Independent `REV-0069` result SHA-256:
  `c1e153e737f4f0cf3d4d5eb159f3be87f4f12cf91d0773afa3fceea93f529764`;
  verdict `ACCEPT`, P0=0, P1=0, P2=0.
- Exact retirement and post-delete stability evidence:
  `work/queue/M2-REGENERATION-2026-08-21/05-RETIREMENT-AND-GATE-B-EVIDENCE.md`.
- Local, remote-tracking, and fresh live-remote target refs are absent; unrelated ref/worktree
  inventories are unchanged.
- Terminal state: `READY_FOR_HUMAN_M2_REGENERATION_RATIFICATION — GATE B`.
- No accepted architecture changed, so no PKL update was required.
- No M2 implementation, schema/DDL, database, runtime, broker/credential activity, provider
  selection, promotion, or merge to `master` occurred.

```yaml
fable_done:
  status: VERIFIED
  evidence: "REV-0069 ACCEPT P0=0/P1=0/P2=0; exact local/live-remote c9 retirement; unchanged unrelated ref/worktree inventory; repository-native closeout checks."
  command: "See 05-RETIREMENT-AND-GATE-B-EVIDENCE.md and the final validation transcript."
  terminal_state: "READY_FOR_HUMAN_M2_REGENERATION_RATIFICATION — GATE B"
```

## Distillation and deletion decision

Keep this compact work order after completion because it is the authority and evidence record for
a high-risk M2 planning regeneration and exact branch retirement. Delete no accepted ADR, PKL,
review history, research artifact, or unrelated work record.
