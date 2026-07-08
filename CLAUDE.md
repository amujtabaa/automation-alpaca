# CLAUDE.md — Alpaca Spine v2 (post-migration)

Repo-level contract for any AI coding agent. **Safety and correctness outrank velocity.**

> Project: browser-operated, paper-first Alpaca trading platform on the Spine v2 execution architecture. Migration to Spine v2 is complete; current posture is **cleanup → full-repo audit → beta roadmap**.

<!-- AI-PROJECT-OS:BEGIN -->
## Operating system

This repo runs the **AI Project OS** (canonical: `.ai-os/`). This file is the Claude adapter shim plus the always-on safety core below.

Read order for engineering work:
1. This file.
2. Your assigned work order in `work/active/` or `work/queue/` — it defines scope, allowed paths, and done-when.
3. Only the PKL pages (`pkl/`) and source/test files the work order names.

Execution discipline: **Fable v3** (`.ai-os/templates/fable-core-v3.md`; Claude adapter: `.claude/skills/fable`). GATE before building, TDD, fresh pasted evidence for every claim, FIX blocks with root cause, disposition on close. No completion claims without evidence — VERIFIED / UNVERIFIED / BLOCKED / NEEDS-INPUT only.

No work order? Ask for one or draft one for approval (`.ai-os/templates/work-order.md`). Don't freelance.
<!-- AI-PROJECT-OS:END -->

## Safety core — always in force, never overridden

**Invariants (acceptance criteria):**
1. No live trading in beta — `PAPER` or `LIVE_SHADOW` only; live modes disabled by config.
2. Alpaca Paper only for beta.
3. FastAPI backend is the durable engine and source of truth.
4. Streamlit is a thin client — observes state, issues intents; never mutates state directly.
5. The UI never calls Alpaca — only the Broker Adapter does.
6. The UI owns no strategy/risk/order/fill/position state.
7. All important logic lives in the backend.
8. Submitted does **not** equal filled.
9. Only fill events change position quantity.
10. Kill switch blocks new order intent.
11. Browser-first workflow.

Plus spine invariants **INV-1…INV-9** (`docs/SPINE_EXECUTION_ARCHITECTURE_v2.md §5`).

**Safety rails:**
- Ambiguous/timeout broker responses → `TIMEOUT_QUARANTINE`, reconcile via deterministic `client_order_id`. **Never blind-resubmit.**
- Broker-authoritative overfill/negative-position facts are recorded and quarantined — never hidden.
- Invalid market data (stale/NaN/negative/out-of-range) must halt or quarantine the flow — never drive sizing or submission.
- Manual flatten: allowed in `Reducing`, blocked in `Halted` except via explicit audited emergency override; always routes through session control, risk checks, event log, single-writer engine.
- Never weaken a test to make code pass. Fix the code or flag the conflict.

**Human-gated surfaces** — never auto-approved, never auto-executed: order submission, cancel/replace, kill switch, manual flatten, live/shadow mode config, schema/DB migration, event-log truth changes, deletions of tests/docs/ADRs.

## Boundaries and stack

- Layers: `ui → api → facade → engine → adapter/store`. Imports flow only through approved seams; `alpaca-py` only inside the adapter; Streamlit imports only the typed API client.
- Single writer: only the Execution Engine mutates order/fill/position state; positions derive only from deduped fill events; `SUBMITTED`/`ACCEPTED` structurally cannot change quantity.
- Stack pinned: Python 3.12, FastAPI, Streamlit, SQLite + in-memory. No React/Dash/other brokers. New dependency ⇒ ADR first.
- Details, rationale, and current facts: `pkl/architecture/` and `docs/adr/`.

## Testing and CI

- Engine logic: injected clock (no bare `datetime.now()`/`time.time()`), no unseeded randomness, deterministic IDs/queues.
- State/order/fill/position/reconciliation/kill-switch changes: test **both** in-memory and SQLite paths, expand tests in the same change.
- Gate: `ruff` + `pytest` (+ import-linter, replay/parity verifier where configured). Formatting authority is **ruff** — never Prettier/Biome on Python. (A `mypy` typecheck gate is aspirational — not yet wired in CI/config; deferred to `work/queue/WO-0008`, see `pkl/architecture/testing-model.md`.)

## Review

Three-seat model: planning seat accepts decisions → implementer executes bounded work orders with built-in adversarial checks (Fable evidence, quality-engineer validation, review checklist, CI gates). **Independent cross-model review (Codex/other) runs at the human's discretion**, batched at milestones rather than per wave — except: changes to human-gated safety surfaces and ADR amendments queue for independent review before any beta-relevant milestone relies on them. In-process validation never counts as independent review; no seat's self-review is ever the only review. ADR/decision updates ship with the change, not after.

## ClaudeFast kit (subordinate tooling)

The kit in `.claude/` provides skill activation, session backups, session types, `/team-plan → /build|/team-build|/workflow-build`, and specialist agents. Rules:
- Plans always **pause for human approval**; no auto-execution, no auto-advance.
- Anything touching a human-gated surface above is Complex by definition, regardless of size.
- Permission auto-approve (`cf-approve`): off, or deny-by-default with mandatory escalation on gated surfaces.
- FormatterHook → `ruff format` or disabled; Biome validator disabled.
- Out-of-scope agents/skills (frontend/Supabase/mobile/n8n/SEO/growth, React/payments/email) — do not invoke.

## Conflict rule

Docs/code/ADRs disagree → don't silently pick one. Code is evidence of behavior; accepted ADRs + Spine v2 spec are the target. If the conflict touches a safety surface, **stop and record the decision gap** before coding. Older `IMPLEMENTATION_PROMPT_*` files are historical unless a human reactivates them.
