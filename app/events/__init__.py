"""Spine v2 event-sourcing layer (Phase 2 — additive / shadow).

The append-only ``ExecutionEvent`` log (``app/models.py``) is the durable-truth
substrate of the migration (Spine v2 §11); this package holds the **pure**
projection + replay machinery that reconstructs state from that log.

Phase 2 scope, deliberately bounded (see ``docs/SPINE_MIGRATION_PROGRESS.md``):

* ``projectors.PositionProjector`` — the one projector with real current-model
  semantics, reusing ``app/position.py:apply_fill`` so the safety-critical
  average-cost formula is never duplicated.
* ``replay`` — the dual-store parity + snapshot/replay verifier (§11).

Projectors for primary / spawn / TradingState / quarantine are Phase 3 (those
state machines do not exist yet); building them now would mean inventing Phase 3
behavior with nothing real to project. Everything here is pure and IO-free: it
consumes already-read ``ExecutionEvent`` lists, so it is trivially and
deterministically testable, and nothing in Phase 2 wires it into a production
write path.
"""
