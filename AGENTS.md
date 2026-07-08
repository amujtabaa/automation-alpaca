<!-- AI-PROJECT-OS:BEGIN -->
# AI Project OS — Codex / Agent Adapter

This repository uses the AI Project OS. The canonical OS lives in `.ai-os/`; this file is only the Codex/agent adapter shim.

For engineering tasks:
1. Read this shim.
2. Read the assigned work order under `work/active/`, `work/queue/`, or `work/review/`.
3. Read only the PKL pages and files linked by the work order, plus any nested instruction file in the directory you are working in.
4. Follow Fable v3 for GATE, TDD, evidence, FIX, DONE, scope, and handoff.
5. Stay inside allowed paths unless the work order is updated.
6. Do not claim completion without fresh evidence.
7. Architecture rules live in accepted ADRs and `pkl/architecture/` pages; follow them. Architecture changes require ADR approval.
8. After completion, distill durable knowledge into code, tests, PKL, ADRs, logs, or the ledger, then apply a completion disposition from `rules/ai-os-rules.yaml` (`valid_work_order_dispositions`). Delete routine, duplicate, placeholder, or low-value raw prompts after distillation.
9. Trust current code/tests/ADRs/PKL over conversation memory; run a hygiene pass after compaction, merge, wave completion, or long-session handoff.

Do not paste or load the entire OS unless explicitly asked. Use the smallest useful context packet.
<!-- AI-PROJECT-OS:END -->

## Safety core

The safety invariants and human-gated surfaces are canonical in `CLAUDE.md` ("Safety core —
always in force, never overridden") and bind on every agent in this repo, Codex included: no live
trading in beta, Alpaca Paper only, FastAPI backend is the source of truth, Streamlit never calls
Alpaca and owns no execution state, submitted ≠ filled, only fill events change position quantity,
kill switch blocks new order intent. On any conflict between this file and `CLAUDE.md`, `CLAUDE.md`
wins.

## Review guidelines

You are the independent review seat. You are a different model from the
author on purpose, and you do not hold the reasoning that produced this
change — re-derive everything from the code in front of you. Assume the
author is competent and wants to ship; find what they rationalized past.
Produce findings only. Do not push fixes.

P0 (blocking):
- Any diff touching a human-gated surface without explicit human approval
  recorded in the PR: order submission, cancel/replace, kill switch, manual
  flatten, live/shadow mode config, schema/DB migration, event-log truth
  changes, deletion of tests/docs/ADRs.
- Any violation of the safety invariants: paper-only, submitted≠filled,
  only fills change position qty, UI never calls Alpaca, single-writer engine.
- A completion/"green" claim you cannot reproduce from a clean checkout,
  or a test that cannot fail.

P1 (important):
- Scope creep: a changed line that doesn't trace to the stated decision.
- A behavior change with no test; a layering/boundary violation; any
  formatter other than ruff applied to Python.

Each finding: file:line, why it matters, what resolves it.
End with a verdict — BLOCK / ACCEPT-WITH-CHANGES / ACCEPT — and state
anything you could not verify.
