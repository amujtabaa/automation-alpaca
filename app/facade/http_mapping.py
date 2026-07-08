"""HTTP mapping for facade domain errors — Spine v2 Phase 1 (ADR-005).

Translates ``app.facade.errors.FacadeError`` subclasses into the
``fastapi.HTTPException`` a route should raise, so a route never has to
inspect a facade error's type itself (ADR-005: "routes... map the resulting
domain error to an HTTP response").

Route usage::

    try:
        return await facade.some_command(...)
    except FacadeError as exc:
        raise facade_error_to_http(exc) from exc
"""

from __future__ import annotations

from fastapi import HTTPException, status

from app.facade.errors import (
    BrokerGatewayError,
    ConflictError,
    EngineNotReadyError,
    EntityNotFoundError,
    FacadeError,
    InvalidInputError,
    NotYetImplementedError,
)


def facade_error_to_http(exc: FacadeError) -> HTTPException:
    """Map a facade domain error to the ``HTTPException`` a route should raise."""

    if isinstance(exc, EngineNotReadyError):
        # ADR-005's required test: "engine-not-ready returns 503 for commands."
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc) or "engine not ready",
        )
    if isinstance(exc, NotYetImplementedError):
        # Distinct from 503: the method exists on the Protocol but has no
        # concrete Phase-1 implementation yet — a different fact than "the
        # engine isn't up," so it gets a different status.
        return HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=str(exc) or "not yet migrated behind the facade",
        )
    # Phase-6 domain-outcome errors — the status a migrated route's store error
    # used to produce inline, now preserved at the facade boundary.
    if isinstance(exc, EntityNotFoundError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc) or "not found"
        )
    if isinstance(exc, ConflictError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc) or "conflict"
        )
    if isinstance(exc, InvalidInputError):
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc) or "invalid input",
        )
    if isinstance(exc, BrokerGatewayError):
        return HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc) or "broker gateway error",
        )
    # Fallback for any other FacadeError subclass — never let a raw facade
    # exception propagate past a route unmapped.
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=str(exc) or "facade error",
    )
