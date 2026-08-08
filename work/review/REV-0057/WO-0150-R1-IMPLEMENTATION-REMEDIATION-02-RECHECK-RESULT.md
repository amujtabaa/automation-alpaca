# WO-0150 R1 implementation remediation-02 focused recheck result

Review target: the exact six-path local candidate frozen by
`WO-0150-R1-IMPLEMENTATION-REMEDIATION-02-CANDIDATE-MANIFEST.md` over tracked
parent `fdd99d9386994dc1910e891537fcc6cecc127434`.

## Verified manifest and path hashes

- Manifest SHA-256:
  `075033205364c3f10a1d67707f5d0505ca000c2b2e825de065edcb8ce8446dd5`.
- `HEAD` resolved to the stated tracked parent.

| Path | Verified SHA-256 |
| --- | --- |
| `app/execution_core/__init__.py` | `43588087ee39b20c27b02f49120dbc83989b3fbdf34e86a50b89d3c41582b642` |
| `app/execution_core/identity.py` | `9699684d376fe476e867be69b1b9654a26a8814d2ea1440dabe98fa1965768ea` |
| `app/execution_core/acquisition.py` | `404ffacc3452e1a98816ce4942b1000c56e0935e89361bc955f8b9bc87f36215` |
| `app/execution_core/venue.py` | `7ae6d1b809419a64b48d5fe74ec0cc2e40713af00edaea84e14461579d1a663b` |
| `tests/execution_core/test_acquisition.py` | `eaf766ba01282c573d45df13990976e2bb8c0af47176c319d5d084f1ba6e5cbc` |
| `tests/execution_core/test_import_boundary.py` | `94d72676b5d62f148fac895f93446e56f2f5e8e934cbe85ff1033f3e9a658f5f` |

## Exact focused evidence

- `reproduced-live`:
  `.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider tests/execution_core/test_import_boundary.py tests/execution_core/test_acquisition.py`
  exited 0. Pytest emitted 52 progress dots and `[100%]` under the current quiet
  configuration.
- `static-reasoning`: the prior identity-control P1 is resolved. The control now
  pins a literal successor value and replay, varies the ordinal alone while the
  other coordinates remain fixed, and applies malformed type/length cases to
  each of the three commitment coordinates.

## P0 findings

None.

## P1 findings

### P1 - The direct-producer exemption still accepts a same-named nested class

- Location: `tests/execution_core/test_import_boundary.py:6099`
- Requirement: `WO-0150-RED-CONTRACT-R1.md` requires the query to be the sole
  production construction site and no production consumer to accept the
  projection as authority; the remediation-02 request narrows the exemption to
  the direct `VenueRecoveryBook.acquisition_correlation` method and requires a
  nested look-alike to be rejected.
- Evidence (`static-reasoning`): `_is_exact_venue_correlation_producer` finds the
  nearest enclosing `ast.ClassDef`, checks only that its name is
  `VenueRecoveryBook`, and checks that the function is directly parented by that
  class. It does not require that class node to be the unique top-level
  production `VenueRecoveryBook`. The included nested-function mutant is
  rejected because its direct parent is another function, but a nested class
  also named `VenueRecoveryBook` with a directly declared
  `acquisition_correlation` method and the correlation return annotation meets
  every exemption predicate. Its annotation references are then exempted too,
  so this source checker can return no violation for that nested look-alike.
- Impact: the focused control does not prove that the exemption belongs only to
  the actual production class; the requested nested-look-alike failure pin
  remains bypassable even though the focused suite is green.
- Resolution: bind the exemption to the unique top-level `VenueRecoveryBook`
  class node (at minimum require its parent to be `ast.Module`, with uniqueness
  checked) and add a same-named nested-class mutant that must produce a
  violation.

## P2 findings

None.

## Unverified gates

- The venue recovery/binding/ownership suites, Ruff, Mypy, scope, disposition,
  ledger, PKL, diff, full-suite, Python 3.11/3.12 CI, exact-head CI, and WO-0150
  closeout gates were not run in this explicitly focused seat.
- No database, SQL/DDL, broker, network, credentials, runtime, commit, push,
  cleanup, deletion, or later-work-order action was performed.

Verdict: **ACCEPT-WITH-CHANGES**

P0: 0
P1: 1
P2: 0
Unverified: the gates listed above.
