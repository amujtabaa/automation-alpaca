# ADR-023 GREEN pre-flight derived-identity setter review

## Review boundary

- Parent: `17accddabd1defa14176f00b0328a300d936ae3c`
- Candidate: `157c7d43c11c9323cd9e7aba7ed5168cc0f8132e`
- Exact candidate paths:
  - `tests/execution_core/test_import_boundary.py`
  - `work/active/WO-0148-reset-kernel-d-position-protection-hybrid-trailing.md`

Review only the immutable parent-to-candidate delta. The local working tree contains uncommitted
application implementation and must not be treated as candidate evidence.

## Required independent determination

Re-derive whether the accepted RED oracle made ratified frozen derived
`MarketOccurrence.occurrence_id` structurally impossible by rejecting the sole canonical
`object.__setattr__` initialization in `__post_init__`. Determine whether the correction admits
only this exact deterministic assignment and continues to reject wrong owner, lifecycle,
receiver, field, constructor, hash input, duplicate setter, rebinding, and every unrelated
attribute mutation.

Verify that the control is failure-capable, the WO record is source-faithful, and the delta changes
no ADR meaning, public API, persistence, runtime wiring, database, broker, network, credential,
M2, merge, deletion, or cleanup surface.

The author-side focused evidence was 7/7 passing for the new mutation control plus exact public
roles, bounded market state/work, public-role independence, complete call/effect binding, and
side-effect-free import. Treat that as a claim to verify, not review authority.

Write findings only to `result.md`. Each finding must include severity, file and line, production
or proof impact, and the smallest root correction. End with `ACCEPT`, `ACCEPT-WITH-CHANGES`, or
`BLOCK`, explicit P0/P1/P2 counts, and anything not verified. Do not edit `request.md`, production,
tests, ADRs, PKL, ledger, or the work order.
