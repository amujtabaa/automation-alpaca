"""The sole human-controlled execution unlock for changed schema DDL.

This module intentionally does **not** know the candidate DDL digest. Candidate
identity is evidence recorded in the review packet; execution authority is a
separate, deny-by-default human decision. Until that decision is recorded in a
bounded unlock commit, every installer fixture fails before it opens a SQLite
connection or creates a temporary database file.

When Ameen approves an exact candidate commit/tree, DDL SHA-256, byte count, and
fresh-file command list, change only ``APPROVED_EXECUTION_DDL_SHA256`` from
``None`` to the approved literal in that unlock commit. Do not derive it from
``schema_ddl_digest()``, a helper, an alias, or a local computation.
"""

from __future__ import annotations

from typing import Final


APPROVED_EXECUTION_DDL_SHA256: Final[str | None] = None


def _validate_approved_ddl_execution_token(approved: object) -> str:
    """Validate one proposed human token without changing the locked global."""

    if approved is None:
        raise RuntimeError(
            "HUMAN-GATE pending: changed DDL remains static-only until Ameen "
            "approves the exact candidate identity and fresh-file test plan"
        )
    if (
        type(approved) is not str
        or len(approved) != 64
        or any(character not in "0123456789abcdef" for character in approved)
    ):
        raise RuntimeError("HUMAN-GATE invalid: approval token must be SHA-256 text")
    return approved


def require_approved_ddl_execution() -> str:
    """Return the human token or refuse before any SQLite activity begins."""

    return _validate_approved_ddl_execution_token(APPROVED_EXECUTION_DDL_SHA256)
