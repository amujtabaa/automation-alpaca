# Human ratification request — template pending independent preflight

Status: **COPY-READY RATIFICATION REQUEST — DRAFT ONLY UNTIL HUMAN APPROVAL**

This text names the frozen candidate-manifest and independent exact-candidate preflight result.
An edited copy is not approval and requires a new manifest, review, and hashes.

## Copy-ready text after preflight acceptance

I approve the ARCH-RESET-2026-07 serial acquisition-generation architecture decision only at the
exact frozen candidate manifest SHA-256: **d2538dedb9f9eb05368eb892e83c7ae0dd2872ea0e991f5ee225c88f7ec4714c**.

I approve the proposed complete replacement ADR-020 R2 SHA-256:
**eab0c18cc08539a0c2b1dbc6d61f6d2a0ff359d38b71e8d659cb1ff620513653**, whose body predecessor is ADR-020 R1 SHA-256
35c6782ff7c09ec125b2acad859b4080302660531004db47b8c544b4cf2a5838.

I approve the proposed complete replacement ADR-021 R2 SHA-256:
**b2527dc5285137ef829211b293411e03168458d34b9d3dce96d04b521394c30c**, whose body predecessor is ADR-021 R1 SHA-256
ca822fe682bc2ccca32b5a7915ea4f07bd4ad2319e62d48312edd12c3f8f44f0, while preserving accepted
ADR-023 R1 SHA-256 9a61d4f952079b5f78da7a8f1a17f70dc3099d20fb359596923c5938cc421eaf
as controlling market-occurrence authority.

I approve the selected serial same-symbol acquisition model: distinct reducer-minted
AcquisitionGenerationIds, immutable direct root/effect/owner lineage, one aggregate
SymbolAcquisitionController, at most one LIVE acquisition generation, exactly one active
protection/broker authority, and equal bounded EmergencyRecoveryCompatibility for successor
mandates. I approve no concurrent generations, per-generation protection controllers, generic
policy arbitration, history scans, caller-shaped authority, market-stream reset/reuse, or
ownership transfer.

I acknowledge that the independent static preflight result SHA-256
**c2bbe63a0dd71f5154713554b28af417bef10b86ed6d96847763be09feb2e0e9** concluded P0=0 and P1=0 for this exact candidate, and
that REV-0053 through REV-0055 remain retained negative/unaccepted evidence. I authorize only the
documentation reconciliation needed to record the approved ADRs and the drafting, but not
activation, of the three future pure-M1 work-order candidates described in REV-0056. I do not
authorize their implementation, test implementation, or activation yet.

This approval does not authorize application/test implementation, active work-order activation,
SQL/DDL or database work, persistence/runtime wiring, credentials, broker/Alpaca/network
activity, M2 implementation, master merge, pull request, push, deletion, cleanup, force-push,
rebase, or any later work-order activation. All existing safety boundaries remain in force.

## Attached verification

1. Frozen candidate manifest: 13-CANDIDATE-MANIFEST-R3.md, SHA-256
   d2538dedb9f9eb05368eb892e83c7ae0dd2872ea0e991f5ee225c88f7ec4714c.
2. Independent static preflight: result.md, SHA-256
   c2bbe63a0dd71f5154713554b28af417bef10b86ed6d96847763be09feb2e0e9;
   verdict ACCEPT, P0=0, P1=0, P2=0.
3. Present this exact text with the manifest, independent review result, clause map, and
   non-authoritative downstream reconciliation. Do not treat an edited copy as approved.
