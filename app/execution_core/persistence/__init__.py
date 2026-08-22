"""M2 reset-kernel persistence contracts.

This subpackage currently holds only the inert, human-gated SQLite schema
definition and its pure installer (`app.execution_core.persistence.schema`).
Importing this package performs no work: there is no database discovery, no
connection factory, and no runtime wiring. M2-I2 authorizes the schema bytes
and their tests only; repository/hydration behavior arrives with M2-I3 under
its own authority.
"""
