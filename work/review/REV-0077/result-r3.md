# REV-0077 R3 reconciled result

Date: 2026-08-23

Candidate: `280a675cedf19dd32aa4f0408749ef258b7d42df`

Verdict: **ACCEPT-WITH-CHANGES** (`P0=0`, `P1=5`, `P2=0`)

Three fresh-context reviewers verified the exact candidate. The outer/component rows and all twenty
flattened repository vectors matched current source. Findings reconcile to:

1. R3's closed authority still transitively imports superseded wire clauses and excludes the exact
   reconciled API/export/outcome/CAS surface; authority must be recursively hash-bound or inlined.
2. Binding preimages need literal domains, scalar/optional/list framing, exact private fields, and
   known answers; field names alone are not bytes.
3. Q2 inner joins can silently omit a scope lacking controller/protection rather than refuse it.
4. Materialized selected-generation discovery is not bounded on the over-cap refusal path; LIVE and
   unresolved discovery must be split/gated before later CTE use.
5. Q4a's forced index cannot provide created-ordinal order while the plan rules forbid its required
   bounded temporary sort; SQL/index/plan expectations and deletion mutants must agree.

The added R3 failure-control prose also needs stable test IDs and source mutants in the final
matrix; this is incorporated into findings 1-2 as missing exact surface.

No SQLite, query plan, DDL installation, runtime, transaction, or fault test ran.
