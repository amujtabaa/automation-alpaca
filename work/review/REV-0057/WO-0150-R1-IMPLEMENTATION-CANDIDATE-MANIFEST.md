# WO-0150 R1 implementation candidate manifest

Status: **FROZEN LOCAL IMPLEMENTATION REVIEW SET**

Parent and exact tracked baseline: `fdd99d9386994dc1910e891537fcc6cecc127434`.
At freeze, local `HEAD` and `origin/codex/arch-reset-2026-07-r1` both resolve
to that SHA. The candidate is an intentionally uncommitted six-path delta with
no staged paths. It is limited to the active work order's R1 allowed
application/test paths; all review evidence remains under `REV-0057`.

This candidate implements only the accepted narrow E1 contract: deterministic
identity wire data, opaque inert readers, and an output-only direct venue
correlation bridge. It does not implement registry/index population, admission,
currentness, routing, late-fact mutation, runtime wiring, persistence, SQL/DDL,
broker/network behavior, or later-work-order behavior.

| Path | SHA-256 |
| --- | --- |
| `app/execution_core/__init__.py` | `43588087ee39b20c27b02f49120dbc83989b3fbdf34e86a50b89d3c41582b642` |
| `app/execution_core/identity.py` | `9699684d376fe476e867be69b1b9654a26a8814d2ea1440dabe98fa1965768ea` |
| `app/execution_core/acquisition.py` | `404ffacc3452e1a98816ce4942b1000c56e0935e89361bc955f8b9bc87f36215` |
| `app/execution_core/venue.py` | `7ae6d1b809419a64b48d5fe74ec0cc2e40713af00edaea84e14461579d1a663b` |
| `tests/execution_core/test_acquisition.py` | `fab928ab235699c483de819977aba00c69529049da4051da0444b567c42a41e6` |
| `tests/execution_core/test_import_boundary.py` | `c87e2e4b908eead7a98b07846f2caab2245a3c889f5c486cd0290977e985391c` |

## Fresh local evidence

- `pytest -q -p no:cacheprovider tests/execution_core/test_import_boundary.py tests/execution_core/test_acquisition.py`: **44 passed**.
- The direct venue recovery, binding, ownership, checkpoint-hardening,
  provenance-hardening, and stateful pure suites passed after the production
  candidate was implemented. The final static-control repair changed only the
  focused import-boundary test; its 44-case focused gate was re-run afterwards.
- Ruff format/check, Mypy over the four changed production modules,
  `git diff --check`, work-order scope, disposition, PKL, and ledger checks all
  passed after the final repair.
- A text-only database-surface scan found only denylist literals in
  `test_import_boundary.py`; no database engine, SQL/DDL, or network activity
  was invoked for this candidate.

## Review history and remaining gate

Two Terra implementation reviews found and then rechecked the same closed
static-boundary rule. The final focused recheck returned `ACCEPT` with
P0=0/P1=0/P2=0: immutable declarations, direct and builtins dynamic-execution
mutants, foreign empty-factory mutation, and legitimate local argument disposal
are all failure-capable. A narrow Sol Ultra escalation was used only after two
root-cause remediation attempts; it confirmed the final declaration,
dynamic-capability, and exact-empty-construction rule as the smallest complete
correction.

The required remaining local acceptance gate is one fresh, independent Sol
review of this exact manifest and source hashes. An `ACCEPT` is necessary but
not sufficient to close WO-0150: closeout reconciliation, commit/push, and
unchanged exact-head Python 3.11/3.12 CI remain subsequent gates.
