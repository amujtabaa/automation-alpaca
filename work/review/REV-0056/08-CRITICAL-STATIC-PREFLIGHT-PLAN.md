# Critical static preflight plan — serial generation candidate

Status: **PREFLIGHT PLAN — DRAFT ONLY — NOT IMPLEMENTATION AUTHORITY**

## Review boundary

This is a text-and-static-contract review only. The reviewer must not execute application code,
tests, SQL/DDL, a database engine, broker/network/credential activity, or a Git mutation. Review
the frozen candidate documents, current accepted ADRs, domain specification, active WO-0149,
preserved REV-0053 through REV-0055 evidence, and relevant public source only as necessary to
check feasibility. Do not edit the candidate or active work order. Deposit findings only in an
independent result artifact.

The review is bounded to realistic correctness, capital safety, lifecycle, replay/crash,
concurrency/currentness, provenance, and maintainability risks. Do not invent speculative
requirements or turn a clear P2/M2 deferral into an artificial M1 blocker.

## Static war-game matrix

| Probe | Candidate result required | P0/P1 if absent or contradictory |
|---|---|---|
| A terminal -> exact flat/CLOSED -> B first fill | Fresh B normal state, sealed LIVE_FIRST_ROOT, one aggregate delta, FLOOR_ONLY, no cancel/exit self-preemption. | P1 |
| Late A fill before B first fill | Direct A route, exact economics first, B remains capacity-isolated, controller advances and enters one mixed HARD_BAIL route. | P0 if fact is lost/double-counted; P1 otherwise |
| Late A fill after B first fill | Direct A route, no B credit, stale/preempt B BUY authority, one aggregate protection authority. | P0 if two authorities/actions; P1 otherwise |
| Late A correct and late A bust | Exact A current-head predecessor route; correction/bust is not reattributed to B; one aggregate delta per canonical fact. | P0 if fact rules break; P1 otherwise |
| A -> B -> C then late A | Direct lookup to A with no predecessor/tombstone walk or history materialization; C currentness becomes stale. | P1 |
| B created but unclaimed then late A | A update atomically advances controller head; B final claim refuses; no dispatch race/duplicate cancel action. | P0 if stale BUY can dispatch; P1 otherwise |
| Existing exit/cancel/unknown at retired fact | Preserve one existing bounded wait/reconciliation route; at most one newly eligible broker-facing protective action. | P0 if duplicate execution authority; P1 otherwise |
| Successor gate under nonflat, OPEN, INVALIDATED, pending, unknown, basis/reconciliation, live exit/flatten/reservation, or executable old BUY | Admission refuses without clearing historical evidence. | P1 |
| Forged/cross-scope/duplicate/reused/forked generation or stale controller head | Direct index/currentness rejection; no fallback to current symbol/binding. | P0 if caller-shaped authority grants; P1 otherwise |
| Different normal P mandate, equal recovery compatibility | Allowed only with a distinct MarketStreamGenerationId and fresh ADR-023-compliant normal evidence state after the predecessor state is non-serving, plus the exact shared emergency commitment. | P1 |
| Different/replaced emergency compatibility or cap exceedance | The controller-lifetime compatibility commitment cannot change; no successor or no dispatch authority follows. Economics remain exact and controller becomes non-serving/reconciliation-only. | P0 if policy is fabricated; P1 otherwise |
| Restart/replay / persistence boundary | Proposed M2 atomic state identifies old-or-complete-new, never an unbound root, two LIVE generations, or a valid stale claim. | P1 |
| Boundedness | All live routes use direct indexes and bounded summaries; no audit-history collection, effects scan, owner scan, or predecessor-chain walk. | P1 |
| ADR-023 overlay | Acquisition identity does not reset/reuse market stream, cursor, or evidence; every successor has a distinct stream in a fresh state after old state is non-serving and follows the existing separate mandate/cutover rule. | P1 |

## Required disproof pass

The independent reviewer must actively try to disprove:

1. that B's first root can be told apart from A's late root without caller input;
2. that the equality of EmergencyRecoveryCompatibility genuinely preserves the minimum original
   emergency authority rather than quietly merging normal policies;
3. that A -> B -> C remains directly addressable after any number of retired generations;
4. that controller currentness reaches every create and final claim, including created-but-
   unclaimed B work;
5. that one exact fact produces one aggregate economic delta and at most one broker-facing action
   eligibility; and
6. that the selected design did not smuggle in an unbounded history collection, second controller,
   or unapproved ADR-023 market-state transfer.

## Acceptance rule

Accept only if the frozen candidate has P0=0 and P1=0 and all prior REV-0054 P1s have an exact
root-level disposition. Record P2/deferred items separately. If a P0/P1 is found, do not silently
edit this frozen candidate; create a successor candidate/review cycle or return it to human
decision. A static acceptance neither ratifies the ADRs nor authorizes application/test work.
