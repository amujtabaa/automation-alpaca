---
type: Work Order
title: "R6a-C1R — one rail sequence rule: kernel and stores together"
status: ACTIVE
ratified: "2026-07-28 (Ameen) — R6A-CONSOLIDATION-PROGRAM.md §1 decision block in full: D-1-c, D-2-b, D-3-c; one ADR-016; the D-3-c write cap included in this WO (P-3 score 4, coupled); WO-0140 and WO-0104a both stay OPEN in REVIEW; §6 two-part merge/enable gate accepted. D-1-d and D-3-b rejected."
work_order_id: WO-0141
program: work/queue/R6A-CONSOLIDATION-PROGRAM.md (WO-A of A/B/C)
remediates: "REV-0045 P0-2, P0-3, P0-4, P0-6 — kernel halves. Store halves are WO-0142 (WO-B)."
parent: WO-0104a (held in REVIEW); WO-0140 (held in REVIEW, not superseded)
branch: codex/signal-r6a-rails-store
model_tier: strong (LOCAL — event-log truth interpretation, human-gated recovery semantics)
review: "Codex-owned REV-0045 continuation. This seat implements; it does not clear its own gate. The §5 holdout obligation is discharged under ratified D-6(b) (2026-07-29) by a RECORDED REVIEWER ADOPTION of the pre-registered tests/_rail_reference_model.py — not by authorship in this WO, which cannot satisfy it, and not by silence. The file is unmodifiable by this WO either way; until adoption is recorded the item is OPEN and model/kernel agreement may not be reported as a gate."
scope_budget: "P-3 score 6 (coupled) after the 2026-07-29 scope extension: 1 state machine, 0 independent effect authorities, 1 human-gated surface, 1 truth owner, +1 core.py write cap, and **1 paired-store limb** — originally recorded as 0, which was the error behind P0-7. A limb is counted where a derived quantity is CONSUMED, not where files are edited (ratified P-3 amendment)."
scope_extension: "2026-07-29 (Ameen) — allowed paths extended to app/store/memory.py and app/store/sqlite.py, release-floor functions and mint-input clamping ONLY, after self-audit found P0-7: the fold demanded next_mintable while both stores minted at release-floor + 1, so the human release never survived a restart. The kernel and the store floors are one semantic limb."
deferred: "2026-07-29 (Ameen), program D-4 'review first': §2 items 1 and 5 (typed ProducerRailFact union, one ProducerRailMachine) and §5.2 (Hypothesis RuleBasedStateMachine) are deferred to WO-0143 until an independent verdict clears the semantic layer. Done-when #1 is scoped to the §1 rulings, which ARE delivered; the structural items are not part of this WO's completion."
filter_risk: LOW-MED
---

# WO-0141 — R6a-C1: one producer-rail kernel

> **Why this exists.** Four consecutive BLOCKs on one surface. The P-1 tripwire and the operator's
> pre-commitment route the open rail P0s to consolidation rather than a fifth patch round. The
> diagnosis is single: *a producer-rail state machine implemented three times over an ownership
> domain that does not match the global key domain.* This WO builds the machine once.

## 0. GATE — what is settled before any code

| Question | Ruling | Source |
|---|---|---|
| Whose event is a rail event? | One attribution function; for a release the key is authoritative **and** the payload must agree, or it is structurally invalid | D-1-a (ratified) |
| May a refused event move the high-water? | **No.** Only structurally valid events contribute | D-2-b (ratified); reverses and withdraws §2.6 |
| What happens at the top of the sequence domain? | Mintable sequences are capped below the readable domain; the parser still reads to `2**63-1` | D-3-c (ratified) |
| Can a production writer mint a key/payload mismatch? | **No** — six closed-domain callers, enumerated and discharged | F-1, program §0 |
| Does this WO touch stores, schema, DDL, or payloads? | **No.** One exception: the D-3-c write cap in `app/store/core.py`, pure validation, no state mutation | ratified scope |

**Anti-goal — WITHDRAWN 2026-07-29.** This WO originally declared "landing a kernel nobody calls
is acceptable here". That was the defect: a kernel the stores do not call is a kernel the stores
CONTRADICT, because they still read the same derived quantity under the old meaning. P0-7 was the
direct consequence. Both stores now call the kernel rule; WO-0142 keeps only append-time binding
validation (D-1-b) and the replay/restart assurance.

## 1. The design decision this WO turns on

The four open P0s are downstream of **one conflation**: the code treats "this event proves sequence
N" and "sequence N's dedupe key is taken" as the same fact. They are not, and separating them is
what makes D-2-b implementable without recreating P0-6.

- **Proof is semantic.** Only a structurally valid event proves a sequence. (D-2-b.)
- **Occupancy is syntactic.** A `producer_release:` key is consumed by the UNIQUE index the moment
  the row lands, *whether or not the event was valid*. Occupancy is a property of the log's key
  set, computable identically by the fold and by the minter.

The whole of the reservation problem was trying to express occupancy through the high-water mark.
That is why it granted refused events authority over truth (P0-4, then P0-6). Separated:

```
high_water(p)      = max sequence PROVEN by p's structurally valid events        (0 if none)
consumed(p)        = { s : some log event carries a well-formed producer_release
                       key bound to p at sequence s }        # valid or not
next_mintable(p)   = min { s : s > high_water(p) and s ∉ consumed(p) }
```

`next_mintable` is a **pure function of the log**, so the fold's heal rule and the store's minter
compute the same value without coordinating. The heal rule becomes `healed_sequence ==
next_mintable(producer)`, which is still exact-next in spirit — no gap-skipping — but is now total:
a successor always exists below the cap.

Openers and releases do **not** share a key namespace (`producer_quarantine:` vs
`producer_release:`, minted by the two `app/store/core.py` builders), so `consumed` is
release-keys-only. Verified, not assumed.

**D-3-c makes `next_mintable` total.** With `SIGNAL_EPOCH_SEQUENCE_MINT_MAX` strictly below the
readable `2**63-1`, headroom above any mintable high-water is guaranteed. The probe is bounded by
`|consumed(p)| + 1` and fails closed with a typed error if it would exceed the cap — a bounded
refusal, not an unbounded scan.

## 2. Contents

1. **`app/events/producer_rail.py`** — the kernel. Typed decode of existing v1 events into a
   `ProducerRailFact` union: `AttributableDebit`, `EpochOpened`, `EpochReleasedV1`. A fact is typed
   only after payload closure, actor hygiene, timestamps, counters, producer binding, canonical
   codec, and integer domain all validate. Anything else decodes to `MalformedRailEvent` carrying
   its reason — refusal is a value, not an exception, so the tolerant and strict policies differ in
   *what they do with it*, never in *how they compute it*.
2. **One attribution function** (D-1-a): `attributed_producer(event) -> Attribution`, answering
   "whose event is this?" from the event alone. Consumed by every reader. For `PRODUCER_RELEASED`
   the key producer and payload producer must agree; disagreement yields `Attribution.conflicted`,
   which contributes nothing anywhere and marks the producer.
3. **Valid-only contribution** (D-2-b) plus `consumed_release_sequences` and `next_mintable_sequence`
   as above. The minting *contract* is defined and pinned here; the store-side *implementation* is
   WO-0142.
4. **The write cap** (D-3-c): `SIGNAL_EPOCH_SEQUENCE_MINT_MAX` single-sourced in `app/models.py`,
   enforced in `producer_released_event` / `producer_quarantined_event` as pure validation. The fold
   and row validator keep reading to `2**63-1` — read-structural, write-capped, the slice-5 rule.
5. **One `ProducerRailMachine`** with explicit `strict` and `tolerant` policies over a single
   transition kernel, replacing two policies currently expressed as separate code paths that must be
   kept in sync by hand. `project_producer_rails`, `fold_producer_rail`, and
   `project_producer_rails_tolerant` become thin wrappers preserving their signatures.
6. **The F-1 enumeration as a committed structural gate** — see §4. Prose in a document is the S-3
   inert-evidence class; this converts it to a machine-consumed, failure-capable control.

## 3. Behavior this WO deliberately changes (read this before reviewing the diff)

**WO-0141 touches no store file, yet changes values the stores read.** Saying otherwise would repeat
the mistake of treating "no file changed" as "no behavior changed."

| Consumer | Before | After |
|---|---|---|
| `InvalidProjectionMarker.last_known_epoch_sequence` | max over *all* readable contributions, valid or not | max over *valid* contributions only (D-2-b) |
| tolerant heal acceptance | `prior_high_water + 1` | `next_mintable(producer)` |
| a key/payload-conflicted release | memory floor attributes it; SQLite and the fold do not | attributed to nobody, everywhere; producer marked |

Consequence: **dual-store parity pins must be re-run even though no adapter changed**, and any pin
that asserted the old marker value is a real behavior pin that must be re-derived, not edited to
match. `last_known_epoch_sequence` is retained (its meaning is unchanged: highest *proven*); a new
`next_mintable_epoch_sequence` field is added for WO-0142's minters. The marker is derived and never
persisted, so this is not a schema or payload change.

## 4. Allowed and forbidden paths

- **Allowed:** `app/events/producer_rail.py` (new), `app/events/projectors.py`, `app/models.py`
  (the one constant), `app/store/core.py` (**write-cap validation only** — no state mutation, no
  other edit), `tests/`, `docs/spec/signal-seat/`, `docs/adr/ADR-016-*`, `docs/adr/ADR-009-*`
  (release-semantics paragraph), `pkl/architecture/signal-seat.md`, `pkl/architecture/testing-model.md`.
- **Forbidden:** `app/store/memory.py`, `app/store/sqlite.py`, any DDL, any event payload field or
  vocabulary *value*, `app/api/`, `cockpit/`, every R6b surface. Reviewer-owned holdouts (§5) are
  forbidden to this WO by construction.

## 5. Assurance — designed before the implementation

Six P0s came from this surface and three more from controls this seat built. The verification is
therefore specified first, and part of it is not this seat's to write.

1. **Reviewer-owned holdouts**, authored outside this WO and unmodifiable by it (S-8):
   - a raw-fact reference model for rail state importing **no** production projector or store query;
   - a metamorphic relation — *adding a malformed event to a valid prefix may mark a producer, but
     may never change another producer's outcome, nor convert a refusal into an authorization*;
   - attribution agreement — every consumer answers "whose event is this?" identically.

   > **How this is satisfied — ratified D-6(b), 2026-07-29.** As written this obligation is not
   > satisfiable by this seat: holdouts owned by the reviewer cannot be authored by the reviewed.
   > What exists is `tests/_rail_reference_model.py`, **pre-registered** — written by this seat from
   > the ratified decision block *before* the implementation, and labelled as pre-registered in its
   > own header. That is a real but weaker property: it constrains shaping an oracle to fit the code,
   > and constrains nothing about a blind spot the seat and the model share.
   >
   > Four routes were put to the operator. **(b) is ratified: the reviewer ADOPTS the pre-registered
   > model after reading it, recorded as adoption in `result-addendum-04.md`.** Adoption is what
   > converts it from *this seat's model* into *a model an independent seat has accepted*, and it is
   > what discharges this item — not authorship by this seat, and not silence. Codex authoring its own
   > holdouts (option (a)) remains welcome and strictly stronger; (b) was chosen as the floor that
   > does not stall the round.
   >
   > **Until an adoption verdict is recorded this item is OPEN**, and agreement between the model and
   > the kernel may not be reported as a gate. See `work/review/REV-0045/request-round-4.md` §9.
2. **Hypothesis stateful testing** where the escapes actually happened: a `RuleBasedStateMachine`
   over open / close / heal / restart / append-malformed, compared against the reference model,
   covering epoch 2+, both opener triggers, cross-producer interleavings, and restart mid-sequence.
3. **Vocabulary parameterization is mandatory, non-vacuity asserted.** P0-2's surviving mutant was
   trigger-specific because the pin drove only the rate path. Every obligation touching a ratified
   vocabulary (`{rate_breach, budget_exhausted}`, release states, store kinds) is parameterized over
   the whole set. Proposed as a fourth standing rule in `pkl/architecture/testing-model.md`.
4. **The F-1 enumeration becomes a gate.** A committed structural check that (a) the set of
   production callers of `append_execution_event` is exactly the six enumerated, and (b) no
   production `PRODUCER_*` construction bypasses the two `core.py` builders. Shipped with an
   adversarial fixture that plants a seventh caller and proves the gate fires.
5. **Every control is attacked, not merely exercised** — the P1-4/5/6 lesson. A gate without a
   committed negative fixture is not failure-capable and does not count as landed.
6. **ADR-015 mutation baseline over the finished kernel**, with `MAX_SURVIVORS` lowered from the 999
   sentinel in the same change that records it.

## 6. Obligation matrix

| Obligation | strict / valid | strict / malformed | tolerant / valid | tolerant / malformed | tolerant / legacy-v1 corpus |
|---|---|---|---|---|---|
| Closed release payload | required | refuse | required | mark, no contribution | required |
| Mint/parse total inverse | required | refuse | required | refuse | required |
| Bounded read domain (`2**63-1`) | required | refuse | required | refuse | required |
| **Write cap (D-3-c)** | required | refuse at mint | required | refuse at mint | n/a (read-structural) |
| **Attribution agreement (D-1)** | required | refuse | required | mark | required |
| **Valid-only contribution (D-2)** | n/a | refuse | required | **contributes nothing** | required |
| **Occupancy ≠ proof** | required | refuse | required | key still occupied | required |
| Heal at `next_mintable` | required | refuse | required | refuse | required |
| Exact open-epoch close identity | required | refuse | required | refuse | required |
| Mid-cycle reset refused | required | refuse | required | marker retained | required |
| **Both opener triggers** | required | required | required | required | required |
| Terminal-domain behavior | required | refuse | required | refuse | n/a |

No cell is unclassified.

## 7. Done-when

1. Every §1 ruling implemented and pinned, each with a RED-first proof and a mutation certificate.
2. Both opener triggers exercised on every sequence obligation; parameterization asserted non-vacuous.
3. Holdouts present and **unmodified** by this WO, with their independence status recorded truthfully.
   Discharged under ratified **D-6(b)** by a recorded reviewer **adoption** of the pre-registered
   `tests/_rail_reference_model.py` — see §5 item 1. A decline is a finding, not a discharge; silence
   is neither, and leaves this item open.
4. The legacy v1 corpora fold to byte-identical read models before and after, **except** the three
   §3 changes, each of which is separately pinned as an intended change with its old value recorded.
5. The F-1 gate committed with its adversarial fixture.
6. Full battery green with counts and the coverage line **read from output, never the exit code**.
7. ADR-016 + the 02-lifecycle replacement rule + ADR-009 + pkl ship in the same commit as the code
   that makes them true; the enable-gate launch guard is recorded.
8. Mutation baseline recorded and `MAX_SURVIVORS` lowered.

## 8. Out of scope, stated so it cannot be quietly absorbed

Store consumption of the kernel, append-time binding validation (D-1-b), collision-aware minting
*implementation*, replay/restart parity proof, and every R6b surface. Those are WO-0142 and WO-0143.
