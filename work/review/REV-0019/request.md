---
type: Review Request
rev_id: REV-0019
campaign_id: CAMPAIGN-0001
title: re-review of the Tier-1 gated remediation (CAMPAIGN-0001 Wave-1 confirmed findings)
status: AWAITING_REVIEW
targets: [ENG-001, "REV-0006-F-001", "UC-002", "ADR-008/INV-075 wording"]
human_gated_surfaces: [manual-flatten, kill-switch, cancel-replace, event-log-truth]
review_branch: claude/fable-mode-os-install-1dlyk8
base_sha: b600101            # the frozen Wave-1 base; the fixes sit on top of it
gated_fix_commits: [27bbffb, 6841b82, a22837e]   # F-001, ENG-001, UC-002
context_commits: [d3a3456, a0d1722]              # doc-accuracy + P2 batch (non-gated)
env: python 3.12             # see work/review/CAMPAIGN-0001/CODEX_ENV_SETUP.md
created: 2026-07-10
---

# Review Request REV-0019 — re-review of the Tier-1 gated remediation

## Your role
You are the **independent review seat** — a different model from the author. Read `AGENTS.md`
("## Review guidelines") and `prompts/INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md`: **re-derive from the
code, don't rubber-stamp, findings only — do not push fixes.** You have the full repo on branch
`claude/fable-mode-os-install-1dlyk8`.

This packet exists because the CAMPAIGN-0001 Wave-1 review (your own results, verified in
`work/review/REV-0004…0008/disposition.md` + `CAMPAIGN-0001/synthesis.md`) confirmed three P1 findings
on **human-gated safety surfaces**, and the author has now remediated them. Per the CLAUDE.md Review
policy, a change re-touching a gated surface **queues for a fresh independent review before its gate
clears** — even though the author ran an in-process adversarial pass (which never counts as
independent review). Your job: confirm each fix is **correct, safe, complete, and introduces no new
hazard**, and that it actually closes its finding.

> Run on **Python 3.12** (`work/review/CAMPAIGN-0001/CODEX_ENV_SETUP.md`) so your evidence is
> authoritative, not environment-limited. `git diff b600101..HEAD -- app` shows the whole remediation.

## What you're reviewing (three gated fixes + one ADR clarification)

### 1. REV-0006-F-001 — sqlite `flatten_position` atomicity (manual-flatten) — commit `27bbffb`
- **Finding (CONFIRMED P1, `work/review/REV-0006/disposition.md`):** the sqlite flatten committed
  supersede + create + approve in one `_tx()` then **dispatched in a separate transaction**, so a hard
  crash between them durably stranded an `APPROVED` `MANUAL_FLATTEN` intent with no order (the memory
  store was already atomic). Human decision: make it a **single transaction** (option B).
- **The fix:** `app/store/sqlite.py::flatten_position` now wraps the whole SUPERSEDE_AND_CREATE branch
  in ONE `with self._tx()`; the shared `_dispatch_order_for_sell_intent_locked` gained an optional
  `cur=None` (uses the caller's cursor when given, via `nullcontext`) so dispatch joins that
  transaction — a reject or crash rolls the fresh intent's insert+approve back too. The
  `create_order_for_sell_intent` caller passes `cur=None` and is unchanged.
- **Probe:** does a dispatch reject/crash now leave **nothing** durable (both stores), matching the
  in-memory store? Does the `cur=None` path preserve the old `create_order_for_sell_intent` behaviour
  (its self-heal-on-reject must still PERSIST, since it opens its own tx)? Any nested-`_tx()`/
  read-your-writes hazard from folding dispatch's `_position_locked` re-read into the open transaction?
  Pinned by `tests/test_phase7_flatten_atomic.py::test_flatten_dispatch_crash_leaves_no_partial`.

### 2. ENG-001 — autonomous protection intent under HALTED (kill-switch) — commit `6841b82`
- **Finding (CONFIRMED P1, `work/review/REV-0005/disposition.md`):** `_run_protection` cached the
  kill-switch state once, then created a `PROTECTION_FLOOR` intent several awaits later, so a
  concurrent kill let a spurious intent + order + `PROTECTION_TRIGGERED` event be created under HALTED.
  Human decision: the **store-atomic gate** (option A).
- **The fix:** `create_sell_intent` (both stores) now refuses a NEW `PROTECTION_FLOOR` intent when the
  session is `HALTED`, checked under the same single-writer lock as the insert (new
  `ProtectionHaltedError`, INV-060) — an already-active exit still returns idempotently. The engine
  re-reads the FSM **fresh per symbol** and treats the store's refusal as "pause this symbol"
  (`_open_protective_exit` now returns `bool`).
- **Probe:** is the TOCTOU **fully closed** now (a kill landing during any tick await cannot create an
  intent/order/`PROTECTION_TRIGGERED` event)? Does the gate ever refuse a **legitimate** protection
  intent (non-HALTED)? Does the `bool` return + `paused_breaching` recording preserve the D-P2 pause
  semantics (existing `tests/test_phase7_protection_loop.py`)? Is the claim-gate backstop still intact?
  Pinned by `tests/test_eng001_protection_halted.py`.

### 3. UC-002 — operator actor dropped on cancel (cancel-replace) — commit `a22837e`
- **Finding (CONFIRMED P1, `work/review/REV-0004/disposition.md`):** the facade `cancel` resolved the
  operator actor but dropped it at `_cancel_transition → transition_order → plan_transition_order`
  (whose `order_transition` payload carried only `{from,to}`).
- **The fix:** `transition_order` (ABC + both stores) gained `actor: str = COMMAND_ACTOR_SYSTEM`
  threaded to `plan_transition_order`, which stamps it into the `order_transition` payload; the facade
  `cancel` threads the operator actor through `_cancel_transition`.
- **Probe:** is the actor now on **every** cancel's audit event (both the CREATED→CANCELED and the
  SUBMITTED→CANCEL_PENDING branch)? Does the default `"system"` hold for routine engine transitions
  (no false operator attribution)? Purely additive (no order/fill/position state change)? Pinned by
  `tests/test_uc002_cancel_actor.py`; two pre-existing tests were updated to the completed payload —
  confirm they were **corrected, not weakened**.

### 4. ADR-008 / INV-075 wording clarification (event-log-truth, doc-only) — commit `d3a3456`
REV-0007-F002 (PARTIAL, `work/review/REV-0007/disposition.md`) noted the ADR-008 "Truth model" /
INV-075 text read as if `project_order_status` consults `ORDER_TRANSITIONS`; it does **not** — the
transition bound is enforced at the *write path* (`plan_transition_order`). The wording was clarified
(no behaviour change). Confirm the clarified statements are **accurate** and don't over/under-claim.

## Scope note (non-gated context — glance only if time)
The P2 batch (`a0d1722`): ENG-002 (quarantine-resolution queries now consume the reconcile budget),
REV-0006-F-002 (docstrings declare the intentional `ValueError`), ARCH-001 (two INI-independent
route-boundary regressions). None touch a hard-gated safety surface; not a gate for this packet.

## Independent-oracle hooks (check code against the STATEMENT, not the test — X-002)
Check the fixes against the invariant **statements** — INV-050 (atomicity), INV-060 (kill switch
blocks new order intent), the safety core (#8/#9/#10), and the `order_transition` audit contract — not
against the new pinning tests (a test can assert the very behaviour it should challenge). Re-derive
"what must always hold" and probe the code directly, dual-store where relevant.

## Evidence & how to respond
Copy `.ai-os/templates/review-result.md` to **`result.md` in THIS folder** and fill it: a findings
table, an overall **verdict** (`ACCEPT | ACCEPT-WITH-CHANGES | BLOCK`), and a **per-target gate
decision** (does F-001 / ENG-001 / UC-002 / the ADR clarification clear?). Every P0/P1 needs a runnable
repro + pasted 3.12 output, dual-store where relevant. State plainly anything you could not verify. Do
**not** edit `request.md`; do **not** push code fixes.
