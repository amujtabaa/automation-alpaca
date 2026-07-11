---
type: Review Disposition
rev_id: REV-0008
campaign_id: CAMPAIGN-0001
verdict_received: BLOCK
disposition_status: VERIFIED
remediation_status: DEFERRED-GATED (forward-hardening) + doc-fix
verified_env: python 3.12.3 (venv, with import-linter/grimp/mypy), frozen base b600101 == HEAD app/
date: 2026-07-10
---

# Disposition — REV-0008 (ARCH, holistic architecture)

Reviewer: GPT-5 Codex, verdict **BLOCK** (ARCH-001 P1). Author-side verification ran the **real
`lint-imports`** the reviewer lacked. Both findings' mechanics are **CONFIRMED**; ARCH-001's severity
downgrades **P1 → P2** because it is **latent** (no current route exploits it).

## Per-finding verdicts

### ARCH-001 — Contract-5 facade boundary is bypassable (reviewer P1) → **CONFIRMED (mechanics)**, **P2 (latent / forward-hardening)**
Reproduced with the real linter (baseline `5 kept, 0 broken`):
- **New-route bypass:** a scratch `app/api/routes_escape.py` with `import app.store` (NOT in the
  hand-enumerated Contract-5 source list, `.importlinter:139-147`) → linter stays `5 kept, 0 broken`
  despite two direct forbidden imports.
- **Indirect bypass:** a *listed* route importing `app.api.deps.get_store` (`deps.py:26-29`, returns
  the raw `StateStore`) passes because `allow_indirect_imports = True` and `app.api.deps` is neither a
  source nor a forbidden target.
- **Control (linter is not toothless):** the same listed route with a *direct* `import app.store` →
  `4 kept, 1 broken`. So the gap is precisely the enumeration + indirection.
- **Statement check:** INV-074 ("New route→backend imports are forbidden … can only tighten") and the
  `.importlinter` comments ("any new direct route→backend edge fails the build") are **overstated** vs
  what is mechanically enforced — a real contradiction, which is exactly this packet's mandate. (ADR-005
  itself is worded as intent, not total mechanical closure.)
- **Why P2:** **latent** — `grep get_store app/api/routes_*.py` → none; no route reaches a backend
  module directly today. No independent test guards it (`tests/test_import_boundaries.py` admits the
  route→facade ratchet is INI-only). It is a completeness/forward-hardening gap, not a live defect.

### ARCH-002 — stale facade-protocol module docstrings (reviewer P2) → **CONFIRMED**, **P2**
Module docstrings in `app/facade/commands.py:3-24`, `queries.py:3-8`, `protocols.py:9-14` still say
only Phase-1 methods are real / everything else raises `NotYetImplementedError`, while an AST
comparison (my run) confirms **all 12 command methods + 17/20 query methods are real** (only
`list_primaries`/`list_spawns`/`kill_state` remain stubs) and there is **no** protocol/impl drift.
Purely a stale-docs coherence defect — but it actively misleads a future agent about whether
safety-relevant methods (`set_kill_switch`, `create_exit`, `cancel`) are live, so P2 (not P3) is fair.

## Disposition
- **ARCH-001:** CONFIRMED P2 → **gated** forward-hardening WO (route/facade boundary): derive Contract-5
  sources from all `app/api/routes_*.py` (or add an INI-independent test that fails on an unlisted
  route) **and** stop routes obtaining a raw store via `get_store` (split composition-only providers
  from route-importable facade providers; forbid the former to routes). Regression proving both the
  new-file and `get_store` bypasses fail. Test-first, Codex re-review.
- **ARCH-002:** CONFIRMED P2 → refresh the three module docstrings to the P6-complete surface (name
  the three remaining stubs). Low-risk docs; batch with cleanups.

## Gate
The architecture-foundation BLOCK is **downgraded to a forward-hardening P2**: the enforced structure
matches the target *today* (cockpit↛app, SDK confined, models leaf, no store↔events cycle all
independently reconfirmed); the gap is the contract's completeness against *future* additions.
Evidence: real `lint-imports` runs (baseline + bypass experiments + control), AST port/impl diff.
`git status` clean after scratch modules removed.
