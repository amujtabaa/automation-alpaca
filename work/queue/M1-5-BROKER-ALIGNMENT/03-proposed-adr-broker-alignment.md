# ADR-024 — Broker roles, single active execution-connection identity, and provider-neutral M2 persistence boundary

Status: **PROPOSED — DRAFT ONLY — NOT RATIFIED**

Decision owner: human architecture authority

Predecessors: accepted ADR-020 R2, ADR-021 R2, ADR-022, and ADR-023 as
indexed by `ARCH-RESET-2026-07-RATIFICATION.md`.

## Context

The reset beta deliberately uses Alpaca Paper as its low-cost conformance
provider while preserving a narrow, broker-neutral execution kernel. ADR-022
requires a fail-closed generation fence containing exact Alpaca/Paper/account/
origin/credential-fingerprint values. The current M2 planning material repeats
those values as provider-literal proposed DDL clauses. That preserves immediate
Paper safety but risks mistaking the selected beta profile for permanent durable
schema identity.

The project needs portability without routing: one selected execution connection
per application generation, no concurrent capital authority, and no provider
change without a reviewed recutover. It also needs a distinct market-data
provenance contract because an execution broker cannot certify market evidence.

## Decision

### 1. Broker roles and milestone boundary

- Alpaca Paper is the only mutation-capable execution provider for M2 through
  M8. The project remains paper-only; live trading is not authorized.
- Webull is the preferred future production-candidate subject of a separate M9
  feasibility and adapter wave. This ADR grants no Webull credential, network,
  API, data, or execution authority.
- IBKR Pro is an optional future execution-quality benchmark only.
- FIX/QuickFIX, Robinhood agentic MCP, Tradier, multi-broker routing, failover,
  and simultaneous execution providers are deferred.
- M1 remains closed and unchanged; this is not M2 activation, DDL, or runtime
  wiring.

### 2. One immutable execution connection profile

Every application generation SHALL have one and only one immutable selected
`ExecutionConnectionProfile`:

```text
ExecutionConnectionProfile
├── connection_profile_id
├── application_generation
├── broker_provider
├── environment_class
├── account_identity
├── trade_command_origin
├── order_query_origin
├── order_event_origin
├── credential_handle_fingerprint
├── adapter_contract_version
├── capability_profile_sha256
├── deployment_identity
└── profile_commitment_sha256
```

`connection_profile_id` is an opaque activation-minted identity and MUST NOT be
derived from a profile commitment. The profile is constructed from canonical,
non-secret values. `profile_commitment_sha256` is the SHA-256 of one versioned,
domain-separated canonical preimage (`execution-connection-profile/v1`) that
contains, in the field order shown above, every profile coordinate from
`connection_profile_id` through `deployment_identity`, but excludes
`profile_commitment_sha256` itself. The commitment is the digest output, not a
member of its own preimage. `credential_handle_fingerprint` is only a
non-reversible recognized-handle/version fingerprint; no credential, bearer
token, API key, secret, or recoverable secret material may be stored in a
profile, receipt, log, manifest, or public repository.

For M2–M8 the sole selected profile resolves to broker provider `ALPACA` and
environment class `PAPER`. The exact Paper account and origins remain mandatory
profile coordinates. A live origin, live credential, absent field, unknown
fingerprint, mismatched profile commitment, or any coordinate mismatch denies
broker I/O and mutation eligibility.

### 3. Single active mutation authority

Exactly one profile may be mutation-eligible for an application generation.
The immutable selected profile, not a mutable preference or runtime default,
defines that authority. There is no hot swap, simultaneous active profile,
standby provider, cross-broker inventory, routing weight, fallback, or provider
selection policy. Historical generations retain their own immutable profile
binding and never regain mutation authority by matching a current symbol or
account.

### 4. Capital-relevant durable binding

M2 must bind every capital-relevant durable authority to the exact selected
profile identity or `profile_commitment_sha256`, in addition to its existing
application-generation and safety coordinates. At minimum this includes:

- checkpoint/current state and application-generation activation record;
- canonical execution facts and revision-chain heads;
- input/inbox identities, broker-visible client identities, and coverage
  watermarks;
- effects, immutable dispatch claims, concrete venue owners, acceptance-set and
  terminal-closure evidence;
- controller/generation bindings, protection/authority state, mandates, and
  composite decision receipts; and
- startup, final-claim, cutover, rollback, and reconciliation comparisons.

An external identifier is profile-scoped. A broker order ID, source event ID,
cursor, client order ID, owner, effect, or receipt from one profile cannot bind
to another profile merely because its raw provider string, account text, or
symbol matches. Existing first-occurrence FILL and predecessor-linked
broker-authoritative TRADE_CORRECT/TRADE_BUST truth rules remain unchanged.

### 5. Material change requires a new-generation recutover

Provider, environment, account identity, any command/query/event origin,
credential-handle fingerprint, adapter contract version, capability-profile
digest, or deployment identity is material. It cannot be edited in place after
profile creation. Any material change requires a new application generation and
the complete separately reviewed cutover/recutover proof: old-generation
occurrence closure and coverage, flat/no-open-or-unknown-order proof where
required, selected-profile validation, and final-claim/startup mismatch denial.
This ADR neither defines nor approves that proof's DDL or runtime implementation.

### 6. Separate market-data source profile

Execution identity SHALL NOT imply market-data provenance. A future selected
market source uses a separate immutable `MarketDataSourceProfile`:

```text
MarketDataSourceProfile
├── market_source_profile_id
├── provider
├── environment_or_feed
├── source_origin
├── entitlement_class
├── normalization_contract_version
├── data_capability_profile_sha256
└── source_profile_commitment_sha256
```

`market_source_profile_id` is likewise opaque and activation-minted, not
digest-derived. `source_profile_commitment_sha256` is the SHA-256 of a
versioned, domain-separated canonical preimage
(`market-data-source-profile/v1`) containing the preceding market-source fields
in displayed order and excluding `source_profile_commitment_sha256` itself.

`MarketStreamGenerationId` and market-evidence authority must bind an exact
market-source profile commitment. An execution connection neither creates nor
infers market-source authority. This preserves ADR-023's stream-generation,
strict-coordinate, and restart-fence requirements.

### 7. Evidence-backed broker capability profile

`BrokerCapabilityProfile` is a versioned immutable required-capability contract,
identified by the profile's `capability_profile_sha256`. Its domain-separated
`broker-capability-profile/v1` preimage names the selected product/account
scope, required sessions and early-close rules, extended-hours combinations,
order/time-in-force semantics, submit/cancel/replace and client-ID behavior,
targeted-query and full coverage, stream cursor/reconnect, corrections/busts,
partial fills, limits/reserved capacity, quantity constraints, data
entitlements, paper-versus-production distinctions, and adapter/normalization
version. The digest commits the required capability contract and validation
rules, not a mutable observed test result.

`BrokerCapabilityEvidence` is separately append-only, non-secret, and bound to
the exact capability-profile digest and selected execution-profile commitment.
It records dated normalized official-source and empirical outcomes, their
evidence digests, and whether each required capability was proven, refused, or
unknown. A profile claim is not usable merely because the requirement digest
exists: an exact complete evidence set must validate every required capability.
Marketing claims and generic documentation cannot alone establish conformance.
Refreshing evidence that validates the same required capability contract does
not rewrite an execution profile. Evidence that refutes, omits, or no longer
matches a required capability leaves the profile non-serving; changing the
required capability contract is material and requires the new-generation
recutover route.

### 8. M2 schema boundary and explicit refusals

This ADR is a schema-neutral contract. Exact DDL, constraints, serialization,
database creation, migrations, runtime composition, credential use, and broker
calls remain deferred to a separately activated M2 work order.

M2 must not preserve `broker='ALPACA'` or `environment='PAPER'` as an eternal
provider-literal constraint on every durable capital row. Instead, it must bind
that row to the selected profile/commitment, whose M2–M8 values are Alpaca Paper.
This is a representation constraint, not permission to loosen the Paper profile
comparison or accept another provider.

This ADR refuses mutable broker settings, profile overwrite, profile inference
from a symbol/account/current SDK, generic multi-broker interfaces, automatic
failover, routing, inventory netting across providers, live trading, Webull
integration, and any second writer or execution authority.

### 9. Preservation and narrow supersession

ADR-020's one logical writer, atomic M2 unit of work, direct generation
lineage, and first-occurrence execution-fact rules remain controlling. ADR-021's
one active protection/broker authority and its refusal of parallel controllers
remain controlling. ADR-023's independent market-source/evidence constraints
remain controlling. ADR-022's selected beta values and fail-closed cutover
comparisons remain controlling.

ADR-024 narrowly supersedes only the inference that ADR-022's selected
`ALPACA`/`PAPER`/account/origin/credential coordinates must be permanently
duplicated as provider-literal durable-schema constraints. They are now the
immutable coordinates of the selected execution profile and must still compare
exactly at startup and final claim.

## Consequences

M2 can construct one provider-neutral durable identity boundary without
implementing a multi-broker runtime. M3 can replay profile-scoped facts and
recutover refusals; M4 can establish Alpaca Paper conformance evidence; M5–M8
remain Paper milestones. M9 begins only with official-document and empirical
Webull feasibility work. No provider change follows from this ADR alone.

## Required evidence before implementation reliance

- A reviewed M2 contract/DDL design proves one selected immutable profile per
  generation, total profile binding, historical retention, and refusal of
  profile mismatch at startup and final claim.
- Crash/replay controls prove an old-or-new atomic profile binding and refuse
  cross-profile identifier substitution, two eligible profiles, and recutover
  without new-generation proof.
- M4, under its existing explicit human gate for credentials and bounded
  outbound Alpaca Paper conformance calls, produces the complete evidence set
  for the already selected required-capability contract before any profile can
  become `PAPER_MUTATION_ELIGIBLE`.
- M9 records official-document and empirical feasibility evidence before any
  Webull adapter decision.
- An independent review accepts the exact candidate with P0=0/P1=0 and the
  human ratifies exact hashes before this body is copied to canonical ADR path.
