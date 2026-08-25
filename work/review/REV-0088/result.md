# REV-0088 result — WO-0168c lexical-capability boundary review

Date: 2026-08-24

## Reviewed identity

- Candidate code commit: `9a3b3367e032be92e5235e07d65b74b3c92d2c93`
- Candidate code tree: `7978c33cd457e328ee91e4c5e3780a88c3b52b01`
- Prior review candidate: `d9296eec74027e54c619a8d2186ea7761cd4317f`

This result faithfully consolidates two independent fresh-context reviews of
the exact candidate. Both performed pure/static analysis only: no SQLite
connection, DDL installation, SQLite-bearing test, database creation,
credentials, network, broker, or order path, push, or merge.

## Findings

### [P1] Static capability lookups do not establish a dynamic source

- Location: `tests/execution_core/test_persistence_write_capability.py:1514-1557`
  at the reviewed identity.
- Requirement: the stated grammar covers known `builtins`, `importlib`, and
  `sys` capability members, including statically named lookup forms.
- Evidence: `reproduced-live` and `static-reasoning` (pure AST audit).
  `getattr(importlib, "import_module")`, `getattr(sys, "modules")`, and
  `getattr(builtins, "__import__")` can recover SQLite and construct or expose
  a connection without a violation.
- Impact: a named dynamic acquisition route remains outside the human-gate
  source audit.
- Resolution: recognize statically named lookups of a lexically proven
  capability module/member as a source, including relevant builtin getter
  aliases, while honoring actual lexical shadowing.

### [P1] A dynamic capability value can escape the marked lexical region

- Location: `tests/execution_core/test_persistence_write_capability.py:1559-1570`,
  `:1585` at the reviewed identity.
- Requirement: the grammar must cover its declared lexical capture and
  escaped-value acquisition routes.
- Evidence: `reproduced-live` (pure AST audit). A sibling consumer of a
  `recover_module()` function returning `globals()["sqlite3"]`, and a callback
  form receiving that recovered value, can call `.connect` with no violation.
- Impact: direct namespace recovery can cross a return or callback boundary
  and open SQLite without the approval gate.
- Resolution: a real dynamic SQLite acquisition must escalate to its enclosing
  ownership boundary when it can escape, rather than relying only on the
  immediate lexical region.

### [P1] `global` and `nonlocal` escalation over-taints a benign client

- Location: `tests/execution_core/test_persistence_write_capability.py:1565-1570`
  at the reviewed identity.
- Requirement: unrelated custom-client methods must not become SQLite solely
  through a method name.
- Evidence: `reproduced-live` (pure AST audit). An unrelated
  `globals()["document_fixture"]` use with a declared `global` or `nonlocal`
  target makes `Client().get("sqlite3").connect(path)` fail even though the
  client path never recovers SQLite.
- Impact: ordinary fixture delegation is rejected for an unrelated source
  feature.
- Resolution: escalate only an actual/potential SQLite capability acquisition,
  not every dynamic namespace use with a declared binding target.

### [P1] The endpoint rule mistakes arbitrary two-argument calls for lookups

- Location: `tests/execution_core/test_persistence_write_capability.py:1592-1596`
  at the reviewed identity.
- Requirement: static connection-member lookup must be recognized without
  classifying arbitrary client calls by an argument spelling.
- Evidence: `static-reasoning`. Within a capability region,
  `emit(client, "connect")` is reported as a SQLite connection route despite
  neither being a connection member nor a member-lookup primitive.
- Impact: valid unrelated client/control code can be falsely refused.
- Resolution: restrict endpoint detection to lexically proven lookup
  primitives and add a passing arbitrary-two-argument control.

### [P1] Capability module names ignore lexical shadowing

- Location: `tests/execution_core/test_persistence_write_capability.py:1148-1168`,
  `:1526-1532` at the reviewed identity.
- Requirement: unknown/custom objects must not become capability sources only
  because they share an imported module's spelling.
- Evidence: `static-reasoning`. After `import importlib`, a parameter named
  `importlib` shadows that module, but
  `importlib.import_module("transport").connect(path)` is still refused.
- Impact: the custom-client allowance contradicts the implementation's lexical
  name handling.
- Resolution: resolve known capability bindings per lexical scope and treat a
  parameter/local rebind as unknown; add a passing shadowed-client control.

## Verdict

Verdict: **ACCEPT-WITH-CHANGES**

P0: 0
P1: 5
P2: 0

Unverified: DDL installation and every SQLite-bearing suite remain intentionally
`NOT_RUN`; broader runtime composition and the known `mypy` internal error are
outside this static review.
