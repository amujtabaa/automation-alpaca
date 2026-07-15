---
type: Architecture Knowledge
title: Sell-side policy research notes (mechanisms, not parameters)
status: draft
authority: low
owner: planning-seat
last_verified: 2026-07-11
tags: [sellside, research, lase, w4-seed]
source_refs: []
supersedes: []
superseded_by: null
---

# PKL — Sell-side policy research notes (mechanisms, not parameters)

Distilled 2026-07-11 (planning seat) from external sources for the WO-0018 policy rebuild and the
W4 harness/entry-envelope seeds. **Extraction rule: mechanisms transfer, parameters do not.** All
quantitative results below came from daily-bar large-cap backtests or discretionary practice —
none is evidence about extended-hours penny stocks. Which variants pay is decided only by the W4
replay harness under a pessimistic fill model. Do not port Pine/indicator code (license +
tests-after); the underlying math (ATR, Chandelier, Keltner, VWAP, pivots) is public domain.

## Exit mechanisms adopted into WO-0018

- **ATR-denominated trails** (Supertrend family): trail distance = multiple of realized-volatility
  ATR, so one policy self-calibrates across price levels/volatility. Bands are classically
  **monotonic** in-trend — independent validation of our ratchet. Too-tight multiples
  systematically exit the bar before continuation ⇒ the envelope's *minimum* trail multiple is a
  protective bound, not just the maximum.
- **Chandelier formulation**: trail from the *highest high since activation* minus k×ATR (not from
  last price). Composes naturally with the monotonic ratchet.
- **Recovery-style adaptive tightening**: when adverse movement exceeds a threshold in ATR units,
  the stop transitions to exponential tightening toward price — secures profit early on failed
  recoveries without violating monotonicity.
- **Noise-threshold ("evasive") widening**: within soft bounds, widen tolerance when price hovers
  near the band to avoid shakeout flips — for the grinder regime.
- **One-bar trail**: stop at prior bar's low; ultra-tight, high shakeout risk — correct only in
  the FAST_SPIKE regime near a blow-off.
- **Structural exits beat fixed-offset exits** (87-stops study: Keltner/MA/pivot classes
  outperformed offset trails): reference *moving structural levels* — session-anchored VWAP,
  short-EMA ± ATR band — with the peak-ratchet as the monotonic backstop beneath.
- **Historical-quantile fade detector**: exit/tighten trigger when the latest short-window return
  sits in the lowest quantile of its own recent distribution. Nonparametric, self-calibrating;
  our pullback-vs-reversal discriminator.
- **Regime classification**: ATR-ratio (current vs. rolling baseline) + trend strength (+ volume
  behavior) is the practitioner-consensus classifier; tighten in ranging, widen in volatile.

## Entry-side findings (seed parameters for W4 ADR-011 — defaults, all tunable; seed renumbered from ADR-010 on 2026-07-12, see W4-SEED-NOTES)

- Liquidity gate: relative volume ≥ ~5x session-adjusted baseline; ≥ ~200k premarket shares;
  price band ~$2–$20 (below ~$2 = manipulated territory). Refuse to enter what you couldn't exit.
- Trigger taxonomy (not naive %-move): break-and-hold above premarket high; break-and-retest;
  first pullback to anchor (VWAP/EMA) after a clean drive — pullback on *contracting* volume,
  bounce on *expanding* volume. Overextension filter: no entry far above VWAP without
  consolidation.
- Catalyst/volume validation: gaps on weak volume are noise; low-float no-catalyst spikes fade.
- Time decay: momentum plays out in ~30–90 min; TTL is a strategy parameter, not just safety.
- **Anti-pattern (hard rail)**: martingale/averaging-down — an entry envelope may never add size
  while the mark is below average cost. Backtests of these look great until the terminal sequence.

## Harness scoring spec (W4) — five metrics per (policy, tape)

1. **Exit efficiency** = realized return ÷ MFE (how much of the move the policy kept).
2. **MAE** — worst adverse excursion while open (protection quality).
3. **Ulcer Index** — RMS of running drawdown from peak while open (path quality).
4. **Post-exit downside avoided** — forward-return distribution after exit (did exiting help).
5. **Upside captured vs. available** — against the tape's max favorable window.
Grade per regime bucket; policies trade off 1 vs 4 differently per regime by design.

## Sources (accessed 2026-07-11; credibility notes inline)

- LuxAlgo library/blog (Supertrend family, Recovery, Evasive, AI Adaptive; Chandelier oscillator;
  pre-market momentum scans). Vendor content; mechanisms sound, performance claims unaudited;
  their own disclaimer concedes simulations misprice liquidity — reinforcing the pessimistic-fill
  harness.
- papertoprofit.substack.com — "87 stop losses" + "5-point trade quality" (Stuart Farmer).
  Measurement methodology strong (per-trade path metrics, post-exit forward returns); headline
  strategy posts (69% CAGR, martingales, 30x AI agents) are single-backtest overfit — mine for
  *how to measure*, never *what to trade*.
- Gap-and-go / VWAP practitioner corpus (tradezella, tradealgo, highstrike, trademomentum,
  snappchart): consistent on RVOL gates, PMH levels, trigger taxonomy, time-based exits;
  discretionary, unbacktested — treated as defaults to test, not truths.
