# REV-0077 R6 reconciled result

Date: 2026-08-23

Candidate: `2c6c680742aec2ed04465d1818887d591836e797`

Verdict: **ACCEPT-WITH-CHANGES** (`P0=0`, `P1=7`, `P2=0`)

Three fresh-context reviewers verified R6's identities, authority graph, vector/BLOB corrections,
and static scope, then reconciled these remaining findings:

1. Declare R2 `ManualFlattenRows` exactly identical to contract-07 `ManualRows`.
2. Bind actual `_provenance`, not a replacement literal.
3. Bind the active runtime registry to the exact capability object and kill copy/deepcopy/reduction.
4. Separate exact runtime/setup out-of-transaction behavior and zero-SQL evidence.
5. Enumerate all future lease activation/retirement success and exceptional exits.
6. Add failure-capable AST/reference controls confining lease activation/retirement calls to
   `unit_of_work.py`.
7. Separate WO-0168c setup-capability commit ambiguity from future runtime lease behavior and pin
   the exact outcome/exception/receipt for every F00-F11 variant.

No SQLite, DDL, query-plan, source, runtime, transaction, or fault test ran.
