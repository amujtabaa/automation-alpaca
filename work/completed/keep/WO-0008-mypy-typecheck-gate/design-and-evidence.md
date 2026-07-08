---
work_order: WO-0008
title: mypy typecheck gate — design, proven ratchet, and the exact diffs to apply on acceptance
date: 2026-07-08
status: APPLIED — ADR-007 accepted 2026-07-08; Diffs 1-4 merged; ruff+mypy+pytest green
---

# WO-0008 — mypy gate: design + evidence (apply on ADR-007 acceptance)

Design decisions live in **ADR-007** (Proposed). This doc holds the proven ratchet and the exact,
ready-to-apply diffs. **Nothing tooling-related is merged yet** — `requirements.txt`, `pyproject.toml`,
`ci.yml`, `CLAUDE.md`, `testing-model.md` are unchanged; they land only when you accept ADR-007.

## Evidence (all from this session, config at scratchpad/mypy_ratchet.toml)

- Baseline before ratchet: `mypy app/` (pydantic plugin + ignore-missing-imports) = **187 errors / 16 files**.
- Under the ratchet: `Success: no issues found in 54 source files` (exit 0) — **GREEN**.
- Teeth: injected `def f(x:int)->str: return x` in `app/main.py` → `app/main.py:172: Incompatible return value type (got "int", expected "str") [return-value]`, exit 1.
- Limitation: same injection in grandfathered `app/policy.py` → `Success` (not caught). Documented in ADR-007.
- 30 of 46 non-`__init__` modules are actively checked now; 16 grandfathered.

## Diff 1 — `pyproject.toml` (append)

```toml
[tool.mypy]
python_version = "3.11"
ignore_missing_imports = true      # alpaca-py / streamlit ship no stubs
plugins = ["pydantic.mypy"]
warn_unused_ignores = false        # future tightening: flip to true after burn-down

# Baseline-and-ratchet grandfather list (ADR-007). New modules ARE checked; this
# list only shrinks — burn down safety-critical stores first. Mirrors the
# import-linter ignore-list + coverage fail_under ratchets already used here.
[[tool.mypy.overrides]]
ignore_errors = true
module = [
  "app.store.sqlite", "app.store.memory", "app.store.core",
  "app.monitoring", "app.features", "app.protection", "app.policy",
  "app.reconciliation", "app.strategy",
  "app.broker.alpaca_paper", "app.broker.factory",
  "app.marketdata.alpaca_stream", "app.marketdata.factory", "app.marketdata.fake",
  "app.facade.store_backed", "app.api.routes_dev",
]
```

## Diff 2 — `requirements.txt` (add near ruff/import-linter)

```
mypy>=1.10  # static typecheck gate over app/ (ADR-007); baseline-and-ratchet, enforced in CI
```
(pydantic is already a dependency; `pydantic.mypy` plugin ships with it.)

## Diff 3 — `.github/workflows/ci.yml` (new step, after "Lint (ruff)")

```yaml
      - name: Typecheck (mypy)
        # ADR-007 gate. Green today under the pyproject baseline-and-ratchet;
        # fails on a NEW type error in any non-grandfathered module.
        run: mypy app/
```

## Diff 4 — instruction files (move mypy "deferred" → "wired")

- `CLAUDE.md` §Testing gate line: restore `mypy` to the enforced list (`ruff` + `mypy` + `pytest`),
  drop the "aspirational/deferred" parenthetical.
- `pkl/architecture/testing-model.md`: move the mypy bullet from "Deferred gate" to the wired CI gate
  line; keep the burn-down note (punch-list shrinking) + baseline reference.

## Burn-down plan (post-acceptance, each its own small WO/PR)

1. `app/store/sqlite.py` + `app/store/memory.py` (the single-writer stores — highest safety value).
2. `app/monitoring.py`, `app/policy.py` (execution loop + risk).
3. Remaining modules; then flip `warn_unused_ignores=true`; then evaluate line-level `mypy-baseline`.

## fable_done

```yaml
fable_done:
  task: "WO-0008 — design + prove the mypy baseline-and-ratchet gate; draft ADR-007"
  done_when_results:
    - "config decided + recorded in ADR-007: MET"
    - "ratchet proven green + proven to have teeth + limitation proven: MET (evidence above)"
    - "exact diffs prepared: MET (Diffs 1-4)"
    - "ADR created: MET (ADR-007 Proposed)"
    - "CLAUDE.md/testing-model flip: PREPARED, held for acceptance"
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
  evidence:
    - "mypy app/ Success (0 issues); injected error in app/main.py caught (exit 1); grandfathered miss shown"
  status: VERIFIED   # ADR-007 accepted; Diffs 1-4 + ruff exclude applied; ruff/mypy/pytest all green locally
```
