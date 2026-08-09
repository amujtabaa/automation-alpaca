# M2 provider-neutral persistence contract amendment

Status: **schema-neutral candidate contract — no DDL or database work authorized**

## Required M2 contract

1. The M2 activation record creates one immutable selected
   `ExecutionConnectionProfile` for its application generation, verifies its
   complete commitment, and permits mutation only when that exact profile is
   eligible.
2. Every capital-relevant durable row carries the selected profile identity or
   immutable commitment as a required coordinate. The binding covers checkpoints,
   input/fact chains, effects/claims/owners/closures, client identities, coverage
   watermarks, controller/generation/protection/authority state, and decision
   receipts. A row without an exact selected-profile binding is non-serving.
3. Every external identifier is profile-scoped. Unique keys and lookup/refusal
   logic must include the profile binding where a broker/event/order/cursor/
   client identity could otherwise collide across profile history.
4. Startup, reconciliation, and each final effect claim re-derive and compare
   profile provider, environment, account, all command/query/event origins,
   credential-handle fingerprint, adapter version, capability digest, deployment
   identity, and complete profile commitment. `account` means the exact
   profile-committed `broker-account-identity/v1` assertion: one selected
   adapter extractor produces one non-secret provider-authoritative account
   identifier, then the implementation re-derives and compares its digest.
   A local alias, label, or account-name match cannot stand in for that
   comparison. Any missing, unknown, live, cross-profile, or changed coordinate
   refuses broker I/O and mutation.
5. Historical records retain their original profile binding. No repair, replay,
   current-symbol lookup, or account-name match may reattribute an old fact,
   effect, owner, claim, closure, or receipt to a newer profile.
6. A material provider/profile change requires a new application generation and
   separately reviewed flat recutover. Updates, hot swaps, multiple active
   profiles, standby routing, cross-profile inventory, and automatic failover
   are prohibited.
7. `MarketDataSourceProfile` is separately committed. Market stream provenance
   binds the market-source commitment; no M2 query may infer it from the
   execution profile.
8. `BrokerCapabilityProfile` is an immutable versioned required-capability
   contract, not a user-editable broker setting. Its profile-bound hash freezes
   requirements and validation rules without claiming empirical conformance.
   Separately append-only `BrokerCapabilityEvidence`, bound to the exact
   capability and execution-profile commitments, must prove every required
   capability before the existing M4 human credential/call gate may lead to
   `PAPER_MUTATION_ELIGIBLE`. Evidence refresh for the same requirement profile
   does not rewrite the selected profile; an altered requirement hash is a
   material new-generation recutover change.

## Provider-literal clauses inadmissible for future M2 schema approval

The following existing planning clauses are not rejected as evidence of the
selected beta values; they are rejected as the durable representation to carry
into M2 without reconciliation:

| Current planning anchor | Why inadmissible without amendment | M2 replacement obligation |
| --- | --- | --- |
| `04-persistence-and-cutover.md` proposed `execution_facts.broker TEXT ... CHECK (broker = 'ALPACA')` | Repeats the provider on a capital row without a profile identity and makes the beta choice indistinguishable from an eternal schema rule. | Bind the row to exact profile identity/commitment; M2 selected profile resolves to Alpaca. |
| Proposed `execution_facts.environment ... CHECK (environment = 'PAPER')` | Same permanent-literal problem; environment must be part of a complete immutable profile. | Bind environment through selected profile commitment and fail closed on mismatch. |
| Tables whose durable rows carry only `application_generation` | Generation alone cannot prove which external provider/account/origin/capability/deployment was selected. | Require selected profile binding for every capital-relevant row. |
| OS lock/fence keyed or described only as `(broker, environment, account)` | The selected values are necessary but omit origin, credential-handle, adapter/capability, deployment, and full commitment. | Compare the complete profile at startup and final claim; preserve single-writer semantics. |
| Any future `broker` enum/default/config setting capable of update in place | A mutable preference can silently change capital authority without recutover. | No mutable broker setting; material change mints a new application generation. |

## Non-goals and anti-overengineering guardrails

- No table names, SQL, migration, database file, schema version, serialization,
  or runtime object is selected here.
- No generic provider plug-in registry, routing algorithm, failover tree,
  cross-broker position model, multi-account abstraction, or capability
  framework is authorized.
- M2 implements only the selected Alpaca Paper profile for the one active
  application generation. Provider-neutral identity does not imply provider-
  neutral execution behavior before future separate evidence.
- Historical evidence remains append-only and profile-bound; no M1 or retained
  planning artifact is rewritten by this amendment.

## Failure-capable M2 acceptance obligations

The M2 work order must demonstrate refusal for an altered origin, live endpoint,
credential fingerprint change, profile digest change, duplicate mutation-eligible
profile, cross-profile identifier collision, unbound capital row, and attempted
in-place provider change. Crash injection must prove profile binding is old-or-
new atomically with its corresponding fact/effect/claim/receipt transition.
