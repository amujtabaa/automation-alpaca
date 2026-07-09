---
type: Work Order
title: Fix fractional trade-size truncation in the alpaca market-data stream (REV-0002 F-003)
status: DRAFT
work_order_id: WO-0014
wave: W1
model_tier: mid
risk: medium
disposition: []
owner: Ameen (safety-adjacent: market-data drives the min-volume sizing gate)
created: 2026-07-09
---

# Work Order: Fix fractional trade-size truncation in the alpaca market-data stream

## Goal

Stop silently truncating fractional `trade.size` values into the session-volume
accumulator (a behavior change the WO-0012 type-cleanup introduced), so market-data
volume feeding the Strategy Engine's min-volume gate is not corrupted.

## Context packet

Read only these first:

- `AGENTS.md`
- `work/review/REV-0002/result.md` (F-003)
- `app/marketdata/alpaca_stream.py` — `_on_trade` (~400-420); `volume=int((existing.volume or 0) + trade.size)`
- `app/models.py` — `MarketSnapshot` (the `volume` field type)
- the min-volume gate consumer in the Strategy Engine (grep `min_volume`)
- `tests/test_alpaca_marketdata_stream.py` (existing stream tests use integral sizes only)

## Allowed paths

```yaml
allowed_paths:
  - app/marketdata/alpaca_stream.py
  - app/models.py
  - tests/test_alpaca_marketdata_stream.py
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/store/**
  - app/broker/**
  - app/api/**
  - cockpit/**
  - .github/workflows/**
  - .ai-os/**
```

## Required behavior

- [ ] A fractional `trade.size` (e.g. `0.5`) is no longer silently dropped from the
      accumulated session volume.
- [ ] The chosen policy (see Notes — **human decision D-1**) is implemented at root cause,
      not with another lossy `int()`.
- [ ] `mypy` stays green for the touched module without reintroducing the truncation.

## Required tests

- [ ] Regression: a fractional-size print (existing volume 100, `trade.size = 0.5`) is
      reflected per the chosen policy — RED against current `int(...)`, GREEN after.
- [ ] Existing integral-size stream tests still pass unchanged.

## Required commands

```bash
python -m pytest -q tests/test_alpaca_marketdata_stream.py
python -m pytest -q
ruff check app/ && ruff format --check app/
mypy app/
```

## Acceptance criteria

- [ ] Fractional sizes handled per the approved policy; no silent truncation.
- [ ] RED→GREEN regression; no existing test weakened.
- [ ] Scope limited to allowed paths.
- [ ] Fable DONE block with fresh evidence.

## Model-tier rationale

**mid** — small, well-localized fix; the only subtlety is the policy choice, which is a
human decision surfaced below.

## Notes

- **Human decision D-1 — fractional-size policy:**
  - **(A) Preserve fractional (recommended).** Accumulate volume as `float` (change
    `MarketSnapshot.volume` to `float`); the min-volume gate compares as float. Restores
    the pre-cleanup behavior with no data loss; the gate is a coarse threshold so float
    precision is harmless. Smallest correctness-true change.
  - **(B) Fail-closed.** Validate each incoming `trade.size` is a finite, positive,
    whole-share value; on violation halt/quarantine the symbol's feed per the market-data
    safety invariant ("invalid market data must halt or quarantine — never drive sizing").
    More defensive, but treats fractional equity prints (which do occur) as invalid.
- **Safety-adjacent, not on the human-gated list**, but it feeds sizing — treated as
  gated for approval out of caution.

## Completion disposition

_(complete after merge)_

## Distillation checklist

_(complete after merge)_

## Deletion decision

_(complete after merge)_
