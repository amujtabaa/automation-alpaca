"""Spine v2 Phase 6 — facade foundations (ADR-005 route→facade migration prereqs).

Pins the two seams every Phase-6 route migration relies on:

* the store-error → facade-error → HTTP-status translation preserves the EXACT
  code the un-migrated routes produced inline (404/409/422), so a route can drop
  its ``app.store.base`` import (a Contract-5 forbidden edge) without changing any
  response; and
* ``get_actor`` resolves the minimal actor-audit label (``X-Actor`` header, else
  ``operator``).
"""

from __future__ import annotations

import pytest

from app.api.deps import DEFAULT_ACTOR, get_actor
from app.facade.errors import (
    ConflictError,
    EntityNotFoundError,
    FacadeError,
    InvalidInputError,
)
from app.facade.http_mapping import facade_error_to_http
from app.facade.store_backed import (
    StoreBackedCommandFacade,
    StoreBackedQueryFacade,
    _translate_store_errors,
)
from app.store.base import (
    CandidateTransitionError,
    EmergencyReduceBlockedError,
    FlattenBlockedError,
    InvalidControlValueError,
    InvalidOrderError,
    OrderIntentBlockedError,
    OrderTransitionError,
    RiskLimitBlockedError,
    SessionAlreadyClosedError,
    UnknownEntityError,
)
from app.store.memory import InMemoryStateStore

# (store error instance, expected FacadeError type, expected HTTP status)
_CASES = [
    (UnknownEntityError("no such candidate x"), EntityNotFoundError, 404),
    (CandidateTransitionError("already rejected"), ConflictError, 409),
    (OrderTransitionError("illegal transition"), ConflictError, 409),
    (InvalidOrderError("oversell"), ConflictError, 409),
    (OrderIntentBlockedError("kill_switch"), ConflictError, 409),
    (RiskLimitBlockedError("exceeds max notional"), ConflictError, 409),
    (SessionAlreadyClosedError("already closed"), ConflictError, 409),
    (FlattenBlockedError("halted"), ConflictError, 409),
    (EmergencyReduceBlockedError("not halted"), ConflictError, 409),
    (InvalidControlValueError("engaged must be a bool"), InvalidInputError, 422),
    (ValueError("SYMBOL out of domain"), InvalidInputError, 422),
]


@pytest.mark.parametrize("store_error, facade_type, http_status", _CASES)
def test_store_error_translates_to_expected_status(
    store_error, facade_type, http_status
):
    with pytest.raises(FacadeError) as caught:
        with _translate_store_errors():
            raise store_error
    assert isinstance(caught.value, facade_type)
    # The original message is preserved for the HTTP detail.
    assert str(store_error) in str(caught.value)
    http_exc = facade_error_to_http(caught.value)
    assert http_exc.status_code == http_status
    assert str(store_error) in str(http_exc.detail)


def test_unmapped_store_error_is_not_wrapped_and_propagates_as_500_material():
    """An unmapped StoreError (or any non-domain error) must NOT become a
    FacadeError — it propagates raw, exactly as today's routes let a genuine bug
    surface as a 500."""

    class WeirdStoreError(Exception):
        pass

    with pytest.raises(WeirdStoreError):
        with _translate_store_errors():
            raise WeirdStoreError("bug")


def test_translate_is_transparent_on_success():
    with _translate_store_errors():
        result = 42
    assert result == 42


# --------------------------------------------------------------------------- #
# get_actor — minimal actor-audit label.
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "header, expected",
    [
        (None, DEFAULT_ACTOR),
        ("", DEFAULT_ACTOR),
        ("   ", DEFAULT_ACTOR),
        ("alice", "alice"),
        ("  bob  ", "bob"),
    ],
)
def test_get_actor_resolves_header_or_default(header, expected):
    assert get_actor(x_actor=header) == expected


# --------------------------------------------------------------------------- #
# Facade constructors accept the Phase-6 injected collaborators (keyword-only,
# optional — a store-only construction still works).
# --------------------------------------------------------------------------- #
def test_facades_construct_store_only_and_with_injected_deps():
    store = InMemoryStateStore()
    # store-only (unit-test shape) still works
    assert StoreBackedQueryFacade(store) is not None
    assert StoreBackedCommandFacade(store) is not None
    # with injected collaborators (sentinels stand in for the real ports)
    q = StoreBackedQueryFacade(store, market_data=object())
    c = StoreBackedCommandFacade(
        store,
        broker=object(),
        market_data=object(),
        approval_gate=object(),
        settings=object(),
    )
    assert q._market_data is not None
    assert c._broker is not None and c._approval_gate is not None
