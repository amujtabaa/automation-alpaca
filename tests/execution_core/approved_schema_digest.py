"""Human-controlled execution unlock, separate from the expected DDL identity.

The application-side installer owns and enforces the expected digest and human
flag. This module is the earlier fixture guard: until Ameen explicitly authorizes
the one-line flag change from an exact accepted parent, every held fixture refuses
before opening a SQLite connection or creating a database file.

The unlock protocol and post-commit identity checks are recorded in WO-0168d
and the governing DDL gate. Agents never infer approval from a matching digest.
"""

from __future__ import annotations

from app.execution_core.persistence.schema import (
    DDL_EXECUTION_AUTHORIZED_BY_AMEEN,
    EXPECTED_EXECUTION_DDL_SHA256,
)


def require_approved_ddl_execution() -> str:
    """Return the human token or refuse before any SQLite activity begins."""

    if DDL_EXECUTION_AUTHORIZED_BY_AMEEN is not True:
        raise RuntimeError(
            "HUMAN-GATE pending: changed DDL remains static-only until Ameen "
            "authorizes the exact accepted parent, commands, and attempt count"
        )
    approved = EXPECTED_EXECUTION_DDL_SHA256
    if (
        type(approved) is not str
        or len(approved) != 64
        or any(character not in "0123456789abcdef" for character in approved)
    ):
        raise RuntimeError("HUMAN-GATE invalid: approval token must be SHA-256 text")
    return approved
