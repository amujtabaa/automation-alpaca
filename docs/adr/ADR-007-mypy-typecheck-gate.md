# ADR-007 — Adopt a mypy Static-Typecheck Gate (baseline-and-ratchet)

## Status

Accepted (2026-07-08, by Ameen). Raised by WO-0008; tooling wired in the same change
(`requirements.txt`, `pyproject.toml [tool.mypy]`, `.github/workflows/ci.yml`, CLAUDE.md, testing-model.md).

## Context

The always-on contract (CLAUDE.md §Testing, `pkl/architecture/testing-model.md`) named a
`ruff + mypy + pytest` gate, but `mypy` was wired nowhere (WO-0008; corrected to "deferred" in
commit `3989984`). A static type gate has real safety value here: a measured baseline of the code
today is **187 errors across 16 modules (`mypy app/`, pydantic plugin + `ignore_missing_imports`)**,
~85% None/Optional-flow (`union-attr`/`operator`/`arg-type`) — exactly the class of bug that is
money-affecting in an execution engine (a `None` price into sizing, a short-flip on a bad Optional).
The debt concentrates in the highest-risk modules (`store/sqlite` 58, `store/memory` 40,
`monitoring` 24). Fixing all 187 up front would block the gate indefinitely.

## Decision

Adopt `mypy` as a CI gate over `app/`, introduced by **baseline-and-ratchet**, mirroring the repo's
existing import-linter ignore-list and coverage `fail_under` ratchets:

- Config in `pyproject.toml [tool.mypy]`: `python_version=3.11`, `plugins=["pydantic.mypy"]`,
  `ignore_missing_imports=true` (alpaca-py/streamlit ship no stubs).
- A **grandfather punch-list** — the 16 currently-erroring modules get `ignore_errors=true` via
  `[[tool.mypy.overrides]]`. New modules are type-checked from day one; the punch-list only shrinks.
- CI runs `mypy app/` as a step next to `ruff check` / `lint-imports`; it is **green today** (proven).
- Burn down the punch-list over time, **safety-critical stores first** (`store/*`, `monitoring`,
  `policy`), each removal its own small change.

`mypy` is added to `requirements.txt` (pydantic is already present). Scope is `app/` (backend);
`cockpit/` is out of scope for now.

## Consequences

- New CI dependency + step; the gate can only tighten (`unmatched`-style ratchet).
- **Known limitation (accepted):** a new type error inside a *grandfathered* module is NOT caught
  until that module is cleaned and removed from the punch-list — the coarse, module-level trade-off.
  Finer, line-level baselining (e.g. the `mypy-baseline` tool) is a documented future upgrade, as is
  flipping `warn_unused_ignores` to `true` after burn-down.
- CLAUDE.md §Testing and `testing-model.md` move `mypy` from "deferred" to "wired" on acceptance.

## Required tests / evidence

- `mypy app/` is green under the ratchet config — **PROVEN** (`Success: no issues found in 54 source files`).
- The gate has teeth — a new error in a checked module fails it — **PROVEN**
  (`app/main.py:172: Incompatible return value type … [return-value]`, exit 1).
- The limitation is real — a new error in a grandfathered module passes — **PROVEN** (documented above).
- CI step fails the build on a new type error in a checked module (to be added with the tooling change).
