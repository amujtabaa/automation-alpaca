# WO-0151 R12-R1 malformed-presence remediation disposition

Status: **RE-GATE REQUIRED -- documentation only**

## Trigger

The active R12 working copy established the intended direct stream-route map,
but focused static review found a concrete malformed-entry bypass before any
R12 implementation acceptance. `_PersistentKeyMap.get(key)` returns `None`
both when a key is absent and when a retained radix node has
`has_value=True, value=None`. Its insertion/replacement path used that same
ambiguous result for presence decisions.

Consequently, a test-owned forged registry can retain a physically present
candidate-stream entry whose value is `None` while preserving its stored value
commitment. The former R12 route lookup would classify that entry as absent and
could admit the candidate as fresh. This conflicts with R12's explicit rule
that malformed present candidate routes refuse and malformed current routes
fail closed.

## Root correction

R12-R1 adds one internal, fixed-key `_PersistentKeyMap._lookup(key)` primitive
in `app/execution_core/fills.py`. It returns `(False, None)` only for an absent
key and `(True, value)` for every present radix node, including a malformed
`None` value. `get()` retains its existing public behavior by delegating to
that primitive, and `_set()` uses its presence bit for exact insert/replace
semantics.

`acquisition._registry_market_stream_route(...)` then consumes the same
presence bit: absent is the only route to `None`; present `None`, wrong-type,
or otherwise malformed route raises `ValueError`. Candidate lookup converts
that error to the ordinary exact `REFUSED` transition only after authenticating
the current state. A present malformed current route therefore remains an
invalid predecessor state, not a fabricated refusal.

This is one reusable container correctness repair, not a route-specific guard.
It introduces no export, public reader, iterator, map escape hatch, scan,
history walk, authority-side index, persistence work, or runtime surface.

## Working-copy treatment

The existing uncommitted R12 changes in `app/execution_core/acquisition.py`
and `tests/execution_core/test_acquisition.py` are preserved as unaccepted
working context only. They are not R12-R1 evidence and must not be committed,
pushed, or treated as accepted implementation until this replacement contract,
manifest, independent preflight, and a fresh records-only activation gate have
all completed.

The frozen E3 detector and evidence remain unchanged and unexecuted.

## Required R12-R1 controls

1. Map-level direct lookup distinguishes absent from present `None`, and uses
   the presence bit to reject duplicate insert / permit exact replacement.
2. An authentic A -> B controller with a present-`None` A candidate route
   returns ordinary exact `REFUSED`, with no registration, effect, claim, or
   component replacement.
3. A present-`None` current route makes controller state unauthentic and
   successor admission rejects invalid input rather than manufacturing a
   refusal.
4. The sealed route remains reducer-constructed; an immutable value-equivalent
   copy is valid, while altered stream/key/binding relations are not.
5. The existing R12 direct-lookup and replacement-retention mutation controls
   remain required and must restore their targets.

No test, runtime, database, SQL/DDL, broker, network, CI, or external command
was run to establish this disposition.
