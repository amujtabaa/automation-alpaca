# WO-0152 coverage-ratchet remediation 01 disposition

Date: 2026-08-08

The first independent review, result SHA-256
`6d33708046fc7e3ec726b725817b1db9db3e8461f306bf51a1fae5ff29f111dc`,
returned `ACCEPT-WITH-CHANGES`, P0=0/P1=2/P2=1.

The root correction remains accepted in principle. This focused remediation
closes only its evidence and integration gaps:

1. The validator test now pins one exact branch-aware JSON measurement command,
   one exact validator command, their order, `source = app`, branch
   instrumentation, and the disabled built-in combined gate. Removing or
   reordering the validator therefore fails a normal repository test.
2. Negative values, exact-integer type rejection, valid non-branch metadata,
   impossible totals, invalid JSON, and a missing file are each isolated so an
   unrelated error cannot mask the intended refusal.
3. Both threshold constants and exact-boundary behavior remain pinned.
4. The pytest configuration comment now names the JSON-plus-validator sequence
   as the complete coverage gate.

There is no application, API, runtime, persistence, database, broker, network,
credential, M2, exclusion, pragma, or threshold change. The original candidate
manifest, request, and result remain immutable negative review evidence. The
replacement candidate requires a fresh independent `ACCEPT` at P0=0/P1=0.
