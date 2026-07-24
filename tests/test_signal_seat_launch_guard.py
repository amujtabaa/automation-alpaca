"""WO-0102 / ADR-009 A-1 clause 6 (REV-0025-F-001): construction-time
launch-provenance guard — the primary proxy-private-bind control.

With ``signal_seat_enabled`` on, the app may be built ONLY through the sanctioned
backend launcher's capability. A bare ``uvicorn app.main:app`` imports the
module-level ``app`` with no capability, so construction must RAISE — Uvicorn
never receives an app and no listener is ever opened (true pre-serve failure).
An in-app setting check or a request-time 503 alone is insufficient (a
``--lifespan off`` bare launch would still accept TCP and serve 503 on the
forbidden port); the guarantee is therefore enforced at construction.

The 503 fail-closed request guard is defense-in-depth, tested separately.
Flag OFF ⇒ construction is unrestricted (beta's current dev command unchanged).
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
import uvicorn
from uvicorn.importer import import_from_string

from app.config import Settings
from app.launch_guard import (
    consume_launch_capability,
    is_sanctioned,
    mint_launch_capability,
)
from app.main import create_app
from tests.signal_seat_helpers import (
    _IN_PROCESS_TEST_AUTHORITY,
    build_flag_on_app,
)


def test_flag_on_without_capability_refuses_construction():
    # A bare uvicorn import path (no capability) must fail before any listener.
    with pytest.raises(RuntimeError, match="launcher|python -m app|A-1"):
        build_flag_on_app(
            test_authority=_IN_PROCESS_TEST_AUTHORITY,
            with_capability=False,
        )


def test_flag_on_with_sanctioned_capability_and_full_wiring_constructs():
    # The positive control now ALSO wires the operator credential + producer map
    # + a conforming (test-double) rails provider — the flag-on app is only
    # constructible when the whole A-1/A-4 boundary is satisfied (no-unrailed,
    # no-lockout contract). A bare capability + bare Settings must NOT construct.
    app = build_flag_on_app(test_authority=_IN_PROCESS_TEST_AUTHORITY)
    assert app is not None


def test_flag_on_capability_only_but_no_credentials_fails():
    with pytest.raises(RuntimeError, match="OPERATOR_API_KEY|credential"):
        create_app(
            settings=Settings(signal_seat_enabled=True),
            launch_capability=mint_launch_capability(
                host="127.0.0.1", uds=None, settings=Settings(signal_seat_enabled=True)
            ),
            signal_rails=object(),
        )


def test_mint_refuses_non_proxy_private_bind_under_flag():
    # Round-6 hardening (REV-0025-F-001): a capability is bind-bound — minting for
    # a non-loopback/non-UDS bind under the flag RAISES, so an alternate in-repo
    # launcher cannot mint while claiming a 0.0.0.0 bind. A Unix socket or a
    # loopback host is accepted.
    on = Settings(signal_seat_enabled=True)
    with pytest.raises(RuntimeError, match="proxy-private|A-1"):
        mint_launch_capability(host="0.0.0.0", uds=None, settings=on)
    assert is_sanctioned(
        mint_launch_capability(host="127.0.0.1", uds=None, settings=on)
    )
    assert is_sanctioned(
        mint_launch_capability(host=None, uds="/tmp/x.sock", settings=on)
    )
    # Flag OFF ⇒ the bind policy permits any bind (beta dev unchanged).
    assert is_sanctioned(
        mint_launch_capability(host="0.0.0.0", uds=None, settings=Settings())
    )


def test_flag_on_with_credentials_but_no_rails_fails():
    with pytest.raises(RuntimeError, match="rails"):
        build_flag_on_app(
            test_authority=_IN_PROCESS_TEST_AUTHORITY,
            with_rails=False,
        )


def test_flag_off_constructs_without_capability():
    # Beta's current `uvicorn app.main:app` dev command keeps working unchanged.
    app = create_app(settings=Settings(signal_seat_enabled=False))
    assert app is not None


def test_capability_is_code_owned_not_forgeable_from_plain_construction():
    # The capability cannot be forged by constructing the class directly.
    from app import launch_guard

    with pytest.raises(RuntimeError):
        launch_guard._LaunchCapability(object())  # wrong token
    assert (
        is_sanctioned(
            mint_launch_capability(host="127.0.0.1", uds=None, settings=Settings())
        )
        is True
    )
    assert is_sanctioned(object()) is False
    assert is_sanctioned(None) is False


def test_incorrect_type_acceptance_rejects_launch_guard_subtypes():
    from app import launch_guard

    class BindText(str):
        pass

    class CapabilitySubtype(launch_guard._LaunchCapability):
        def __init__(self) -> None:
            pass

    reason = launch_guard.validate_transport_bind(
        host=BindText("127.0.0.1"),
        uds=None,
        settings=Settings(signal_seat_enabled=True),
    )
    assert reason is not None and "string" in reason
    assert is_sanctioned(CapabilitySubtype()) is False


def test_identity_validation_rejects_nonidentical_registry_value(monkeypatch):
    from app import launch_guard

    settings = Settings(signal_seat_enabled=True)
    capability = mint_launch_capability(host="127.0.0.1", uds=None, settings=settings)
    other = mint_launch_capability(host="127.0.0.1", uds=None, settings=settings)
    assert launch_guard._ISSUED_CAPABILITIES.get(id(capability)) is capability
    with launch_guard._ISSUED_CAPABILITIES_LOCK:
        monkeypatch.setitem(
            launch_guard._ISSUED_CAPABILITIES,
            id(capability),
            other,
        )
    assert is_sanctioned(capability, settings=settings) is False


def test_non_atomic_one_use_validation_yields_exactly_one_success():
    settings = Settings(signal_seat_enabled=True)
    capability = mint_launch_capability(host="127.0.0.1", uds=None, settings=settings)
    worker_count = 16
    start = Barrier(worker_count)

    def consume_once(_index: int) -> bool:
        start.wait(timeout=10)
        return consume_launch_capability(capability, settings=settings)

    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        results = list(pool.map(consume_once, range(worker_count)))

    assert results.count(True) == 1
    assert results.count(False) == worker_count - 1


def test_capability_reacquisition_via_importable_factory_is_rejected():
    import_path = "tests.signal_seat_helpers:build_flag_on_app"

    with pytest.raises(RuntimeError, match="in-process test authority"):
        uvicorn.Config(import_path, factory=True).load()
    with pytest.raises(RuntimeError, match="in-process test authority"):
        uvicorn.Config(import_path).load()
    with pytest.raises(RuntimeError, match="in-process test authority"):
        import_from_string(import_path)()


def test_is_conforming_rails_rejects_non_async_check_ingest():
    # Round-6 (P2): a runtime_checkable Protocol only checks attribute presence,
    # so a provider with a SYNCHRONOUS check_ingest would pass the A-4 presence
    # gate and then 500 at `await rails.check_ingest(...)`. The gate must require
    # check_ingest to be a coroutine function.
    from app.facade.signal_rails import RailsDecision, is_conforming_rails

    class AsyncRails:
        async def check_ingest(self, producer_id: str) -> RailsDecision:
            return RailsDecision(allowed=True)

    class SyncRails:
        def check_ingest(self, producer_id: str) -> RailsDecision:  # NOT async
            return RailsDecision(allowed=True)

    assert is_conforming_rails(AsyncRails()) is True
    assert is_conforming_rails(SyncRails()) is False
    assert is_conforming_rails(object()) is False


def test_flag_on_injected_settings_with_overlapping_credentials_fails():
    # Auto-review round 10 (P2): an INJECTED Settings (built directly, bypassing
    # load_settings' role-separation check) whose operator key equals a producer
    # key must be REFUSED at construction — otherwise that producer could present
    # its own secret as X-Operator-Key and pass every operator-only route.
    from tests.signal_seat_helpers import PermissiveSignalRails

    on = Settings(signal_seat_enabled=True)
    with pytest.raises(RuntimeError, match="role separation|OPERATOR_API_KEY"):
        create_app(
            settings=Settings(
                signal_seat_enabled=True,
                operator_api_key="shared-secret",
                signal_producer_keys={"shared-secret": "vibe"},
            ),
            launch_capability=mint_launch_capability(
                host="127.0.0.1", uds=None, settings=on
            ),
            signal_rails=PermissiveSignalRails(),
        )


def test_is_conforming_rails_rejects_a_class_object():
    # Round-13: a CLASS (not an instance) with an async check_ingest satisfies the
    # Protocol + iscoroutinefunction, but `await Cls.check_ingest(pid)` would 500
    # (missing self). The guard must require a bound-method instance.
    from app.facade.signal_rails import RailsDecision, is_conforming_rails

    class Rails:
        async def check_ingest(self, producer_id: str) -> RailsDecision:
            return RailsDecision(allowed=True)

    assert is_conforming_rails(Rails) is False  # the class itself
    assert is_conforming_rails(Rails()) is True  # a real instance


def test_flag_on_injected_settings_out_of_range_budget_fails():
    # Round-13: an injected Settings bypassing load_settings cannot ship an
    # out-of-range signal_invalid_budget_per_epoch (A-4 cap) or server TTL (A-3).
    from tests.signal_seat_helpers import PermissiveSignalRails

    on = Settings(signal_seat_enabled=True)
    for bad in (
        {"signal_invalid_budget_per_epoch": 0},
        {"signal_invalid_budget_per_epoch": 1001},
        {"signal_server_max_ttl_seconds": 0},
        {"signal_server_max_ttl_seconds": 999999},
    ):
        with pytest.raises(RuntimeError, match="budget|TTL|A-3|A-4"):
            create_app(
                settings=Settings(
                    signal_seat_enabled=True,
                    operator_api_key="op-key",
                    signal_producer_keys={"prod-key": "vibe"},
                    **bad,
                ),
                launch_capability=mint_launch_capability(
                    host="127.0.0.1", uds=None, settings=on
                ),
                signal_rails=PermissiveSignalRails(),
            )


def test_flag_on_injected_settings_whitespace_credentials_fail():
    # Round-13: whitespace-only operator key / blank producer key or id must be
    # refused at construction even for an injected Settings.
    from tests.signal_seat_helpers import PermissiveSignalRails

    on = Settings(signal_seat_enabled=True)
    for creds in (
        {"operator_api_key": "   ", "signal_producer_keys": {"p": "vibe"}},
        {"operator_api_key": "op", "signal_producer_keys": {"   ": "vibe"}},
        {"operator_api_key": "op", "signal_producer_keys": {"p": "   "}},
    ):
        with pytest.raises(RuntimeError, match="non-blank|OPERATOR_API_KEY|PRODUCER"):
            create_app(
                settings=Settings(signal_seat_enabled=True, **creds),
                launch_capability=mint_launch_capability(
                    host="127.0.0.1", uds=None, settings=on
                ),
                signal_rails=PermissiveSignalRails(),
            )


def test_is_conforming_rails_rejects_wrong_arity():
    # Proactive review P3-1: an async check_ingest with the wrong arity (no
    # producer_id) passes the Protocol + coroutine checks but would 500 on the
    # first request. The guard probes the signature.
    from app.facade.signal_rails import RailsDecision, is_conforming_rails

    class NoArg:
        async def check_ingest(self):  # missing producer_id
            return RailsDecision(allowed=True)

    assert is_conforming_rails(NoArg()) is False


def test_flag_on_injected_settings_bad_transport_policy_fails():
    # Proactive review P3-2: an injected Settings cannot ship a transport policy
    # outside the closed set (the validator now checks it too).
    from tests.signal_seat_helpers import PermissiveSignalRails

    on = Settings(signal_seat_enabled=True)
    with pytest.raises(RuntimeError, match="transport_policy"):
        create_app(
            settings=Settings(
                signal_seat_enabled=True,
                operator_api_key="op",
                signal_producer_keys={"p": "vibe"},
                signal_transport_policy="garbage-EVIL",
            ),
            launch_capability=mint_launch_capability(
                host="127.0.0.1", uds=None, settings=on
            ),
            signal_rails=PermissiveSignalRails(),
        )
