"""WO-0102 — backend-owned launcher bind guard (ADR-009 A-1 clause 6).

Pure ``validate_transport_bind`` cases + mutation-sensitive subprocess proofs:
(c) a non-loopback launch exits non-zero BEFORE serving, asserting the exact A-1
bind-policy reason; and a loopback flag-on launch passes the bind check and then
fails DOWNSTREAM on the (WO-0104) rails — proving the bind guard is a distinct,
removable-detectable check, not a generic pre-serve error.

NOT run here (joint WO-0102+0104 milestone against WO-0104's REAL rails): the (b)
positive control reaching a ready ``GET /api/health`` on a sanctioned loopback
launch — an enabled app needs the real rails provider, which WO-0104 supplies.
The (a) hostile ``uvicorn app.main:app`` "no accepting listener" is covered
structurally by ``test_signal_routes.test_module_app_is_none_under_flag`` (the
module-level ``app`` is ``None`` under the flag, so uvicorn gets no app).
"""

from __future__ import annotations

import subprocess
import sys


from app.config import Settings
from app.server import validate_transport_bind

_FLAG_ON = dict(signal_seat_enabled=True)


def _settings(**over) -> Settings:
    base = dict(state_store="memory")
    base.update(over)
    return Settings(**base)


def test_flag_off_bind_unrestricted():
    assert validate_transport_bind(
        host="0.0.0.0", uds=None, settings=_settings()
    ) is None


def test_flag_on_non_loopback_refused():
    reason = validate_transport_bind(
        host="0.0.0.0", uds=None, settings=_settings(**_FLAG_ON)
    )
    assert reason is not None and "A-1" in reason and "non-loopback" in reason


def test_flag_on_loopback_ok():
    assert validate_transport_bind(
        host="127.0.0.1", uds=None, settings=_settings(**_FLAG_ON)
    ) is None


def test_flag_on_unix_socket_ok():
    assert validate_transport_bind(
        host=None, uds="/tmp/app.sock", settings=_settings(**_FLAG_ON)
    ) is None


def test_flag_on_no_host_no_socket_refused():
    reason = validate_transport_bind(
        host=None, uds=None, settings=_settings(**_FLAG_ON)
    )
    assert reason is not None and "A-1" in reason


_ENV = {
    "SIGNAL_SEAT_ENABLED": "true",
    "OPERATOR_API_KEY": "op",
    "SIGNAL_PRODUCER_KEYS": '{"k": "p"}',
    "STATE_STORE": "memory",
    "PATH": "/usr/bin:/bin:/usr/local/bin",
}


def _run(code: str):
    return subprocess.run(
        [sys.executable, "-c", code],
        env=_ENV,
        capture_output=True,
        text=True,
        cwd=".",
    )


def test_subprocess_non_loopback_exits_with_a1_reason():
    # (c) non-loopback bind + flag on → exit non-zero BEFORE serving, exact reason.
    proc = _run("from app.server import run; run(host='0.0.0.0')")
    assert proc.returncode != 0
    assert "A-1" in proc.stderr and "non-loopback" in proc.stderr


def test_subprocess_loopback_passes_bind_then_fails_on_rails():
    # Mutation-sensitivity: a loopback launch PASSES the bind check and fails
    # DOWNSTREAM on WO-0104's (absent) real rails — so removing/mutating the bind
    # check would change THIS outcome from a rails error to a served listener.
    proc = _run("from app.server import run; run(host='127.0.0.1')")
    assert proc.returncode != 0
    # The failure is the rails guard, NOT the bind reason.
    assert "A-1" not in proc.stderr
    assert "WO-0104" in proc.stderr or "rails" in proc.stderr
