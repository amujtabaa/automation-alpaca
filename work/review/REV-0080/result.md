# REV-0080 result — WO-0168c second fresh static review

Date: 2026-08-24

## Reviewed identity

- Candidate commit: `426935eee5808055796cba360d3be95a15ac55a3`
- Candidate tree: `67353f300a11ef9d90a576b8ee31d9fba8ef7a02`
- Review range: `2f16f52763add275892836b396f1f8b9decfd1f7..426935eee5808055796cba360d3be95a15ac55a3`

This result faithfully consolidates independent fresh-context functional and
gate-audit reviews. The implementation seat re-derived the reported boundary
relationships before accepting them as remediation input. No SQLite connection,
DDL installation, database-bearing test, or runtime composition was performed.

## Findings

### [P1] Selected current effect relationships are not completely bound

- Location: `app/execution_core/persistence/checkpoint_codec.py:3644-3690`,
  `app/execution_core/persistence/checkpoint_codec.py:3702-3745`
- Requirement: R15 section 2 and R1 section 4 require every selected current
  effect, claim, acceptance/evidence, and closure relationship to be reached by
  exact key and agree with the repository selection proof. R20 retains those
  rules.
- Evidence: `reproduced-live (pure)` reviewers showed that an ownerless-effect
  scope splice is now refused, but a dispatch claim whose scope has a foreign
  generation still projects when its effect ID and occurrence match. A forged
  acceptance proof also projects from an OPEN selected effect with no selected
  closure relation. Static re-derivation confirms the encoder checks only the
  claim effect ID/occurrence and only structural proof members.
- Impact: a checkpoint may seal a current claim or closure payload that is not
  the proof-selected durable relation.
- Resolution: bind every reached claim scope to its selected effect, and bind
  runtime lifecycle/acceptance/proof fields to the selected effect plus selected
  claim and acceptance-evidence records. Preserve payload-owned reference
  semantics rather than inventing a second durable identity.

### [P1] Static DDL-gate audit admits indirect pre-approval routes

- Location: `tests/execution_core/test_persistence_write_capability.py:1027-1231`
- Requirement: the WO-0168c human gate requires approval before any SQLite
  connection on a changed-DDL fixture route; REV-0080 explicitly requires
  fail-closed handling of aliased, composed, and dynamic access.
- Evidence: `reproduced-live (pure AST)` independent reviewers obtained no
  violations for aliased `sqlite3.connect`, aliased/dynamic module imports,
  `vars`/`__dict__` installer recovery, and composed attribute access. The
  current held-fixture corpus itself had no false positives.
- Impact: a future held fixture could create a temporary SQLite file before the
  approval accessor refuses, defeating the pre-open gate.
- Resolution: enforce a small direct-call grammar for connection and installer
  routes: direct canonical connection calls only, approval as the first
  executable action of each connection-opening function, and rejection of
  aliases, namespace introspection, and dynamic import/access routes. Add a
  negative control for each bypass family.

### [P2] Range-wide diff-check claim is too broad

- Location: `work/review/REV-0080/request.md:58`
- Requirement: exact-head evidence claims must be reproducible and must not
  silently treat historical reviewer artifacts as clean implementation output.
- Evidence: `reproduced-live`; `git diff --check 2f16f52..426935e` reports
  trailing whitespace in immutable `work/review/REV-0079/result.md`.
- Impact: the request's unqualified diff-check claim is inaccurate for its
  stated full review range.
- Resolution: preserve the reviewer-owned historical artifact and scope future
  diff-check evidence to the candidate implementation/governance changes it
  actually covers.

## Verdict

Verdict: **ACCEPT-WITH-CHANGES**

P0: 0
P1: 2
P2: 1

Unverified: Changed-DDL installation, SQLite-bearing tests, query-plan behavior,
database execution, and runtime composition remain deliberately not run.
