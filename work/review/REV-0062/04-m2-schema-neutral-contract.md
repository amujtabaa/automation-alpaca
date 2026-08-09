# M1.5 schema-neutral M2 contract amendment

Status: **TASK A CANDIDATE — M2 REMAINS INACTIVE**

## Required atomic boundary

M2 must preserve the existing M1 composite transition atomically. In the same SQLite transaction
that persists an accepted transition and its current-state/checkpoint/effect/ownership consequences,
it must preserve the exact `ExecutionConnectionProfile` identity or commitment governing every
capital-relevant row. A crash may expose all of that committed unit or none of it, never a mixture
that can be hydrated under another connection profile.

## Schema-neutral invariants

1. One application generation has exactly one committed connection profile and no more than one
   mutation-eligible profile.
2. M2–M8 mutation eligibility is possible only when that profile is exactly Alpaca Paper and every
   existing cutover coordinate and safety gate matches.
3. Facts, effects, claims, owners, closures, receipts, and checkpoints cannot be created, hydrated,
   correlated, claimed, closed, or replayed without an exact profile binding.
4. Profile semantic coordinates are immutable after any external fact/effect exists.
5. Identity changes require a new application generation and reviewed recutover; updates, hot
   swaps, failover, and concurrent broker authority are structurally unavailable.
6. Credentials are never stored; only opaque handle/version/fingerprint identity may be committed.
7. Market-stream provenance binds a separate market-source commitment and is never inferred from
   the execution profile.
8. A capability-profile hash identifies the evidence set used for conformance; it grants no
   authority beyond the accepted beta boundary.
9. Missing, orphaned, duplicate, ambiguous, or mismatched bindings fail closed before broker I/O.
10. Provider-literal constraints may validate the selected beta profile, but may not define the
    permanent provider universe of dependent capital-relevant tables.

## M2 deliverables before implementation

The M2 work order must separately propose exact DDL, canonical commitment encoding, uniqueness and
foreign-key constraints, immutable-write enforcement, transaction boundaries, hydration checks,
crash points, corruption probes, and recutover refusal behavior. It must reconcile all literal
provider constraints against ADR-024 and obtain the human approval required for schema/DB work.

This amendment neither chooses table names nor authorizes DDL, a database, persistence code,
runtime wiring, or broker activity.
