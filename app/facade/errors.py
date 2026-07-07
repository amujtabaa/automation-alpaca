"""Facade domain errors — Spine v2 facade boundary (ADR-005).

Phase 0 added these as an inert skeleton (nothing raised them, no route
depended on this module). Phase 1 (``prompts/CLAUDE_CODE_PHASE_1_FACADE_
SEAM.md``) wires ``app.facade.http_mapping`` to translate these into HTTP
responses and adds :class:`NotYetImplementedError`, raised by every facade
method that has no current-codebase analogue yet (see
``docs/SPINE_PHASE0_INVENTORY.md``'s dependency map and ADR-conflict list).
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
    ``app.facade.http_mapping`` translates this to HTTP 503 (ADR-005's
    "engine-not-ready returns 503 for commands" required test). No "engine"
    module with a startup-reconciliation gate exists yet in this repo — the
    Phase 1 concrete facade (``app.facade.store_backed``) never raises this;
    it exists so the mapping layer has a stable target once Phase 2+ adds a
    real readiness gate.
    """


class NotYetImplementedError(FacadeError):
    """A facade method is defined by the Protocol but not migrated behind it
    yet — either because it has no current-codebase analogue (``primary``/
    ``spawn``/``TradingState`` don't exist yet — Spine v2 §4/§8), or because
    migrating it now would freeze an ADR-conflicted behavior (manual
    flatten, kill-switch) as the facade's contract before Phase 3 makes a
    deliberate decision (see ``docs/SPINE_PHASE0_INVENTORY.md`` §3.1/§3.4).

    ``app.facade.http_mapping`` translates this to HTTP 501 — distinct from
    ``EngineNotReadyError``'s 503, since "not implemented" and "not ready"
    are different facts a caller needs to distinguish.
    """
