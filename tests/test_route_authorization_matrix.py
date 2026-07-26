"""WO-0139 literal mounted-route authorization matrix.

The required set is deliberately independent of runtime discovery. Discovery
then proves both required-route existence and the unclassified-route ratchet.
FastAPI 0.139 stores included routers as wrappers, so the flattener must recurse
through ``original_router.routes``; a top-level ``app.routes`` walk is vacuous.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator

import pytest
from fastapi.testclient import TestClient
from starlette.routing import Mount

from tests.signal_seat_helpers import (
    OPERATOR_KEY,
    PRODUCER_KEY,
    _IN_PROCESS_TEST_AUTHORITY,
    build_flag_on_app,
    flag_on_settings,
)

Operation = tuple[str, str]

PUBLIC = frozenset(
    {
        ("GET", "/api/health"),
    }
)

PRODUCER_ONLY = frozenset(
    {
        ("POST", "/api/signals"),
    }
)

OPERATOR_ONLY = frozenset(
    {
        ("DELETE", "/api/watchlist/{symbol}"),
        ("GET", "/api/candidates"),
        ("GET", "/api/candidates/{candidate_id}"),
        ("GET", "/api/envelopes"),
        ("GET", "/api/events"),
        ("GET", "/api/marketdata/snapshots"),
        ("GET", "/api/operator/orders"),
        ("GET", "/api/order-recoveries"),
        ("GET", "/api/orders"),
        ("GET", "/api/orders/{order_id}"),
        ("GET", "/api/positions"),
        ("GET", "/api/positions/{symbol}"),
        ("GET", "/api/protection"),
        ("GET", "/api/reconciliation"),
        ("GET", "/api/review"),
        ("GET", "/api/sell-intents"),
        ("GET", "/api/session"),
        ("GET", "/api/signals"),
        ("GET", "/api/watchlist"),
        ("POST", "/api/candidates/{candidate_id}/approve"),
        ("POST", "/api/candidates/{candidate_id}/reject"),
        ("POST", "/api/controls/kill-switch"),
        ("POST", "/api/controls/pause-buys"),
        ("POST", "/api/controls/resume-buys"),
        ("POST", "/api/envelopes/approve"),
        ("POST", "/api/envelopes/{envelope_id}/cancel"),
        ("POST", "/api/order-recoveries/{recovery_id}/fills"),
        ("POST", "/api/order-recoveries/{recovery_id}/reconcile"),
        ("POST", "/api/orders/{order_id}/cancel"),
        ("POST", "/api/positions/{symbol}/emergency-reduce"),
        ("POST", "/api/positions/{symbol}/flatten"),
        ("POST", "/api/session/close"),
        ("POST", "/api/watchlist"),
    }
)

DEV_OPERATOR_ONLY = frozenset(
    {
        ("POST", "/api/dev/candidates"),
    }
)

# REQUIRED is literal and never computed from the app. The one conditional row
# is also literal and selected only from the Settings object used to build it.
REQUIRED = PUBLIC | PRODUCER_ONLY | OPERATOR_ONLY
CLASSIFIED = PUBLIC | PRODUCER_ONLY | OPERATOR_ONLY

AUTO_DOC_PATHS = (
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
)

_PATH_PARAMETER = re.compile(r"\{[^}]+\}")


def _join_path(prefix: str, path: str) -> str:
    if not prefix:
        return path
    if path == "/":
        return prefix or "/"
    return f"{prefix.rstrip('/')}/{path.lstrip('/')}"


def _leaf_operations(
    routes: Iterable[object],
    *,
    prefix: str = "",
) -> Iterator[Operation]:
    """Recursively flatten FastAPI include wrappers and Starlette mounts."""

    for route in routes:
        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            include_context = getattr(route, "include_context", None)
            include_prefix = getattr(include_context, "prefix", "")
            yield from _leaf_operations(
                original_router.routes,
                prefix=_join_path(prefix, include_prefix) if include_prefix else prefix,
            )
            continue

        if isinstance(route, Mount):
            yield from _leaf_operations(
                route.routes,
                prefix=_join_path(prefix, route.path),
            )
            continue

        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if path is None or methods is None:
            continue
        concrete_path = _join_path(prefix, path)
        for method in methods - {"HEAD", "OPTIONS"}:
            yield method, concrete_path


def _discover_mounted_operations(app) -> frozenset[Operation]:
    """Return every mounted HTTP operation, including schema-hidden routes."""

    return frozenset(_leaf_operations(app.routes))


def _openapi_operations(app) -> frozenset[Operation]:
    http_methods = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
    return frozenset(
        (method.upper(), path)
        for path, item in app.openapi()["paths"].items()
        for method in item
        if method.lower() in http_methods
    )


def _required_for(settings) -> frozenset[Operation]:
    return REQUIRED | (DEV_OPERATOR_ONLY if settings.enable_dev_routes else frozenset())


def _classified_for(settings) -> frozenset[Operation]:
    return CLASSIFIED | (
        DEV_OPERATOR_ONLY if settings.enable_dev_routes else frozenset()
    )


def _concrete_path(path: str) -> str:
    return _PATH_PARAMETER.sub(
        lambda match: "AAPL" if "symbol" in match.group() else "missing",
        path,
    )


def _fresh_app():
    settings = flag_on_settings()
    app = build_flag_on_app(
        test_authority=_IN_PROCESS_TEST_AUTHORITY,
        settings=settings,
    )
    return settings, app


def test_required_routes_exist_and_every_discovered_route_is_classified():
    settings, app = _fresh_app()
    discovered = _discover_mounted_operations(app)
    required = _required_for(settings)
    classified = _classified_for(settings)

    assert required <= discovered
    assert discovered <= classified

    expected_bound = len(REQUIRED) + (
        len(DEV_OPERATOR_ONLY) if settings.enable_dev_routes else 0
    )
    assert len(discovered) == expected_bound
    assert discovered == _openapi_operations(app)


@pytest.mark.parametrize("operation", sorted(OPERATOR_ONLY | DEV_OPERATOR_ONLY))
@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        ({}, 401),
        ({"X-Operator-Key": "unknown"}, 401),
        ({"X-Producer-Key": PRODUCER_KEY}, 403),
        ({"X-Operator-Key": OPERATOR_KEY}, None),
    ],
    ids=["none", "invalid", "producer-role", "operator"],
)
def test_operator_route_auth_outcome(operation: Operation, headers: dict, expected):
    settings, app = _fresh_app()
    if operation in DEV_OPERATOR_ONLY and not settings.enable_dev_routes:
        pytest.skip("dev route not mounted by these settings")

    method, template = operation
    kwargs = {"headers": headers}
    if method == "POST":
        kwargs["json"] = {}
    with TestClient(app) as client:
        response = client.request(method, _concrete_path(template), **kwargs)

    if expected is None:
        assert response.status_code not in (401, 403)
    else:
        assert response.status_code == expected


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        ({}, 401),
        ({"X-Producer-Key": "unknown"}, 401),
        ({"X-Operator-Key": OPERATOR_KEY}, 403),
        ({"X-Producer-Key": PRODUCER_KEY}, None),
    ],
    ids=["none", "invalid", "operator-role", "producer"],
)
def test_producer_route_auth_outcome(headers: dict, expected):
    _, app = _fresh_app()
    with TestClient(app) as client:
        response = client.post("/api/signals", json={}, headers=headers)

    if expected is None:
        assert response.status_code not in (401, 403)
    else:
        assert response.status_code == expected


def test_public_health_requires_no_credential():
    _, app = _fresh_app()
    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200


@pytest.mark.parametrize("path", AUTO_DOC_PATHS)
def test_auto_docs_are_absent_and_never_public(path: str):
    _, app = _fresh_app()
    discovered_paths = {operation[1] for operation in _leaf_operations(app.routes)}
    assert path not in discovered_paths

    with TestClient(app) as client:
        assert client.get(path).status_code == 401
        assert (
            client.get(
                path,
                headers={"X-Operator-Key": OPERATOR_KEY},
            ).status_code
            == 404
        )


@pytest.mark.parametrize(
    ("headers", "expected"),
    [
        ({}, 401),
        ({"X-Operator-Key": "unknown"}, 401),
        ({"X-Producer-Key": PRODUCER_KEY}, 403),
        ({"X-Operator-Key": OPERATOR_KEY}, 404),
    ],
    ids=["none", "invalid", "producer-role", "operator"],
)
def test_unmatched_path_is_denied_by_default(headers: dict, expected: int):
    _, app = _fresh_app()
    with TestClient(app) as client:
        assert (
            client.get("/internal/not-mounted", headers=headers).status_code == expected
        )


def test_exact_exemptions_use_the_routed_method_and_root_path():
    _, app = _fresh_app()
    with TestClient(
        app,
        base_url="http://test/prefix",
        root_path="/prefix",
    ) as client:
        assert client.get("/api/health").status_code == 200
        assert client.post("/api/health").status_code == 401
        assert client.get("/api/healthz").status_code == 401
        assert (
            client.get(
                "/api/healthz",
                headers={"X-Operator-Key": OPERATOR_KEY},
            ).status_code
            == 404
        )
        assert client.post(
            "/api/signals",
            json={},
            headers={"X-Producer-Key": PRODUCER_KEY},
        ).status_code not in (401, 403)
        assert (
            client.post(
                "/api/signals/not-mounted",
                json={},
                headers={"X-Producer-Key": PRODUCER_KEY},
            ).status_code
            == 403
        )
