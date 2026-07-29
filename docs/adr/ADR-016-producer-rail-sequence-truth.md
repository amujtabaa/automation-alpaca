# ADR-016 — Producer-rail sequence truth: attribution, proof, and occupancy

- **Status:** Accepted (operator ratification, Ameen, 2026-07-28 — the
  `work/queue/R6A-CONSOLIDATION-PROGRAM.md` §1 decision block in full: D-1-c, D-2-b, D-3-c)
- **Date:** 2026-07-28
- **Deciders:** Operator (human gate); Claude seat (proposal, after REV-0045 round 3)
- **Supersedes:** the §2.6 sequence-reservation ruling of 2026-07-28 (withdrawn, not repaired)
- **Amends:** ADR-009 release semantics (two amendment bullets added 2026-07-29 — the precise
  `next_release_sequence` definition and the INV-100 enable gate) and
  `docs/spec/signal-seat/02-lifecycle.md` §2/§4. This ADR previously declared an ADR-009 amendment
  that had never been made, leaving two accepted ADRs in conflict on the merge path; found by an
  independent merge-readiness assessment, not by this seat.

> ## Delivery note — the first implementation was defective; read this before the diff
>
> The decision below is operator-ratified and unchanged. The **first** implementation
> (`c20ca47`) did not correctly realise it, and an adversarial self-audit of that commit found
> four independent P0 defects before any cross-model review. All four are fixed in WO-0141R
> (scope extended by operator ratification to both store release floors):
>
> 1. **The fold and the stores disagreed about where recovery may land.** The fold demanded
>    `next_mintable` while both stores still minted at `release-floor + 1`, so the store's own
>    recovery event was refused by the fold that gates recovery — live cleared the marker, the
>    next restart re-marked the producer, and each retry consumed another key. The human release
>    could never succeed. Both stores now call `next_release_sequence`, the same kernel rule.
> 2. **`occupied(p)` was bucketed by the PAYLOAD producer**, so a key/payload-conflicted release
>    consumed `p`'s key without entering `p`'s occupied set. Occupancy now follows the KEY via
>    `release_key_claim`, because the UNIQUE index does not read payloads.
> 3. **Occupancy leaked on the shape-refusal path.** It is now recorded once, unconditionally,
>    against a frozen prior snapshot, so no exit path can skip it.
> 4. **The cap bound the mint but not the minter's input**, so the release path could raise an
>    uncaught `ValueError`. The minter now returns a typed refusal when the domain is exhausted.
>
> **The root cause was a scoping error, not four coding slips.** WO-0141 was cut along a FILE
> boundary ("kernel now, stores later"). `contributed_epoch_sequence` is read by both stores, so
> changing what it MEANS is a store change whether or not a store file is edited. The kernel and
> the store floors are one semantic limb. That lesson is now a standing P-3 rule: **a limb is
> counted where a derived quantity is CONSUMED, not where files are edited.**
>
> One further correction, recorded because it nearly shipped: the first repair let the stores
> pass their own `proven` value, and SQLite's row-drift marker carries a value copied from the
> DURABLE ROW. That leaked a drifted row straight back into the mint and re-opened the
> never-trust-a-drifted-row property. `proven_epoch_high_water` now derives it from the log, and
> a pre-existing pin written long before this change (`test_double_heal_mints_distinct_keys`)
> independently confirmed the corrected value.

## Context

The producer-rail surface returned four consecutive independent-review BLOCKs (REV-0045
rounds 1-3 plus the round-2 addendum), carrying six P0 findings. Patching them one at a
time did not converge: each round fixed the named instances and the next round found the
same class somewhere else. The P-1 treadmill tripwire fired.

The consolidated diagnosis is that **one conflation** sits under P0-3, P0-4 and P0-6:

> The code treated *"this event proves epoch sequence N"* and *"epoch sequence N's release
> dedupe key is taken"* as the same fact.

They are different facts with different owners:

- **Proof is semantic.** It is a statement about a validated event's meaning.
- **Occupancy is syntactic.** `dedupe_key` is `UNIQUE` across the entire event log
  (`app/store/sqlite.py:423`). The instant a row lands its key is consumed, regardless of
  whether the payload was well-formed.

Expressing occupancy *through* the high-water mark is how an event the fold had refused
acquired authority over future truth. That was reported as P0-4. The operator's §2.6
ruling then made the behavior deliberate — on an argument this seat supplied, which was
locally correct (the UNIQUE key *is* consumed, so a heal there would collide) but assumed
a valid successor always exists. At `2**63-1` none does, so the human release path — the
single ratified recovery for a stuck rail — could not mint, and both stores wedged
permanently. That was reported as P0-6.

A third symptom shared the same root. Three consumers answered "whose event is this?"
differently: the in-memory floor by dedupe key, the SQLite floor by payload pre-filter,
the tolerant fold by payload. One append-only history therefore produced different release
floors in different stores, which then minted *different next keys* — the histories
themselves diverged. That was reported as P0-3.

## Decision

### 1. One attribution rule (D-1-a)

A `PRODUCER_RELEASED` event is attributable to a producer only when the producer named
inside its dedupe key and the producer named in its payload **agree**, and both equal the
producer being asked about. A disagreement is structurally invalid: the event contributes
nothing to anybody, in every consumer.

The rule lives in `contributed_epoch_sequence()` — already the single derivation source —
so all three consumers agree by construction rather than by three implementations being
kept in sync by hand.

Append-time binding validation (D-1-b) is **also** adopted, sequenced into WO-0142, so new
mismatches become unrepresentable rather than merely handled. It is defense-in-depth, not
urgent: the F-1 enumeration establishes that no production writer can mint one today
(six append-seam callers, every `event_type` domain closed and non-`PRODUCER_*`; every
`PRODUCER_*` event minted by two builders that derive the key from the same `producer_id`
they place in the payload). That enumeration is enforced by
`tests/test_wo0141_append_caller_gate.py`, so it fails the build rather than silently
expiring.

**Rejected — D-1-d, a per-producer key namespace.** A DDL migration to prevent a state no
ratified writer can mint is disproportionate, and it would invalidate every dedupe key
already written.

### 2. Only valid events prove anything (D-2-b)

The high-water mark advances **only** when the fold has accepted the event. The previous
code advanced it before the applier ran; the §2.6 ruling made that permanent. Both are
withdrawn.

Occupancy is tracked separately and unconditionally, as the syntactic fact it is:

```
high_water(p)    = max sequence PROVEN by p's accepted events            (0 if none)
occupied(p)      = { s : some event carries a well-formed producer_release
                     key bound to p at sequence s }        # valid or not
next_mintable(p) = min { s : s > high_water(p) and s ∉ occupied(p) }
```

`next_mintable` is a pure function of the log, so the fold's heal rule and the stores'
minters compute the same value without coordinating. The tolerant fold's heal must land
exactly there.

**In a fully valid history the new rule and the old `high_water + 1` rule return the same
value**, because every consumed key was consumed by an event that also proved its
sequence. They diverge only where an invalid event took a key without proving anything —
which is exactly the tolerant-startup case the rule exists for, and why the pre-existing
heal pins continued to hold unchanged.

**Rejected — D-2-c, bounded reservation.** It preserves a principle we now believe is
wrong and adds a bound to contain the damage.

### 3. The sequence domain is read-structural, write-capped (D-3-c)

`SIGNAL_EPOCH_SEQUENCE_MINT_MAX = 2**62` (`app/models.py`) caps what may be **minted**.
The fold, the release-key parser, and the durable row validator continue to read the full
SQLite signed domain. This reuses the repo's existing read-structural/write-capped rule
(ratified at WO-0140 slice 5) rather than inventing a mechanism, and it guarantees that
the domain can only be exhausted by legitimate consumption, never by one refused
event reaching the ceiling.

Capping the *reader* would retroactively invalidate an append-only log, which is why the
durable row validator at `app/store/core.py` is deliberately left uncapped.

**Rejected — D-3-b, a distinct terminal-recovery event.** It would require a new payload
shape and reopen WO-0140's ratified closed field list.

## Consequences

- No schema change, no DDL, no migration, no event payload or vocabulary change.
- `InvalidProjectionMarker.last_known_epoch_sequence` keeps its meaning (highest *proven*
  sequence) but changes value where a refused event previously contributed. Stores read
  this, so dual-store parity must be re-verified even though no adapter file changed.
- The strict fold is unaffected in behavior: with no invalid events, occupancy and proof
  coincide.
- One pin that asserted the withdrawn reservation
  (`test_release_high_water_ignores_a_forbidden_payload_sequence`) is re-derived rather
  than edited to match, and keeps its protective half — the refused event's key is still
  consumed, so recovery may not land on it.
- The R6a **merge** gate and the R6a **enable** gate are separated: `signal_seat_enabled`
  stays `false` in every environment until R6b ships the release route and cockpit
  control, because a human-gated recovery surface with no human interface would contradict
  invariant 11.

## Alternatives considered and why the cheap ones fail

*Patch the three consumers to agree.* This was rounds 1-3. Agreement enforced by review
rather than by construction regressed each time the surface was touched.

*Keep reservation, cap the domain.* Contains P0-6 without addressing why a refused event
had authority at all, and leaves the same class free to reappear anywhere else that
conflates the two facts.

## Status of the review record

This decision was authored by the seat that produced the defects it corrects, including
the withdrawn §2.6 argument. The gate-clearing verdict is Codex-owned under REV-0045; the
holdouts in `tests/_rail_reference_model.py` are **pre-registered, not independent**, and
their header says so. Agreement between a pre-registered model and the implementation
constrains specification-reading errors only — it is not evidence against a common-mode
blind spot, and must not be reported as though it were.
