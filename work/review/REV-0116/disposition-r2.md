# REV-0116 R2 disposition

Date: 2026-08-29

Status: **ACCEPTED FINDING — P0=0 / P1=1 / P2=0**

The fresh review independently reproduced the predecessor conflict and accepted the compact
behavioral-cutover direction, but demonstrated one ordering defect: queried recovery operations
could not run through M2-I4 until the compact successor had first committed and been reread.

The finding is accepted at the root. The corrected sequence now commits and rereads the atomic
compact-owner plus cold-market-invalidation successor before reconciliation. Reconciliation then
uses only that admitted successor and advances it normally through M2-I4. Immediately before the
first source call, the same private cold-invalidation transition is applied to the latest context;
it is exact replay if reconciliation preserved invalidation, or commits and rereads one new
invalidated successor otherwise. This closes the ordering gap without preserving an
unreconstructable old commitment or introducing a second mutation path.

Hydration/cutover source remains held until the same reviewer verifies this exact correction with
zero open P0/P1.
