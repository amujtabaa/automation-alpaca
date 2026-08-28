# ADR-026 — Interim changed-DDL gate threat model and review convergence

Status: **ACCEPTED DIRECTION — exact implementation subject to REV-0108**

Decision owner: Ameen Mujtabaa

Authority: Ameen's 2026-08-26 hybrid ratification and 2026-08-27 approval of the
Codex handoff corrections recorded in WO-0168d.

## Context

WO-0168c attempted to prove that arbitrary Python in the execution-core corpus
could never reach SQLite by any route. Twenty-seven review packets showed that
this was an unbounded claim: each counterexample enlarged a bespoke partial
Python interpreter, the scanner grew beyond 12,000 lines, and ordinary pytest
stopped running. The scanner became a larger reliability risk than the four
fresh-file SQLite suites it was intended to guard.

The protected artifact is still human-gated changed schema DDL. Its exact bytes
must not execute before review and Ameen's separate authorization. The control
must be small enough to inspect, failure-capable, and proportionate to temporary
paper-phase databases without weakening any live, safety, or data-integrity
invariant.

## Decision

### 1. Threat model

This interim gate protects against accidents and non-evasive agent mistakes:
ordinary imports, direct `sqlite3` use, direct public API calls, stale digests,
premature suite invocation, and ordinary edits that bypass a named gate.

Deliberate dynamic-name construction, reflection used specifically to evade the
guard, editing the guard during an approved run, and a malicious host owner are
outside this in-repository mechanism. They are recorded as threat-class
proposals for Ameen rather than silently expanding the current claim. A future
decision may move enforcement to an external process or OS boundary.

### 2. Small load-bearing controls

1. The four SQLite-bearing suites live under `tests_gated/execution_core/`,
   outside ordinary pytest `testpaths`.
2. One central pre-open helper has exactly two executable statements: call
   `require_approved_ddl_execution()`, then call `sqlite3.connect`. Every held
   suite routes connection opening through it; no held suite has another
   ordinary direct `.connect` or `Connection()` capability.
3. The application-side installer owns `EXPECTED_EXECUTION_DDL_SHA256` and
   `DDL_EXECUTION_AUTHORIZED_BY_AMEEN`. Expected identity grants no authority;
   the flag remains `False` until Ameen's separately bounded gate-day act.
4. `install_schema` computes the actual digest, requires that application-owned
   authorization and expected identity, then checks the caller digest, all before
   it inspects or changes the supplied connection. The fixture guard reads the
   same facts; it is an earlier convenience refusal, not the load-bearing boundary.
5. A finite lexical allowlist identifies justified mentions. Bounded AST pins
   separately prohibit ordinary direct connection capability in production and
   held-suite files, and pin the central helper and installer ordering exactly.
   Conditional-gate, alias, and count-preserving-drift canaries prove the
   structural controls can fail.
6. CODEOWNERS marks the gate, gated suites, schema, workflows, and ownership
   policy for Ameen's review. Repository settings determine whether GitHub can
   enforce this marker.

No control claims that arbitrary Python cannot evade an in-process guard.

### 3. Exact unlock lifecycle

The DDL candidate is frozen and independently reviewed while the authorization
flag is `False`. A valid source-recorded unlock must:

1. have the exact REV-0108-accepted candidate as its parent;
2. change only the installer-owned authorization flag from `False` to `True`;
3. record Ameen's approved commands and bounded attempt count;
4. record the resulting commit and tree before execution; and
5. re-verify a clean, published checkout plus unchanged DDL digest, byte count,
   schema blob, catalog digest, and SQL-manifest identity.

The human act supplies authorization. The resulting Git identity supplies the
audit record. Neither a matching digest nor an agent-authored record authorizes
execution.

### 4. Review contract

REV-0106 and REV-0107 exhausted two rounds each while confirming the installer,
central-opener, and executable-alias corrections and exposing finite static-control
gaps. REV-0108 reviews the exact successor and permits
failure-capable no-I/O runtime, source/contract, mutation, scope, regression, safety,
and data-integrity evidence. Deliberate-evasion concerns outside section 1 are
proposals, not automatic blockers.

There are at most two review rounds. Round two covers remediations and
regressions they introduce. The cap never forces acceptance: unresolved P0/P1
findings return as exact blockers for re-diagnosis or human disposition.
`ACCEPT-WITH-CHANGES` closes only with zero open P0/P1.

Core 20 and its routing text receive a separate governance lens under
`AGENTS.md` and doc 15; Core 20 cannot constrain findings about itself.

### 5. Proportionality and promotion

Live-grade safety invariants and durable data semantics remain full-strength in
paper. Reversible operational hardening and ordinary proof ceremony scale with
blast radius. `docs/LIVE_READINESS.md` defines the evidence required before any
live-mode configuration can exist.

Any proposal exceeding approximately 500 SLOC of proof/meta-code stops for a
solution-class decision. It may not silently regrow the retired scanner.

## Consequences

- Ordinary pure verification resumes while held SQLite suites remain
  structurally excluded and fail closed when directly invoked. Broader checks
  that create databases remain deferred under the narrower F1 authority.
- The gate is legible and bounded; it protects against the declared accidental
  threat, not a hostile interpreter or host owner.
- The four held suites remain NOT_RUN until Ameen completes the separate DDL
  intent review and exact unlock. This ADR grants no database, migration,
  credential, broker, order, promotion, or master-merge authority.
- The static provenance/topology/trace scanner is superseded as an assurance
  design. Its Git history and prior review packets remain immutable evidence.
