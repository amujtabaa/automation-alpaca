# WO-0150 R1 implementation remediation-01 candidate manifest

Status: **FROZEN LOCAL FOCUSED-RECHECK SET**

Tracked parent: `fdd99d9386994dc1910e891537fcc6cecc127434`.

This six-path local candidate remains limited to the active WO-0150 R1 allowed
application and test paths. It implements only deterministic identity wire
data, opaque inert readers, and the output-only current-book venue correlation
projection. It contains no E2 admission/currentness/registry mutation,
late-fact behavior, runtime wiring, persistence, SQL/DDL, broker, or network
behavior.

`WO-0150-R1-IMPLEMENTATION-CANDIDATE-MANIFEST.md` and its corresponding
acceptance result are retained unchanged as negative predecessor evidence. The
final acceptance of that predecessor set found two P1 test/control gaps. This
replacement changes only their owning test controls; it does not change the
four production files.

| Path | SHA-256 |
| --- | --- |
| `app/execution_core/__init__.py` | `43588087ee39b20c27b02f49120dbc83989b3fbdf34e86a50b89d3c41582b642` |
| `app/execution_core/identity.py` | `9699684d376fe476e867be69b1b9654a26a8814d2ea1440dabe98fa1965768ea` |
| `app/execution_core/acquisition.py` | `404ffacc3452e1a98816ce4942b1000c56e0935e89361bc955f8b9bc87f36215` |
| `app/execution_core/venue.py` | `7ae6d1b809419a64b48d5fe74ec0cc2e40713af00edaea84e14461579d1a663b` |
| `tests/execution_core/test_acquisition.py` | `eaf766ba01282c573d45df13990976e2bb8c0af47176c319d5d084f1ba6e5cbc` |
| `tests/execution_core/test_import_boundary.py` | `f4a4b476f19b1c927f98406c78fc53e41624c86e3d85e33d08f953af9148b226` |

## Exact P1 remediations

1. The identity control now pins a literal successor known answer and replay,
   varies the ordinal alone while holding the other five coordinates constant,
   and checks malformed values in every opaque commitment position.
2. The correlation-boundary control now scans the owning `venue.py` module as
   well as every other production module. Its only narrow exemptions are the
   direct `VenueRecoveryBook.acquisition_correlation` return annotation and
   its sole `object.__new__` allocation. An in-module method consuming the
   projection is a required rejected mutant.

## Fresh local evidence

- Focused acquisition/import gate: passed after both remediations.
- Pure venue group A (acquisition, import, recovery, binding): passed.
- Pure venue group B (ownership, checkpoint hardening, provenance hardening,
  stateful): passed.
- Ruff check and format-check over all six candidate paths: passed.
- Mypy over the four changed production modules: passed.
- Work-order scope, disposition, ledger, PKL, and `git diff --check`: passed.
- A text-only scan of the six candidate paths found only the intentional
  `sqlite3` and `sqlalchemy` denylist literals in the import-boundary test. No
  database, SQL/DDL, broker, credential, or network behavior was exercised.

## Remaining local acceptance gate

Request one focused independent recheck of only the two remediated P1 controls
against these exact hashes. An `ACCEPT` with P0=0/P1=0 is necessary before
closeout; it does not itself close WO-0150 or establish later exact-head CI.
