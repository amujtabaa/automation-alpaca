# Option matrix and decision

| Option | Preserves Alpaca Paper M2–M8 | Keeps one active broker authority | Avoids permanent provider literals | Avoids premature runtime complexity | Decision |
| --- | --- | --- | --- | --- | --- |
| 1. Permanent Alpaca-literal persistence | Yes | Yes | No | Yes | Rejected: turns a beta selection into a permanent historical-schema constraint. |
| 2. General multi-broker runtime now | No: changes the M2 task | No: introduces selection/routing/failover questions | Partly | No | Rejected: expands authority and risk before conformance evidence exists. |
| 3. One immutable provider-neutral selected active connection profile | Yes | Yes: exactly one profile is mutation-eligible | Yes | Yes | **Selected.** |
| 4. Mutable broker settings | Superficially | No: permits identity drift after effects/facts | Partly | No | Rejected: defeats durable provenance and recutover gates. |

## Decision

Adopt option 3. The active application generation has one immutable
`ExecutionConnectionProfile`; its selected M2–M8 values are `ALPACA` and
`PAPER`. Every capital-relevant durable authority binds the profile identity or
commitment. A material external-connection change is a new-generation reviewed
recutover, never an update, hot swap, failover, second simultaneous profile, or
routing decision.

## Consequences

- M2 receives a provider-neutral persistence contract without a premature
  multi-broker adapter abstraction or a DDL mandate.
- Webull stays future-only in M9; it is not a standby or alternate M2 profile.
- IBKR Pro may inform future measured execution-quality comparison but receives
  no execution authority.
- Existing Paper-only cutover and mismatch-denial controls are retained as
  profile-value comparison requirements.
