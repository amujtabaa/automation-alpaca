"""WO-0102 — backend-owned launcher bind guard (ADR-009 A-1 clause 6).

Pure ``validate_transport_bind`` cases + mutation-sensitive subprocess proofs:
(a) a bare hostile ``uvicorn app.main:app`` under the flag — both ``--lifespan``
modes — NEVER accepts a TCP connection on the forbidden port, asserted at the
SOCKET level (REV-0025-F-002; auto-reviewer P1 #7 fix — a module-level
``app = None`` is insufficient, see ``app/main.py``'s comment); (c) a non-loopback
launch exits non-zero BEFORE serving, asserting the exact A-1 bind-policy reason;
and a loopback flag-on launch passes the bind check and then fails DOWNSTREAM on
the (WO-0104) rails — proving the bind guard is a distinct, removable-detectable
check, not a generic pre-serve error.

NOT run here (joint WO-0102+0104 milestone against WO-0104's REAL rails): the (b)
positive control reaching a ready ``GET /api/health`` on a sanctioned loopback
launch — an enabled app needs the real rails provider, which WO-0104 supplies.
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time

import pytest

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


# --------------------------------------------------------------------------- #
# (a) Bare hostile `uvicorn app.main:app` — socket-level proof (REV-0025-F-002,
# auto-reviewer P1 #7). Empirically reproduced pre-fix: a module-level
# `app = None` let uvicorn's Config.load() return a `None` "app", which still
# proceeded to bind a listening socket and report "startup complete" (serving a
# 503/error per-request) — reachable is NOT proxy-private. The fix makes the
# module attribute UNDEFINED under the flag, so uvicorn's own
# `getattr(module, "app")` raises AttributeError inside Config.load(), which
# runs synchronously before any socket is bound.
# --------------------------------------------------------------------------- #
def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _never_accepts(
    host: str, port: int, proc: "subprocess.Popen[str]", *, duration: float = 3.0
) -> bool:
    """Poll a TCP connect for ``duration`` seconds (or until ``proc`` exits).
    Returns ``True`` iff NO connect attempt ever succeeded — the mutation-
    sensitive proof: a broken guard that still opens a listener (even one that
    only serves an error response) is caught here, not by reading an HTTP body."""

    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.settimeout(0.2)
        try:
            probe.connect((host, port))
        except OSError:
            pass
        else:
            probe.close()
            return False  # accepted a connection -- the guard is broken
        finally:
            probe.close()
        if proc.poll() is not None:
            break
        time.sleep(0.1)
    return True


@pytest.mark.parametrize("lifespan_mode", ["on", "off"])
def test_bare_uvicorn_under_flag_never_accepts_a_connection(lifespan_mode):
    # All OTHER startup preconditions are satisfiable (_ENV carries
    # OPERATOR_API_KEY + SIGNAL_PRODUCER_KEYS + STATE_STORE=memory), so no
    # unrelated guard could supply the failure — this isolates the A-1 clause-6
    # bind boundary specifically, exactly as REV-0025-F-002 requires.
    port = _free_port()
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--lifespan",
            lifespan_mode,
        ],
        env=_ENV,
        cwd=".",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        assert _never_accepts("127.0.0.1", port, proc, duration=3.0), (
            f"bare `uvicorn app.main:app --lifespan {lifespan_mode}` accepted a "
            f"TCP connection on the forbidden port under signal_seat_enabled — "
            f"the A-1 clause-6 boundary is broken (auto-reviewer P1 #7)."
        )
        try:
            _, stderr = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            _, stderr = proc.communicate()
        assert proc.returncode != 0, (
            "the process must have exited (pre-serve failure), not merely be "
            "slow to bind"
        )
        assert 'Attribute "app" not found' in stderr, stderr
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.communicate()

