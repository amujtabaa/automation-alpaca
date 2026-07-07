"""Facade domain errors — Spine v2 Phase 0 skeleton.

**Phase 0 scope note:** nothing raises these yet. There is no concrete facade
implementation and no route depends on this module — see
``docs/SPINE_PHASE0_INVENTORY.md`` for the current (unmediated) route →
store/broker/monitoring dependency map. Phase 1
(``prompts/CLAUDE_CODE_PHASE_1_FACADE_SEAM.md``) is expected to add the
HTTP-mapping layer that translates these into responses.
"""

from __future__ import annotations


class FacadeError(Exception):
    """Base class for every error a facade command/query may raise.

    Kept separate from the store's own domain errors
    (``app.store.base.StoreError`` and its subclasses) — a facade error
    represents a decision made *at the facade boundary* (not ready, not
    authorized, unknown command), not a decision the underlying store/engine
    made. A future HTTP-mapping layer (Phase 1) maps subclasses of this to
    specific status codes; it must never let a raw store/broker exception
    leak past the facade once routes stop calling those directly.
    """


class EngineNotReadyError(FacadeError):
    """The execution engine has not completed startup reconciliation.

    Spine v2 §7: "If startup reconciliation fails, trading is not enabled."
    A Phase-1 route-layer error mapper is expected to translate this to HTTP
    503 (ADR-005's "engine-not-ready returns 503 for commands" required
    test). No "engine" module with a startup-reconciliation gate exists yet
    in this repo — this class exists so Phase 1's mapping layer has a stable
    target to catch, not because anything raises it today.
    """
