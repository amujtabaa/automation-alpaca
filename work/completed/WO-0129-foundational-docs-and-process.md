---
type: Work Order
title: "Foundational docs & process: fill the repo primer, complete .env.example, land the P-1/P-2 review-protocol amendments"
status: CLOSED
work_order_id: WO-0129
wave: post-R2 beta-prep (foundational; from session-history review 2026-07-20)
model_tier: mid
risk: low
disposition: [RESULT_SUMMARY_KEPT, PKL_UPDATED]
owner: Ameen / implementer: Codex ultra session
created: 2026-07-20
gated_surface: .ai-os/core protocol text (operator-approved via the kickoff decision block)
---

# Work Order: make the meta-layer as truthful as the code

## Goal

Three foundational gaps found across this planning campaign: the repo primer every agent
session loads is an EMPTY template; the env-var surface is undocumented (`ALPACA_DB_PATH`,
`STATE_STORE` absent from `.env.example`); and two review-protocol policy gaps (AUDIT-0002
C104/C105) are noted but not landed. Close all three.

## Context packet

- `.claude/rules/repo-primer.md` (the empty template + the one real section: operator prefs)
- `.env.example` + `app/config.py` (the actual env-var surface: `ALPACA_DB_PATH:25`,
  `STATE_STORE:24`, `BROKER_ADAPTER:41`, `ENABLE_*` flags — enumerate ALL from config.py)
- `work/queue/AUDIT-0002-REMEDIATION-BATCH.md` P-1/P-2 + `work/review/AUDIT-0002-priorwork/addendum-claude-seat.md` C104/C105
- `.ai-os/core/15_CROSS_MODEL_REVIEW.md` (the protocol file to amend)
- `work/queue/PD1-R2-PLANNING-PACKAGE.md` (the recorded operator execution preference to promote)
- `CLAUDE.md` + `docs/00_START_HERE.md` (facts source for the primer — verify, never invent)

## Allowed paths

```yaml
allowed_paths:
  - .claude/rules/repo-primer.md
  - .env.example
  - .ai-os/core/15_CROSS_MODEL_REVIEW.md
  - work/**
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/**
  - tests/**
  - docs/adr/**
  - .github/**
```

## Required behavior

- [x] **Primer fill:** populate every empty section of `repo-primer.md` with VERIFIED facts
      (grep/read evidence per claim): what the repo is, layer map (`ui → api → facade → engine
      → adapter/store`), important-paths table, real build/gate commands (`ruff check .`,
      `ruff format --check .`, `mypy app/`, `lint-imports`, `pytest -q`, the conformance
      oracle, the scaling gate), env vars, gotchas (scratch-dir rule / OS-temp basetemp, the
      close-out-ships-with-work CI ratchet, dual-store test rule, injected-clock rule,
      work-order protocol pointers). Respect the 150-line root-instruction budget
      (`ai-os-rules.yaml`) — link out rather than inline where needed.
- [x] **Execution-preference promotion (pre-approved via kickoff block):** add the recorded
      operator preference (strongest model locally for gated/perilous surfaces; cloud for
      mid-tier) as a durable primer bullet; strip the archive-only `recommended_model`
      frontmatter convention (plan §5 verify amendment B).
- [x] **`.env.example` completion:** every env var `app/config.py` reads, with one-line
      descriptions and safe defaults; explicitly note which are optional and that credentials
      stay absent in mock/paper-dev mode.
- [x] **P-1 amendment** (per ratified policy): a reviewed party never edits a reviewer-owned
      `result.md` in place — corrections go in a separate, disclosed addendum file in the
      packet. **P-2 amendment:** gated-surface changes get a tracked `REV-*` packet even when
      the review conversation happens in PR threads (the packet records the thread verdict).
      Both as dated additions to `15_CROSS_MODEL_REVIEW.md`; no retroactive relabeling of past
      packets.
- [x] Every primer claim carries verify-evidence in the close-out (no unverified assertions in
      a file every future session trusts).

## Fable v3 evidence

### GATE — VERIFIED

- Read the required facts sources (`CLAUDE.md`, `docs/00_START_HERE.md`, `app/config.py`, the
  P-1/P-2 audit records, and the execution-preference planning package) before drafting.
- The current WO scope check passed: `check_work_order_scope.py ...WO-0129...`.
- The five AI Project OS checks passed before close-out: installation, version consistency,
  ledger, PKL, and work-order disposition checks.

### RED — VERIFIED

- Before the edit, the primer audit found 36 template markers and the review protocol had neither
  P-1 nor P-2. The then-current `.env.example` visibly lacked the state, reconciliation, recorder,
  protection, and recovery configuration groups present in `app/config.py`.

### FIX — VERIFIED

- **Root cause:** a generic starter primer and a pre-WO-0123 environment template had never been
  reconciled to the mature backend configuration or AUDIT-0002's identified protocol gaps.
- Replaced only the template material with source-backed operational facts, enumerated every
  declared configuration name with a safe default, and added dated forward-only P-1/P-2 protocol
  rules. No past review packet was relabeled or modified.

### GREEN / DONE — VERIFIED

- Post-change audit: `CONFIG_READ_COUNT=40`, `ENV_DOCUMENTED_COUNT=40`, no missing or unexpected
  names, `PRIMER_LINES=91`, zero template markers, and both P-1/P-2 present.
- Configuration smoke: `ENV_EXAMPLE_LOADS_MOCK_SAFE`.
- Quality gate: `ruff check .` passed; `mypy app/` reported 70 source files with no issues;
  `lint-imports` kept all 6 contracts; conformance oracle and scaling gate passed; full
  `pytest -q --basetemp <unique OS-temp path>` exited 0.
- `ruff format --check .` was observed but is not a CI gate; it reports six pre-existing,
  out-of-scope source files. They were intentionally not reformatted by this docs-only WO.

## Acceptance criteria

- [x] Primer sections all filled + within budget; `.env.example` complete vs `config.py`;
      both protocol amendments landed with dates.
- [x] All five AI-OS checks green; full CI gate green (docs-only, but run it).
- [x] Fable DONE with evidence; close-out + ledger with the work.

## Stop conditions

Stop if any primer fact cannot be verified from the tree (omit it, note it) — the primer must
never teach a future session something false; that is how OBS-2-class errors start. Rollback:
revert; docs-only. Independent of every other WO; runs any time.

## Completion disposition

Expected: `[RESULT_SUMMARY_KEPT, PKL_UPDATED]`.
