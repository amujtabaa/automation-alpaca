# REV-0081 result — WO-0168c selected-relation and pre-open-gate review

Date: 2026-08-24

## Reviewed identity

- Candidate code commit: `9984232fcc6fce9b9261798858262e529c3729e2`
- Candidate code tree: `1f36eaf9b260a7182c5c6541833c236d8090685b`
- Review range: `426935eee5808055796cba360d3be95a15ac55a3..9984232fcc6fce9b9261798858262e529c3729e2`

This result faithfully records two independent fresh-context review returns:
one selected-relation/functional pass and one static pre-open-gate pass. Both
were pure/static only. No SQLite connection, DDL installation, database-bearing
test, runtime composition, credential, network, broker, or order path was used.

## Findings

### [P1] Approval provenance can be forged or rebound

- Location: `tests/execution_core/test_persistence_write_capability.py:1087`,
  `:1233`, `:1333`
- Requirement: WO-0168c requires the human approval accessor to be the direct,
  pre-open gate on every held SQLite route; REV-0080 requires fail-closed alias
  and dynamic handling.
- Evidence: `reproduced-live (pure AST)`. A locally defined
  `require_approved_ddl_execution()` and a rebound imported name both passed the
  audit before a direct `sqlite3.connect`.
- Impact: a fixture could appear gated while the real human approval literal is
  still `None`, then open SQLite.
- Resolution: require the one canonical, un-rebound top-level accessor binding
  on every connection/installer route and reject local definitions, assignments,
  aliases, and dynamic recovery. Add those mutants.

### [P1] Literal dynamic and alternate SQLite connection routes evade the audit

- Location: `tests/execution_core/test_persistence_write_capability.py:1068-1117`,
  `:1211-1231`, `:1333`
- Requirement: the human gate applies before every SQLite connection; indirect
  routes must fail closed.
- Evidence: `reproduced-live (pure AST)`. A connection-only helper using
  `importlib.import_module("sqlite3").connect(path)` returned no violations.
  `from sqlite3 import dbapi2; dbapi2.connect(path)` and
  `sqlite3.dbapi2.connect(path)` also returned no violations. The implementation
  seat separately reproduced the equivalent literal-`__import__` connection-only
  route with no database activity.
- Impact: an unapproved route can open SQLite without calling the human gate.
- Resolution: accept only the canonical `import sqlite3` plus direct
  `sqlite3.connect` grammar guarded first; reject literal dynamic SQLite imports
  and unmodelled SQLite module/import routes. Add negative controls.

### [P1] Lexical function ancestry is not pre-open dominance

- Location: `tests/execution_core/test_persistence_write_capability.py:177-186`,
  `:1242-1256`
- Requirement: approval must dominate connection acquisition at runtime, not
  merely appear first in a surrounding function body.
- Evidence: `reproduced-live (pure AST)`. The audit accepted a direct connection
  in a function default expression even though Python evaluates the default at
  function definition time before the body can call the gate.
- Impact: a connection can open before approval while the static audit passes.
- Resolution: admit connection calls only in an approved function-body execution
  region; reject defaults, decorators, lambdas/generators, and escaped closures.
  Add focused controls.

### [P1] INVALIDATED effects do not bind proof-selected invalidation evidence

- Location: `app/execution_core/persistence/checkpoint_codec.py:2179`, `:2259`,
  `:3783`
- Requirement: R1 §4, R15 §2, and R20 §4 require selected acceptance/evidence
  and mutable effect state to remain exact. `VenueRecoveryBook` requires an
  INVALIDATED effect to retain contradiction evidence.
- Evidence: `static-reasoning`. The new relation binder checks closure-proof
  evidence only, then emits `current.effect.contradiction_evidence` directly.
  It does not bind that tuple to selected `INVALIDATION` evidence rows. The
  projector does not invoke full venue validation.
- Impact: a checkpoint can serialize an INVALIDATED mutable effect with missing
  or substituted proof-selected invalidation evidence.
- Resolution: bind runtime contradictions exactly to selected effect
  invalidation evidence—owner, observation, canonical ordering, and no
  extras/missing rows—and enforce the directly related NEVER_DISPATCHED
  lifecycle/claim rule. Add pure empty/spliced-evidence controls.

### [P2] Bare `.install_schema()` is an overbroad audit trigger

- Location: `tests/execution_core/test_persistence_write_capability.py:1277-1282`
- Requirement: the gate governs the canonical changed-DDL installer, not an
  unrelated method that happens to share its name.
- Evidence: `reproduced-live (pure AST)`. An unrelated
  `DocumentInstaller().install_schema()` source with no SQLite or canonical
  schema import produced audit violations.
- Impact: the corpus-wide audit could block unrelated future source based only
  on a method name.
- Resolution: bind installer recognition to canonical schema-module provenance,
  retaining fail-closed behavior only for actual SQLite/schema routes.

## Verdict

Verdict: **ACCEPT-WITH-CHANGES**

P0: 0
P1: 4
P2: 1

Unverified: changed-DDL installation, all SQLite-bearing suites, repository and
load behavior, query plans, runtime composition, and a completed post-remediation
review are deliberately not run.
