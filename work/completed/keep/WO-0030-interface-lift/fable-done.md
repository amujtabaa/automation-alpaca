# WO-0030 — DONE (VERIFIED)

[FABLE • FULL • verification: DIRECT • task: WO-0030]

Approved in-chat ("You may proceed"). Non-gated surfaces; mechanical but broad
import surface. Interface-only — no behavior change.

## done_when → met

1. **Envelope API lifted onto the `StateStore` ABC.** Eight abstract methods
   declared in `app/store/base.py` (create_envelope / get_envelope /
   list_envelopes / transition_envelope / supersede_envelope /
   record_envelope_fill / stage_envelope_action / approve_envelope_activation),
   signatures copied verbatim from the two concrete stores (confirmed identical
   memory ↔ sqlite before lifting). `EnvelopeTransitionError` relocated to
   base.py (kept a plain `ValueError` subclass — reparenting to `StoreError`
   would widen every `except StoreError`; a relocation must not); core.py
   re-imports it so `from app.store.core import EnvelopeTransitionError` still
   resolves for every existing caller. `PlannedAction` /
   `EnvelopeActionStageResult` are TYPE_CHECKING-guarded in base.py — core.py
   imports base.py, so a runtime import would cycle; `from __future__ import
   annotations` keeps the annotations as strings, which is all mypy needs.
2. **Facade Protocols extended.** `list_envelopes` on `ExecutionQueryFacade`;
   `approve_envelope` / `cancel_envelope` on `ExecutionCommandFacade` (the
   latter now imports `ExecutionEnvelope`). The trading routes call them
   directly, typed — no cast.
3. **Four structural Protocols + every envelope-seam cast deleted.** Grep
   evidence:
   ```
   $ grep -rn "_EnvelopeStore\b\|_EnvelopeSeamStore\|_EnvelopeStoreOps\|_EnvelopeFacadeOps" app/
     (none)
   $ grep -rn "cast(_Envelope\|cast(Any, store)\|_cast(Any, self._store)" app/
     (none)
   $ grep -rn "class EnvelopeTransitionError" app/
     app/store/base.py:262:class EnvelopeTransitionError(ValueError):
   ```
   The two `cast(Any, store)` at the production executor call sites
   (`redrive_staged_envelope_action` / `execute_envelope_action` in
   monitoring.py) are now bare `store` — those functions take `StateStore`.
   The remaining `cast(...)` in app/ are broker/marketdata SDK-response casts,
   out of scope.

## Deliberate-drift proof (the mutation-equivalent for an interface change)

Before the lift, these seams went through `cast(Any, ...)`, so a store that
dropped or mistyped an envelope method type-checked fine. After the lift, run
against committed code (tree clean) then reverted:

- **Drop** — rename `create_envelope` → `create_envelope_DROPPED` on
  `InMemoryStateStore`:
  ```
  app/store/__init__.py:50: error: Cannot instantiate abstract class
    "InMemoryStateStore" with abstract attribute "create_envelope"  [abstract]
  Found 1 error in 1 file (checked 64 source files)
  ```
- **Mistype** — `snapshot_fingerprint: str` → `int` on
  `SqliteStateStore.stage_envelope_action`:
  ```
  app/store/sqlite.py:2123: error: Argument 3 of "stage_envelope_action" is
    incompatible with supertype "app.store.base.StateStore"; supertype defines
    the argument type as "str"  [override]
  Found 2 errors in 1 file (checked 64 source files)
  ```
  Both reverted clean; `mypy app/` back to "no issues in 64 source files".

Both stores are instantiated in `app/store/__init__.py` (the factory), so a
DROP on either surfaces under `mypy app/`, not just at a test call site.

## Deviation (visible — the "green UNMODIFIED" clause)

The WO said "full suite green UNMODIFIED (interface-only diff outside tests)."
ONE test needed a one-line change: `test_fills_append_only.py::
test_interface_has_no_fill_mutators` enumerates every `StateStore` method whose
name contains the substring "fill" and asserted the set equals
`{append_fill, list_fills}`. Lifting `record_envelope_fill` onto the ABC made
that (correctly named, pre-existing) method visible to `dir(StateStore)`, so the
exact-set assertion failed. This is a naming-heuristic collision, NOT a behavior
change and NOT a weakening: `record_envelope_fill` records an execution-fill
FACT into the event log and decrements an envelope's `remaining_quantity` — it
never inserts/updates/deletes a `fills` row. The substantive guards (the
`forbidden` mutator set `{update_fill, delete_fill, ...}` disjointness, and the
sibling `test_sqlite_source_never_updates_or_deletes_fills` source scan) are
untouched. The expected set was widened to include `record_envelope_fill` with a
rationale comment. This is the ONLY test change; it does not touch the
append-only fills invariant it guards. Flagged to Ameen in-chat.

## Gate (fresh, this container)
- `ruff check .` → All checks passed
- `ruff format --check .` → 222 files already formatted
- `mypy app/` → Success: no issues found in 64 source files
- `lint-imports` → Contracts: 6 kept, 0 broken
- `pytest -q` → exit 0 (baseline before the lift: also exit 0; the interim red
  was solely the naming-heuristic guard above, now green)

Diff: 9 app files + 1 test file, +223 / −178. No new dependency, no ADR change,
no runtime behavior change.

## Status: VERIFIED
Disposition: RESULT_SUMMARY_KEPT
