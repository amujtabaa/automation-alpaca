# Proposed ADR-023 — bounded market-occurrence authority

Status: **PROPOSED — NOT ACCEPTED AUTHORITY**

Decision owner: human architecture authority

Precipitating review: `REV-0050/replay-retention-successor/result.md`

Rejected candidate: `488ce0e7cb954d7b1d19c2bc0127a925e069ea58`

## Context

ADR-020 requires bounded incremental market state and prohibits live work proportional to audit
history. ADR-021 requires distinct source occurrences for corroboration and makes replay, including
restart replay, an evidence no-op. The present public contract also allows source sequence to be
absent and allows distinct sequence-less occurrences to share one source time.

Those rules cannot all be implemented exactly with bounded state. For an unbounded opaque identity
domain, two long histories eventually share one bounded reducer state. A later identity can then be
new in one history and a replay or changed-payload reuse in the other. An exact aggregate-lifetime
receipt map resolves that ambiguity only by growing with history.

Candidate `488ce0e7` therefore is not acceptable. It closes the observed non-last replay defect, but
its authenticated receipt map grows once per routed occurrence. A fresh review probe grew it from
0 to 1,000 entries, contrary to ADR-020.

This decision removes the ambiguity at its source. Every protection-authoritative market stream
uses one generation-global strict coordinate: source sequence when the source has one, otherwise
source time. A distinct occurrence must strictly advance that coordinate across every market epoch.
Equal-coordinate identical content is one replay; equal-coordinate different content is an
ambiguous stream and invalidates evidence.
This is deliberately conservative for sequence-less feeds: two indistinguishable or same-time
frames can never satisfy two-occurrence corroboration.

## Decision

### 1. One fixed stream contract is bound into the mandate

`EvidencePolicy` SHALL bind all existing fields plus:

- one exact 32-byte `MarketStreamGenerationId`; and
- one exact `MarketSequenceMode`: `SEQUENCED` or `SOURCE_TIME`.

The mode cannot change inside a mandate or generation. In `SEQUENCED` mode every occurrence must
carry a source sequence. In `SOURCE_TIME` mode source sequence must be absent. A source that cannot
provide the selected retry-stable coordinate is not authoritative for protection evidence.

`MarketOccurrence` SHALL bind the stream generation in addition to its existing route, session,
epoch, coordinate, delivery context, kind, prices, optional trail inputs, and halt state. The
generation, source, scope, session, and sequence mode must exactly match the mandate before any
market state can advance.

Stream generation is not an automatic reset mechanism. A protection state never accepts a
different generation. Generation replacement requires a new, separately reviewed mandate/cutover
after the old generation is non-serving.

### 2. Occurrence identity is a canonical content commitment

`MarketOccurrenceId` SHALL be an owning-constructor-derived lowercase hexadecimal SHA-256
commitment of a
versioned, domain-separated canonical encoding of:

- source, position scope, session, and stream generation;
- market epoch;
- sequence-present marker and sequence value when present;
- source time;
- market kind, bid, ask, trade, ATR, structure, and halt fields, including absence markers.

`evaluation_time` is delivery context. It SHALL NOT enter occurrence identity. The exact
`MarketOccurrence` constructor validates its source fields and derives the identity; callers do not
supply or override it. `occurrence_id` remains a public immutable result field, but is excluded from
the constructor signature. This keeps one identity algorithm at the owning semantic boundary and
makes a changed immutable coordinate or payload produce a different identity without a second
caller-shaped truth.

The identity preimage is exact, not implementation-selected. It is `_pack_parts` with domain
`b"execution-core/market-occurrence/v1"` and, in this order, the canonical source-id text,
canonical position-scope bytes, canonical session-id text, raw 32-byte stream generation, u64
market epoch, one-byte sequence-present marker, an eight-byte sequence payload (all zero when
absent), u64 source time, canonical market-kind text, canonical encodings of best bid, best ask,
trade price, ATR distance, and structure trail, then one byte for halted. `_pack_parts` is the
existing four-byte domain-length prefix followed by the domain and an eight-byte length prefix for
each part. Text is length-prefixed UTF-8; u64 is exactly eight unsigned big-endian bytes; booleans
are exactly `0x00` or `0x01`; position scope and reported prices use their existing canonical
encoders. The constructor and commitment use one pure private preimage function; tests inspect that
same function rather than reimplementing the algorithm. Independent known-answer controls do not
use that helper. `MarketOccurrenceId` is the lowercase hexadecimal SHA-256 digest of those bytes.

In `SOURCE_TIME` mode, two frames with identical canonical source facts intentionally have one
identity and count once even if the provider emitted them twice. Two different frames with the same
source time are not ordered and do not count as two occurrences. This deterministic denial is the
accepted cost of supporting a source without sequence; no local receive time, arrival ordinal, or
adapter-generated retry counter may manufacture distinctness.

Adapter and M2 conformance must separately prove that immutable source time/sequence and payload
are normalized consistently across retry, reconnect, and restart. WO-0148 proves the pure contract
only and cannot claim source authenticity or runtime integration.

### 3. Protection retains one bounded market cursor

Protection state SHALL retain only constant-size current market data:

- mandate-owned stream generation and sequence mode, without duplicate mutable copies, plus market
  epoch;
- current generation-global source sequence when sequenced;
- current generation-global source-time and evaluation-time watermarks;
- current occurrence epoch and canonical occurrence identity;
- committed market epoch, optional expected recovery epoch, and halt/baseline-required/exhausted
  latches;
- one optional last-primary-price commitment and at most one hard-bail bid, trade, and trail-bid
  identity with its paired source time; and
- existing public price, policy, execution cursor, commitment, and provenance fields, which remain
  in the main state commitment and are not duplicated in the private market cursor.

It SHALL NOT retain an aggregate-lifetime occurrence set, a probabilistic membership structure, a
raw-feed tape, or a pointer whose live evaluation scans history.

One pure private market-cursor preimage SHALL use `_pack_parts` with domain
`b"execution-core/protection-market-cursor/v1"` and exactly these 19 parts in order:

1. raw 32-byte mandate stream generation;
2. one-byte sequence mode (`0x00` sequenced, `0x01` source-time);
3. optional current occurrence epoch;
4. optional committed epoch;
5. optional expected recovery epoch;
6. optional current source sequence;
7. optional current source-time watermark;
8. optional current evaluation-time watermark;
9. optional current occurrence identity;
10. one-byte halted latch;
11. one-byte baseline-required latch;
12. one-byte exhausted latch;
13. optional last-primary canonical reported-price commitment;
14. optional hard-bail bid identity;
15. optional hard-bail bid source time;
16. optional trade identity;
17. optional trade source time;
18. optional trail-bid identity; and
19. optional trail-bid source time.

Each optional u64 is one presence byte plus an always-present zero-filled eight-byte payload when
absent. Each optional identity or price commitment is one presence byte plus an always-present
zero-filled 32-byte payload when absent. Presence is exactly `0x00` or `0x01`; current occurrence
epoch and identity must have identical presence, as must each paired evidence identity and source
time. With the existing `_pack_parts` prefixes, the exact preimage is always 19 parts and 480 bytes.
Its SHA-256 digest is one fixed part of the main protection-state commitment. The mandate is the
sole mutable-state source of generation/mode; the
cursor does not store a second copy. The main commitment continues to bind every public economic,
policy, execution-cursor, and provenance field separately.

Within one stream generation, including across market epochs:

1. Exact constructor types and fixed-width values are validated before reduction. Construction uses
   `TypeError` for wrong exact types (including boolean-as-integer) and `ValueError` for
   out-of-range
   or noncanonical values. A reducer never receives a construction-malformed exact occurrence.
2. The market reducer first requires the exact current projection and exact route, source,
   generation, mode, scope, and session. A mismatch is state-preserving `REFUSED` and cannot reserve
   a coordinate.
3. An occurrence whose epoch, strict coordinate, and derived identity exactly match the retained
   current occurrence is `EXACT_REPLAY`; changed delivery context does not mutate state. A different
   identity at that same retained epoch and strict coordinate is a coordinate conflict. It clears
   active evidence and, if serving, enters baseline-required and returns `APPLIED` with
   `MARKET_BASELINE_REQUIRED`. If baseline-required is already latched, it is `REFUSED`; the
   retained current identity never oscillates.
4. Epoch validity is decided before any other coordinate can be reserved. While serving with
   committed epoch `C`, an epoch below `C` is `STALE`, exactly `C` is admitted, and above `C` is
   `REFUSED`. While baseline-required with expected epoch `E`, the exact-current replay/conflict
   rule
   above applies first; every other epoch below `E` is `STALE`, exactly `E` is admitted, and above
   `E` is `REFUSED`. An old or skipped/future epoch never consumes the generation-global cursor.
5. Inside the admitted epoch, a strict coordinate lower than or equal to the retained coordinate is
   `STALE` unless the exact-current replay/conflict rule above applied. A fresh distinct occurrence
   must have a greater source sequence in `SEQUENCED` mode or a greater source time in `SOURCE_TIME`
   mode. Source time remains nondecreasing in sequenced mode.
6. In `SEQUENCED` mode, a greater sequence with a lower source time consumes the greater sequence
   and derived identity, preserves the prior source-time high-water, clears active evidence, enters
   baseline-required, emits no goal, and returns `APPLIED` with `MARKET_BASELINE_REQUIRED` when that
   latch is new. A later delivery at that sequence is replay/conflict, never a corrected
   opportunity.

Every well-routed, canonical, strictly advancing occurrence commits the current market cursor
only after the epoch-admission rule and before freshness, evaluation-time, quote, tick, step,
formula, flat, or policy eligibility is evaluated. A contextually ineligible first delivery
therefore returns cursor-only `APPLIED`, grants no evidence, and cannot later be redelivered under
friendlier context. The reducer never reuses or rolls back an accepted coordinate.

### 4. Overflow, restart, reconnect, and halt require a fresh baseline

Initialization has no committed epoch or current coordinate, has expected recovery epoch zero,
sets baseline-required, and clears halted/exhausted and all active evidence. Invalidation before the
first baseline is therefore `EXACT_REPLAY`. Every transition that newly enters baseline-required
uses one rule: preserve the committed epoch and generation-global cursor; clear active evidence; set
expected recovery epoch to `committed_epoch + 1`; or enter terminal exhaustion under Section 6 when
that increment is not representable. A transition while baseline-required preserves its already
fixed expected epoch. This rule applies equally to coordinate conflict, sequenced time regression,
explicit invalidation, serving-state halt, startup, reconnect, overflow, and uncertain cache
publication.

A new pure, monotonically restrictive operation
`invalidate_position_protection_market(state, projection)` SHALL require the exact current
projection, clear active market evidence, latch baseline-required, emit no goal, and preserve
the generation-global strict cursor, source/evaluation watermarks, execution economics, mandate,
trigger, trail, and exit provenance. Unless maximum-epoch exhaustion applies under Section 6, it
fixes the expected recovery epoch at exactly committed epoch plus one. Calling it again with the
same current projection is an exact no-op. It grants no
authority and is safe for the engine to invoke on startup, reconnect, protection-market mailbox
overflow, uncertain cache publication, or another detected stream gap. While baseline-required,
every projection and market transition suppresses `ExecutionGoal` emission even when a prior exit
policy remains sticky.

Ordinary market observations remain in the bounded in-memory cache described by the accepted
target architecture. They do not require a durable inbox or an unbounded market tape. A protection
edge, trail increase, halt, invalidation, or baseline transition is persisted under the later M2
unit-of-work contract before it gains runtime authority. Startup never scans decision receipts or
market history.

Initial state and every invalidated/halted state require a baseline. The next baseline:

- uses the mandate's exact stream generation and sequence mode;
- uses epoch zero initially, otherwise the already-fixed exact recovery epoch;
- when a cursor exists, strictly advances the generation-global source coordinate beyond it, keeps
  source time nondecreasing in sequenced mode, and has evaluation time at least the retained
  evaluation watermark; initial state has no predecessor-coordinate or watermark comparison;
- is a canonical, routed, fresh, non-crossed `BEST_BID` with valid tick/coordinate data, received
  after the new subscription is established, with `halted == false`; and
- is committed before later evidence can be evaluated.

Epoch gaps, reuse, branches, or reopen without a latched baseline requirement are refused. The
baseline may update the monotone high watermark and persist a tighter trail, but it clears and does
not count toward hard-bail or trail-exit corroboration and emits no execution goal. At least two
later distinct eligible occurrences are still required where the policy requires two observations.
A valid reopen baseline skips step comparison through the invalidated/halted gap.

A favorable valid baseline may perform the ordinary `FLOOR_ONLY` to `TRAIL_ACTIVE` activation and
may tighten the high watermark/trail. It may never loosen a trigger or trail, count as hard-bail or
normal-exit evidence, create an exit policy, or emit a goal. Existing sticky exit policy remains
sticky but goal emission stays suppressed until recovery completes and later authoritative inputs
satisfy the ordinary goal rules.

While baseline-required, every canonical candidate at the expected recovery epoch whose
generation-global coordinate strictly advances first consumes that coordinate. A non-halted
candidate that is freshness-expired, crossed, tick-invalid, or evaluation-regressed, or a candidate
that is still halted, leaves the committed epoch unchanged, remains baseline-required, emits no
goal, and returns cursor-only `APPLIED`; the next candidate must advance again at the same expected
recovery epoch. Lower coordinates remain state-preserving `STALE`; an equal coordinate remains
`EXACT_REPLAY` or coordinate conflict under Section 3; constructor-invalid values fail before the
reducer and cannot mutate its cursor. A valid candidate atomically commits the recovery epoch and
clears both baseline-required and halted unless committing epoch maximum enters the terminal
exhaustion state under Section 6. Exhaustion never clears either restrictive latch.

A halt occurrence consumes its strict coordinate, latches halt and baseline-required, fixes the
next recovery epoch unless maximum exhaustion applies, clears active evidence, and emits no goal.
Only a valid baseline at that exact epoch reopens evaluation. Inside one uninterrupted process the
retained cursor rejects non-advancing buffered input, but coordinate comparison alone is
insufficient across a crash because volatile facts may be ahead of the durable checkpoint. The M2
source-authoritative recovery fence below must exclude every pre-fence observation from baseline
delivery; post-resubscription provenance remains an adapter/engine proof.

Cold restart discards or invalidates volatile market evidence before any adapter task starts. A
checkpoint is "warm exact" only when runtime proof shows the adapter was quiesced, the last
published market transition and its bounded cursor were committed atomically, and no later market
transition could have published. Otherwise the engine must obtain a source-authoritative
post-resubscription recovery fence `F` before delivering market work to the reducer. The selected
source must guarantee that `F` is at or beyond every coordinate it could have emitted before the
subscription acknowledgement. If a cursor survives, `F` must also be strictly greater than that
cursor; equality remains `EXACT_REPLAY` and cannot recover. If no cursor has ever been retained, the
initial epoch-zero baseline has no predecessor-coordinate comparison, so any canonical u64 `F`
except the exhausting maximum may be admitted. The exact fresh non-halted snapshot at admissible
`F` is delivered as the sole baseline, counts as no evidence, and every later delivered occurrence
must strictly exceed `F`.
Buffered or replayed facts at or below `F` are never delivered before that baseline and are stale
after it. A source without this fence capability leaves protection non-serving or requires a
separately reviewed generation/mandate cutover. This is adapter/engine authority for M2, not a
caller-supplied M1 baseline flag. Crash injection after every cursor-only publication and replay
across the restart boundary must prove the fence prevents prior occurrences from regaining evidence
authority. No restart path may rely on an uncommitted cache or infer the fence from local time.

### 5. Projection and market transitions are structurally separate

The public projection reducer SHALL have no market-occurrence parameter. It applies only an exact
predecessor-linked venue/execution projection and returns its economic/policy transition.

A separate market reducer SHALL accept only an already-current projection plus one exact
`MarketOccurrence`. A stale, forked, or advancing projection is refused by that entry point. An API
call therefore cannot represent “apply projection and silently ignore market input,” and no caller
is responsible for resubmitting an accepted-but-unclassified occurrence.

The existing name `reduce_position_protection` remains the projection-only entry point with a
two-argument signature. `reduce_position_protection_market` is the market-only entry point. The
invalidation operation is separate from both. All return the existing `ProtectionTransition`;
`APPLIED` means that the named transition changed state, while `EXACT_REPLAY`, `STALE`, and
`REFUSED` remain state-preserving.

Disposition and alert behavior is exact. Except for maximum exhaustion under Section 6, the first
coordinate conflict, explicit invalidation, or serving-state halt that newly latches
baseline-required returns `APPLIED` with the one-shot
`MARKET_BASELINE_REQUIRED` alert. A strictly advancing but invalid baseline candidate consumes its
cursor and returns `APPLIED` without repeating that alert. A valid non-exhausting baseline returns
`APPLIED` without an alert. Repeated invalidation of an already baseline-required state under the
exact current projection is `EXACT_REPLAY`. Exact current identity is `EXACT_REPLAY`; an old epoch or
lower strict coordinate is `STALE`; wrong route/generation/mode, unexpected future epoch,
cross-shaped call, or a different identity at the current coordinate after the latch is already set
is `REFUSED`. Constructor-invalid values raise before reduction. None of those state-preserving
outcomes emits an alert.

### 6. Coordinates are fixed-width and never wrap

Market epoch, source sequence, source time, and evaluation time are unsigned 64-bit values encoded
as exactly eight bytes. Construction and reduction refuse negative, oversized, boolean, or
otherwise noncanonical values. Occurrence identities and stream generations are exact 32-byte
values represented by canonical lowercase hexadecimal text.

No coordinate wraps, truncates, silently widens, or resets anywhere inside a stream generation.
Accepting a strict coordinate equal to u64 maximum, committing epoch maximum, or needing
`committed_epoch + 1` when the committed epoch is already maximum atomically clears active market
evidence, latches baseline-required and exhausted, clears the optional expected recovery epoch,
suppresses goals, and returns `APPLIED` with the one-shot `MARKET_COORDINATE_EXHAUSTED` alert. The
max-coordinate occurrence is not evidence and cannot emit a goal. Once exhausted, exact current
identity remains `EXACT_REPLAY`, lower/old input remains `STALE`, repeated invalidation is
`EXACT_REPLAY`, and every other market input is `REFUSED`; no transition advances the market cursor
or emits another exhaustion alert. Projection-only economics may still advance but cannot emit a
goal. Recovery requires a separately reviewed generation/mandate cutover; an epoch increment cannot
reset or reuse the strict coordinate.

## Consequences

- Live protection state and transition work are constant in market-history length.
- No new mandatory database, schema, raw-feed retention, or high-rate execution-storage dependency
  is introduced.
- Sequenced sources retain full throughput subject to their strict source sequence.
- Sequence-less sources remain usable but distinct authoritative observations must have strictly
  increasing source times. Same-time ambiguity fails closed and requires a fresh baseline.
- Immediate replay remains `EXACT_REPLAY`; older non-last replay is `STALE`. Both are complete
  evidence no-ops, including after restart.
- An exact volatile checkpoint may retain the one current cursor. Missing or uncertain cache state
  causes safe baseline recovery instead of history reconstruction.
- The canonical identity, strict-coordinate rule, split reducers, generation binding, and baseline
  operation are deliberate M1 public-contract changes requiring this ratification and a fresh
  independently accepted RED contract.

## Required acceptance evidence

Before production edits, RED controls must prove:

- the constructor-derived canonical identity changes for every immutable field but not evaluation
  time, and cannot be supplied or overwritten. At least two immutable literal known-answer fixtures
  cover present and absent optionals and compare exact preimage bytes and SHA-256 hex without using
  the production preimage helper. Negative controls alter the domain, part order, prefix widths,
  u64 endianness, presence marker, absence payload, and evaluation time one at a time;
- wrong generation/mode/route and malformed fixed-width values fail closed;
- sequenced immediate replay, non-last replay, regression, equal-sequence conflict, and advance;
- sequence-less immediate replay, non-last replay, lower time, equal-time conflict, and strict
  source-time advance;
- identical sequence-less frames count once, while two later strictly timed frames can corroborate;
- the exact route and epoch-precedence matrix rejects/stales every non-admitted epoch before cursor
  reservation, then cursor reservation precedes freshness/crossed/step/formula/flat eligibility;
- formula loss/restoration, flat/late-positive, ratchet, projection advance, halt, warm restart, and
  cold restart preserve the bounded cursor or enter baseline-required as specified;
- mailbox/startup invalidation is idempotent, grants no goal, and cannot loosen trigger or trail;
- only a non-halted exact-recovery-epoch baseline with strictly advancing generation-global
  coordinate and nonregressing source/evaluation watermarks recovers, does not count as
  corroboration, clears baseline-required and halted, and cannot emit a goal;
- initial baseline has no predecessor comparison; recovery with a retained cursor refuses fence
  equality and requires a strict advance;
- a favorable baseline may activate or tighten trailing without exit evidence or goal authority;
- maximum coordinate/epoch and increment-at-maximum enter the exact terminal exhausted state with
  one-shot alert/disposition behavior and no recovery inside the mandate;
- every invalidation, halt, baseline, replay/stale/conflict/refusal, and exhaustion path returns the
  exact disposition/alert pair specified above;
- projection-only and market-only entry points reject every cross-shaped call; and
- retained market-field/cardinality shape and the exact private market-cursor preimage field count
  and byte length are unchanged after 10 versus at least 100,000 mixed occurrences, including
  replay, conflict, contextual rejection, invalidation, baseline, halt/reopen, and branch-reset
  cycles, at low and boundary coordinates. The proof pins exactly one current identity and at most
  the three single-identity corroboration slots named above; no variable-cardinality market
  container is permitted. Independent literal absent/present known-answer fixtures pin all 19 parts,
  the exact 480-byte preimage, including current-occurrence epoch/identity pairing and both latch
  clearings, and its digest without reusing the production helper; and
- a static AST/call-graph oracle covers both market entry points and every protection-owned private
  helper they transitively call. It rejects recursion, loops, comprehensions, generator traversal,
  iteration/membership/length operations over state-derived values, variable-cardinality container
  access, history/tape/receipt helpers, and starred/dynamically sized arguments to canonical
  packers.
  Shared canonical encoders are permitted only through statically fixed argument lists. Every call
  in the protected closure must resolve statically; an indirect, dynamic, or unresolved call fails
  the oracle unless its exact symbol is allow-listed as one fixed shared canonical encoder. This
  structural oracle, plus the 10-versus-100,000 state/preimage proof, is the bounded-work measure;
  wall-clock timing and interpreter bytecode counts are not acceptance evidence.

Named mutations must weaken identity field coverage, delivery-context exclusion, exact domain/part
order/prefix width/u64 endianness/presence or absence encoding, generation/mode binding,
epoch-before-cursor precedence, strict coordinate comparison, cursor-before-context ordering,
invalidation retention, current-occurrence epoch binding, exact-next epoch recovery, strict
fence/cursor advance,
baseline latch clearing, baseline non-corroboration, baseline-only activation limits,
fixed-width/no-wrap/exhaustion validation, disposition/alert mapping, or the split entry points.
Mutants that append on replay/conflict/invalidation paths, omit a cursor-preimage component, resolve
a dynamic helper, or traverse retained history are also mandatory. Every mutant must fail for its
intended reason and restore cleanly.

The later M2/runtime gate must separately prove adapter retry/restart normalization, selected source
mode and recovery-fence capability, exact fence-at-or-beyond-prior-emission coverage,
post-resubscription baseline provenance and ordering, crash/replay safety after cursor-only
publication, mailbox-overflow delivery of invalidation before later market work, persistence of
invalidation/baseline/protection edges, startup invalidation before adapter tasks,
baseline-required goal suppression, and no market-history scan. None may be claimed by WO-0148
tests.

All existing focused/stateful, predecessor, R2, execution-core, full-repository coverage,
static/type/import/grammar/scope/governance, immutable exact-candidate review, and exact-head Python
3.11/3.12 CI gates remain mandatory.

## Rejected alternatives

1. **Aggregate-lifetime receipt map:** exact but violates ADR-020.
2. **Mandatory durable market inbox:** conflicts with the accepted bounded-cache and independently
   supervised optional-recorder architecture.
3. **Finite receipt cache with silent eviction:** makes an evicted replay fresh again.
4. **Arbitrary same-time cache capacity:** adds a tunable denial boundary when the source coordinate
   can instead define exact order.
5. **Content address alone with unrestricted equal-time distinctness:** cannot distinguish a
   legitimate second frame from altered or replayed content without another stable coordinate.
6. **Local arrival ordinal or receive time:** changes on retry/restart and can manufacture evidence.
7. **Bloom filter or rolling digest:** bounded but not exact membership authority.
8. **Caller-supplied baseline boolean:** grants recovery through caller-shaped state instead of a
   fail-closed prior latch and exact epoch transition.
9. **One-call projection plus market classification:** conflates two outcomes and can lose accepted
   market input.
10. **Persist every ordinary cursor-only observation:** removes the volatile restart gap but
    contradicts the accepted bounded in-memory current-market path. The selected runtime control is
    a source-authoritative post-resubscription fence; unsupported sources remain non-serving.

## Exact WO-0148 re-gate required by ratification

Human approval of this proposal SHALL authorize only the following architecture-record and
work-order amendments before a new RED freeze:

1. Add `docs/adr/ADR-023-bounded-market-occurrence-authority.md` as an allowed WO-0148 path and
   preserve this accepted decision there with its exact SHA-256.
2. Add one matching pre-implementation ratification entry to
   `docs/adr/ARCH-RESET-2026-07-RATIFICATION.md`, notwithstanding its current activation/closeout-
   only restriction, and reconcile the matching architecture-map/log references. No existing
   accepted ADR body or packet file is rewritten. ADR-023 supersedes only the occurrence-authority
   portions of the accepted ADR-021 paragraph at lines 120-126: how a second occurrence proves
   distinctness, aggregate retention of source-occurrence identities, and replay/restart
   classification. ADR-023's generation/mode/global-cursor rules govern both sequenced and
   source-time modes. ADR-021 remains controlling for hard-bail-before-trail ordering, sticky
   hard-bail, two distinct fresh consecutive eligible best bids or the eligible trade-plus-bid
   window, trigger/trail economics, execution guards, suspect/crossed/stale-data denial, fill truth,
   and every other protection and safety clause.
3. Amend the active WO's normative market clauses, RED contract, import/public-surface pin, and
   replay re-gate history so they point to ADR-023 and no longer freeze the superseded interface.
4. Replace the superseded public-contract pin with these exact amendments:
   `MarketStreamGenerationId`; `MarketSequenceMode(SEQUENCED, SOURCE_TIME)`;
   `ProtectionAlert(LATE_POSITIVE_AFTER_FLAT, MARKET_BASELINE_REQUIRED,
   MARKET_COORDINATE_EXHAUSTED)`;
   `EvidencePolicy(source_id, stream_generation, sequence_mode, max_age,
   corroboration_window, max_step_fraction)`; and
   `MarketOccurrence(occurrence_id[derived, init=False], source_id, stream_generation,
   position_scope, session_id, market_epoch, source_sequence, source_time, evaluation_time, kind,
   best_bid, best_ask, trade_price, atr_distance, structure_trail, halted)`.
5. Replace the exact-three-entry-point pin with exactly five public functions:
   `project_protection_venue(transition, mandate)`,
   `initialize_position_protection(mandate, projection)`,
   `reduce_position_protection(state, projection)`,
   `reduce_position_protection_market(state, projection, occurrence)`, and
   `invalidate_position_protection_market(state, projection)`. Update the already allowed
   protection, stateful, identity/authority, and import-boundary controls accordingly.

The new ADR file, this single ratification addendum, active-WO amendment, and matching existing PKL
records are the only added documentation scope. Application/test paths remain the current allowed
paths. This re-gate authorizes no implementation until its replacement RED contract receives an
independent exact-commit `ACCEPT` with zero P0/P1.

## Ratification boundary

This proposal narrows sequence-less authority and changes the public protection contract, so it
cannot authorize itself. Implementation remains barred until the human architecture authority
approves this exact proposal and exact re-gate, the work-order/ADR/PKL ratification chain records
that approval, and a fresh immutable RED contract receives independent `ACCEPT` with zero P0/P1.
