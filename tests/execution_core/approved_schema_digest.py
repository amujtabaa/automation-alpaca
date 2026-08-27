"""Human-controlled execution unlock, separate from the expected DDL identity.

The expected digest is reviewed evidence, not authority. Until Ameen explicitly
authorizes the one-line flag change from an exact accepted parent, every held
fixture refuses before opening a SQLite connection or creating a database file.

The unlock protocol and post-commit identity checks are recorded in WO-0168d
and the governing DDL gate. Agents never infer approval from a matching digest.
"""

from __future__ import annotations

from typing import Final


EXPECTED_EXECUTION_DDL_SHA256: Final[str] = (
    "2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5"
)
DDL_EXECUTION_AUTHORIZED_BY_AMEEN: Final[bool] = False


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
