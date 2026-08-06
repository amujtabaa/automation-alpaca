# CORRECTION-03 — R1 authority and boundary-closure synthesis

Status: **AUTHORIZED DOCUMENTATION CORRECTION — replacement exact R1 review required**

## Why this correction exists

The first R1 documentation preflight preserved the intended E1/E2 split but found
that predecessor R0 authority remained too easy to mistake for current authority,
and that the proposed failure controls did not close every disclosed boundary at
the actual production-module and direct-venue-relation level. These are contract
and provenance corrections only. No application or test implementation resumes
from this record.

## Required R1 corrections

1. The active work order, PKL, append-only project log, and append-only ledger
   must identify the R0 acceptance/activation as historical evidence only and
   make `R1_PENDING` plus a fresh exact-candidate `ACCEPT` at P0=0/P1=0 the one
   controlling implementation gate.
2. The R1 static control must use a literal AST import tuple allowlist against
   the actual `acquisition.py` source and a closed E1 structural surface. Its
   synthetic snippets demonstrate that the checker can fail; they are not the
   sole evidence that the production module lacks a raw-to-trusted or mutation
   seam.
3. `VenueAcquisitionCorrelation` must be exact-type, nonconstructable,
   non-subclassable, and publicly producer-bound to the direct
   `VenueRecoveryBook.acquisition_correlation` query. Its commitment and seal
   must bind every exposed relation field, so a caller-built lookalike is not
   venue provenance.
4. The direct venue bridge must require a unique, fully consistent relation
   across the request, effect, application generation, exact position scope,
   and every supplied leg/root selector. It must refuse a missing selector,
   zero or ambiguous relation, conflicting dual selectors, same-account
   cross-symbol scope, and every request/effect/owner/leg/root mismatch.

## Preserved boundaries

This correction does not activate WO-0151 or change accepted ADRs. Successful
registry/index/fact mutation, controller currentness, and acquisition admission
remain E2-only. Runtime, persistence, SQL/DDL, broker/network activity,
credentials, M2, merge, deletion, cleanup, rebase, and force-push remain out of
scope.

## Next gate

The detached manifest and request must be regenerated over the corrected
documentation source set. A fresh independent review of that exact manifest
must return `ACCEPT` with P0=0/P1=0 before E1 test or production implementation
resumes.
