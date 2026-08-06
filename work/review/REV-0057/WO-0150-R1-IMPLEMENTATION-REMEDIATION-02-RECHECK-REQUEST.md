# WO-0150 R1 remediation-02 focused recheck request

Review only the exact six-path candidate frozen by
`WO-0150-R1-IMPLEMENTATION-REMEDIATION-02-CANDIDATE-MANIFEST.md`, SHA-256
`075033205364c3f10a1d67707f5d0505ca000c2b2e825de065edcb8ce8446dd5`,
over tracked parent `fdd99d9386994dc1910e891537fcc6cecc127434`.

The original final acceptance result is retained negative evidence and
identified two P1 control gaps. Remediation-01 was intentionally stopped
before a verdict. Remediation-02 retains its identity corrections and makes
the output-only correlation exception exact: its permitted producer is a
direct `VenueRecoveryBook.acquisition_correlation` method only; a nested
look-alike producer is a required rejected mutant.

## Focused independent task

Re-derive the active R1 requirements from the work order and
`WO-0150-RED-CONTRACT-R1.md`. Hash every manifest path, inspect the two
remediated controls and their immediate production context, and run only:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/execution_core/test_import_boundary.py tests/execution_core/test_acquisition.py
```

Determine whether the previous identity and output-only-projection P1s are now
failure-capable. Confirm the new direct-method exemption does not permit a
nested or another venue-local consumer. Do not repeat unrelated broad review.
If a new P0/P1 is directly exposed by these controls or their immediate
context, report it precisely; otherwise do not widen the review.

Do not edit application or test code, commit, push, run SQL/DDL, initialize a
database, access a broker, or activate another work order. Write findings only
to `work/review/REV-0057/WO-0150-R1-IMPLEMENTATION-REMEDIATION-02-RECHECK-RESULT.md`.
State the manifest hash, verified path hashes, exact test evidence, P0/P1/P2
counts, any unverified gates, and a verdict. `ACCEPT` requires P0=0/P1=0 and
authorizes only the existing WO-0150 closeout sequence.
