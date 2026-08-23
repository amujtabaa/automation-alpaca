# REV-0076 R5 independent behavioral-boundary review result

- Candidate: `d268d5c3774aefa0828287cfa5e998ab8056d16d`
- Tree: `168aafbf4a4973442ec0b9eae3320cd8e03107e0`

Verdict: **BLOCK**

### [P0] Proof-byte decoding can mint existing serving authority

- Location: `work/queue/M2-EXECUTION-2026-08-21/07-WO-0168H-FROZEN-OWNER-STATE-WIRE-CONTRACT.md:923`, `:949`, `:982`
- Evidence: `reproduced-live` static inspection. The contract requires bytes to reconstruct exact `_M2ExecutionObservationProof` and `_M2ProtectionAuthorityProof` objects. Those types are consumed as serving authority by `position.py:1182-1242` and `protection.py:2757-2823`. Their authenticity checks use caller-recomputable hashes and structural validation, not unforgeable owner or repository provenance.
- Impact: Arbitrary internally coherent bytes could become the exact serving proof type. Alternatively, retaining the existing checkpoint-codec issuance gate makes the required owner-local byte round-trip impossible. Either outcome violates R5’s owner-authenticated, non-serving boundary.
- Resolution: Decode into separate immutable non-serving wire types, or permit only encode/byte-compare of an already-authentic proof. Conversion into existing serving proof types must remain behind the future R13-C repository authority gate.

### [P1] Acquisition snapshot selection is not owner-local

- Location: `...FROZEN-OWNER-STATE-WIRE-CONTRACT.md:802`, `:858`, `:967`
- Evidence: `static-reasoning`. `_m2_acquisition_snapshot_from_state` accepts only `AcquisitionControllerState`, but standing-lineage selection requires venue disposition/late-owner facts and the authority acquisition slot. `GenerationRouteView` retains only route kind, source commitment, generation ID, and seal (`acquisition.py:296-302`); it does not retain the required `LineageSourceBinding` coordinates.
- Impact: The specified snapshot cannot be projected exactly from the authentic owner. Implementation must either introduce undeclared cross-owner/repository inputs, serialize history, or omit/invent semantic rows.
- Resolution: Define the bounded snapshot solely from information retained by `AcquisitionControllerState`, or defer this standing subset and its source bindings to R13-C.

### [P1] Venue projection requires repository-only provenance

- Location: `...FROZEN-OWNER-STATE-WIRE-CONTRACT.md:374`, `:491`, `:963`
- Evidence: `static-reasoning`. Required ordinals and contradiction validation depend on `VenueEffectRecord.created_ordinal`, `DurableInputRecord.created_ordinal`, and `AcceptanceEvidenceRecord`. The owner’s `AcceptanceContradiction` contains only leg and observation IDs (`venue.py:797-800`), while `VenueIdentityOwner` has no `admitted_after_effect_closed` member (`venue.py:847-852`).
- Impact: An owner-only projector cannot determine the required evidence ordinal or distinguish a late-owner closed effect from unrelated closed history. Exact selection and “extra row” rejection therefore cannot be implemented from `VenueRecoveryBook`.
- Resolution: Derive ordering and selection exclusively from owner-retained fields, adding an owner-local semantic marker if necessary, or move repository-derived predicates to R13-C.

### [P1] Normative R5 scope still changes serving venue behavior

- Location: `...FROZEN-OWNER-STATE-WIRE-CONTRACT.md:204`, `:216`, `:414`, `:442`
- Evidence: `static-reasoning`. The normative contract introduces `M2VenueTransitionProof`, changes bootstrap records to retain it, and replaces ordinal-positive protection-cursor commitment construction.
- Impact: These are serving reducer/bootstrap and behavioral-commitment changes, contradicting R5’s snapshot-only rule and its prohibition on replacing existing behavior commitments.
- Resolution: Remove these transition-proof and cursor changes from normative R13-H scope and defer them to a separately reviewed serving-boundary contract.

Field census independently passed: all **57/20/13** source fields were classified exactly once with no missing names. Candidate/tree identity matched, the review diff contains no `app/` or `tests/` changes, and no SQLite or database-bearing command was run.

P0: 1  
P1: 3  
P2: 0  
Unverified: none within the normative documentation-only R5 scope.
