---
type: Work Order
title: Add a mypy static-typecheck gate (baseline-and-ratchet)
status: CLOSED
work_order_id: WO-0008
wave: W3-quality
model_tier: strong
risk: medium
disposition: [ADR_CREATED, PKL_UPDATED]
owner: Ameen (planning) / Claude (implementer)
created: 2026-07-08
---

# Work Order: Add a mypy static-typecheck gate (baseline-and-ratchet)

> DRAFT earmark. Raised while correcting the CLAUDE.md/testing-model "gate" claim,
> which named `mypy` although it is wired nowhere. This order makes the claim true.
> Adding a dependency + a CI gate ⇒ **ADR required** (CLAUDE.md: "New dependency ⇒ ADR first").
> Prioritize when the team wants the type-safety gate; not urgent, not safety-runtime.

## Goal

Introduce a `mypy` static-typecheck gate that catches type errors (especially
None/Optional-flow) on new code from day one, without blocking on the pre-existing
backlog — via a baseline-and-ratchet, mirroring the import-linter and coverage gates.

## Measured baseline (2026-07-08, throwaway `mypy app/`, no config — UPPER bound)

- **193 errors across 17 files** (54 source files checked). Identical with
  `--ignore-missing-imports`, so it is real code, not third-party-stub noise.
- Category mix: `union-attr` 103 · `operator` 30 · `arg-type` 32 · misc/assignment/
  return-value/attr-defined/type-var 28. ~85% is None/Optional handling.
- Upper bound: no pydantic mypy plugin and default strictness; a real config + the
  pydantic plugin + targeted ignores will reduce the actionable count.

## Context packet

- `CLAUDE.md` (§Testing and CI — the corrected gate line), `pkl/architecture/testing-model.md`
- `pyproject.toml` (`[tool.pytest]`/`[tool.coverage]` — where a `[tool.mypy]` block would live)
- `.github/workflows/ci.yml` (add a `mypy` step next to `ruff check` / `lint-imports`)
- `.importlinter` (the existing ratchet pattern to mirror)

## Allowed paths (when activated)

```yaml
allowed_paths:
  - "**"                       # read-only everywhere
write_allowed:
  - pyproject.toml             # [tool.mypy] config
  - requirements.txt           # add mypy (+ pydantic plugin if used)
  - .github/workflows/ci.yml   # the mypy CI step
  - docs/adr/**                # the "adopt mypy" ADR (human-approved)
  - app/**                     # only if fixing real type bugs found during baselining
  - tests/**
  - pkl/architecture/testing-model.md
  - work/active/WO-0008*/**
```

## Forbidden paths

```yaml
forbidden_paths:
  - "cockpit/**"   # unless UI typing is explicitly in scope
```

## Required behavior

- [ ] Decide + record (ADR) the config: strictness, pydantic plugin, `ignore_missing_imports`, per-module overrides, whether cockpit/ is in scope.
- [ ] Baseline-and-ratchet: grandfather the existing errors (baseline file or per-module ignores) so CI fails only on NEW type errors; the baseline only shrinks (never grows — mirror import-linter's `unmatched_ignore_imports_alerting = error`).
- [ ] Wire the CI step; document how to reduce the baseline over time.

## Required tests / commands

```bash
python -m pip install mypy   # + pydantic plugin if adopted
mypy app/                    # against the new config
ruff check . && python -m pytest -q && lint-imports   # existing gates still green
```

## Acceptance criteria

- [ ] `mypy` runs in CI and fails the build on a NEW type error; the grandfathered baseline is documented and monotonically shrinking.
- [ ] ADR created (new dependency + new gate).
- [ ] CLAUDE.md / testing-model.md updated: `mypy` moved from "deferred" to "wired".
- [ ] Fable DONE block with evidence.

## Model-tier rationale

Strong: config/ratchet design + judgment on which of the 193 are real bugs vs
false positives, on a codebase where None-flow errors can be money-affecting.

## Notes

- Sequencing: independent of WO-0007; either can go first. Consider doing this
  BEFORE the WO-0007 order-status/spawn work so that new safety-critical code lands
  under the type gate.

## Completion disposition

- [x] PKL_UPDATED — testing-model.md: mypy deferred→wired
- [x] ADR_CREATED — ADR-007 (Accepted)
- [ ] RESULT_SUMMARY_KEPT
