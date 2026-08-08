# REV-0058 R5 request -- WO-0151 scope continuity pre-flight

Review the exact composite candidate formed by R2 at SHA-256
343a00f90e854fed0017c708ec99b7da864462ec973b147f77900fd0af8463f5, R3 at
SHA-256 8cc7d58f6c554ead157f0418c93722c9d831db9aa63c78bde992930e1ed19b31,
R4 at SHA-256 bd1f4cabb9071d45586ddfa908f0f4db0c538869b53ee34e0a5b16ee0fa1ae91,
and R5 at the SHA-256 in the R5 manifest. R0 through R4 results are retained
negative evidence, not acceptance evidence.

Review only. Do not edit source, tests, ADRs, work orders, PKL, ledger, or
lifecycle records. Re-derive the candidate against ADR-020 R2, ADR-021 R2,
ADR-023 R1, WO-0151, and the active E1 public seams.

Verify specifically:

1. long-lived controller continuity uses an opaque exact-scope token, not
   ExecutionSnapshot.commitment or another account-wide registry value;
2. a full current snapshot/account-registry/reconciliation check still occurs
   at every owner boundary and cannot be replaced by that scope token;
3. clean unrelated-symbol facts and resolved catch-up do not stale/rewrite a
   target controller, whereas a target execution or required reconciliation
   change fails closed; and
4. source proof, fact, protection-rebase, authority receipt, and application
   generation paths remain feasible without a private read, history scan,
   import cycle, or second aggregate writer.

Return findings only in result-r5.md: severity, precise location, why it
matters, and the smallest root-level correction. End with ACCEPT,
ACCEPT-WITH-CHANGES, or BLOCK; state P0/P1/P2 counts and anything not
verifiable. Do not elevate a style preference into a blocker.

