# REV-0058 R4 pre-flight result

Status: **RETAINED NEGATIVE EVIDENCE -- R4 IS NOT ACCEPTED**

Three fresh independent static reviewers verified the exact R2+R3+R4 candidate
against its manifest, ADR-020 R2, ADR-021 R2, ADR-023 R1, WO-0151, and the
active E1 seams. They changed no source, test, ADR, work-order, PKL, ledger, or
lifecycle record.

## Result

**BLOCK** -- P0: 0, P1: 1, P2: 0.

R4 correctly closed the application-generation and whole-book/authority-context
gaps. However, its target venue context still bound
ExecutionSnapshot.commitment. In the active E1 seam, that commitment contains
the account-wide seen-fact registry and reconciliation high-water. A valid
unrelated-symbol canonical fact or resolved unrelated registry catch-up can
therefore change the full snapshot commitment even when the target
VenueExecutionBinding, target ownership, and account-reconciliation-required
state remain exact. That contradicts WO-0151 FR-03 and R4's own
unrelated-symbol continuity control.

## Required replacement direction

R5 must define a venue-owned, scope-local execution-context commitment for
long-lived controller continuity. It must derive only the exact target position,
root, integrity, and direct venue-binding/safety state plus the bounded
account-reconciliation fence. A full ExecutionSnapshot remains mandatory only
as an immediate authenticated input to a venue/authority operation; a clean
unrelated registry advance must not itself stale or advance target controller
currentness. R4 and this result remain unchanged as retained negative evidence.
A new exact R5 freeze and focused review are required before activation.

