# WO-0150 R1 implementation remediation-02 candidate manifest

Status: **FROZEN LOCAL FOCUSED-RECHECK SET**

Tracked parent: `fdd99d9386994dc1910e891537fcc6cecc127434`.

This six-path local candidate remains limited to the active WO-0150 R1 allowed
application and test paths. It implements only deterministic identity wire
data, opaque inert readers, and the output-only current-book venue correlation
projection. It contains no E2 admission/currentness/registry mutation,
late-fact behavior, runtime wiring, persistence, SQL/DDL, broker, or network
behavior.

The original implementation candidate, its final acceptance result, and the
remediation-01 manifest/request are retained unchanged as predecessor evidence.
The remediation-01 recheck was deliberately stopped before a verdict when a
direct-method exemption edge was found in its owning AST control. This
replacement changes only `test_import_boundary.py`: the allowed producer must
now be a direct `VenueRecoveryBook` method, and a nested look-alike producer is
a required rejected mutant. The four production files and
`test_acquisition.py` remain byte-identical to remediation-01.

| Path | SHA-256 |
| --- | --- |
| `app/execution_core/__init__.py` | `43588087ee39b20c27b02f49120dbc83989b3fbdf34e86a50b89d3c41582b642` |
| `app/execution_core/identity.py` | `9699684d376fe476e867be69b1b9654a26a8814d2ea1440dabe98fa1965768ea` |
| `app/execution_core/acquisition.py` | `404ffacc3452e1a98816ce4942b1000c56e0935e89361bc955f8b9bc87f36215` |
| `app/execution_core/venue.py` | `7ae6d1b809419a64b48d5fe74ec0cc2e40713af00edaea84e14461579d1a663b` |
| `tests/execution_core/test_acquisition.py` | `eaf766ba01282c573d45df13990976e2bb8c0af47176c319d5d084f1ba6e5cbc` |
| `tests/execution_core/test_import_boundary.py` | `94d72676b5d62f148fac895f93446e56f2f5e8e934cbe85ff1033f3e9a658f5f` |

## Required focused proof

The candidate must prove all of the following without adding E2 behavior:

1. A literal successor identity and replay, ordinal-only variance, and
   malformed-value refusal in every commitment coordinate.
2. A correlation consumer is rejected in another module and inside `venue.py`.
3. Only the direct `VenueRecoveryBook.acquisition_correlation` return
   annotation and its sole allocation are exempt; a nested look-alike is
   rejected.

## Fresh local evidence

- The focused acquisition/import gate passed after this replacement.
- Pure venue group A and group B passed before the replacement; the replacement
  changes only AST inspection controls and its focused gate was rerun after the
  direct-method correction.
- Ruff check/format, Mypy, scope, disposition, ledger, PKL, and diff checks
  passed before the replacement. They must be repeated for the frozen exact
  candidate before closeout.
- No database, SQL/DDL, broker, credential, or network behavior was exercised.

## Remaining local acceptance gate

Request one focused independent recheck of the two prior P1 controls and the
new direct-method correction against these exact hashes. An `ACCEPT` with
P0=0/P1=0 is necessary before closeout; it does not itself close WO-0150 or
establish later exact-head CI.
