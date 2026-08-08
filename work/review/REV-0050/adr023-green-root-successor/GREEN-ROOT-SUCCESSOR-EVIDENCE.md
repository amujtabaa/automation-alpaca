# WO-0148 position-local pre-exposure root-successor evidence

Status: **PRE-FREEZE IMPLEMENTATION EVIDENCE — NOT ACCEPTANCE**

Review-record parent: `2982048b3247e0c9cee5c9988b77fc43cd208235`

The exact-delta review of candidate `2848b8540645dbd6c58e62dffa867e666b0c32f9`
returned `ACCEPT-WITH-CHANGES`, P0=0/P1=1. Its counterexample correctly exposed that the
candidate's documented count predicate and generic zero-quantity preservation branch disagreed,
but the proposed disposition treated an account-wide execution-registry count as MSFT exposure.
Hostile disproof showed the count advanced only because AAPL filled: MSFT still had zero roots and
had never been exposed. Making that account-global count authoritative would force MSFT's genuine
first fill into `HARD_BAIL`, contradicting ADR-021's first-fill `FLOOR_ONLY` rule.

## Root correction

- `ProtectionVenueProjection` now retains the authenticated per-position `root_count` derived
  from the proof-bound execution position, rather than account-wide seen-fact count.
- The opaque projection seal binds that position-local count under a new private v3 commitment
  domain; the existing every-field forgery control covers it.
- Pre-exposure persists only while quantity and position root count are both zero. A zero state
  after a root exists cannot regain never-exposed authority.
- `HARD_BAIL` is sticky across zero quantity and later positive correction whenever the prior
  state is not pre-exposure. Pre-exposure remains the sole first-fill exception.

This adds no public field/function, caller flag, variable history, runtime authority, persistence,
I/O, database, broker, or network surface.

## Failure-capable controls

- A real same-position fill -> bust to zero -> correction control failed against the prior policy
  guard because the correction returned `FLOOR_ONLY`; it passes with sticky `HARD_BAIL`, no
  late-flat alert, and no goal.
- A genuine two-symbol venue history proves an AAPL fill can advance the account registry while
  MSFT remains at position root count zero; MSFT stays pre-exposure and its own first fill arms
  `FLOOR_ONLY`.
- Temporarily substituting the rejected account-registry count for both projection-factory inputs
  made that cross-scope control fail (`_position_root_count` was 1 instead of 0). Restoration
  returned `protection.py` to the exact hash below and the paired controls passed 2/2.
- The stateful economics oracle now pins the same fill/bust/restore history to `HARD_BAIL` rather
  than retaining its stale `FLOOR_ONLY` expectation.

## Fresh local evidence

- Critical position-local lifecycle set: **4/4 passed**.
- Hostile lifecycle/projection-seal focus: **10/10 passed**.
- Complete protection/stateful/import contract: **513/513 passed** in 99.1 seconds.
- Complete execution core: **1,258/1,258 passed** in 308.4 seconds.
- `ruff check .`: pass; exact three-file Ruff format check: pass.
- `mypy app --no-incremental`: pass, 86 source files.
- Import Linter: pass, 122 files / 621 dependencies / 6 contracts kept / 0 broken.
- Python 3.11 grammar parse: 3/3 changed Python files passed.
- `git diff --check`: pass.

Exact pre-freeze SHA-256 values:

- `app/execution_core/protection.py`:
  `F6161F16CF7D900EA4851A06121301B14E5648BA45CC2519460DD90D292CAE9D`
- `tests/execution_core/test_protection.py`:
  `521B2BF0A9A2D2CC4B438482B0965E5A8D05576AEE300F11C113919663787DAE`
- `tests/execution_core/test_protection_stateful.py`:
  `1488E98A2DD6424892FF143916B062102AA8932ABD0514B071E28D75F28C94FC`

Freeze this exact bounded successor and obtain one fresh independent exact-delta review with zero
unresolved P0/P1. R2, full-repository coverage, closeout, push, and exact-head CI remain pending;
their existing SQLite/SQL fixtures were not run under the current explicit SQL/DDL prohibition.
No Alpaca, broker, network, credentials, runtime wiring, persistent database, M2, master merge,
deletion, or cleanup activity occurred.
