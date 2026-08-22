---
type: Work Order
title: M2-I1 immutable durable value and profile codec contract
status: ACTIVE
work_order_id: WO-0165
wave: M2-I1
model_tier: strong
risk: high
disposition: []
owner: local coding LLM implementation seat; Codex checkpoint governor
created: 2026-08-21
branch: codex/m2-i1-durable-codec-r1
base_sha: PENDING_EXACT_DOCUMENTATION_BASELINE_MERGE
review_id: REV-0070
execution_authority: Ameen Mujtabaa approved the exact M2-I1 activation in the Codex task on 2026-08-21; implementation is held until the separately authorized documentation-only preparation baseline is merged and the implementation branch base is recorded.
---

# Work Order: M2-I1 immutable durable codecs

**Author:** Codex planning/orchestrator seat
**Date:** 2026-08-21
**Status:** Approved by Ameen Mujtabaa; implementation held for the saved-baseline merge

`[FABLE • FULL • spec-first/TDD • task: pure schema-neutral value/profile codecs and known answers]`

## Context

M1/M1.5 already owns exact values, identities, and immutable execution/market profile semantics. M2-I1 gives those values a deterministic, schema-neutral representation before any SQLite or
runtime work. It adds no persistence owner, reducer, dispatcher, or broker behavior.

The coding LLM works independently between checkpoints. Return the required bundle in
`work/queue/M2-EXECUTION-2026-08-21/00-CHECKPOINT-ORCHESTRATION-PROTOCOL.md` at RED,
GREEN-CANDIDATE, scope pressure, or completion.

## Pre-implementation hold

Source/test work may begin only after:

- the documentation-only preparation packet is merged under separate human authority;
- this branch is created from that exact verified `master` head;
- `base_sha` is recorded in an append-only activation checkpoint; and
- the source/member/typed-route inventory is regenerated with no unexplained drift.

The human has authorized I1; this hold sequences the saved fallback baseline and is not a request
to re-approve I1.

## Context packet

1. `AGENTS.md` and `CLAUDE.md` safety core.
2. `docs/adr/ADR-020-current-state-execution-kernel.md`.
3. `docs/adr/ADR-024-broker-roles-execution-connection-profile.md`.
4. `work/queue/M2-REGENERATION-2026-08-21/03-FRESH-M2-GATE-A-CANDIDATE.md`.
5. `work/queue/M2-REGENERATION-2026-08-21/06-HUMAN-GATE-B-RATIFICATION.md`.
6. `work/queue/M2-EXECUTION-2026-08-21/00-CHECKPOINT-ORCHESTRATION-PROTOCOL.md`.
7. `work/queue/M2-EXECUTION-2026-08-21/02-CURRENT-SOURCE-INVENTORY.md`.
8. `app/execution_core/values.py` and `app/execution_core/identity.py`.
9. `tests/execution_core/test_values.py` and `tests/execution_core/test_import_boundary.py`.

## Functional requirements

- FR-1: The implementation MUST provide an immutable, versioned, schema-neutral durable atom
  for every value class in `values.py`, every concrete exact identity in `identity.py`, and the
  three public composite identity keys. Encode/decode MUST preserve exact type and constructor
  value; it MUST NOT persist private seals/caches or invoke a reducer.
- FR-2: Integer fields MUST use canonical base-10 text: ASCII, optional leading `-` only where
  the owning value permits it, no `+`, no leading zero except `0`, and no negative zero.
- FR-3: `Decimal` fields MUST preserve the exact finite decimal tuple `(sign, digits, exponent)`;
  `Fraction` fields MUST preserve reduced numerator and positive denominator. Float conversion is
  forbidden.
- FR-4: Composite atoms MUST use exact ordered typed child atoms. Unknown tag/version, missing,
  extra, reordered, duplicate, malformed, or wrong-type fields MUST be refused.
- FR-5: The implementation MUST add immutable `ExecutionConnectionProfile` and
  `MarketDataSourceProfile` value contracts matching every ADR-024 field, validation rule, and
  material coordinate. No raw credential or provider account identifier may be retained.
- FR-6: Account assertion, execution profile, and market-source profile commitments MUST use
  ADR-024's exact domains, four-byte domain length, eight-byte part lengths, field order, NFC/text,
  origin, version, token, lowercase-hex, and digest-self-exclusion rules.
- FR-7: Profile IDs remain activation-minted inputs and MUST NOT be derived from commitments.
  Execution identity MUST NOT imply market-source identity.
- FR-8: Decode and profile construction MUST fail closed on noncanonical values; it MUST NOT
  trim, case-fold, URL-normalize, reserialize, infer, substitute, or silently repair input.
- FR-9: Tests MUST independently build literal known-answer preimages/digests without calling
  the production framing or commitment helper and MUST kill mutations to domain, order, length
  width, normalization, origin, case, omission, unknown tag/version, and self-inclusion.
- FR-10: Existing M1 reducers, public behavior, and source bytes outside the allowed paths MUST
  remain unchanged.

## Non-functional requirements

- NFR-1: Pure, deterministic, I/O-free, clock-free, randomness-free, and side-effect-free.
- NFR-2: No new dependency; Python 3.11/3.12 compatible and fully typed under current mypy.
- NFR-3: No import of `sqlite3`, store, broker, API, runtime, config, environment, network, or
  credential modules.
- NFR-4: Round-trip and rejection work are bounded by the fixed atom/profile field count and
  input byte length; no history or repository scan.

## API Contracts

The exact public surface is limited to:

```text
DurableAtom(contract_version, type_tag, fields)
encode_m1_value(value) -> DurableAtom
decode_m1_value(atom) -> exact owning M1 value/identity/key
broker_account_identity_sha256(...non-secret assertion fields...) -> lowercase hex digest
ExecutionConnectionProfile(...accepted ADR-024 coordinates...)
MarketDataSourceProfile(...accepted ADR-024 coordinates...)
execution_profile_preimage(profile_without_digest) -> bytes
market_source_profile_preimage(profile_without_digest) -> bytes
```

Names may receive one spec amendment before RED only if required to match house naming; semantics,
field order, and export count may not expand. No generic serialization registry, plugin system,
schema object, or public runtime facade is permitted.

This is a pure Python API. N/A — there is no HTTP endpoint, request, response, or external service
contract in M2-I1.

## Data Models

| Model | Fields | Constraints |
| --- | --- | --- |
| `DurableAtom` | `contract_version`, `type_tag`, ordered `fields` | Immutable; known version/tag; exact field count/order; no private seal/cache |
| `ExecutionConnectionProfile` | ADR-024 execution coordinates plus commitment | Immutable; one activation-minted ID; no raw credential/account identifier; exact commitment |
| `MarketDataSourceProfile` | ADR-024 market-source coordinates plus commitment | Immutable; separate activation-minted ID; exact commitment; no execution-profile substitution |
| Account assertion input | provider, environment, adapter version, transient provider account ID | Input-only; provider account ID is not retained; result is lowercase SHA-256 |

## Acceptance Criteria

### AC-1: Exact M1 atom round trip (FR-1, FR-2, FR-4)

Given each minimum, boundary, and representative valid M1 value, identity, and composite key
When it is encoded and decoded through the public I1 API
Then exact owning type and constructor value equality hold and malformed atom variants are refused

### AC-2: Exact decimal and rational preservation (FR-3)

Given decimal trailing-zero/exponent cases and rational numerator/denominator cases
When each value is round-tripped
Then the exact decimal tuple and rational value remain correct without any float conversion

### AC-3: Profile construction and separation (FR-5, FR-6, FR-7, FR-8)

Given canonical execution and market-source coordinates with activation-minted profile IDs
When both immutable profiles are constructed
Then commitments match independent literal fixtures and neither profile can substitute for the other

### AC-4: Failure-capable known answers (FR-9)

Given each domain, order, length, normalization, origin, case, omission, and self-inclusion mutant
When the real decisive commitment or validation check evaluates it
Then the control passes and every mutant fails for its intended contract violation

### AC-5: Existing semantics remain unchanged (FR-10, NFR-1, NFR-2, NFR-3, NFR-4)

Given the accepted M1 source and import boundaries
When the complete I1 candidate is compared and tested
Then no reducer/runtime/database/dependency behavior changes and all work remains pure and bounded

## Edge Cases

- EC-1: Unknown contract version or type tag is refused; no fallback or best-effort decode occurs.
- EC-2: Empty, extra, missing, duplicate, reordered, wrong-type, non-NFC, or control-bearing fields
  are refused without normalization or partial object creation.
- EC-3: Integer negative zero/leading-zero/plus forms, non-finite decimal, zero denominator, and
  upper-case or wrong-length hex are refused by the decisive path.
- EC-4: Credential text, recoverable secret material, or a retained provider account identifier is
  rejected and never appears in object representation, test output, receipt, or manifest.

## Allowed paths

```yaml
allowed_paths:
  - app/execution_core/profiles.py
  - app/execution_core/durable_codec.py
  - tests/execution_core/test_profiles.py
  - tests/execution_core/test_durable_codec.py
  - tests/execution_core/test_import_boundary.py
  - work/active/WO-0165-m2-i1-durable-codec-contract.md
  - work/completed/keep/WO-0165-m2-i1-durable-codec-contract.md
  - work/queue/M2-EXECUTION-2026-08-21/**
  - work/queue/WO-0166-m2-i2-schema-direct-proof-foundation.md
  - work/queue/WO-0167-m2-i3-sqlite-repository-hydration.md
  - work/queue/WO-0168-m2-i4-atomic-unit-of-work-effects.md
  - work/queue/WO-0169-m2-i5-startup-reconciliation-cold-recovery.md
  - work/queue/WO-0170-m2-i6-crash-restore-fault-closeout.md
  - work/queue/WO-0171-m3-p1-deterministic-simulator-tape-clock.md
  - work/queue/WO-0172-m3-p2-semantic-replay-regression-corpus.md
  - work/review/REV-0070/**
  - work/ledger.jsonl
```

`test_import_boundary.py` may change only for direct I1 import/refusal pins. Any need to edit
`values.py`, `identity.py`, package-root exports, another test, PKL, ADR, or dependency returns a
scope checkpoint before editing.

The `work/queue/**` paths above authorize only this documentation preparation commit. After the
saved preparation baseline lands, they are read-only inputs for the local coding LLM; changing a
future order or preparation contract requires a Codex checkpoint before edit.

## Out of scope

- OS-1: SQL/DDL, schema, database creation/access, repository, hydration, unit of work, and outbox —
  deferred to separately activated M2-I2 through M2-I4.
- OS-2: Runtime, startup, owner lock, broker/adapter/network/credentials/orders — deferred to later
  human-gated milestones; I1 is pure and offline.
- OS-3: M2-I2+, M3, public HTTP API, accepted ADR change, provider selection, promotion, and
  `master` merge — each requires its own recorded authority.

## Validation and completion

Required evidence: intended RED; focused I1 and existing pure `tests/execution_core` tests;
independent literal known answers and mutation controls; Ruff; mypy; import boundaries;
repository-native governance; exact changed-path proof; independent REV-0070 result. Do not run a
broader suite until a read-only inventory proves it cannot create/open a database or touch another
excluded surface.

Completion requires P0=0/P1=0 independent acceptance, exact publication, clean worktree, lifecycle/
ledger/disposition closeout, and no activation of M2-I2. PKL update is required only if a current
accepted claim actually changes; otherwise record why it is not required.
