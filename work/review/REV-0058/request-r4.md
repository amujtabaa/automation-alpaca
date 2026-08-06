# REV-0058 R4 request -- WO-0151 target-context pre-flight

Review the exact composite candidate formed by R2 at SHA-256
343a00f90e854fed0017c708ec99b7da864462ec973b147f77900fd0af8463f5, R3 at
SHA-256 8cc7d58f6c554ead157f0418c93722c9d831db9aa63c78bde992930e1ed19b31,
and R4 at the SHA-256 in the R4 manifest. R0 through R3 results are retained
negative evidence, not acceptance evidence.

Review only. Do not edit source, tests, ADRs, work orders, PKL, ledger, or
lifecycle records. Re-derive the composite against ADR-020 R2, ADR-021 R2,
ADR-023 R1, WO-0151, and the active E1 public seams.

Verify specifically:

1. ApplicationGenerationId is bound from the live venue/authority fence and is
   checked at genesis, registration, successor, and serving operations.
2. The venue continuity value is exact PositionScope context, not a full
   VenueRecoveryBook or audit/history commitment; unrelated clean symbol
   activity cannot stale a target controller.
3. Authority continuity is also exact PositionScope context, while global
   kill/mode/session/budget controls remain live checks rather than stale
   controller inputs.
4. The R2/R3 fact, protection-rebase, receipt, and BUY mandate routes still
   remain feasible without a private read, history scan, import cycle, or
   second aggregate writer.

Return findings only in result-r4.md: severity, precise location, why it
matters, and the smallest root-level correction. End with ACCEPT,
ACCEPT-WITH-CHANGES, or BLOCK; state P0/P1/P2 counts and anything not
verifiable. Do not elevate a style preference into a blocker.

