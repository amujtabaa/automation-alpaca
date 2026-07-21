---
type: Work Order
title: Pure sell-side policy rebuild — regime-adaptive LASE core (ADR-010 §1, §7; research notes)
status: CLOSED
work_order_id: WO-0018
wave: W3
model_tier: strong
risk: medium
disposition: [RESULT_SUMMARY_KEPT]
record_reconciliation: "WO-0120 (2026-07-20) verified fable-done.md status VERIFIED and the existing WO-0018 DISPOSED ledger row; a canonical CLOSED ledger row is appended."
owner: Ameen
created: 2026-07-11
---

# Work Order: Pure sell-side policy rebuild (spike re-derivation, test-first)

## Goal

Rebuild the LASE policy as a **pure function** of `(envelope, MarketSnapshot, injected clock, prior
envelope events)` in a new `app/sellside/` package, red-green from scratch per ADR-010 D-4 —
now specified as a **regime-adaptive** policy per `pkl/architecture/sellside-research-notes.md`.
The bundled LASE code is design reference only and is **not ported**.

## Context packet

Read only these first:

- `AGENTS.md`
- `docs/adr/ADR-010-execution-envelope.md` (§2 bounds semantics, §7 spike ruling)
- `pkl/architecture/sellside-research-notes.md` — the distilled mechanism research (authoritative
  for the classifier/trail design below; do not re-derive from external sources)
- LASE design docs `00/01/02/05` (intent; the `code/` files are reference-to-delete)
  — **anchor divergence (2026-07-11, implementation seat):** the LASE package was never
  placed in this environment; design derived from ADR-010 §1/§2/D-4 + the research notes
  (which the final drop made authoritative anyway). If the docs later surface and diverge,
  that is WO-0022 / W4 input, not silent adaptation.
- `app/marketdata/service.py` — `MarketSnapshot` shape; staleness/finiteness semantics
- `app/models.py` — envelope model from WO-0016
- import-linter contracts (new package needs a contract entry — see Notes)

## Allowed paths

```yaml
allowed_paths:
  - app/sellside/**        # new package
  - tests/**
  - .importlinter          # import-linter contract addition ONLY (divergence note: the
                           # contracts live in .importlinter, not pyproject.toml as drafted)
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/store/**
  - app/broker/**
  - app/api/**
  - app/facade/**
  - app/monitoring.py
  - app/approval/**
  - cockpit/**
  - .github/workflows/**
  - .ai-os/**
```

## Required behavior

**Purity and rails (unchanged core):**
- [ ] `decide(envelope, snapshot, clock, history) -> PlannedAction | NoAction | BreachSignal` is
      pure: no I/O, no global state, no bare `datetime.now()`/`time.time()` (injected clock only),
      deterministic for fixed inputs.
- [ ] Hard rails never clamp (below-floor price, cooldown-floor violation, over-qty ⇒
      `BreachSignal`, never a submit plan). Soft bounds clamp into envelope ranges and report the
      clamp in action metadata.
- [ ] Stale/NaN/non-finite/out-of-range snapshot ⇒ fail closed + the envelope's stale-data
      disposition signal. Session phases outside the envelope's allowed set ⇒ `NoAction`.
- [ ] Cancel/replace budget and cooldown accounting derive from passed event history, never
      internal mutable state.

**Market-structure inputs (new, per research notes):**
- [ ] Internal **bar aggregator**: builds 5s/30s/1m bars from the snapshot history inside the
      policy (pure; no external bar feed).
- [ ] Volume profiler outputs: multi-window recent volume, **relative volume vs. session-adjusted
      baseline**, and **session-anchored VWAP** (anchored at extended-session open) accumulated
      from snapshot price×size.
- [ ] **ATR** computed from internal bars; all trail distances are denominated in **ATR multiples**
      (the envelope's soft trail range is `[min_atr_mult, max_atr_mult]`), not fixed percent.
- [ ] **Quantile fade detector**: flags when the latest short-window return falls in the lowest
      quantile of its own recent return distribution (nonparametric; no tuned constants beyond
      window + quantile).

**Regime classifier and regime→trail mapping (new):**
- [ ] Classifier over internal bars using ATR-ratio (current vs. rolling baseline) + trend
      strength + volume behavior, yielding: `FAST_SPIKE | STEADY_SURGE | MATURE_TREND |
      STALL_FADE | UNCERTAIN`. `UNCERTAIN` defaults conservative.
- [ ] Trail selection by regime: FAST_SPIKE → one-bar trail (prior internal bar low);
      STEADY_SURGE/MATURE_TREND → Chandelier ratchet (highest high since envelope activation minus
      ATR multiple) with structural exit checks against anchored VWAP / short-EMA band;
      STALL_FADE → Recovery-style accelerated tightening; UNCERTAIN → default ATR trail at the
      conservative end of the envelope range.
- [ ] **Working-stop ratchet is monotonic non-decreasing** for the life of the envelope,
      regardless of regime switches.
- [ ] **Trail-floor invariant**: the working trail is never tighter than the envelope's minimum
      ATR multiple, even at maximum urgency (over-tight stops systematically exit pre-continuation).
- [ ] Pullback discrimination: pullback on contracting volume tolerated within trail; pullback on
      **expanding** volume or a quantile-fade flag ⇒ tighten within bounds immediately.
- [ ] **Tranche exits**: policy may plan partial-size sells (first-objective tranche into strength,
      trail the remainder); tranche sizing respects participation caps and remaining qty.
- [ ] Time-to-close urgency ramp adjusts within soft bounds only.

## Required tests

- [ ] Unit, red-green each piece in order: bar aggregator; ATR; profiler windows/RVOL; anchored
      VWAP; quantile detector; classifier per regime (synthetic tapes); each regime's trail rule;
      ratchet monotonicity across regime switches; trail-floor invariant; floor/qty/cooldown
      breach signals; stale-data fail-closed per invalid-data class; tranche accounting.
- [ ] Property (hypothesis): for arbitrary envelopes + snapshot sequences — no plan ever violates
      a hard rail; determinism; **working-stop sequence is monotonically non-decreasing**; working
      trail ≥ envelope min ATR multiple at every step.
- [ ] Regression: bare-clock ban (grep/AST test: no `datetime.now(`/`time.time(` in `app/sellside/`).

## Required commands

```bash
ruff check . && ruff format --check . && mypy && lint-imports && pytest -q
```

## Notes

- Fable FULL. The D-4 spike ruling covers deleting the reference code, not skipping tests.
- Parallel-safe with WO-0017 once WO-0016 lands. Never touch `app/models.py` (worktree overlap
  rule, W3-README); policy-local types live in `app/sellside/`.
- Which regimes/parameters actually pay is an **empirical question for the W4 replay harness**
  (`work/queue/W4-SEED-NOTES.md`); do not add regimes beyond the five above.
