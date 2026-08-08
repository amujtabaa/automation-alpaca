# REV-0060 R13-R1 activation R1 focused review request

Status: **FOCUSED RECORDS-ONLY RECHECK REQUIRED**

Review only the exact replacement candidate frozen by
`WO-0151-R13-R1-ACTIVATION-DELTA-R1-MANIFEST.md`. Do not edit candidate files,
source, tests, ADR bodies, work orders, PKL, ledger, ratification, or retained
evidence. Do not stage, commit, push, or run application tests, coverage,
runtime, database, SQL/DDL, broker, network, or CI work.

Write only `result-r13-r1-activation-r1.md` in this directory.

## Required focused checks

1. Verify every R1 manifest hash, exact branch/base, empty index, and absence
   of the future R1 reviewer result before writing it.
2. Confirm the prior result SHA-256
   `72fce061222edf684cdd2684aeebbf740c1432fbefc4df10dc6b3eb1354b2d89`
   remains retained and its sole P1 is accurately represented.
3. Confirm R1 closes that P1: R13 edits are limited exactly to `venue.py`,
   `authority.py`, `acquisition.py`, `test_acquisition.py`, and
   `test_import_boundary.py`; the authority, venue, and protection regression
   suites are execution-only; every other path requires a new exact freeze
   and review before editing.
4. Confirm the first commit remains documentation-only, and the second commit
   remains only exact publication-SHA reconciliation plus activation of those
   five edit paths. R13 implementation remains forbidden before both steps.
5. Confirm the two original format-blocked manifests remain byte-stable,
   untracked, excluded, and unnormalized; the frozen WO-0152 detector remains
   unchanged and unstaged; E3 remains ACTIVE/PAUSED.
6. Confirm the unchanged paired 93% Python 3.11/3.12 gate and all safety
   exclusions remain controlling.
7. Run manifest, whitespace, scope, ledger, PKL, and disposition checks without
   staging the candidate.

End with `BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT` and exact P0/P1/P2
counts. `ACCEPT` requires P0=0/P1=0/P2=0 and authorizes only the two-step
records-only activation sequence, not implementation by itself.
