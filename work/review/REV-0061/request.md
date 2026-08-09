# Independent review request: WO-0152 coverage-ratchet semantics

Review the exact candidate frozen by
`WO-0152-COVERAGE-RATCHET-CANDIDATE-MANIFEST.md` as a fresh independent seat.

Determine whether the change corrects the accidental combined-denominator
gate without weakening capital-safety evidence, functional verification, line
coverage, branch coverage, or CI integrity. Re-derive the arithmetic from the
coverage JSON and inspect the validator, its failure-capable controls, the CI
ordering, the active work-order authority, and the E3 behavior-test boundary.

Required verdict: `ACCEPT`, `ACCEPT-WITH-CHANGES`, or `BLOCK`, with explicit
P0/P1/P2 counts. Write findings only to `result.md`; do not edit the candidate.

Do not run broker, Alpaca, network, credential, database, SQL/DDL, runtime, M2,
merge, PR, deletion, cleanup, force-push, or rebase operations.
