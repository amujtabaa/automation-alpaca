---
type: Work Order
title: M1.5 broker-role and provider-neutral persistence-boundary alignment
status: ACTIVE
work_order_id: WO-0157
wave: M1.5
model_tier: strong
risk: high
disposition: []
owner: Codex local architecture and delivery seat
created: 2026-08-09
branch: codex/m1-5-broker-alignment-local-r1
base_sha: 5eea154f7fbdaa6d77519bdda0edd7ac706f9b5f
execution_authority: "The 2026-08-09 Codex Local Orchestrator Prompt authorizes ordinary reversible documentation-only work, independent-review orchestration, normal commits/pushes, and draft-PR work inside this exact scope. Exact human ratification remains required before ADR landing or authority reconciliation; merge remains human-gated."
cloud_attempt: "PR #12 is closed, unmerged, abandoned, non-authoritative, and unusable. It consumed WO-0156 and REV-0062; this order deliberately uses fresh WO-0157 and REV-0063 and re-derives every artifact from current master."
---

# WO-0157 — M1.5 broker-role and persistence-boundary alignment

`[FABLE • FULL • verification: DIRECT plus INDEPENDENT • task: M1.5 broker alignment]`

## Goal

Complete an independently reviewed and exactly human-ratified M1.5 architecture overlay that keeps
Alpaca Paper as the M2–M8 conformance broker while making M2's external-connection identity
provider-neutral, immutable, and single-active-profile.

## Context packet

- `AGENTS.md`; `CLAUDE.md`; `.ai-os/templates/fable-core-v3.md`.
- `.ai-os/templates/work-order.md`; `.ai-os/core/15_CROSS_MODEL_REVIEW.md`; `.ai-os/core/19_AUTONOMY_AND_ESCALATION.md`.
- `pkl/project/goals.md`; `pkl/architecture/architecture-map.md`; `pkl/log.md`.
- `work/review/REV-0059/handoff.md`.
- `docs/adr/ARCH-RESET-2026-07-RATIFICATION.md`; `docs/adr/ADR-020-current-state-execution-kernel.md`; `docs/adr/ADR-021-position-protection-liquidity-execution.md`; `docs/adr/ADR-022-reset-beta-scope-cutover-governance.md`; `docs/adr/ADR-023-bounded-market-occurrence-authority.md`.
- `work/queue/ARCH-RESET-2026-07/04-persistence-and-cutover.md`; `work/queue/ARCH-RESET-2026-07/06-roadmap.md`.

## Fable gate

```yaml
fable_gate:
  goal: "Complete and land an independently reviewed, exactly ratified M1.5 architecture overlay that preserves Alpaca Paper for M2-M8 while making M2 external-connection identity provider-neutral and single-active-profile."
  assumptions:
    - claim: "Pure M1 is closed and merged."
      status: VERIFIED
      evidence: "master 5eea154 plus REV-0059 handoff and current PKL/ratification records"
    - claim: "M2 remains inactive."
      status: VERIFIED
      evidence: "current goals, architecture map, and M1 handoff"
    - claim: "ADR-022 keeps Alpaca Paper/live-shadow as beta."
      status: VERIFIED
      evidence: "accepted ADR-022 body via ratification index"
    - claim: "Provider-literal persistence assumptions exist in the M2 planning record."
      status: VERIFIED
      evidence: "04-persistence-and-cutover.md DDL, startup, and cutover clauses"
    - claim: "Fresh identities are WO-0157, REV-0063, and ADR-024."
      status: VERIFIED
      evidence: "master inventory ends at WO-0155/REV-0061/ADR-023; closed-unmerged PR #12 consumed WO-0156/REV-0062"
    - claim: "Cloud PR #12 is unmerged and abandoned."
      status: VERIFIED
      evidence: "GitHub PR metadata: state=closed, merged=false, merged_at=null"
  approach: "Re-derive from current master; freeze a complete semantic manifest; obtain clean-room independent review; remediate/re-review to P0=0/P1=0; obtain exact human ratification; then land the unchanged ADR and reconcile only current authority."
  out_of_scope:
    - "app/** or tests/** edits; M1 behavior, public surface, or proof changes"
    - "DDL, database, persistence, runtime, M2 implementation, broker/network/API activity, credentials"
    - "Webull/FIX/IBKR/Robinhood/Tradier implementation, routing, failover, or live trading"
    - "dependency, CI workflow, coverage-threshold, project-name, destructive-Git, or master-merge changes"
  done_when:
    - "candidate has independent ACCEPT with P0=0 and P1=0"
    - "human approves the exact ADR, manifest, and review-result hashes"
    - "accepted ADR lands unchanged and current PKL/ratification/ledger/lifecycle records reconcile"
    - "required local gates and exact-head CI pass; PR is ready for human merge"
  blast_radius: "Documentation-only architecture, roadmap, PKL, ledger, work-order, review, and ratification records."
```

Documentation-only TDD exception: no production behavior exists to test. The acceptance suite is
failure-capable static scope, SHA-256 manifest, authority-conflict, review, and consistency gates,
followed by unchanged repository CI.

## Prompt-engineering plan critique and refinement

Applied once from `senior-prompt-engineer` before drafting. The supplied orchestrator prompt has a
clear outcome contract but risks three failure modes: scope drift during post-ratification
reconciliation, treating a summary as an immutable candidate, and confusing an independent
reviewer with an author-side critique. This refined execution plan preserves every business
decision and exclusion:

1. Establish one immutable, non-glob candidate-file registry before substantive drafting; every
   semantic file is manifest-covered, while the self-referential manifest explicitly excludes
   itself and its own digest is separately recorded.
2. Split semantic candidate, reviewer-owned result, and post-ratification authority records. No
   candidate edit occurs after review acceptance without a new manifest and independent re-review.
3. Treat provider-literal clauses as a classification problem: preserve the selected Alpaca Paper
   beta coordinates, reject their elevation into permanent schema literals, and avoid general
   multi-broker semantics.
4. Make every M2/M9 obligation failure-capable by naming the required refusal, evidence, or future
   separate work order; do not claim a runtime capability from this documentation wave.
5. Stop exactly at the human hash-ratification gate. Only an exact approval resumes canonical ADR
   landing, current-authority reconciliation, lifecycle closeout, normal publication, and CI.

## Allowed paths

```yaml
allowed_paths:
  - work/active/WO-0157-m1-5-broker-alignment.md
  - work/completed/keep/WO-0157-m1-5-broker-alignment.md
  - work/queue/M1-5-BROKER-ALIGNMENT/README.md
  - work/queue/M1-5-BROKER-ALIGNMENT/01-current-authority-and-conflict-audit.md
  - work/queue/M1-5-BROKER-ALIGNMENT/02-option-matrix-and-decision.md
  - work/queue/M1-5-BROKER-ALIGNMENT/03-proposed-adr-broker-alignment.md
  - work/queue/M1-5-BROKER-ALIGNMENT/04-m2-persistence-contract-amendment.md
  - work/queue/M1-5-BROKER-ALIGNMENT/05-roadmap-and-milestone-reconciliation.md
  - work/queue/M1-5-BROKER-ALIGNMENT/06-m2-m9-obligations-and-acceptance.md
  - work/queue/M1-5-BROKER-ALIGNMENT/07-human-ratification-request.md
  - work/queue/M1-5-BROKER-ALIGNMENT/AUTHORITY-MANIFEST.sha256
  - work/review/REV-0063/request.md
  - work/review/REV-0063/request-remediation-01.md
  - work/review/REV-0063/request-remediation-02.md
  - work/review/REV-0063/result.md
  - work/review/REV-0063/result-remediation-01.md
  - work/review/REV-0063/result-remediation-02.md
  - work/review/REV-0063/disposition.md
  - docs/adr/ADR-024-broker-roles-execution-connection-profile.md
  - docs/adr/ARCH-RESET-2026-07-RATIFICATION.md
  - pkl/project/goals.md
  - pkl/architecture/architecture-map.md
  - pkl/log.md
  - work/ledger.jsonl
```

## Forbidden paths and operations

```yaml
forbidden_paths:
  - app/**
  - tests/**
  - migrations/**
  - .github/workflows/**
  - requirements.txt
  - constraints.txt
  - pyproject.toml
  - lockfiles
  - .env
  - secret/account artifacts
forbidden_operations:
  - "SQL/DDL execution, database creation, application/server startup, broker/API calls, or credential use"
  - "Webull/FIX/IBKR/Robinhood/Tradier implementation, multi-broker runtime, routing, failover, or live trading"
  - "git reset, git clean, force-push, history rewrite, or merge to master"
  - "M1 source/test modification, dependency change, or CI-threshold/workflow change"
```

## Candidate and review rules

- Semantic candidate is exactly the eight `work/queue/M1-5-BROKER-ALIGNMENT/` documents plus
  this active work order and each exact `REV-0063` request; all are frozen by
  `AUTHORITY-MANIFEST.sha256`. The manifest excludes its own file to avoid a hash cycle and lists
  its included paths, algorithm, base SHA, and exclusion rule.
- The reviewer owns `work/review/REV-0063/result.md` and each result addendum; the author never
  edits either. Any finding is dispositioned in `disposition.md` and every semantic correction
  triggers rehash plus independent re-review.
- Candidate commit and review result are normal committed/pushed checkpoints. A missing separate
  reviewer stops only at `SEPARATE REVIEW SESSION REQUIRED`; it is not disguised as acceptance.

## Human gates and stop conditions

1. Stop after independent `ACCEPT`, P0=0/P1=0, to request exact candidate-hash ratification.
2. Stop for a conflict among accepted ADR/PKL authority, indispensable unavailable external fact,
   or a requested action beyond this non-glob allowlist.
3. Do not merge. A final ready-to-merge report is the merge gate.

## Required validation

```powershell
# Candidate phase
git diff --check
Get-FileHash -Algorithm SHA256 <each semantic candidate file>
.\.venv\Scripts\python.exe .ai-os\scripts\check_ledger.py
.\.venv\Scripts\python.exe .ai-os\scripts\check_pkl.py pkl
.\.venv\Scripts\python.exe .ai-os\scripts\check_work_order_scope.py

# Post-ratification exact-head gate (commands verified from current CI before use)
ruff, mypy, import boundaries, AI-OS checks, R2 conformance oracle,
full pytest with line/branch coverage, coverage ratchet, and git diff --check
```

## Completion disposition

- [ ] PKL_UPDATED
- [ ] ADR_CREATED
- [ ] RESULT_SUMMARY_KEPT
- [ ] ARCHIVED

## Deletion decision

Retain this high-risk ratification work order under `work/completed/keep/`; it carries exact
authority, candidate, review, and publication provenance.
