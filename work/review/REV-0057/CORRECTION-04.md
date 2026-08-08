# CORRECTION-04 — R1 wire, export, and current-book projection clarification

Status: **AUTHORIZED DOCUMENTATION CORRECTION — replacement exact R1 review required**

## Independent adjudication

An independent architecture adjudication found no accepted-ADR ambiguity and no
need for a new ADR. The remaining issues are bounded R1 contract/interface
ambiguities. This correction preserves the narrow E1/E2 split and does not
resume application or test implementation.

For current R1 meaning, this correction supersedes only CORRECTION-03's
producer-bound wording: field integrity is not producer authentication, and the
projection must instead be current-book-derived and output-only.

## Corrections

1. E1 identity derivation validates only wire shape: exact types, non-boolean
   uint64 ordinal, and exact 32-byte commitments. A well-formed substituted
   predecessor/genesis, mandate, or compatibility coordinate derives a different
   non-authoritative data ID. E2 alone determines admission and currentness.
2. The exact acquisition-module export set is separate from the established
   broader package root. `acquisition.__all__` has exactly seven names; the
   WO-0150 package-root delta has exactly those seven plus
   `AcquisitionGenerationId` and `VenueAcquisitionCorrelation`, with all
   predecessor root exports preserved.
3. `VenueAcquisitionCorrelation` is a current-book-derived output-only read
   projection, not a standalone provenance proof or capability. Its commitment
   and seal provide deterministic field integrity, not producer authentication.
   The raw-field factory is forbidden: only
   `VenueRecoveryBook.acquisition_correlation`, after exact direct-index proof,
   may construct the production projection. Future E2 must re-query the
   authenticated current book inside its composite transition and must never
   accept a caller-, persistence-, or test-supplied correlation alone.

## Required controls

The R1 implementation controls must prove malformed-wire refusal, deterministic
well-formed coordinate variation, exact module exports and additive root delta,
the sole venue projection construction site, absence of a raw-field factory,
absence of any standalone-authority consumer, and the existing direct-relation
negative cases. These controls remain pure and static/focused; they add no E2
transition, database, runtime, broker, or network behavior.

## Next gate

The prior replacement candidate and its review remain retained negative
evidence. A new detached manifest and fresh independent exact-candidate review
must reach `ACCEPT` with P0=0/P1=0 before E1 RED or production work resumes.
