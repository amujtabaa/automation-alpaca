# WO-0150 R1 remediation-03 focused recheck request

Review only the exact six-path candidate frozen by
`WO-0150-R1-IMPLEMENTATION-REMEDIATION-03-CANDIDATE-MANIFEST.md`, SHA-256
`a68c5897717e0e3ee735af6a95ff768c59951338dff321aca9ab42bc662acfde`,
over tracked parent `fdd99d9386994dc1910e891537fcc6cecc127434`.

The retained remediation-02 result resolved the identity P1 but found one
output-only projection P1: a same-named nested class could satisfy the direct
producer exemption. Remediation-03 changes only the owning boundary test. It
requires the exempt owner to be the unique top-level `VenueRecoveryBook` class
and adds nested- and duplicate-class look-alike mutants.

## Focused independent task

Re-derive the relevant active R1 requirement from the work order and
`WO-0150-RED-CONTRACT-R1.md`. Hash every manifest path, inspect only this
remaining boundary-control correction and immediate venue context, and run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/execution_core/test_import_boundary.py tests/execution_core/test_acquisition.py
```

Determine whether the remaining P1 is now failure-capable and whether the
unique direct-producer exception is limited to the actual module-level class.
Do not repeat unrelated review. Report a new P0/P1 only if directly exposed by
the corrected control or immediate context.

Do not edit application or test code, commit, push, run SQL/DDL, initialize a
database, access a broker, or activate another work order. Write findings only
to `work/review/REV-0057/WO-0150-R1-IMPLEMENTATION-REMEDIATION-03-RECHECK-RESULT.md`.
State the manifest hash, verified path hashes, exact test evidence, P0/P1/P2
counts, any unverified gates, and a verdict. `ACCEPT` requires P0=0/P1=0 and
authorizes only the existing WO-0150 closeout sequence.
