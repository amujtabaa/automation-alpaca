---
type: Review Disposition
rev_id: REV-0020
verdict_received: ACCEPT
disposition_status: RESOLVED
date: 2026-07-11
---

# Disposition — REV-0020 (ENG-001 follow-up re-review)

Reviewer: GPT-5 Codex, verdict **ACCEPT** on the authoritative env (Python 3.12.13, single clean commit
`9fd1e74`, no checkout movement between probes). Both gated targets **clear**.

## Gate decisions
| Target | Gate | Basis |
|---|---|---|
| ENG-001 / REV-0019-F-001 (kill-switch) | **CLEARED** | The whole exit-open (dedup → HALTED check → create → approve → dispatch → audit) is one store-atomic unit; **no await between the HALTED check and the durable writes** in either store. |
| REV-0019-F-002 (stale flatten commentary, doc-only) | **CLEARED** | Comment + test docstring now describe the one-transaction contract accurately; the defense-in-depth self-heal remains for intents stranded by another route. |

## Verification (dual confirmation)
- **Author (in-process, at build):** the post-create/pre-atomic kill probe returned `halted [] [] 0`
  in both stores; wiring test pins `open_protection_exit` is called and public `transition_sell_intent`
  is not; full suite 2018→2044 green.
- **Independent (Codex, 3.12.13):** reproduced identical results with its own spy + probe —
  `route {'open':1,'transition':0}`, `last_await_kill halted [] [] 0 paused 1` (both stores),
  `dispatch_reject InvalidOrderError artifacts 0 0 0 active None`, `legit_concurrent 1 1 1 event_link
  True True same_return True`, `claim_backstop blocked kill_switch`. Gate green (ruff / mypy /
  lint-imports 5-0 / full pytest exit 0).
- I confirmed Codex reviewed the current code: `7d41e4d` is an ancestor of the reviewed tip `9fd1e74`,
  and `app/` is byte-identical between `9fd1e74` and the current branch tip.

No P0/P1/P2 finding. No disputed items.

## Follow-up
- **ENG-001 gate CLEARED** — the kill-switch surface has passed independent cross-model re-review. The
  Wave-1 Tier-1 remediation set (F-001, ENG-001, UC-002) is now fully closed.
- Ledger updated (`work/ledger.jsonl`: REV-0020 outcome).
