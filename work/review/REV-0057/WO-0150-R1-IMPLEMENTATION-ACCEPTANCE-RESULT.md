# WO-0150 R1 implementation acceptance result

Review target: local uncommitted six-path E1 candidate over tracked parent
`fdd99d9386994dc1910e891537fcc6cecc127434`.

## Verified manifest and scope

- Manifest SHA-256:
  `1704eb96f252b77da7a7e5ab466f3caa27ce79e7a676d89550095db04ffb8d8c`.
- `HEAD` and `origin/codex/arch-reset-2026-07-r1` both resolved to
  `fdd99d9386994dc1910e891537fcc6cecc127434`.
- No staged paths were present.
- The implementation delta comprised exactly the six manifest paths. The
  untracked manifest and acceptance request were confined to `REV-0057` review
  evidence.

| Path | Verified SHA-256 |
| --- | --- |
| `app/execution_core/__init__.py` | `43588087ee39b20c27b02f49120dbc83989b3fbdf34e86a50b89d3c41582b642` |
| `app/execution_core/identity.py` | `9699684d376fe476e867be69b1b9654a26a8814d2ea1440dabe98fa1965768ea` |
| `app/execution_core/acquisition.py` | `404ffacc3452e1a98816ce4942b1000c56e0935e89361bc955f8b9bc87f36215` |
| `app/execution_core/venue.py` | `7ae6d1b809419a64b48d5fe74ec0cc2e40713af00edaea84e14461579d1a663b` |
| `tests/execution_core/test_acquisition.py` | `fab928ab235699c483de819977aba00c69529049da4051da0444b567c42a41e6` |
| `tests/execution_core/test_import_boundary.py` | `c87e2e4b908eead7a98b07846f2caab2245a3c889f5c486cd0290977e985391c` |

## Executed evidence

- `reproduced-live`: the literal command
  `pytest -q -p no:cacheprovider tests/execution_core/test_import_boundary.py tests/execution_core/test_acquisition.py`
  could not start because `pytest` was not on this PowerShell session's
  `PATH`; no test was executed by that attempt.
- `reproduced-live`: the same interpreter-level gate was then run through the
  repository virtual environment as
  `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/execution_core/test_import_boundary.py tests/execution_core/test_acquisition.py`:
  **44 passed**.
- `reproduced-live`: `git diff --check`: exit 0 with no output. Because two
  candidate files are untracked, this Git command checks only the tracked
  portion of the delta.
- `static-reasoning`: the complete six manifest files and their diffs/changed
  semantic centers were inspected against the active work order and exact R1
  contract.

## P0 findings

None.

## P1 findings

### P1 - FR-01 controls do not independently pin the successor ordinal or all commitment validators

- Location: `tests/execution_core/test_acquisition.py:125`
- Requirement: `work/review/REV-0057/WO-0150-RED-CONTRACT-R1.md:275`
  requires literal first and successor known answers, independent variation of
  every coordinate, and refusal of invalid commitment sizes.
- Evidence (`static-reasoning`): the only successor case at lines 147-154
  changes both `successor_ordinal` and
  `predecessor_or_genesis_head_commitment`. The test asserts only that the
  result differs from the first-controller value; it has no literal successor
  expected value or successor replay assertion. An implementation that validates
  the ordinal but always encodes `_encode_int(0)` would still satisfy every
  focused assertion because the successor case also changes its predecessor.
  Separately, the invalid-commitment parameterization at lines 200-210 injects
  its bad value only into `dual_mandate_binding_commitment`, so omission of
  exact-length validation for either of the other two commitments is not
  failure-capable.
- Impact: the green gate does not prove that all six frozen identity coordinates
  participate independently in the wire identity or that all three opaque
  commitments reject malformed lengths. A collapsed ordinal or malformed
  predecessor/compatibility coordinate would violate FR-01 while this 44-case
  gate remained green.
- Resolution: add a literal successor known-answer with replay; vary ordinal
  alone while holding the other five coordinates fixed; and parameterize the
  malformed commitment controls across each of the three commitment positions.

### P1 - The output-only correlation guard skips consumers inside its owning venue module

- Location: `tests/execution_core/test_import_boundary.py:6140`
- Requirement: `work/review/REV-0057/WO-0150-RED-CONTRACT-R1.md:292`
  requires a source-level control proving that no production consumer accepts a
  `VenueAcquisitionCorrelation` as standalone authority.
- Evidence (`static-reasoning`):
  `_venue_correlation_source_violations` skips `venue.py` entirely when scanning
  production consumers. Its separate scan of `venue.py` checks only construction
  count/location, normal construction, and top-level function return annotations;
  it does not inspect parameter annotations or value use inside the owning
  module. A private function or method in `venue.py` accepting
  `VenueAcquisitionCorrelation` as an argument therefore passes this checker.
  The synthetic failure control at lines 6307-6313 places its consumer in a
  different file and does not exercise the bypass.
- Impact: the named output-only control cannot fail if the projection is turned
  into standalone authority within `venue.py`, leaving the exact boundary it is
  intended to enforce bypassable.
- Resolution: scan the owning venue tree for correlation consumers too, with
  narrow exemptions only for the declaration and the exact
  `VenueRecoveryBook.acquisition_correlation` return/construction site; add an
  in-module consumer mutant that must be rejected.

## P2 findings

None.

## Unverified gates

- Venue recovery/binding/ownership/checkpoint suites, Ruff, Mypy, scope/PKL/
  ledger/disposition checks, full suite, Python 3.11/3.12 CI, exact-head CI, and
  later closeout evidence were not run in this bounded acceptance seat.
- No database, SQL/DDL, broker, network, credentials, runtime, commit, push, or
  later-work-order action was performed.

Verdict: **ACCEPT-WITH-CHANGES**

P0: 0
P1: 2
P2: 0
Unverified: the gates listed above.
