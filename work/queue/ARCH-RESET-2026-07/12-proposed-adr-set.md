# Clause-level safety migration matrix

Status: **PROPOSED**. This matrix and the three exact proposed ADR files are an indivisible
clause-migration subset inside the single fifteen-numbered-document R1 ratification unit; they are
not a second or smaller approval unit. A renamed aggregate never supersedes behavior by
implication.

## Always-on authority

Every `CLAUDE.md` safety-core item remains binding:

- paper/live-shadow only;
- Alpaca Paper for beta;
- FastAPI backend truth and thin Streamlit client;
- no UI→broker path or UI-owned trading state;
- only first-occurrence canonical execution facts change position quantity: `FILL`, plus
  predecessor-linked `TRADE_CORRECT`/`TRADE_BUST` revisions of fill economics; acknowledgements
  and status never do;
- submitted/accepted does not mean filled;
- kill blocks new order intent;
- ambiguous broker outcomes quarantine and never blind-resubmit;
- invalid market data cannot drive an order;
- manual flatten/emergency behavior remains engine-mediated and audited.

Spine INV-1…INV-9 remain binding behavior, translated to the new types:

| Existing invariant | Reset expression | Disposition |
|---|---|---|
| INV-1 fills only | Raw position changes only through first-occurrence canonical economic execution facts: `FILL`, or immutable predecessor-linked `TRADE_CORRECT`/`TRADE_BUST` revisions | Preserved with correction/bust representation (`AR-04` / `PA-04`) |
| INV-2 one active spawn | Symbol-wide `may_execute` permits at most one potentially live venue attempt for the relevant exposure | Preserved and widened across mandates |
| INV-3 block on ambiguity | Submit/cancel/replace/ownership unknown blocks new attempt | Preserved |
| INV-4 no oversell/overfill | Pre-claim reduce-only cap; broker overfill applied exactly and quarantined | Preserved |
| INV-5 fill dedup | Stable broker execution-fact identity plus exact economic payload and predecessor; duplicates are no-ops and changed payloads conflict | Preserved and extended to correction/bust facts |
| INV-6 monotonic order status | Reducer legal-transition table; terminal cannot regress | Preserved |
| INV-7 reduce-only | Smaller trustworthy residual; raw broker negative remains visible | Preserved |
| INV-8 completion | Fill-derived zero plus no potentially live attempt; terminal fact may finalize without changing qty; a later correlated BUY fill exits `FLAT` into protected `HARD_BAIL`/critical handling | Preserved with explicit late-fill recovery (`AR-09` / `PA-06`) |
| INV-9 acknowledgements do not change position | Attempt/effect acknowledgements are non-fill inputs | Preserved |

## Existing ADR disposition

| Authority | Clause-level disposition |
|---|---|
| ADR-001 overfill quarantine | Preserve exact broker-authoritative fill application, negative-position visibility, quarantine, no local masking; translate order/envelope names |
| ADR-002 timeout quarantine | Preserve generation-bound deterministic identity, targeted query, query-failure-is-not-absence, no blind resubmit, blocking ambiguity, and one local effect owning multiple distinct concrete broker acceptances that resolve independently; one terminal leg cannot close the request occurrence without coverage-backed canonical `broker_effects.acceptance_set_state=CLOSED`, while a disproved closure becomes non-releasable `INVALIDATED` (`AR-02` / `PA-02`) |
| ADR-003 manual flatten | Preserve `REDUCING` allowance, ordinary `HALTED` denial, explicit audited emergency override, session/risk/single-writer route |
| ADR-004 event-log truth | Supersede universal operational event-log truth and projection rebuilding; preserve narrow immutable execution-fact and terminal-leg closure ledgers, schema versions, deterministic testing, and replay as forensic/test evidence (`AR-04`, `AR-05` / `PA-04`, `PA-05`) |
| ADR-005 API facade | Preserve thin API/facade/read boundaries |
| ADR-006 imports | Preserve adapter-only broker SDK and layer direction |
| ADR-007 typing | Preserve baseline/ratchet gate |
| ADR-008 order status/provenance | Preserve provenance, async ingestion through the single writer, legal transition table, immutable predecessor-linked fill/correction/bust handling, terminal non-regression, occurrence-level acceptance-set closure, bounded active/unresolved checkpoint legs, immutable terminal closure evidence, and tripwire tests; supersede only projector/event-log-as-live-authority mechanics |
| ADR-009 Signal Seat | Preserve untrusted-advisor principle for any future design; disable/unmount the feature in reset beta. Existing R6 implementation is not a reset dependency. Any reintroduction needs a new threat/auth/finite-audit ADR |
| ADR-010 execution envelope | Preserve immutable bounded human approval, execution-fact-only quantity, single-flight, ambiguity, kill freeze, cross-side exposure/preemption, dispositions, rate/quantity/session/data rails, and manual-flatten semantics. Protection evidence requires distinct deduplicated advancing occurrences; hard bail preserves immutable formula/inputs plus mutable armed trigger; BUY-resolution wait is orthogonal to `EXIT_NORMAL`/`HARD_BAIL`; a late BUY after `FLAT` re-enters protected critical handling (`AR-06`, `AR-07`, `AR-08`, `AR-09` / `PA-06`). Supersede the all-purpose envelope type, floor-as-minimum-limit meaning, and live event-history fold |
| ADR-012 operator release | Preserve separate capacity-capped `HUMAN_ATTESTED` fill ingestion, non-economic exact-leg terminal release, full identity/cumulative-fill parity, durable `needs_review`, contribution-only release, and no same-transition replacement. A leg release cannot by itself set occurrence-level `broker_effects.acceptance_set_state=CLOSED`; coverage and all sibling closures are independent prerequisites (`AR-02` / `PA-02`) |
| ADR-013 public ingress | Defer; no public/tailnet producer endpoint |

## Current implementation disposition

| Surface | Reset treatment |
|---|---|
| `app/store/memory.py` business behavior | Historical/reference only; not ported |
| `app/store/sqlite.py` business behavior | Historical/reference only; new unit of work contains no policy branches |
| `app/events/projectors.py` | Test/reference corpus; not live authority |
| `app/protection.py` | Port validated trigger rules selectively |
| `app/sellside/*` | Port validated pure formulas/tests selectively; remove floor-limit conflation and \(O(n^2)\) live recompute |
| `app/broker/adapter.py` | Translate validated outcome/identity contracts |
| `app/broker/alpaca_paper.py` | Conformance source; port rule-by-rule after M4 evidence |
| `app/reconciliation.py` | Scenario and accepted-safety source; not wholesale port |
| R6 branch | Frozen evidence and regression corpus; never merged into reset |

## Persistence translation pins

- `broker_effects` has no singular mutable broker-order owner. Immutable
  `venue_identity_owners` permits one effect to own multiple concrete broker legs while binding
  each broker ID through a composite parent key to one effect/generation/Paper-account/symbol/
  occurrence/client-binding/economic scope. Creating client identities are nonempty, unique within
  the generation/Paper account, and generation-bound. Occurrence-wide release additionally
  requires durable, coverage-backed `acceptance_set_state=CLOSED`; no one leg can imply it. The
  `broker_effects` closure/invalidation fields are the sole persisted acceptance authority;
  `INVALIDATED` is permanently non-releasable and the checkpoint carries no duplicate. Immutable
  `broker_effect_claims`, not decision receipts or mutable effect fields, makes
  `NEVER_DISPATCHED` impossible after claim.
- `execution_facts` persists immutable predecessor-linked `FILL`, `TRADE_CORRECT`, and
  `TRADE_BUST` facts plus `BROKER_AUTHORITATIVE` versus `HUMAN_ATTESTED` authority. Human evidence
  never receives ADR-001 overfill authority or direct correction/bust roots, and correction/bust
  never rewrites its predecessor.
- Only active/unresolved `VenueAttempt` legs, recovery status, startup phase, broker coverage, and
  request budgets remain in versioned checkpoint state. Immutable owner, execution-fact, and
  terminal-leg closure authority is checked at normal startup through indexed active-owner/current-
  head bindings; the separately measured non-serving audit verifies full ledger history. Each
  owner's ordinal chain has one root and one greatest-ordinal head, so compaction cannot erase or
  fork closure.
- Process ownership is an OS lifetime lock, and mutating claims are fenced by
  `BOOTSTRAPPING -> RECONCILING -> SERVING`. Application generation is also durable on startup,
  checkpoint, inbox, immutable claims, effects, execution facts, owners, closures, and receipts. Legacy
  cutover additionally closes every prior-generation claimed/in-flight/outcome-unknown occurrence
  through post-disable broker coverage; after the first reset effect/fact, an old build cannot
  regain broker authority without a reviewed flat/no-open-order fresh re-cutover with the same
  occurrence proof. The supervisor fence additionally binds exact Alpaca/Paper REST/stream origins,
  account, deployment, mode, and recognized credential fingerprint at startup and final claim; a
  live endpoint/credential never matches.

## RESET-PACKET-R1 review disposition cross-reference

Review label: **ADVERSARIAL PLANNING-SEAT REVIEW—NOT AN INDEPENDENT EXTERNAL AUDIT**.

These rows are part of clause-level migration, not evidence that the disposition is implemented
or that a future milestone gate has passed. Each must appear in the listed exact proposed ADR
text, have its named static counterexample dispositioned for R1, receive fresh hashes, and pass
the authorized focused adversarial planning-seat verification. A third R1 review seat is not
required. The listed roadmap gates remain future implementation evidence obligations.

| Accepted disposition | Review finding(s) addressed | Exact proposed ADR target | Roadmap gate | Named counterexample |
|---|---|---|---|---|
| `PA-02` occurrence-level `broker_effects.acceptance_set_state=CLOSED` | `AR-02` latent second acceptance | `13-proposed-adr-current-state-kernel.md` and `14-proposed-adr-protection-execution.md` | M1/M2/M4 in `06-roadmap.md` | `AR-02` row in `07-war-game.md` |
| `PA-03` cross-generation cutover/rollback fence | `AR-03` legacy restart/stale rollback | `13-proposed-adr-current-state-kernel.md` and `15-proposed-adr-reset-scope.md` | M0/M2/M3 in `06-roadmap.md` | `AR-03` row in `07-war-game.md` |
| `PA-04` immutable predecessor-linked `FILL`/`TRADE_CORRECT`/`TRADE_BUST` | `AR-04` correction/bust unrepresentable | `13-proposed-adr-current-state-kernel.md` and `14-proposed-adr-protection-execution.md` | M1/M2/M3/M4 in `06-roadmap.md` | `AR-04` row in `07-war-game.md` |
| `PA-05` bounded active/unresolved checkpoint plus immutable terminal closure ledger | `AR-05` terminal legs unbound the checkpoint | `13-proposed-adr-current-state-kernel.md` | M1/M2/M3 in `06-roadmap.md` | `AR-05` row in `07-war-game.md` |
| `PA-06` trigger dedupe/formula, orthogonal exit wait, and late-fill recovery | `AR-06`, `AR-07`, `AR-08`, and `AR-09` | `14-proposed-adr-protection-execution.md` | M1/M3/M5 in `06-roadmap.md` | `AR-06`, `AR-07`, `AR-08`, and `AR-09` rows in `07-war-game.md` |

## Exact proposed ADR texts

- [13-proposed-adr-current-state-kernel.md](13-proposed-adr-current-state-kernel.md)
- [14-proposed-adr-protection-execution.md](14-proposed-adr-protection-execution.md)
- [15-proposed-adr-reset-scope.md](15-proposed-adr-reset-scope.md)

M0 copies the three exact ADR files byte-for-byte under conflict-free canonical filenames. It
records their accepted status and hashes in a separate ratification/index edit, updates every
superseded ADR's status/backlink, and refreshes `CLAUDE.md`, `AGENTS.md`, PKL, and the architecture
overview. It does not edit a hashed packet file. Any requested content change requires new hashes
and returns to review.
