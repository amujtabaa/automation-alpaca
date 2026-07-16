# FINDING — LASE trail cannot hold a pull-to-VWAP on low-volatility grinds (mechanism gap)

- **Status:** OPEN (found by WO-0021, 2026-07-12). Pinned by
  `tests/test_wo0021_regime_tapes.py::test_trend_pullback_resume_takes_one_tranche_and_survives`
  (`xfail(strict=True)` — flips loudly the moment a fix lands).
- **Severity:** P2 (behavioral quality, not a safety rail — every hard rail still holds; the
  policy exits EARLY, it never exits illegally).
- **Surfaced by:** the WO-0021(final) regime-tape catalog, scenario 3 ("trend-then-pullback ⇒
  remainder survives the pullback").

## What

On a clean low-volatility drive (small per-bar true ranges), the working stop is
`ref_high − k×ATR` with `k ≤ max_atr_mult` (Chandelier). ATR on such a grind is tiny, so even the
WIDEST allowed trail sits a few cents under the highs — while a routine, healthy
pullback-to-anchored-VWAP is many multiples of that. Result: the post-tranche remainder is
stopped out at the first orderly pullback, exactly the shakeout the research notes warn about.

## Why (root cause, design level)

`pkl/architecture/sellside-research-notes.md` adopted "structural exits beat fixed-offset exits:
reference moving structural levels — session-anchored VWAP, short-EMA ± ATR band — with the
peak-ratchet as the monotonic backstop BENEATH". WO-0018's implementation used the structural
level only to TIGHTEN (close < bar-VWAP ⇒ snap toward min multiple); it never lets a healthy
trend REST its stop at the structural level (wider than k×ATR from the highs) with the ratchet
beneath. The "noise-threshold (evasive) widening" mechanism from the notes was likewise not
adopted. Both omissions bind only in the low-ATR-grind regime.

## What resolves it

A follow-up WO (post-review / W4): candidate stop for STEADY_SURGE/MATURE_TREND =
`min( ref_high − k×ATR, structural_hold )` where `structural_hold ≈ anchored_VWAP − m×ATR` on
contracting-volume pullbacks — still monotone under the ratchet, still floored by
`min_atr_mult`, still hard-rail-safe. This is ALSO a prime W4 bake-off axis and is called out in
the SOL-0001 collaboration packet's territory (mechanism design inside the frozen contract).
Parameters (m, hold conditions) are harness-tunable per the extraction rule.

## Safety analysis

No invariant is violated: exits happen above the floor, sized within rails, budget-accounted.
The failure mode is opportunity cost (premature exit), which the W4 five-metric scorer measures
directly (exit efficiency / upside captured).
