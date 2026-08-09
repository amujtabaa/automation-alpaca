# REV-0063 - independent remediation-01 re-review result

## Reviewed identity

- Branch: `codex/m1-5-broker-alignment-local-r1`
- Base: `5eea154f7fbdaa6d77519bdda0edd7ac706f9b5f`
- Candidate: `f5efba1c88dfb48c5fb63878dc02d8d6bcd8b80a`
- Candidate manifest SHA-256 actually reviewed:
  `2dffeb73215ee47dc83d415d4452bb285470bd0d082e6a9e1c74d0dff14b3513`
- Proposed ADR SHA-256 actually reviewed:
  `5764dd5f15d8e06f9e9c13e1f87c163fbaa9eca73fa38472a74ef38df3088e70`

## P0 findings

No P0 findings.

## P1 findings

### P1-1 - Both profile-commitment algorithms still lack constructible byte encodings

- Location: `work/queue/M1-5-BROKER-ALIGNMENT/03-proposed-adr-broker-alignment.md:62-68` and `:140-144`
- Requirement: the remediation request requires independently constructible,
  terminating execution and market-source commitment preimages.  The retained
  ADR-023 commitment authority makes its preimage exact rather than
  implementation-selected, including domain framing, part length prefixes,
  field encodings, fixed-width values, and digest representation
  (`docs/adr/ADR-023-bounded-market-occurrence-authority.md:76-87`).
- Evidence: `[static-reasoning]` The remediation correctly excludes each digest
  output from its own ordered field list and makes both IDs opaque and
  non-digest-derived.  It specifies neither the bytes to hash nor a canonical
  encoding for any new profile field: there is no framing between the domain and
  fields, field length/escape rule, text encoding, enum representation, opaque
  ID representation, or digest case/byte representation.  Thus two independent
  M2 implementations cannot compute the same claimed preimage from the stated
  rule; concatenation, delimiters, JSON, and length-prefixed parts are all
  compatible with the prose but produce different digests.  The same omission
  applies to `execution-connection-profile/v1` and
  `market-data-source-profile/v1`.
- Impact: M2 would have to invent unratified digest semantics for the selected
  profile and market-source profile.  That prevents an independent startup,
  final-claim, historical-binding, or market-provenance verifier from deciding
  whether a stored commitment matches its profile, defeating the intended
  fail-closed comparison at the new binding boundary.
- Resolution: define one exact, versioned byte construction for each profile
  commitment: domain framing; every field's canonical type, normalization and
  byte encoding; part ordering/framing and optional-value rule; and lowercase
  hexadecimal SHA-256 output.  State how opaque activation-minted IDs are
  encoded without making them digest-derived.  Future M2 known-answer controls
  should independently reproduce each specified byte sequence and digest.

## P2 findings

No P2 findings.

## Executed verification

- `[reproduced-live]` `HEAD` resolved to the requested candidate and the named
  base and candidate objects both exist.
- `[reproduced-live]` All 11 manifest-covered semantic files matched their
  recorded SHA-256 values.  The manifest is explicitly self-excluded; its
  separately calculated SHA-256 is recorded above.
- `[reproduced-live]` The base-to-candidate diff contains the 11 covered
  semantic files, the self-excluded manifest, and the reviewer-owned/origin
  disposition artifacts.  The scope checker accepted the complete changed-file
  list for `WO-0157`.
- `[reproduced-live]` `git diff --check`, `check_ledger.py`, and
  `check_pkl.py pkl` passed under available Python 3.14.5.
- `[static-reasoning]` The revised capability contract is immutable and
  credential-free in M2; append-only evidence is bound to both the exact
  capability digest and selected execution-profile commitment.  The existing
  M4 human credential/outbound-call gate produces complete matching evidence
  before `PAPER_MUTATION_ELIGIBLE`; refresh does not rewrite the profile, while
  a changed requirement requires new-generation recutover.  I found no
  remaining P1-2 lifecycle cycle.
- `[static-reasoning]` The candidate retains Alpaca Paper as the sole M2-M8
  mutation provider, M1/M2 inactivity boundaries, one mutation-eligible
  profile, no routing/failover/cross-provider inventory, distinct market-source
  provenance, and the accepted first-occurrence execution-fact and ratification
  restrictions.

## Unverified

- Full pytest, Ruff, mypy, import-boundary, coverage-ratchet, R2 oracle, and
  Python 3.11/3.12 exact-head CI were not run.  The local `.venv\\Scripts\\python.exe`
  is absent; Python 3.14.5 was used only for the AI-OS static checks.
- No M2 schema/runtime implementation, database/DDL execution, credential use,
  broker/network call, external CI, or abandoned Cloud PR #12 material was
  inspected or used.

Verdict: ACCEPT-WITH-CHANGES
P0: 0
P1: 1
P2: 0
