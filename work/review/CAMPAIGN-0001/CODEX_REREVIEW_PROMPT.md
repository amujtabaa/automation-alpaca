# CAMPAIGN-0001 — Codex re-review batch: REV-0019 (re-run), REV-0020, REV-0021

You are the **independent cross-model review seat** for CAMPAIGN-0001 — a different model from the
author. Your job is to re-derive each fix from the code and decide whether it is correct, safe,
complete, and closes its finding. **Findings only — do NOT push code fixes. Re-derive from the code and
the invariant statements, NOT from the author's pinning tests (a test can assert the very behaviour it
should challenge).** Read `AGENTS.md` ("## Review guidelines") and
`prompts/INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md` for the role.

There are **three** packets to review in this pass, in order: **REV-0019 (an env-corrected RE-RUN),
REV-0020, REV-0021.**

---

## 0. Environment — make it authoritative (this is the thing to get right this time)

The prior REV-0019 result was environment-affected: a **transient checkout reversion between probes**
briefly reverted the working tree to the un-fixed code mid-review, producing a false first-pass result.
Two rules fix that:

1. **Run on Python 3.12** (the project pin), NOT 3.14. Set up the workspace-local review venv exactly as
   `work/review/CAMPAIGN-0001/CODEX_ENV_SETUP.md` describes. Quick path with `uv`, from the repo root:
   ```
   uv python install 3.12
   uv venv --python 3.12 .venv-review
   source .venv-review/bin/activate        # Windows: .\.venv-review\Scripts\activate
   uv pip install -r requirements.txt -c constraints.txt
   ```
   Validate before reviewing: `python --version` → 3.12.x; `ruff --version` → 0.15.20;
   `mypy --version` → mypy 2.2.0; `lint-imports --version` → 2.13;
   `python -m pytest -q tests/test_position_folding.py` passes.

2. **Do ALL of this at ONE commit and never let the tree move mid-review.** Before every probe, confirm
   the tree is where you expect:
   ```
   git rev-parse HEAD          # expect the branch tip below
   git status --porcelain      # expect empty (clean tree)
   ```
   If either is unexpected, stop and re-checkout before continuing. Do not `git checkout` other commits
   between probes.

### Branch and commit — use `claude/fable-mode-os-install-1dlyk8` ONLY
```
git fetch origin claude/fable-mode-os-install-1dlyk8
git checkout claude/fable-mode-os-install-1dlyk8
git rev-parse --short HEAD          # expect 513d8a1 (or newer — if newer, note it in each result)
```

> **DO NOT check out `review/campaign-0001`.** That branch is **doc-only**: its `app/` is byte-identical
> to the un-fixed base `b600101` (none of the fixes are on it), and it does **not** contain the
> REV-0019/0020/0021 packets. Reviewing there = reviewing un-fixed code against missing packets (this is
> exactly the earlier mix-up). Everything you need — the fixed code AND all packets AND this prompt —
> is on `claude/fable-mode-os-install-1dlyk8`.
>
> **Right-branch sanity check (run once, right after checkout):**
> ```
> git diff --stat b600101 HEAD -- app     # MUST be NON-EMPTY (the fixes). Empty => you are on the wrong branch.
> ls work/review/REV-0020/request.md      # MUST exist. Missing => wrong branch.
> ```
> If `app/` diff is empty or REV-0020 is missing, you are on `review/campaign-0001` (or base) — switch
> to `claude/fable-mode-os-install-1dlyk8` before doing anything else.

- **Frozen review base:** `b600101`. `git diff b600101 HEAD -- app` is the entire remediation.
- Inspect any single fix's diff without moving the tree: `git show <sha> -- app` or
  `git diff b600101..<sha> -- app`.
- Review **at the current branch tip** (all fixes applied — this is the exact tree that will merge to
  master). Use the `git show`/`git diff` ranges only to *see* each fix; run repros against the checked-
  out tree.

### Gate commands — run ONCE, paste the output into each result.md as shared env evidence
```
ruff check .
mypy app/
lint-imports
python -m pytest -q          # full suite
```
State the interpreter (`Python 3.12.x`) and paste real output — evidence must no longer be
"environment-limited."

---

## A. REV-0019 — RE-RUN (env-corrected; OVERWRITE the old result)

- **Request (read):** `work/review/REV-0019/request.md`
- **Write to (OVERWRITE):** `work/review/REV-0019/result.md`
- **At the top of the new result.md, state:** *"Env-corrected re-run on Python 3.12.x — supersedes the
  prior REV-0019 result.md, which was affected by a transient checkout reversion between probes. All
  evidence below was produced at a single clean commit."*

**Scope (the original REV-0019 gated set):** F-001 sqlite flatten atomicity (commit `27bbffb`), UC-002
cancel operator-actor (commit `a22837e`), ADR-008 / INV-075 wording (commit `d3a3456`), and ENG-001
autonomous protection under HALTED — **first pass** (commit `6841b82`).

**Authoritatively re-confirm** the three that cleared, on 3.12, each with a runnable repro + pasted
output (dual-store where relevant):
- **REV-0006-F-001** — the whole sqlite `flatten_position` SUPERSEDE_AND_CREATE branch commits in ONE
  `_tx()`; a dispatch reject/crash leaves nothing durable; the standalone
  `create_order_for_sell_intent` self-heal still persists.
- **UC-002** — both cancel branches (CREATED→CANCELED and SUBMITTED→CANCEL_PENDING) carry the operator
  actor; routine transitions default to `system`.
- **ADR-008 / INV-075** — the wording accurately describes a pure sequence-ordered projector with
  legality enforced at `plan_transition_order` (does not claim the projector consults
  `ORDER_TRANSITIONS`).

**Continuity note for ENG-001 (important — do not re-open it here):** REV-0019 originally found the
ENG-001 first pass (`6841b82`) **incomplete** — a post-create/pre-approval HALTED window. That residual
has since been **remediated** by commit `7d41e4d`, which is reviewed in full as **REV-0020** below. So
in this REV-0019 re-run: record that the original ENG-001 residual finding stands historically and is
now remediated, and **defer the authoritative ENG-001 verdict to REV-0020**. Per-target gate decisions
for REV-0019: F-001 / UC-002 / ADR-008 → confirm CLEAR; ENG-001 → "remediated under REV-0020."

---

## B. REV-0020 — ENG-001 follow-up (kill-switch, human-gated surface)

- **Request (read):** `work/review/REV-0020/request.md`
- **Write to (CREATE):** `work/review/REV-0020/result.md`
- **Fix commit:** `7d41e4d` — `git show 7d41e4d -- app`.

The fix folds the whole autonomous protective exit into ONE store-atomic operation
`StateStore.open_protection_exit` (both stores): under a single lock hold it dedups single-flight →
checks HALTED (raises `ProtectionHaltedError`) → creates the `PROTECTION_FLOOR` intent → approves →
dispatches the MARKET order → appends `protection_triggered`. The engine
(`app/monitoring.py::_open_protective_exit`) now makes one call instead of the four separate public
awaits. Claim: no `await` sits between the HALTED check and the writes, so a concurrent kill can only
land before the op (refused, nothing durable) or after it committed (a legitimate exit opened while
ACTIVE).

**Key probes** (see the request's Probe section for the full list): re-run your own REV-0019 P1
interleaving against `7d41e4d` — note the engine no longer calls the public `transition_sell_intent`
during a protective exit, so verify (a) the tick truly routes through `open_protection_exit`, and
(b) engaging the kill at the last await before the atomic op leaves **nothing** (`halted [] [] 0`) in
**both** stores. Is there ANY remaining await between the FSM check and the durable writes? Does a
dispatch reject roll the whole unit back cleanly? Is the legitimate (non-HALTED) exit unharmed? Verdict
+ per-target gate for ENG-001, with runnable repro + pasted 3.12 output, both stores.

---

## C. REV-0021 — Wave-2 remediation batch (protective-floor, human-gated surface)

- **Request (read):** `work/review/REV-0021/request.md`
- **Write to (CREATE):** `work/review/REV-0021/result.md`
- **Fix commit:** `2aac709` — `git show 2aac709 -- app`.

Four confirmed Wave-2 findings, each with its own gate decision:
- **W2-CAND (P1)** — active-candidate single-flight now enforced in `create_candidate` (both stores):
  returns the existing PENDING/APPROVED candidate for a symbol+session idempotently instead of
  inserting a duplicate, under the same lock/tx as the insert (mirrors `create_sell_intent`). Probe:
  can any path still create two active candidates → two BUY order intents? Re-buy after ORDERED still
  allowed? Different sessions not deduped? Input validated before the idempotent return?
- **W2-STALE (P1, protective-floor)** — market-data staleness is now judged per-symbol (feed-wide
  connection-liveness OR the symbol's own `updated_at` age) in the real `AlpacaMarketDataStream`
  (`_snapshot_stale_locked`). Probe: does a quiet held symbol read stale while another keeps the feed
  clock fresh (both directions — masked breach AND spurious exit)? Is a total outage still caught? Is
  the change widen-only (nothing that was stale becomes fresh)? Confirm it's in the REAL stream (the
  `FakeMarketDataFeed` returns `stale` verbatim — why the original bug escaped unit tests).
- **W2-SESS (P2)** — operator actor threaded through `close_session` → `plan_close_session` → the
  `session_closed` audit payload; facade stops dropping it; default `system`. Probe: every close path
  stamps the actor; additive; the updated pre-existing test was corrected, not weakened.
- **W2-RISK (P3, non-gated)** — `risk_limit_reason` fails closed on a non-finite exposure/price.

Verdict + per-target gate (W2-CAND / W2-STALE / W2-SESS / W2-RISK), every P0/P1 with a runnable repro +
pasted 3.12 output, dual-store / real-stream where relevant.

---

## Response protocol (for each of the three packets)

1. Copy `.ai-os/templates/review-result.md` into that packet's folder as `result.md` (OVERWRITE for
   REV-0019; CREATE for REV-0020/0021) and fill it: a findings table, an overall **verdict**
   (`ACCEPT | ACCEPT-WITH-CHANGES | BLOCK`), and a **per-target gate decision**.
2. Every P0/P1 needs a **runnable repro + pasted Python 3.12.x output**, dual-store / real-stream where
   relevant. State plainly anything you could not verify.
3. Do **not** edit any `request.md`; do **not** push code fixes; **findings only**.
4. Paste the shared gate output (ruff / mypy / lint-imports / full pytest) once and reference it.

## File map (all on branch `claude/fable-mode-os-install-1dlyk8`)
| Packet | Read | Write result to | Fix commit |
|---|---|---|---|
| REV-0019 (re-run) | `work/review/REV-0019/request.md` | `work/review/REV-0019/result.md` (overwrite) | 27bbffb, a22837e, d3a3456 (+6841b82 → superseded by REV-0020) |
| REV-0020 | `work/review/REV-0020/request.md` | `work/review/REV-0020/result.md` (create) | 7d41e4d |
| REV-0021 | `work/review/REV-0021/request.md` | `work/review/REV-0021/result.md` (create) | 2aac709 |
| Env setup | `work/review/CAMPAIGN-0001/CODEX_ENV_SETUP.md` | — | — |
| Role | `AGENTS.md`, `prompts/INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md` | — | — |
