# REV-0058 R3 request -- WO-0151 final RED pre-flight

Review the exact composite candidate formed by:

1. WO-0151-RED-CONTRACT-R2.md at SHA-256
   343a00f90e854fed0017c708ec99b7da864462ec973b147f77900fd0af8463f5; and
2. WO-0151-RED-CONTRACT-R3.md at the SHA-256 recorded in the R3 manifest.

R0, R1, and R2 results are retained negative evidence. Review only; do not
edit source, tests, ADRs, work orders, PKL, ledger, or lifecycle state.

Re-derive the composite against ADR-020 R2, ADR-021 R2, ADR-023 R1, WO-0151,
and the active E1 public seams. Verify specifically:

1. genesis has an authority-sealed exact-scope registration absence check and
   derives the E1 canonical head plus ordinal zero without caller coordinates;
2. a normal protection rebase carries/checks exact predecessor/current
   execution and venue commitments against both controller and authority;
3. a retired reconciliation fact cannot replace mandatory current-BUY
   preemption and HARD_BAIL mixed recovery; and
4. the specialized BUY request derives BrokerEffectRequest.mandate_id only
   from the bound ProtectionMandate while retaining the distinct acquisition
   identity in the composite lineage.

Return findings only in result-r3.md: severity, precise location, why it
matters, and the smallest root-level correction. End with ACCEPT,
ACCEPT-WITH-CHANGES, or BLOCK; state P0/P1/P2 counts and anything not
verifiable. Do not elevate a style preference into a blocker.
