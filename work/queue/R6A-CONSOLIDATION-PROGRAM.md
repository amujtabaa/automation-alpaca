# R6a consolidation program — decision block, WO-A draft, WO-B/C outlines

- **Status:** **RATIFIED 2026-07-28 (Ameen).** Ruled: **D-1-c**, **D-2-b**, **D-3-c**; one
  **ADR-016** for the reconciled model; **WO-A includes** the D-3-c write cap in `app/store/core.py`
  (P-3 score **4**, *coupled*); **WO-0140 and WO-0104a both stay OPEN in `REVIEW`** — neither is
  superseded; **§6 two-part gate accepted** — merge gate on the five acceptance criteria, enable
  gate holding `signal_seat_enabled=false` in every environment until R6b ships the release route
  and cockpit control. D-1-d and D-3-b are rejected. The §2.6 RESERVE ruling is **withdrawn**, not
  merely suspended (`docs/spec/signal-seat/02-lifecycle.md`).
- **Execution:** WO-A is `work/active/WO-0141R-r6a-c1-rail-sequence-rule.md`.
- **D-4 — sequencing, RATIFIED 2026-07-29 (Ameen): "review first" (option b).** The structural
  consolidation — WO-0141R §2 items 1 and 5 (the typed `ProducerRailFact` union and the single
  `ProducerRailMachine`) and §5.2's Hypothesis `RuleBasedStateMachine` — is **DEFERRED** until an
  independent verdict clears the semantic layer. Rationale as put to the operator: the semantic
  layer is where all eight P0s lived and has never had a clean independent review; stacking a large
  refactor on an unreviewed baseline is how a ninth appears. Options were (a) consolidate now, then
  one review over everything, or (b) review first, then consolidate against a cleared baseline.
  **Recorded here because it was not.** The ruling was given in session and cited in
  `work/review/REV-0045/request-round-4.md` under the label "D-A", which appeared nowhere else in
  the repository — so the largest scope reduction in the delivery rested on an identifier a reviewer
  could not verify, in the very artifact asking them to approve it. Found by an independent
  merge-readiness assessment, not by this seat. Relabelled **D-4** to join the ratified sequence;
  "D-A" was a session-local name.
- **Trigger:** REV-0045 addendum-03 (`48cae49`) BLOCK, fourth consecutive on this surface. The
  P-1 tripwire and the operator pre-commitment in `CLOSEOUT-R6a-CHECKLIST.md` §0 route the open
  rail P0s to consolidation rather than a fourth patch round.
- **Author:** Claude seat (Opus 5). Prepared under the standing rule that this seat's last ad-hoc
  semantics ruling created P0-6; every option below is presented for ratification, not applied.
- **Protocol:** `.ai-os/core/18` (decision block before build), `.ai-os/core/17` (adversarial
  lenses), AUDIT-0003 as amended (S-1..S-8), the P-3 semantic scope budget.

---

## §0 — Two reachability facts that calibrate everything below

Both verified at HEAD before writing this document. They do not reduce any finding's *validity*;
they change its *urgency*, and they change what "ready to merge" can honestly mean.

**F-1 — no production ingress can create a key/payload mismatch.** `producer_released_event()`
and `producer_quarantined_event()` mint the dedupe key from the *same* `producer_id` they place in
the payload (`producer_released_event` / `producer_quarantined_event` in `app/store/core.py`),
so a mismatch is **unmintable by any ratified
writer**. No route or facade path appends a raw `ExecutionEvent` (`grep app/api app/facade` for
`append_execution_event`: no hits). The P0-3 cross-owner composition and the P0-6 terminal
reservation are therefore reachable only through (a) a direct store-API call — tests and probes —
or (b) a pre-existing or corrupted log. Malformed logs **are** in-domain: tolerant startup exists
precisely for them. This is the same classification REV-0044 addendum-01 gave R-1: *latent trap,
not live data risk.*

**F-2 — R6a's recovery path has no product route.** The four *store methods*
`release_producer`, `check_and_debit_producer_rate`, `list_producer_rails` and
`invalid_projection_markers` (`app/store/base.py:1398-1426`) have **no non-test caller** in `app/`
or `cockpit/`. *Precision note:* the identifier `invalid_projection_markers` also names a field on
the replay aggregate, and that field **is** read by the replay comparator
(`app/events/replay.py:167,208,250-253`) — so live/replay marker divergence is already detectable
by an in-app path. The *store* surfaces belong to R6b (WO-0104b, not yet drafted). What *is* live
today, when `signal_seat_enabled=true` (default `False`), is the ingest
path: `routes_signals` → `facade.ingest_signal` → `store.ingest_signal`, which debits the budget
rail, mints epoch openers, and runs the bounded verification fold. Tolerant startup runs on every
store open. **Consequence:** with the seat enabled, a producer can become marked with **no
in-product way to release it** — the browser control is R6b. That is a merge-readiness fact, not a
defect of this program, and §6 treats it as such.

---

## §1 — DECISION BLOCK (ratify before §2 is finalized)

The three open rail P0s are one question in three places: **which producer does a logged event
belong to, and what may an event the fold refuses still change?** Ruling on any one constrains the
others; the interactions are stated at the end.

### D-1 — the key-ownership domain

**Facts.** `dedupe_key TEXT UNIQUE` (`app/store/sqlite.py:423`) is globally unique across *all*
event families; the release key format `producer_release:{len}:{pid}|{len}:{seq}` embeds the
producer. Neither append path validates the embedded producer against the payload
(`sqlite.py:7919-7935`, `memory.py:5636-5650`). Three consumers then attribute differently:

| Consumer | Selects by | Effect on a key=X / payload=Y release |
|---|---|---|
| memory floor (`memory.py:352-362`) | scans all events, helper matches the **key** | attributed to **X** |
| SQLite floor (`sqlite.py:1706-1721`) | SQL pre-filter on **payload**, then helper | attributed to **nobody** |
| tolerant fold (`projectors.py:1633-1642`) | `_producer_id_from_event` (**payload**), then helper | attributed to **nobody** |

That disagreement is Codex's reproduction: victim floor memory 1 / SQLite 0, then divergent mints.

| Option | What it does | Cost / blast radius | Gated? |
|---|---|---|---|
| **D-1-a** read-side single attribution rule | One function answers "whose event is this?", used by all three consumers. For a release the key is authoritative **and** the payload must agree; disagreement ⇒ structurally invalid, contributes nothing anywhere, producer marked. | Pure; no store, schema, or payload change. Changes which logs fold ⇒ 02-lifecycle §4 amendment. | Yes — event-log-truth interpretation |
| **D-1-b** write-side binding validation | Refuse at append any `PRODUCER_*` whose key-embedded producer ≠ payload producer. | Changes what the store accepts; needs a legacy-log story (D-1-a covers it). Touches both append seams. | Yes — write-path refusal |
| **D-1-c** both, sequenced | D-1-a in the pure kernel (WO-A), D-1-b at the append seam (WO-B). | Sum of the above, split across two reviewable units. | Yes |
| **D-1-d** per-producer key namespace | Composite uniqueness or key rewrite so collisions cannot cross producers. | **DDL + migration + every existing key invalidated.** Heaviest by a wide margin. | Yes — schema/migration |

**Recommendation: D-1-c.** The read-side rule alone closes the divergence — all three consumers
agree by construction — and it lands entirely in the pure kernel with no store, schema, or payload
change, which is the tightest scope that can fix the class. The write-side check then makes new
mismatches *unrepresentable* rather than merely handled, which is the difference between detecting
S-1 and preventing it. **D-1-d is rejected**: a schema migration to prevent a state no ratified
writer can mint (F-1) is disproportionate, and it would invalidate every key already written.

**Uncertainty — DISCHARGED 2026-07-28, before WO-A was authored.** The enumeration is complete and
**F-1 is confirmed**, so D-1-b stays defense-in-depth and the A→B→C sequence stands.

The public `append_execution_event` seam has exactly **six** production callers, and the event type
each can construct is closed:

| Caller | `event_type` | Domain | PRODUCER_*? |
|---|---|---|---|
| `monitoring.py:931` | `checkpoint_type` (parameter) | bound at exactly two sites, both `*_REPAIR_CHECKPOINT` (`monitoring.py:979,3373`) | no |
| `monitoring.py:1259` | `ENVELOPE_ACTION` | literal | no |
| `monitoring.py:1341` | `ENVELOPE_ACTION` | literal | no |
| `monitoring.py:3484` | `expected_type` (local) | `{CANCELED, REJECTED}` (`monitoring.py:3479-3483`) | no |
| `reconciliation.py:515` | `VENUE_ORDER_SCOPE` | literal | no |
| `reconciliation.py:1348` | `UNKNOWN_RECONCILE_REQUIRED` | literal | no |

Every production `PRODUCER_*` event is minted by `producer_quarantined_event()` or
`producer_released_event()` (both in `app/store/core.py`), which derive the dedupe key from the
same `producer_id` they place in the payload. The store-internal sinks that append them
(`memory.py:5886,6071,6224`; `sqlite.py:8207,8385,8534`) take those minted events and no others.

**But an enumeration is a snapshot, and a snapshot is exactly the inert evidence AUDIT-0003 S-3
names.** True today, silently false the first time someone adds a seventh caller. WO-A therefore
converts this table into a committed structural gate rather than leaving it as prose — the
enumeration is only durable once it is machine-consumed and failure-capable.

### D-2 — what a refused event may reserve (reverses the suspended §2.6 ruling)

| Option | Rule | Consequence |
|---|---|---|
| **D-2-a** RESERVE *(current, suspended)* | A refused release with a canonical key still raises high-water. | Creates P0-6; grants an event the fold rejected authority over future truth. |
| **D-2-b** VALID-ONLY | Only structurally valid events contribute. Minting probes the key namespace and advances past any occupied key (bounded). | Removes the invalid-event path to a terminal high-water; adds one read on the human release path only. |
| **D-2-c** RESERVE-BUT-BOUNDED | Keep reservation, cap admissible sequences below MAX so a successor always exists. | Preserves the principle I now think is wrong, with a band-aid. |

**Recommendation: D-2-b.** My RESERVE argument was that the UNIQUE key is consumed, so a later
heal would collide — that part is true and Codex confirmed it reproduces. But the correct response
to a *possible* collision is to detect and advance, not to let a refused event move the high-water.
Reservation is exactly the "an unaccepted fact changes future truth" class this review has now
flagged twice (P0-4, then P0-6). **This reverses my own ratified ruling, and I am recommending the
reversal because the reviewer's terminal-sequence case shows the premise was incomplete.**

### D-3 — terminal-sequence recovery

Under D-2-b this stops being reachable via malformed events; it remains reachable only by a
producer *legitimately* consuming `2**63-1` epochs, which is not a practical concern but is a real
totality gap.

| Option | Rule | Assessment |
|---|---|---|
| **D-3-a** documented dead-end | Refuse and require operator intervention. | Honest but leaves a human-gated surface with no recovery. |
| **D-3-b** terminal marker | A distinct recovery form that consumes no successor. | New event shape ⇒ payload/vocabulary change ⇒ contradicts WO-0140's closed list. |
| **D-3-c** write-capped domain | Cap the *mintable* sequence below MAX; the parser continues to *read* to MAX. | Reuses the repo's existing **read-structural, write-capped** rule (slice 5, already ratified and recorded in `pkl/`). One constant in `app/models.py`, single-sourced. |

**Recommendation: D-3-c.** The repo already ratified this exact principle for the other rail caps;
applying it to the sequence domain costs one single-sourced constant and guarantees `high-water+1`
is always representable. **D-3-b is rejected** because it would reopen the closed payload list.

### How the rulings interact

- **D-2 determines whether D-3 is urgent.** Under D-2-b, no malformed event can drive high-water
  to MAX, so D-3 covers only the astronomically distant legitimate case. Under D-2-a, D-3 is
  load-bearing today.
- **D-1 determines what "valid" means in D-2.** If attribution is ambiguous, "structurally valid"
  is undefined — so D-1 must be ruled first, and D-2-b depends on it.
- **D-1-a and D-2-b together are what make the kernel implementable as one function**; splitting
  them across rounds is how this surface produced four BLOCKs.

### What each choice invalidates (ratified-text impact)

| Ratified text | Impact |
|---|---|
| WO-0140's closed `PRODUCER_RELEASED` payload | **Untouched** by every recommended option. D-3-b would have breached it — that is why it is rejected. |
| `docs/spec/signal-seat/02-lifecycle.md` §2/§4 | Amended: attribution rule (D-1), reservation reversal (D-2, already marked suspended), write cap (D-3). |
| `ADR-009` | Amendment likely for the release-semantics paragraph; to be confirmed during WO-A. |
| DDL / schema | **No change** under any recommended option. |
| Event payloads / vocabulary | **No change** under any recommended option. |

**All three rulings are event-log-truth interpretation changes and are therefore human-gated.**
I propose one **ADR-016** covering the reconciled model rather than three separate amendments.

---

## §2 — WO-A draft (contingent on §1 ratification)

**Title:** R6a-C1 — typed v1 rail facts and one pure producer-rail kernel
**Scope:** projector-side only. **No store writes, no schema, no DDL, no event payload change.**

### Scope-budget accounting (first application of P-3)

| Dimension | Count | Note |
|---|---|---|
| State machines | 1 | the producer rail |
| Independent effect authorities | 0 | pure; writes nothing |
| Human-gated surfaces | 1 | event-log-truth *interpretation* (no write path) |
| Truth owners changed | 1 | the rail fold |
| Paired-store limb | 0 | no adapter change in this WO |
| **Score** | **3** | *coupled* bucket — well under the ≥7 umbrella threshold |

**Open scope question for ratification:** D-3-c's write cap belongs in the builder
(`app/store/core.py:producer_released_event`), which is not a store *adapter* but is not the
projector either. I propose including it in WO-A as pure validation (no state mutation), which
raises the score to 4 — still *coupled*. **Ruling requested.**

### Contents

1. Typed decoding of existing v1 events into a `ProducerRailFact` union — `AttributableDebit`,
   `EpochOpened`, `EpochReleasedV1` — where a fact is typed *only after* payload closure, actor,
   timestamps, counters, producer binding, canonical codec, and integer domain all validate.
2. **One attribution function** (D-1-a), consumed by every downstream reader.
3. **Valid-only contribution** (D-2-b) with the collision-aware minting *contract* defined here and
   *implemented* in WO-B (minting is a store concern).
4. **Write-capped sequence domain** (D-3-c) as a single-sourced constant, if ratified.
5. One `ProducerRailMachine` with explicit `strict` and `tolerant` policies over a single
   transition kernel — replacing the two policies currently expressed as separate code paths.
6. An enumeration of every `append_execution_event` caller, discharging the F-1 uncertainty.

### Obligation matrix (WO-A is pure; the store axis collapses to input class)

| Obligation | strict / valid | strict / malformed | tolerant / valid | tolerant / malformed | tolerant / legacy-v1 corpus |
|---|---|---|---|---|---|
| Closed release payload | required | refuse | required | mark, no contribution | required |
| Mint/parse total inverse | required | refuse | required | refuse | required |
| Bounded sequence domain | required | refuse | required | refuse | required |
| **Attribution agreement (D-1)** | required | refuse | required | mark | required |
| **Valid-only contribution (D-2)** | n/a | refuse | required | **contributes nothing** | required |
| Exact-next heal | required | refuse | required | refuse | required |
| Exact open-epoch close identity | required | refuse | required | refuse | required |
| Mid-cycle reset refused | required | refuse | required | marker retained | required |
| **Both opener triggers** (`rate_breach` **and** `budget_exhausted`) | required | required | required | required | required |
| Terminal-domain behavior (D-3) | required | refuse | required | refuse | n/a |

No cell is unclassified. The `budget_exhausted` row exists because P0-2's surviving mutant was
trigger-specific and the round-2 pin drove only the rate path.

### Allowed / forbidden paths

- **Allowed:** `app/events/` (new `producer_rail.py` plus `projectors.py` edits), `tests/`,
  `docs/spec/signal-seat/`, `docs/adr/ADR-016-*`, `pkl/architecture/signal-seat.md`,
  and — *if ratified* — `app/store/core.py` for the write cap only.
- **Forbidden:** `app/store/memory.py`, `app/store/sqlite.py`, any DDL, any event payload or
  vocabulary value, `app/api/`, `cockpit/`, R6b surfaces.

### Done-when

1. Every §1 ruling implemented and pinned, each with a RED-first proof and a mutation certificate.
2. Both opener triggers exercised on every sequence obligation.
3. Reviewer-owned holdouts (§4) present, authored outside this WO, and **unmodified** by it.
4. The legacy v1 corpora fold identically before and after (byte-identical read models).
5. `append_execution_event` caller enumeration complete, with the F-1 conclusion confirmed or
   overturned in writing.
6. Full battery green with counts and the coverage line read from output, never the exit code.
7. Spec/ADR/pkl amendments ship in the same commit as the code that makes them true.

---

## §3 — WO-B and WO-C outlines, with explicit P0 mapping

### WO-B — paired adapters consuming one opaque plan

Both stores in **one** delivery (splitting them would recreate S-2). Stores load facts, invoke the
kernel, and persist a `RailMutationPlan` only the kernel can construct; they contain no independent
transition or recovery classification. Includes D-1-b append-time binding validation and the
collision-aware minting contract from WO-A.

- **Closes:** P0-3 (the ownership divergence, once both floors are kernel-driven), the remaining
  half of P0-4.
- **Does NOT close:** P0-2 (kernel-side, WO-A), P0-6 (WO-A's D-3 constant).
- **Scope note:** paired stores count as **one** limb, never a reason to split.

### WO-C — replay, restart, and property assurance

Replay aggregate, startup/rebuild, historic corpora, comparator completeness canaries, Hypothesis
stateful model, and the ADR-015 mutation baseline over the finished kernel.

- **Closes:** the *verification* half of every P0 — the standing proof that live, replay, restart,
  memory and SQLite agree.
- **Does NOT close:** any semantics. If WO-C finds a divergence, it routes back to A or B.

### Coverage table (nothing assumed)

| Finding | WO-A | WO-B | WO-C |
|---|---|---|---|
| P0-2 seed / trigger coverage | **closes** | — | re-proves under generation |
| P0-3 ownership domain | rule | **closes** (both adapters) | proves parity |
| P0-4 contribution ordering | **closes** (D-2) | append-side half | proves |
| P0-6 terminal sequence | **closes** (D-3) | mint side | proves |
| P1-4/5/6 assurance controls | already repaired at `20b5df7` | — | mutation baseline |

---

## §4 — Assurance design: how this refactor avoids becoming P0 #7

This surface has produced six P0s, and three more came from controls this seat built. The
verification is therefore designed **before** the implementation, and parts of it are owned by a
seat that does not implement.

1. **Reviewer-owned holdouts (S-8), unmodifiable by the implementing WO.** At minimum: (a) a
   raw-fact reference model for rail state that imports **no** production projector or store query;
   (b) a metamorphic relation — *adding a malformed event to a valid prefix may mark a producer but
   may never change another producer's outcome, nor convert a refusal into an authorization*;
   (c) attribution agreement — all consumers answer "whose event is this?" identically.
   The implementer may not amend these in the same work order; a needed change is a separate
   reviewed artifact.
2. **Hypothesis stateful testing replaces example fixtures** exactly where the escapes happened:
   epoch 2+ sequences, both opener triggers, cross-side interleavings, restart mid-sequence, and
   malformed events interleaved with valid ones. A `RuleBasedStateMachine` over
   open/close/heal/restart/append-malformed, compared against the reference model, generates the
   cells no hand-written fixture enumerated.
3. **ADR-015 mutation baseline: yes, in WO-A.** The classifier now works (`20b5df7`), and a pure
   kernel is the ideal target — small, deterministic, no IO. Establish the baseline against the new
   module and lower `MAX_SURVIVORS` from the 999 sentinel in the same change that records it. This
   is the control that would have caught P0-2 without either reviewer noticing.
4. **What P0-2's survivor implies as a standing rule.** A pin that drives one path of a ratified
   enumeration proves nothing about the others. Every obligation touching a value from a ratified
   vocabulary (opener triggers, release states, store kinds) must be **parameterized over the whole
   vocabulary**, and the parameterization asserted non-vacuous. Proposed for
   `pkl/architecture/testing-model.md` as a fourth standing rule.
5. **Adversarial fixtures for every control**, per the lesson of P1-4/5/6: each gate is attacked
   with the evasion class, not merely exercised with the violation the author imagined.

---

## §5 — Bookkeeping: WO-0140 and WO-0104a

**Recommendation: both stay OPEN in `REVIEW`; WO-A/B/C do not supersede them.**

Reasoning: `SUPERSEDED` in this repo's vocabulary means the work was replaced before delivery.
WO-0140 *delivered* — P0-1 and P0-5 are fixed, the battery is green, and its ratified decision block
still governs the payload and vocabulary the new program must respect. Marking it superseded would
discard that ratification and detach the REV-0045 packet from the work it reviewed. WO-0104a is the
parent whose R-1/R-2 gating items the program exists to close; it cannot close before them.

Consequences of keeping them open:
- No ledger rows are owed yet (a row is written at close, not at BLOCK).
- The CI hygiene ratchet stays satisfied: both are in `work/queue/` with status `REVIEW`, which is
  a live status in a live folder — legal.
- `CLOSEOUT-R6a-CHECKLIST.md` remains the executable close-out and is unchanged; it now waits on the
  program's terminal review rather than on a round-4 addendum.
- **REV-0044 addendum-01's R-1 caveat carries forward explicitly** — round-3 confirmed it is *not*
  discharged. The checklist already names it as silent-drop risk #1; that entry stands and must be
  discharged at WO-0104a's eventual close-out, not at WO-A/B/C's.

**Alternative if you prefer a clean slate:** close WO-0140 as `CLOSED` with a partial-delivery
disposition (P0-1/P0-5 fixed, remainder re-cut), and open the program against WO-0104a alone. That
costs one ledger row now and loses the direct WO-0140↔REV-0045 linkage. I recommend against it, but
it is a legitimate choice and it is yours.

---

## §6 — Define done: what "ready to merge to master" means

### Acceptance criteria for the R6a phase

1. An **ACCEPT-class REV verdict** on the consolidation program covering, by name: the §1 rulings
   as implemented; all four open P0s with per-item verdicts; the reviewer-owned holdouts as
   *independent* (not common-mode with the implementation); dual-store and live/replay/restart
   agreement; and the reviewed head SHA covering every commit in the range.
2. **All gates green**, read from output: full battery counts and coverage line; ruff; mypy;
   lint-imports; conformance oracle; scaling gate; AI-OS hygiene; format debt at exactly the ten
   disclosed files.
3. **The mutation baseline recorded** and `MAX_SURVIVORS` lowered from the sentinel.
4. **Close-out complete in one commit** per `CLOSEOUT-R6a-CHECKLIST.md`, including WO-0104a's
   disposition and the explicit discharge-or-carry of REV-0044 addendum-01's R-1 caveat.
5. **Living docs true at merge**: 02-lifecycle, ADR-009/ADR-016, pkl, threat model.

### What legitimately defers to R6b

Provider wiring, `/api/producers`, the release route, cockpit controls, sweeps, and rate settings
(WO-0104a's own OUT list). None of these block the *merge* of the store surface.

### The honest answer on whether R6a can merge alone

**Yes, it can merge — but it must not be ENABLED alone.** Per F-2, `release_producer` has no
product route: with `signal_seat_enabled=true` and no R6b, a producer that becomes marked has **no
in-product recovery path**. Merging is safe because the seat defaults to `False` and the code is
dormant; *enabling* without R6b would ship a human-gated recovery surface with no human interface,
which contradicts invariant 11 (browser-first) and the ratified claim that release is the single
human recovery.

**Therefore I propose a merge criterion in two parts, for ratification:**
- **Merge gate (R6a):** the five acceptance criteria above.
- **Enable gate (R6a+R6b):** `signal_seat_enabled` may not be turned on in any environment until
  R6b lands the release route and cockpit control. Recorded as a launch-guard obligation, not left
  to memory.

If that split is not acceptable, the alternative is to treat R6a and R6b as one deliverable and
merge neither until both are ready — which is defensible but doubles the unmerged surface and
contradicts the scope-budget rule that just came out of the S-6 cohort work.
