# REV-0058 R2 pre-flight result

Status: **RETAINED NEGATIVE EVIDENCE -- R2 IS NOT ACCEPTED**

Two fresh independent static reviewers verified the frozen R2 contract body at
SHA-256 343a00f90e854fed0017c708ec99b7da864462ec973b147f77900fd0af8463f5
against ADR-020 R2, ADR-021 R2, ADR-023 R1, WO-0151, and the active E1 seams.
They changed no source, test, ADR, work-order, PKL, or lifecycle record.

## Result

**BLOCK** -- P0: 0, P1: 4, P2: 0.

R2 closed the R0/R1 source, admission, receipt, direct-reader, and dependency
direction findings. Four bounded provenance/continuity requirements remain:

1. **P1 -- genesis absence and canonical coordinate.** The contract did not
   require a sealed absence of the target acquisition-currentness registration,
   canonical E1 genesis head, and ordinal zero before initial registration.
   A duplicate initialization or substituted first coordinate could therefore
   appear well-formed.
2. **P1 -- retired reconciliation precedence.** A reconciliation-classified
   retired economic fact could select RECONCILIATION_REQUIRED instead of the
   mandatory mixed-generation HARD_BAIL/preemption route. Reconciliation may
   add a non-serving fence, but cannot replace that route.
3. **P1 -- full protection-rebase relation.** The rebase projection bound one
   execution commitment only. It needed predecessor and current execution plus
   predecessor and current venue commitments, all checked against the
   controller and authority pair.
4. **P1 -- specialized BUY mandate field.** The contract did not freeze that
   the existing BrokerEffectRequest.mandate_id is the exact linked
   ProtectionMandate mandate ID, rather than the AcquisitionMandate ID or
   caller-selected data.

## Required replacement direction

R3 must be a narrow additive amendment to the frozen R2 body. It must make
genesis derive the E1 canonical head and ordinal zero after a sealed
absence-proof; define the retired-fact precedence explicitly; bind/check the
full pre/post execution and venue relation for protection rebases; and derive
the specialized BUY request mandate ID only from the complete dual binding.
R2 and this result remain unchanged as negative evidence. A new exact R3
freeze and focused independent review are required before activation.

