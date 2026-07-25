---
type: Review Result Addendum
rev_id: REV-0042
addendum: 01
title: "WO-0138 R5b-1 — re-review of the F-1 remediation and added pins"
reviewer_seat: Claude (independent review seat; implementer was Codex)
prior_verdict: BLOCK
verdict: ACCEPT
re_review_head_sha: 472de422c67cb14a9d0d21517031cdfe619e74b4
re_review_range: 23603ed..472de42
branch: codex/signal-r5b1-producer-ingest
reviewed: 2026-07-25
---

# REV-0042 addendum 01 — blocker cleared, verdict ACCEPT

Reviewer-owned addendum (the reviewed party never edits `result.md` in place; re-reviews are separate
disclosed addenda). The original **BLOCK** stands as the record of the first pass; this addendum
supersedes it with the final verdict.

Scope of this pass, as stated in `result.md`: **F-1's regression plus the added pins** — not a full
re-run. Two commits reviewed: `a92c8b8` (semantic fix) and `472de42` (evidence record).

## F-1 — CLEARED, reproduced directly

The blocker was an authenticated producer driving an unhandled `OverflowError` with **zero events
written**. The review seat re-ran its **own** original probe against the remediated head — the same
three variants, not the implementer's tests:

| Probe | Before (`23603ed`) | After (`472de42`) |
|---|---|---|
| `issued_at="9999-12-31T23:59:59+00:00"`, `ttl=300` | `OverflowError`, **0 events** | **422, 1 event** |
| timezone variant `…T23:59:59-23:59` | `OverflowError`, **0 events** | **422, 1 event** |
| same body on the **validation-failure** path | `OverflowError`, **0 events** | **422, 1 event** |

The safety property is fully restored: **recorded, attributable, no crash**, on all three paths
including the validation path that the original defect also reached.

**Decisively pinned, not merely present.** Neutering the new bound
(`app/api/schemas.py:169`, `_SIGNAL_ISSUED_AT_MIN_UTC <= normalized <= _SIGNAL_ISSUED_AT_MAX_UTC`)
makes `test_max_issued_at_is_recorded_validation_quarantine` fail with the `OverflowError` resurfacing
through starlette's error middleware; restoring it returns green.

**Implementation note — better than specified.** `result.md` asked for the bound to be *mirrored* in
`_safe_optional_issued_at`. Codex instead routed the validation path through the shared
`_normalize_signal_issued_at` helper imported from `app.api.schemas`, giving a **single source of
truth** rather than two constants that could drift. That is an improvement on the instruction, and the
validation-path probe confirms it works.

## Added pins — all present

F-2 through F-7 and F-9 all landed, expanding the corpus **38 → 49** cases:

| Finding | Pin added |
|---|---|
| F-2 | `test_signal_id_outside_wire_domain_is_validation_quarantine` (parametrized) |
| F-3 | `test_case_expanding_non_ascii_symbol_is_validation_quarantine` — the `ı→I` class the prior tests missed |
| F-4 | `test_unknown_top_level_key_is_validation_quarantine` |
| F-5 | `test_numeric_string_issued_at_is_validation_quarantine` |
| F-6 | `test_infinite_suggested_limit_price_is_validation_quarantine` |
| F-7 | `test_empty_thesis_is_validation_quarantine`, `test_provenance_over_wire_caps_is_validation_quarantine` (parametrized) |
| F-1 | `test_max_issued_at_is_recorded_validation_quarantine` (parametrized) + `test_allowed_upper_issued_at_is_normalized_before_freshness_math` |
| F-9 | conflict test strengthened |

The extra `test_allowed_upper_issued_at_is_normalized_before_freshness_math` is a good addition nobody
asked for: it pins that a value *just inside* the new bound still flows through the normal freshness
math, so the fix cannot silently over-reject.

## Scope discipline — verified

| Check | Result |
|---|---|
| `app/store/core.py` / `app/store/**` | **UNTOUCHED** — the out-of-scope store clamp was correctly not self-authorized |
| Reviewer-owned `work/review/REV-0042/result.md` | **byte-identical** to the planning-branch original (diff clean) |
| WO-0139 / disposition file "modifications" | **not implementer edits** — master is an ancestor of the branch, so these are the planning seat's own D5 ratification flowing in |
| F-8 / F-10 / F-11 | correctly untouched (register items) |
| WO-0138 status | still `REVIEW`; no ledger, no PR, no completion move |

## Gates reproduced by the review seat (POSIX, head `472de42`)

- Route corpus: **49 passed**, exit 0, zero failures
- **Full suite: exit 0, zero `FAILED`/`ERROR`, 100%**
- `ruff check .` → All checks passed
- `mypy app/` → **77 source files**, no issues
- `lint-imports` → **6 kept, 0 broken**

## Verdict

**ACCEPT.**

The sole blocker is closed and verified by the reviewer's own reproduction rather than the
implementer's evidence — the exact input that produced an unaudited crash now produces a recorded,
attributable 422 on all three paths, and the control is decisively pinned by red-green. All seven
follow-up pins landed, closing the unheld-guard gap that made several correct behaviours regressible.
Scope discipline was exact, including the judgement call to leave `app/store/` alone and escalate
rather than self-authorize.

**The REV-0042 review gate for WO-0138 is CLEARED.**

Remaining before R5b-2 (implementer/operator, not reviewer):
1. Close out WO-0138 in one commit: `REVIEW` → terminal status, disposition
   `[RESULT_SUMMARY_KEPT, PKL_UPDATED]`, `work/ledger.jsonl` line, move out of `work/active/`,
   signal-seat PKL R5b-1 changelog; both hygiene scripts green.
2. Write `work/review/REV-0042/disposition.md` (the REV-0039/40/41 convention), recording the
   BLOCK → ACCEPT sequence and carrying **F-8, F-10, F-11** forward as register items.
3. Merge the branch and the planning branch to master.
4. R5b-2's hard gate then passes (`routes_signals.py` on master **and** `REV-0042/disposition.md`
   present).

Carried forward to later rungs: **F-8** (the 409 response exposes `approved_by`/`converted_*` once R7
mounts approve), **F-10** (duplicate `SignalIngestResult` name; the `app.api → app.store.base` edge
that contract 5 cannot see by exemption), **F-11** (route corpus is memory-store only).
