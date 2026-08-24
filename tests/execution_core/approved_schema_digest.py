"""The one human-approved DDL digest every installing test fixture must use.

REV-0078 P0-1: fixtures previously passed ``approved_ddl_sha256=schema_ddl_digest()``
-- the token computed from the artifact it approves -- so the installer's
comparison was ``sha256(x) == sha256(x)`` and could never refuse. This constant
is the digest Ameen ratified on 2026-08-24 (gate bundle Amendment 1 and
``36-R16-MANUAL-RULE-RATIFICATION.md`` record the approvals), transcribed here
as a literal. Changing the DDL now breaks every installing fixture until a
human deliberately moves this one value.

``test_persistence_write_capability.py`` holds the AST control that refuses any
new self-derived call site.
"""

APPROVED_DDL_SHA256 = "2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5"
