---
type: Review Request
rev_id: REV-0031
title: WO-0111 — two round-2 PR #9 correctness follow-ups (monitoring supersession attribution + emergency-reduce re-authorization)
status: AWAITING_REVIEW
targets: [WO-0111]
human_gated_surfaces:
  - envelope fill attribution and monitoring cancellation lineage
  - emergency-reduce override authorization (ADR-003; reduce-only flatten while halted)
commit_range: 7194f02..4d607da
branch: consolidate/r2-canonical
created: 2026-07-18
---

> **Context — what this review is.** This is an internal software-correctness review of a
> **paper-trading simulator** (Alpaca Spine v2): a FastAPI + SQLite / in-memory order-lifecycle
> engine that runs only against a broker *paper* sandbox. There is no live trading, no real funds,
> and no network / credential / authentication surface in scope. "Safety" here means order-lifecycle
> **correctness invariants** — a submitted order is not a fill; only fill events change a position's
> quantity; at most one exit per symbol reaches the venue; a reduce-only exit is authorized exactly
> once. The task is ordinary defensive QA: independently confirm that two correctness fixes hold by
> property, and look for a concrete counterexample where they do not. Produce findings only; do not
> push code.
>
> **Domain glossary (bookkeeping terms, not security terms).**
> - *Envelope* — the state-machine row that tracks one symbol's exit obligation.
> - *Supersession* — replacing an envelope with a successor that inherits the same `sell_intent_id`
>   (an amendment); the predecessor becomes `SUPERSEDED`.
> - *ENVELOPE_ACTION* — an append-only event linking an envelope to an order it minted.
> - *Owner-scoped discovery* — monitoring finds an envelope's actions by parent id **or** the shared
>   `sell_intent_id` (`correlation_id`) **or** the referenced order's owner, so a *malformed* action
>   with broken parent linkage is still noticed rather than silently dropped.
> - *Flatten* — mint a market exit to bring a position to zero.
> - *Emergency-reduce override* — an audited, single-use grant (ADR-003) that authorizes one
>   reduce-only flatten while the session is `HALTED`, without lifting the halt.
> - *Recovery record* — a durable "the broker order may still execute even though the local row is
>   terminal" marker.

## Your role

You are the independent review seat, a different model from the author. Re-derive behavior from the
diff and current tests; do not rely on the author's reasoning or the in-process gate output. The
operator has authorized these two follow-up fixes (see `work/completed/WO-0111-pr9-review-round2-
followups.md`); the authorization covers the fix, **not** the merge. This packet clears the
independent-review gate for WO-0111 only on your **ACCEPT / ACCEPT-WITH-CHANGES**.

Create `result.md` in this folder. Each finding: `file:line`, why it matters (a concrete failing
sequence, not a style note), and what resolves it. End with `BLOCK`, `ACCEPT-WITH-CHANGES`, or
`ACCEPT`, plus anything you could not verify.

## What you are reviewing

```
git diff --stat 7194f02..4d607da
git diff 7194f02..4d607da
```

Two correctness follow-ups the diff-scoped round-3 review (REV-0030, ACCEPT) did not reach on the
WO-0109 code. Both were empirically reproduced before any change.

**Finding 1 — a superseded predecessor made monitoring disown the successor's order.**
`_validated_envelope_lineage` (`app/monitoring.py`) builds a **single-envelope** obligation
projection (`envelopes=[envelope]`, line 595) but feeds it the **owner-scoped** action set. After a
legitimate supersession, the `SUPERSEDED` predecessor's own ENVELOPE_ACTION — it carries the shared
`sell_intent_id` as `correlation_id` — was pulled into the successor's projection. The projector,
seeing an action whose parent envelope is not in the one-element set (`app/store/core.py:1186`),
records the predecessor as a *missing envelope*; `_envelope_id_for_order` (line 649) then returns
`None` for the successor's real order (its `missing_envelope_ids` gate, line 672). Downstream, a
`None` attribution means the successor's broker fills **skip `record_envelope_fill`**, so the
successor envelope never decrements and never reaches `COMPLETED`.
- **Fix:** `_owner_scoped` now excludes any action whose parent is a **known, distinct** envelope
  (`known_sibling_ids`, lines 560/565) — that action belongs to the sibling's own lineage. Discovery
  still fires for an action whose parent is **absent, or a fabricated/unknown id** (the malformed-
  lineage diagnostic the owner-scoped pass exists for).

**Finding 2 — the emergency-reduce override wedged the operator's own retry.**
The grant (ADR-003) authorizes one reduce-only flatten and is consumed by it on an authorized
create/existing/flat outcome (`app/store/memory.py:2903`). But the WO-0108/REV-0029 hardening makes
the flatten fail **closed** (409) whenever a venue-uncertain BUY remains — the store returns
`FLATTEN_BUYS_OPEN` *before* it consumes (`memory.py:2896`), and the facade retry loop raises at
`_FLATTEN_MAX_BUY_CANCEL_ATTEMPTS` (`app/facade/store_backed.py:877`). The grant is left **active and
un-consumed**, so the operator's documented remedy ("retry after reconciliation confirms the BUY
terminal") hit the defensive "an override is already active" refusal → a permanent 409.
- **Fix:** re-authorization is **idempotent** (`memory.py:4568`, `sqlite.py` twin) — the ADR-003
  preconditions are re-validated on every call, but an already-active grant is **reused** rather than
  refused or stacked. The one policy-conflict test that pinned the old refusal is amended (its
  invariant, one grant → one exit, is kept and strengthened).

## Start here

- Finding 1: `app/monitoring.py:554-566` (the sibling-exclusion guard), `:595` (single-envelope
  projection), `:649-672` (`_envelope_id_for_order` and its missing-envelope gate);
  `app/store/core.py:1186` (the branch that flags a non-member action's parent as missing).
- Finding 1 store parity: `app/store/memory.py:1064-1117` (`action_in_scope` — note line 1091, the
  single-`envelope_id` strict filter) and the SQLite twin selector.
- Finding 2: `app/store/memory.py:4528` and `:4568` (`authorize_emergency_reduce_override`, idempotent
  reuse); `app/store/sqlite.py:6325` (twin); `app/store/memory.py:2896` and `:2903` (the BUYS_OPEN
  early-return before consume, and consume-on-authorized-outcome); `app/facade/store_backed.py:1041`,
  `:1075`, `:851-895` (the emergency path and the fail-closed retry loop).
- Tests: `tests/test_wo0111_pr9_review_round2.py` (2 pins × both stores); the amended
  `tests/test_spine_phase3e_manual_flatten.py::test_reauthorize_reuses_active_grant_without_stacking`.

## What to verify — closure by property (most important first)

For each, check the full boundary, not just the one instance the fix touched. Where a claim is
universally quantified ("every parent kind", "both stores", "exactly once"), verify the enumeration
against a fresh read — never by sampling positives.

1. **Finding 1 completeness (does the exclusion ever drop a genuinely-malformed action?).**
   Enumerate an ENVELOPE_ACTION's parent-`envelope_id` cases against the reviewed envelope `E`:
   (a) `= E`; (b) `None`; (c) a fabricated / unknown id; (d) a **known** distinct sibling. For each,
   does the new `_owner_scoped` classify it correctly — retain (a)/(b)/(c) so the malformed-lineage
   diagnostic and fail-closed cancel still fire, exclude only (d)? Is there any corruption of `E`'s
   *own* obligation that presents as case (d) and would now be missed? (If so, is it still caught
   when the sibling's **own** lineage is validated — i.e., is monitoring's per-envelope sweep
   total?)
2. **Finding 1 store parity.** Confirm the store's projection cannot exhibit the same successor-
   disown: does any store path combine a single-envelope scope with owner-`correlation_id` discovery?
   Trace `action_in_scope` (memory.py:1079) for a single `envelope_id` (line 1091) versus an
   intent/symbol scope (whole lineage into `envelopes`), and the SQLite selector twin.
3. **Finding 1 exactly-once attribution.** After the fix, when the successor's order fills through the
   monitoring bridge, is it attributed to the successor **exactly once**, and never also to the
   predecessor? Can any interleaving double-count a fill or attribute it to the wrong envelope?
4. **Finding 2 precondition integrity.** On the idempotent path, are ALL ADR-003 preconditions still
   re-checked on every call *before* the reuse (`HALTED`, open position, no unresolved
   `TIMEOUT_QUARANTINE` for the symbol)? Can the idempotent branch ever write a **second** grant, or
   skip a precondition a fresh grant would enforce?
5. **Finding 2 one-grant-one-exit.** Is exactly one reduce-only exit still authorized per grant?
   Trace two `authorize` calls → one grant → is it consumed exactly once by the first authorized
   flatten? Can two flattens each observe an active grant and both mint an exit (a double exit while
   halted)?
6. **Finding 2 residual active-grant window.** By design the grant stays active on the fail-closed
   path so the retry can reuse it. Enumerate every consumer of an active grant: can an **ordinary**
   (non-emergency) same-symbol flatten consume it and slip past the halted-deny? Is that window
   **pre-existing** (present before this change, since the grant already survived the fail-closed
   path) or newly introduced/widened here? State which, with code evidence.
7. **Pin integrity (mutation).** For each new/changed pin, can the guarded branch be removed while the
   exact test turns red? Specifically: does `test_finding1_...` still fail if the `known_sibling_ids`
   exclusion is neutered, and do both Finding-2 pins fail if the idempotent `return` is restored to a
   raise? Does the amended `test_reauthorize_...` still assert the real invariant (`== {"AAPL"}`, one
   grant) rather than merely "does not raise"?
8. **Traceability.** Is every changed line attributable to WO-0111, with no drift in the WO-0109
   hardening, ADR-003/ADR-010, or the paper-only invariants?

## Fresh property probes

WO-0111 **adds/amends no `INV-*`** (it is a correctness fix to existing behavior), so the PROC-0001
new-invariant obligation is N/A. Two fresh end-to-end probes are offered instead — new scenarios, not
reruns of the pinning tests. Record the harness and outcome in `result.md`.

- **Finding 1 (fill attribution).** Activate a predecessor envelope for intent `I`; stage a child
  that fails to submit (a released, staged `CREATED`); supersede it with a successor for the same
  `I`; stage and rest the successor's child; deliver a broker fill for the successor's order through
  the monitoring fill path. Assert the **successor** envelope's `remaining_quantity` decrements by
  exactly the fill and the predecessor's does not; assert the position folds the fill exactly once.
  Both stores.
- **Finding 2 (retry after fail-closed).** Halt the session with an open position and a same-symbol
  BUY that leaves the flatten venue-uncertain (so the emergency reduce fails closed / 409 with the
  grant still active). Reconcile the BUY to a broker-authoritative terminal, then re-issue the
  emergency reduce. It must now authorize and produce a reduce-only exit — not refuse with "an
  override is already active". Confirm exactly one grant existed throughout and is consumed once.
  Both stores.

## Verification commands (each green at `4d607da`)

```
ruff check .
ruff format --check .
mypy app/
lint-imports
pytest -q
pytest -q tests/r2_conformance_oracle.py
pytest -q tests/test_r2_conformance_oracle_claude.py
pytest -q tests/test_review_hardening_gates.py
pytest -q tests/test_wo0111_pr9_review_round2.py
python -m tests.performance.r2_scaling_gate
```

Author evidence — treat as claims to reproduce, not a substitute for review: full suite green on both
stores (exit 0); `mypy app/` clean (64 files); `lint-imports` 6 contracts kept; both spec oracles
green; review-hardening gates green; scaling gate `passed: true` with runtime ratio 1.19 ≤ 3.0 and
startup 7.44 ≤ 12.0 (limits unchanged); AI-OS hygiene green; no tracked `.agents/.codex`. The two new
pins were red on the pre-fix tree and each was mutation-verified (guard neutered → the exact pin
turns red) before commit.
