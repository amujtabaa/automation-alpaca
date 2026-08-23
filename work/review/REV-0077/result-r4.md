# REV-0077 R4 reconciled result

Date: 2026-08-23

Candidate: `8d70951d69f034da98bf6f13ce0dd42eff336b48`

Verdict: **ACCEPT-WITH-CHANGES** (`P0=0`, `P1=10`, `P2=0`)

Three fresh-context reviewers independently verified the exact candidate and its declared hashes.
Their findings reconcile without dismissal:

1. The historical authority graph needs full `commit:path` coordinates, the venue top row, and
   explicit exclusions for superseded transition-proof and authority-top rows.
2. A projected envelope does not retain the source-owner commitments required to freshly
   re-derive its authenticity binding at store.
3. Binding authority is still incomplete: recursively framed durable atoms, every literal field
   and absence domain, flattened field types, all ten absence-key grammars, nineteen record
   sequences, and representative non-empty known answers must be exact.
4. The atomic fault test must enumerate every write/CAS/reread/receipt failure boundary and prove
   rollback by close/reopen state.
5. Q3b's forced partial index is not provably usable for its AND-wrapped OR predicate under
   SQLite's partial-index rules.
6. Q2's present vectors incorrectly imply every column is non-null; exact valid inactive and
   malformed partial-null rules are required.
7. Q5 can sort unbounded selected-parent owner history before its outer LIMIT; admission must be
   bounded before canonical sorting.
8. Q1 cannot distinguish absent application from profile conflict because it filters both profiles
   in SQL.
9. The repeated later LIVE CTE omits Q3a's generation-current join and exposes no realizable
   coordinate equality proof.
10. Exact signatures omit connection/coordinate/capability types and do not decide runtime versus
    setup write authority or a substitution mutant.

No SQLite, query-plan, changed-DDL, transaction, fault, runtime, or source test ran.
