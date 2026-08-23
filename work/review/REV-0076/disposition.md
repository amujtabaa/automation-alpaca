# REV-0076 disposition

Date: 2026-08-23

## Decision

The R5 `BLOCK` is accepted in full. WO-0168h is superseded before source implementation.

## Root findings accepted

1. Canonical proof bytes cannot safely decode into the existing serving execution/protection
   proof types without repository provenance.
2. The proposed venue transition proof, bootstrap replacement, and cursor-head formula were
   reducer behavior changes, not inert snapshot work.
3. Venue and acquisition selection depended on repository or cross-owner facts unavailable to the
   declared owner-only projector.
4. Collection rules did not distinguish keyed sets from ordered witness paths strongly enough for
   one canonical implementation.
5. Required tests did not independently kill repository, serving-proof, reducer, and behavior-
   commitment leakage.

## Disposition

No patch is attempted against the disproved partition. No R13-H source, tests, DDL, or SQLite
activity occurred. WO-0168c will freeze the non-serving wire representation, repository
observation proof, exact serving-proof issuance, outer payload, and atomic checkpoint persistence
as one reviewed contract. This preserves type separation while placing every fact needed for
selection and authority at the same boundary.
