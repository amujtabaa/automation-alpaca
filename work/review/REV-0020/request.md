---
type: Review Request
rev_id: REV-0020
campaign_id: CAMPAIGN-0001
title: re-review of the ENG-001 follow-up (atomic protection exit-open) — REV-0019-F-001 remediation
status: AWAITING_REVIEW
targets: [ENG-001, "REV-0019-F-002"]
human_gated_surfaces: [kill-switch]
review_branch: claude/fable-mode-os-install-1dlyk8
base_sha: b600101                 # the frozen Wave-1 base
prior_fix_commits: [6841b82]      # ENG-001 first pass (create-time gate only — INCOMPLETE)
gated_fix_commits: [7d41e4d]      # ENG-001 follow-up: atomic open_protection_exit
env: python 3.12                  # see work/review/CAMPAIGN-0001/CODEX_ENV_SETUP.md
supersedes_finding: REV-0019-F-001
created: 2026-07-10
---

# Review Request REV-0020 — re-review of the ENG-001 follow-up

## Your role
You are the **independent review seat** — a different model from the author. Read `AGENTS.md`
("## Review guidelines") and `prompts/INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md`: **re-derive from the
code, don't rubber-stamp, findings only — do not push fixes.** The full repo is on branch
`claude/fable-mode-os-install-1dlyk8`; the fix is commit `7d41e4d`.

This packet exists because **your own REV-0019 review** confirmed the first ENG-001 pass (`6841b82`)
was incomplete: it gated only `create_sell_intent`, leaving a post-create/pre-approval window in which
a concurrent kill still left an `ORDERED` intent + `CREATED` sell order + `protection_triggered` event
under `HALTED` in both stores (**REV-0019-F-001, P1**). The author (per the human decision **Option B**)
has now remediated it. The kill switch is a **human-gated surface**, so this follow-up **queues for a
fresh independent review before the ENG-001 gate clears** — an in-process adversarial pass never counts
as independent review. Confirm the fix is **correct, safe, complete, and introduces no new hazard**, and
that it actually closes REV-0019-F-001.

> Run on **Python 3.12** (`work/review/CAMPAIGN-0001/CODEX_ENV_SETUP.md`). `git diff b600101..7d41e4d
> -- app` shows the whole ENG-001 remediation (first pass + this follow-up); `git show 7d41e4d`
> shows only the follow-up.

## What you're reviewing

### 1. ENG-001 — atomic protection exit-open (kill-switch) — commit `7d41e4d`
- **The fix:** a new store method `StateStore.open_protection_exit(...)` (ABC in `app/store/base.py`;
  impls in `app/store/memory.py` and `app/store/sqlite.py`) performs the **whole** autonomous exit-open
  as ONE atomic unit under a single lock hold: single-flight dedup → **INV-060 HALTED gate**
  (`ProtectionHaltedError`) → create `PROTECTION_FLOOR` intent → approve → dispatch MARKET order
  (live-position oversell re-read) → append `protection_triggered`. Memory uses one `_atomic()`; sqlite
  shares one `_tx()` (dispatch joins via `cur=cur`). The engine
  (`app/monitoring.py::_open_protective_exit`) now makes **one** `open_protection_exit` call instead of
  the four separate public awaits (`create_sell_intent` → `transition_sell_intent` →
  `create_order_for_sell_intent` → `append_event`).
- **Claim:** because there is **no `await` between the HALTED check and the writes**, a concurrent kill
  can only land BEFORE the op (refused, nothing durable) or AFTER it committed (a legitimate exit opened
  while ACTIVE) — never mid-sequence.
- **Probes:**
  1. **Re-run your REV-0019 P1 repro** (the barrier at intent-creation→approval) against `7d41e4d`. It
     patched `store.transition_sell_intent`, which the engine **no longer calls** during a protective
     exit — so verify (a) the engine truly routes through `open_protection_exit` and not the public
     steps (see `tests/test_eng001_atomic_exit.py::test_run_protection_uses_atomic_open_and_no_public_transition`),
     and (b) the equivalent post-fix interleaving — engage the kill at the **last await before the atomic
     op** (the live-position read inside `_open_protective_exit`) — leaves **nothing** (`halted [] [] 0`)
     in **both** stores. Is there ANY remaining await between the FSM check and the durable writes that a
     kill could still exploit?
  2. **Dispatch reject (oversell):** the trigger audit is inside the atomic block, so a reject rolls the
     intent+approve back with it. Confirm this leaves no partial and no `protection_triggered` describing
     a non-existent exit — and that this changed reject behaviour (roll-back vs the old persist-a-self-heal)
     doesn't strand or double anything (single-flight end state must be unchanged: symbol free next tick).
  3. **Legitimate path unharmed:** a non-HALTED breach still opens the full exit — ORDERED intent,
     CREATED SELL order, exactly one `protection_triggered` with the right `order_id` / `correlation_id`
     (= intent id) / payload. Does the D-P2 pause semantics + `paused_breaching` recording still hold
     (`tests/test_phase7_protection_loop.py`, `tests/test_eng001_protection_halted.py`)?
  4. **Single-flight / concurrency:** two ticks (or a concurrent `flatten_position`) racing the same
     symbol — can a double intent/order/trigger ever result? Is the store-internal dedup correct given
     the engine also pre-checks `active_sell_intent_for`?
  5. **Claim-gate backstop** still independently blocks any venue submission under HALTED (unchanged).

### 2. REV-0019-F-002 — stale flatten commentary (doc-only) — commit `7d41e4d`
The pre-F-001 "each step commits its own transaction / hard crash between commits strands the intent"
comment in `app/store/sqlite.py::flatten_position` and the matching `tests/test_phase7_flatten_atomic.py`
docstring were refreshed to the single-transaction contract (the self-heal test body is unchanged —
confirm it still reflects real defense-in-depth for an intent stranded by another route, and the new
wording is accurate).

## Independent-oracle hooks (check code against the STATEMENT, not the test — X-002)
Check the fix against the invariant **statements** — INV-050 (atomicity), INV-060 (kill switch blocks
new autonomous order intent), the safety core (#8/#9/#10) — not against the new pinning tests. Re-derive
"what must always hold under a concurrent kill" and probe the code directly, dual-store.

## Evidence & how to respond
Copy `.ai-os/templates/review-result.md` to **`result.md` in THIS folder** and fill it: a findings
table, an overall **verdict** (`ACCEPT | ACCEPT-WITH-CHANGES | BLOCK`), and a **per-target gate decision**
(does ENG-001 clear now? does the F-002 cleanup clear?). Every P0/P1 needs a runnable repro + pasted
3.12 output, dual-store where relevant. State plainly anything you could not verify. Do **not** edit
`request.md`; do **not** push code fixes.
