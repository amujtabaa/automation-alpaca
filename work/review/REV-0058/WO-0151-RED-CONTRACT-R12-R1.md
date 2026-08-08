# WO-0151 RED contract R12-R1 -- presence-aware stream provenance

Status: **DRAFT REPLACEMENT PRE-FLIGHT CANDIDATE -- documentation only**

R12-R1 retains the accepted R12 ownership model and corrects only its
nonconstructible absent-versus-present route premise. R12, its independent
result, and its activation-delta evidence remain immutable historical evidence;
they do not authorize R12-R1 implementation.

## 1. Unchanged boundary

No public signature, type, enum, export, authority command, venue/protection
surface, controller status field, runtime path, database path, or E3 contract
changes. `GenerationRegistry.empty()`, `GenerationRegistry.record(...)`,
`initialize_acquisition_controller(...)`, and
`begin_acquisition_generation(...)` retain their exact public signatures.
No map iterator, public stream-history reader, controller history collection,
caller ownership proof, authority-side duplicate index, migration, hydration,
or backfill is permitted.

## 2. Exact root correction

`_PersistentKeyMap` gains exactly one private internal method,
`_lookup(key) -> tuple[bool, _ValueT | None]`. It follows the same one bounded
radix path as `get()` and exposes no collection. It returns:

- `(False, None)` only if the exact key is absent; and
- `(True, value)` if the exact key has a retained node, even when `value is
  None` or has the wrong runtime type.

`get()` delegates to `_lookup()` and retains its existing `None`-on-absence
behavior for all callers. `_set()` uses the presence bit rather than `get()`
to decide duplicate insertion and missing replacement. No other map reader or
caller changes.

The existing private `GenerationRegistry` stream-route sub-index remains a
sealed, opaque, non-enumerable direct map keyed by the domain-separated exact
canonical `MarketStreamGenerationId`. Its route object is reducer-constructed
only by the existing initial-record and successor-record registry owners;
ordinary construction and subclassing refuse. The registry seal continues to
bind record-map and stream-route-map commitments, preserves the exact empty
registry identity, and uses the R12 nonempty v3 commitment domain.

`_registry_market_stream_route(registry, stream_generation)` uses `_lookup()`:
an absent key alone returns `None`; a present `None`, wrong-type, noncanonical,
key-mismatched, binding-mismatched, or otherwise malformed value raises
`ValueError`. It still proves the retained route against its direct generation
record without map enumeration.

After authenticating the retained current state, successor admission catches
only a candidate-route `ValueError` and returns its existing exact `REFUSED`
transition. A malformed current route makes controller-state authenticity false
and is invalid input; it must not be converted to `REFUSED`.

## 3. Required RED controls

All implementation controls are deterministic, pure, and local.

1. In `tests/execution_core/test_fill_position.py`, prove `_lookup()` returns
   `(False, None)` for an absent key and `(True, None)` for a present `None`
   value; prove insert/replace use the same presence distinction.
2. In `tests/execution_core/test_acquisition.py`, an authentic A -> B -> fresh
   binding reusing A's stream still refuses before authority registration,
   with exact nonmutation/no receipt/effect/claim.
3. A fresh A -> B -> C distinct-stream successor remains applied, advances one
   ordinal/head/currentness registration, and has one LIVE generation.
4. Record/economics replacement retains a retired stream route; a later fresh
   candidate reusing that stream refuses without a scan.
5. A present-`None` or forged candidate-stream route returns ordinary exact
   `REFUSED`; it is never classified as fresh. A present-`None` or forged
   current route makes state unauthentic and successor admission rejects it as
   invalid input. A value-equivalent copied sealed route remains valid.
6. Scoped mutation controls demonstrate that bypassing candidate lookup and
   dropping/polluting routes during record replacement turns their owning
   controls RED, then restores exact behavior.

The frozen WO-0152 detector remains paused and cannot be executed or changed
until R12-R1 implementation independently accepts.

## 4. Allowed paths and exclusions

R12-R1 may change only:

- `app/execution_core/fills.py`;
- `app/execution_core/acquisition.py`;
- `tests/execution_core/test_fill_position.py`;
- `tests/execution_core/test_acquisition.py`; and
- directly necessary current WO-0151/WO-0152, PKL, ledger, ratification, and
  REV-0058 evidence records.

It may not change public APIs, CI, coverage thresholds, runtime wiring,
persistence, SQL/DDL, database fixtures, credentials, broker/Alpaca/network
activity, M2, master, PRs, deletion, cleanup, force-push, rebase, or the frozen
E3 test module/evidence. If the private map primitive cannot remain internal
and bounded, stop for a new scope decision.

## 5. Gate

No R12-R1 source or test implementation begins until an exact replacement
manifest receives independent `ACCEPT` with P0=0/P1=0. That semantic preflight
is followed by a separate records-only activation-delta review, a
documentation-only activation commit, and exact-SHA reconciliation. Only then
may the four named implementation paths be changed. R12-R1 implementation
acceptance, unchanged frozen E3 re-run, and paired WO-0151/WO-0152 93%
exact-head Python 3.11/3.12 CI remain required before either work order can be
effectively closed.
