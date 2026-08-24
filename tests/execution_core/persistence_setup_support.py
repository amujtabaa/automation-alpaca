"""Explicit setup-only write capability issuance for fresh persistence fixtures.

This test-support module is deliberately the sole test-side route to a setup
capability.  Production modules never import it, and it has no connection
creation, schema installation, path discovery, or transaction behavior of its
own; named tmp_path fixtures retain those responsibilities.
"""

from __future__ import annotations

from app.execution_core.persistence import repository as _repository
from app.execution_core.persistence.schema import (
    SQLiteConnectionProtocol as _SQLiteConnectionProtocol,
)


def issue_setup_write_capability(
    connection: _SQLiteConnectionProtocol,
) -> _repository._SetupWriteCapability:
    """Return one connection-bound setup token to a named fresh test fixture."""

    return _repository._issue_setup_write_capability(connection)
