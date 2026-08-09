# Proposed ADR-024 — broker roles, single active execution-connection identity, and provider-neutral M2 persistence boundary

Status: **PROPOSED — NOT ACCEPTED AUTHORITY**

Decision owner: human architecture authority
Task A base: `5eea154f7fbdaa6d77519bdda0edd7ac706f9b5f`

## Context

Pure M1 is complete. Its deterministic execution kernel is provider-neutral, but ADR-022 selects
Alpaca Paper for beta and describes durable M2 bindings using literal provider, environment,
account, origin, and credential coordinates. Encoding that current business selection as the
permanent universe of every table would make a later provider require unnecessary semantic and
schema replacement. Conversely, introducing mutable broker settings or a multi-broker runtime
would weaken the single-authority beta boundary.

Execution connectivity and market-data provenance are also distinct. A future execution provider
must not implicitly become the source of protection-authoritative market evidence.

## Decision

### 1. Broker roles and beta boundary

Alpaca Paper is the sole mutation-eligible execution provider for M2–M8. `PAPER` and
`LIVE_SHADOW` remain the only beta environment classes; live trading remains prohibited. Webull is
only the preferred future production feasibility/adapter candidate for M9. IBKR Pro is only an
optional later execution-quality benchmark. FIX/QuickFIX, Robinhood Agentic/MCP, Tradier,
multi-broker routing, hot swap, automatic failover, routing weights, and cross-broker inventory are
deferred and receive no authority.

### 2. One immutable execution-connection profile

Each application generation SHALL bind exactly one immutable `ExecutionConnectionProfile`:

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

Exactly one profile may be mutation-eligible for an application generation. For M2–M8 its
committed coordinates SHALL resolve to Alpaca Paper and the reviewed Paper origins/account/
credential-handle identity. No secret is stored. Credential identity is limited to opaque handle,
version, and non-reversible fingerprint material.

The profile commitment covers every listed semantic coordinate using a versioned canonical
encoding. The profile is immutable once any external fact, effect, claim, owner, closure, receipt,
or checkpoint exists. A provider, account, environment, origin, credential identity, adapter
contract, capability profile, or deployment-identity change requires a new application generation
and reviewed fail-closed recutover. It is never a hot setting update.

### 3. Durable authority binding

Every capital-relevant fact, effect, claim, venue owner, acceptance closure, receipt, and
checkpoint SHALL bind the exact connection-profile identity or its commitment in addition to the
existing application-generation and domain identities. Hydration, effect eligibility, final-claim
revalidation, broker correlation, and recovery SHALL reject missing, ambiguous, mismatched, or
uncommitted profile identity. No profile match can itself grant mutation eligibility; the existing
mode, cutover, closure, reconciliation, kill-switch, budget, and safety gates remain mandatory.

### 4. Market-data provenance is independent

An execution connection SHALL NOT imply a market-data source. A separately governed immutable
`MarketDataSourceProfile` contains source profile identity, provider, feed/environment, origin,
entitlement class, normalization-contract version, capability-profile hash, and commitment.
`MarketStreamGenerationId` SHALL ultimately bind one exact market-source commitment. Changing that
commitment requires the separately reviewed stream-generation/mandate cutover already required by
ADR-023. This ADR defines the boundary only; it does not authorize a feed, adapter, entitlement,
runtime, or M2 table.

### 5. Evidence-backed capabilities

Provider capability claims SHALL be versioned evidence, not marketing assumptions. A
`BrokerCapabilityProfile` covers tested product/account scope, sessions and early closes,
extended-hours combinations, order types and time in force, submit/cancel/replace identity,
idempotency, targeted and mass query coverage, stream cursor/reconnect behavior, corrections and
busts, partial fills, rate limits and reserved emergency/query capacity, share constraints,
entitlements, paper/production differences, and adapter/normalization versions.

M4 must prove the exact Alpaca Paper capability profile used by its connection profile. M9 must
independently verify Webull before any adapter or production proposal. Capability evidence cannot
expand the accepted beta boundary by itself.

### 6. Preservation and narrow supersession

ADR-020 through ADR-023 remain unchanged. Their pure-kernel, canonical-fact, bounded-state,
single-writer, single-authority, paper-only, fail-closed, atomic-transition, and market-evidence
rules are preserved.

This overlay narrowly supersedes only an inference from ADR-022: literal `ALPACA` and `PAPER`
coordinates are the mandatory values of the immutable beta connection profile, not the permanent
provider domain of every M2 table. Direct row bindings to those duplicated literals are replaced
prospectively by binding to the exact immutable profile identity/commitment. Existing comparisons
remain required against the committed profile values. Provider-literal DDL must not proceed until
M2 reconciles it with this decision.

## Consequences

- M2 receives a provider-neutral identity boundary but no permission to create DDL or a database.
- Portability requires a reviewed new-generation recutover, not runtime multiplicity.
- Market data can later be independent without weakening execution authority.
- M1 source, tests, public contracts, and proof remain byte-unchanged.
- The project remains Automation Alpaca; no rename follows from future-provider portability.
- The public repository must contain no secret or private broker material.

## Deferred work

Exact SQL types, tables, foreign keys, uniqueness rules, canonical commitment encoding, migration,
hydration, and crash semantics belong to a separately activated M2 design. Broker calls and Alpaca
Paper conformance belong to M4. Webull research and feasibility belong to M9. This ADR grants no
schema, persistence, runtime, adapter, network, credential, deployment, broker-mutation, or live-
trading authority.
