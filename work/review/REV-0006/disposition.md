---
type: Review Disposition
rev_id: REV-0006
campaign_id: CAMPAIGN-0001
verdict_received: BLOCK
disposition_status: VERIFIED
remediation_status: NEEDS-HUMAN (F-001 decision gap) + DEFERRED-GATED
verified_env: python 3.12.3 (venv), frozen base b600101 == HEAD app/ (byte-identical)
date: 2026-07-10
---

# Disposition — REV-0006 (STORE-SPEC, store contract + planners)

Reviewer: GPT-5 Codex, verdict **BLOCK** (F-001 P0). Author-side verification reproduced both
findings in 3.12 and finds F-001 is a **genuine INV-050-statement violation on the sqlite-only path**,
but its severity + resolution is a **human decision gap**, not an unambiguous P0 bug.

## Per-finding verdicts

### REV-0006-F-001 — SqliteStateStore.flatten_position non-atomic (reviewer P0) → **CONFIRMED**, **P1 / NEEDS-HUMAN**
`flatten_position` (`app/store/sqlite.py:1624`) holds one lock (`:1632`) but commits in up to **four
separate** `with self._tx()` blocks (`:1697/:1723/:1755/:1765`); **dispatch**
(`_dispatch_order_for_sell_intent_locked`, its own `_tx`) runs **after** the create+approve commit.
A hard crash in that inter-commit window strands a durable `manual_flatten / approved / order_id=NULL`
intent with no order. Reproduced in 3.12 (both stores): **sqlite strands the partial; memory rolls
back atomically** (single `_atomic()` block) — so this is **sqlite-only**.
- **Oracle check:** INV-050's statement (`docs/INVARIANTS.md:328-339`) explicitly says
  "`SqliteStateStore` wraps writes in a single SQL transaction" and lists "`flatten_position`'s
  supersede + create + approve + dispatch" as all-or-nothing. The code (4 transactions) **fails the
  invariant statement itself** — not a test-vs-code artifact.
- **Realism / why not a clean P0:** the window is real without monkeypatching (structural split; a
  hard crash/SIGKILL/power-loss strands). **But** only a *hard crash* strands — a **logical** dispatch
  failure self-heals atomically (`plan_create_order_for_sell_intent` reject → X-002 self-heal expires
  the intent + writes events in its own `_tx`, then raises). Paper-only posture; recovers forward on
  the next (human) flatten, pinned by `tests/test_phase7_flatten_atomic.py`.
- **The decision gap (why NEEDS-HUMAN):** the sqlite code *documents this recover-forward design
  verbatim* (`sqlite.py:1633-1652`: continuous lock hold defeats the concurrency race; a hard crash
  "durably strands … NOT silently unrecoverable"). So **code and invariant disagree on a human-gated
  safety surface** — exactly CLAUDE.md's conflict rule ("record the decision gap, don't silently pick
  a side"). Human must choose:
  - **(A)** amend INV-050's statement to bless the documented recover-forward multi-transaction shape
    **and** close the **interim autonomous-protection gap** (below); or
  - **(B)** make sqlite `flatten_position` a single transaction to match the stated invariant and the
    memory store.
- **Interim autonomous-protection gap (caught in verification, beyond the reviewer's note):** while
  stranded, the orphan intent reads **active**, so the protection tick stands down
  (`monitoring.py:338` early-returns when `active_sell_intent_for(symbol) is not None`) even though
  nothing is working at the broker — the position is **unprotected until a human re-flattens** if the
  floor breaches in the interim. This must be closed under **either** option A or B.

### REV-0006-F-002 — planners raise bare ValueError vs ABC-promised OrderTransitionError (reviewer P2) → **CONFIRMED**, **P2**
`plan_resolve_timeout_quarantine` (`core.py:1980`) and `plan_reconcile_resolve_order` (`core.py:2025`)
raise bare `ValueError`; ABC docstrings (`base.py:856/881`) promise `OrderTransitionError`; tests pin
`ValueError`. No wrapping in the store methods. **No raw 500** — the facade maps `ValueError`→422.
Correction to the reviewer: the two types are **not** interchangeable — `OrderTransitionError`→**409**,
`ValueError`→**422** — so if ever HTTP-reachable this is a status divergence. But the guard is
defensive/**client-unreachable** (target comes from fixed reconcile/quarantine maps, never a
client-chosen enum). Contract/spec-coherence issue with zero live safety impact. P2 fair.

## Disposition
- **F-001:** **NEEDS-HUMAN** — surface option A vs B in the batched decision set. Either path is a
  **gated remediation** (manual-flatten surface + an INV-050 / possible ADR amendment) and, whichever
  is chosen, MUST also close the `monitoring.py:338` orphan-active-intent protection gap. Test-first,
  Codex re-review.
- **F-002:** CONFIRMED P2 → align the error contract (raise `OrderTransitionError`/a `StoreError` and
  update the pinning tests, or amend the ABC docstrings to declare the intentional `ValueError`).
  Batch with P2 cleanups.

## Gate
G-B does **not** clear until the F-001 decision gap is resolved (a real INV-050-statement violation on
a gated surface + an interim protection window). Evidence: `scratchpad/verify_f001.py`,
`verify_f002.py` (3.12, both stores).
