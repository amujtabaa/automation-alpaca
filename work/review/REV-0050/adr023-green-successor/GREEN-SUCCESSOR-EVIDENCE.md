# WO-0148 pre-fill lifecycle successor evidence

Evidence parent: `d3e11f31f16b55f1209f7e2b3f00a1b4056ca157`

The independent review of application candidate
`629ffaa3f9a93ce2cc44ba38197f2ed8428cc11d` returned `ACCEPT-WITH-CHANGES`,
P0=0/P1=1/P2=0. It reproduced a genuine mandate-bound pre-fill venue chain whose first canonical
BUY fill remained `HARD_BAIL` because never-exposed zero had been recorded as formula loss.

## Failure-first and root correction

The new real-transition control advances public protection state through requested BUY, dispatch
claim, unknown outcome, venue-leg discovery, review, and needs-review transitions before applying
the first canonical 4 @ 100 fill. Against the reviewed candidate it failed with positive exact
formula authority but `HARD_BAIL` instead of required `FLOOR_ONLY`.

A trial boundary that rejected every zero-quantity initialization was discarded after the complete
focused suite proved that three existing multi-scope kill/catch-up contracts legitimately require
a zero-quantity protection state before exposure.

The final correction is reducer-derived and bounded:

- `ProtectionVenueProjection` privately authenticates the current execution-fact count from the
  venue proof's exact execution checkpoint; this changes no public field or function.
- a committed internal pre-exposure provenance marks only zero quantity with zero canonical
  execution facts and carries forward only while that condition remains true;
- the first positive projection replaces pre-exposure provenance with ordinary exit genesis, so a
  valid exact-basis first fill arms `FLOOR_ONLY`;
- zero quantity with prior execution facts cannot become pre-exposure, true `FLAT` retains its
  separate provenance, and late positive after true flat remains `HARD_BAIL` with its alert.

The projection commitment domain advances to `protection-venue-projection/v2` and binds the fact
count. Existing projection single-field forgery controls automatically cover the added private
integer.

## Fresh evidence

- Critical eight-case focus covering pre-fill, post-history zero, true-flat late positive,
  multi-scope kill/catch-up, projection forgery, and predecessor continuity: **8/8 passed**.
- Complete direct/stateful/import set: **511/511 passed** in 106.2 seconds.
- `ruff check .`: pass.
- Ruff format check for both changed Python files: pass.
- `mypy app/`: pass, 86 source files.
- Import Linter: pass, 122 files / 621 dependencies / 6 contracts kept / 0 broken.
- `git diff --check`: pass.

Exact changed-file SHA-256 values before freeze:

- `app/execution_core/protection.py`:
  `67D7B0C6CE42628BF80FE0B1CF96D6755DF567DD02F976651458EFCE911F08CC`
- `tests/execution_core/test_protection.py`:
  `1CD0D97FD1B1B6C278BC5270720815B8EA3E1256DC567C9661CF9D0C7354B8F9`

No database or SQL, broker or Alpaca, network, credential, runtime wiring, persistence cutover, M2,
master merge, deletion, or cleanup activity was used. Freeze and independently review only this
successor delta before relying on it for final application acceptance.
