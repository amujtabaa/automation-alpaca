---
type: Review Disposition
rev_id: REV-0025
verdict_received: BLOCK
disposition_status: REMEDIATION_DRAFTED   # Ameen's D-1/D-2 decided; all 7 findings + 2 extras applied; queued for REV-0026
reviewed_commit: 209496d3812648376920a7dacccea6664eb5def8
reviewer_model: GPT-5 Codex
next_packet: REV-0026
date: 2026-07-14
---

# Disposition — REV-0025 (ADR-009 A-1 clause 6 + A-4 re-remediation re-review)

**Verdict: BLOCK** (GPT-5 Codex, staged packet, reviewed frozen `209496d`, result `result.md`
pushed 2026-07-14, environment Python 3.12.13 / Uvicorn 0.51.0). Seven P1 findings. **No direct
A-2/A-3 regression** — those binding algorithms still hold. ADR-009 stays **Proposed**;
WO-0102..0104 stay **RE-GATED**. Unchanged from REV-0024.

## What the third-pass text DID close (credited by the reviewer)

- Lifespan-off **route work** bypass — the fail-closed ASGI request guard does stop route
  processing under `--lifespan off`.
- Dead-on-arrival `SIGNAL_EXPIRED` now debits the budget; lifecycle events carry record identity;
  the release resets the §1a budget; WO-0102's ordinary route tests are runnable via the sanctioned
  fake-rails/sentinel fixture; reads-included enforcement, interim-ceiling withdrawal, and the DOA
  normative-debit all landed.

**But** F-001 and F-004 still are not closed as their **binding invariants** are written, and the
propagation is still internally contradictory. The block resolves along a clean seam again.

## The two genuine human decisions (nothing done yet — yours to decide)

### D-1 (F-001) — proxy-private bind vs. reachable-503. **The central decision.**
My request-guard fix stops *route work* but leaves the forbidden listener **reachable**: under
`uvicorn app.main:app --host 0.0.0.0 --lifespan off`, the reviewer live-reproduced a TCP accept +
`HTTP/1.1 503` on the non-loopback port. That contradicts A-1's binding invariant ("the backend
listener itself stays loopback/UDS; a non-loopback bind fails **before serving**; a same-network
client can never hit the plain-HTTP port"). A 503 is not a proxy-private bind — the socket/parser/
connection surface is still reachable outside the TLS proxy. Two ways to resolve, and this needs you:

- **D-1a — restore the invariant (recommended):** refuse enabled *unsanctioned app construction/
  import* before Uvicorn can open an accepting listener. The sanctioned launcher mints an opaque,
  one-shot, code-owned capability **before** importing the app (or uses a separate factory module);
  no env switch, importable pre-authorized `app`, or zero-arg authorized factory may mint it. So a
  bare `uvicorn app.main:app` fails at import → **no listener** → true pre-serve failure. Keep the
  503 request guard as defense-in-depth. Stronger, faithful to your original F-001 decision; costs a
  module-construction refactor (removes the importable module-level `app` under the flag).
- **D-1b — accept the weaker posture:** explicitly decide that "reachable, but every request 503 +
  no route work" is acceptable, and I reconcile every ADR/spec/request statement that currently
  promises the stronger proxy-private/pre-serve guarantee down to that weaker one. Less work, but
  knowingly weakens the transport boundary you set.

### D-2 (F-005) — how is WO-0103's conversion capability enforced at enablement?
The all-three-WO enablement gate is currently declared in prose, but the only *runtime* startup
check is rails-presence (WO-0104). The reviewer notes a Protocol-presence check can't tell full
enforcement from a permissive no-op fake, and asks whether the WO-0103 half is:
- **D-2a — a release/deployment gate (process):** sequencing dependency + a joint mounted-app test
  proving ingest → operator approval → exactly one atomically linked intent; production entrypoint
  proven to wire the real rails provider; fakes confined to test-only construction. No new startup
  check. (Lighter; the guarantee is process + test, not runtime-structural.)
- **D-2b — a runtime-structural conversion-capability startup check** (the reviewer says this needs
  explicit human approval, as it adds a new human-gated startup surface).

## Mechanical / spec-completeness fixes (clear direction, no fork — I apply once you've decided D-1/D-2)

- **F-002** — make the launcher subprocess proof **mutation-sensitive**: assert the exact
  A-1-specific failure reason (not generic pre-serve failure, which another required guard could
  supply), add a same-config sanctioned-loopback **positive control** that reaches a ready listener.
  Couples to D-1's resolution.
- **F-003** — the invalid-budget ceiling is **not linearizable/crash-atomic** as written: with one
  slot left, concurrent step-2 admissions can all append at step 4 (exceed cap); a slow-streamed
  body admitted at cadence completes as invalid after exhaustion without revisiting step 2. Fix:
  specify a linearizable admission/reservation/recheck; the budget debit + terminal event + epoch
  transition share **one lock/transaction**; add dual-store delayed-body-concurrency, final-slot-
  race, duplicate epoch-open/release, and crash-injection tests. Pin the opener to exactly one
  event/status.
- **F-004** — persist **consumed/remaining** budget (not just the pinned limit) as one durable
  producer-rail state, restored **before serving**, updated atomically with each terminal append;
  specify how replay learns the historical limit. (Else: pin limit=50, consume 49, restart used=0 →
  fresh budget without release — violates reset-only-on-human-release.)
- **F-005 (mechanical parts)** — "**lift the guard**" must mean *satisfy a permanent guard*, not
  delete it; the route matrix must assert **required routes exist**, not merely classify mounted
  ones; confine fake rails + synthetic launch auth to test-only construction production config can't
  select; add the joint conversion oracle.
- **F-006** — carry the **one-write epoch-opener carve-out** through every normative-order/WO
  statement (WO-0102 still says steps 1-2 write **zero** events, omitting it); reserve "write-free"
  strictly for post-opener rejects (kills the §4 line-45-vs-47 "write-free"↔`PRODUCER_QUARANTINED`
  contradiction); narrow every "constant/bounded total storage" claim to **attributable-terminal-at-
  ingest** traffic between releases, explicitly retaining the accepted Option-E scope (valid accepted
  traffic is only rate-bounded over indefinite time).
- **F-007** (beyond the narrow re-remediation, but real) — the §1a fail-closed matrix omits the
  mounted mutating route `POST /api/session/close` (expires candidates, cancels CREATED orders,
  snapshots positions, closes the session). Add it explicitly as **operator-only**, all four
  credential cases.

### Additional mechanical items from the concurrent per-push auto-review of the result commit (fold into the same batch)
These arrived as inline advisory comments on `64c6adf` — subsumed by the formal verdict; the first is
literally F-003, the other two are new-but-mechanical, captured here so they land in the REV-0026 batch:
- (dup of F-003) linearizable last-slot debit under concurrency/slow-body.
- **Replay-vs-quarantine dedupe (03-rails:104):** the pre-body rails check now runs before the
  `(producer_id, signal_id, payload_hash)` dedupe path, so a quarantined/over-limit producer's
  **identical** replay is rejected 403/429 — contradicting `01-schema.md §3`'s "identical replay →
  200, no event, in every status." Fix: make boundary rejection explicitly take precedence over
  idempotent replay (and update the dedupe contract/tests), or define a flood-safe replay carve-out.
- **`SIGNAL_APPROVED` record_id (02-lifecycle:97):** my new "every per-record transition carries
  `record_id`" replay rule isn't reflected in the `SIGNAL_APPROVED` payload row (still lists only
  `producer_id`/`signal_id` + conversion fields). Add `record_id` there for consistency.

## What is NOT being done in this disposition (explicit)

- ADR-009 stays **Proposed** (not accepted). WO-0102..0104 stay **RE-GATED** (not unfrozen).
- No inline PR auto-review comments patched — the staged `result.md` is the authority.
- No remediation applied yet — D-1 and D-2 are yours to decide; the mechanical fixes land in one
  batch alongside your decisions (not per-finding reactive pushes).

## Human decisions (Ameen, 2026-07-14) and the remediation applied

- **D-1 → restore proxy-private (F-001).** The bind guarantee moves to **app construction/import**:
  the sanctioned launcher mints an opaque one-shot code-owned capability (not env/config/importable)
  before importing the app; with the flag on, building the app without it **raises**, so bare
  `uvicorn app.main:app` fails at import → **no listener** (connection refused, true pre-serve
  failure). The 503 request guard is retained only as defense-in-depth. (ADR A-1 clause 6, 04-auth §1,
  WO-0102.)
- **D-2 → release/deployment gate + test (F-005).** The WO-0103 conversion half is a binding
  sequencing/deployment gate + a joint mounted-app conversion oracle (ingest → approval → exactly one
  atomically-linked intent), **not** a new runtime startup check. The rails-presence guard is
  **permanent and satisfied** (never deleted); production is proven to wire the real provider; fakes
  are test-only construction production can't select. (ADR A-4, 03-rails §2, WO-0102/0103/0104.)

### Remediation change set (applied 2026-07-14, PROPOSED — pending REV-0026)
All seven findings + the two extra inline items landed in one batch:
- **F-001/F-002** — construction-time capability refusal (no listener without the launcher);
  mutation-sensitive subprocess proof (all unrelated preconditions set, exact A-1 failure reason,
  same-config loopback positive control, socket-level connection-refused).
- **F-003** — the check-reserve-debit is atomic with the terminal append (one lock/txn); step-2 pass
  doesn't pre-grant a slot; concurrency/slow-body/crash tests.
- **F-004** — pinned limit AND consumed/remaining count are durable rail state, restored before
  serving, replay-reconstructable; restart can't zero consumed.
- **F-005** — permanent guard satisfied-not-deleted; production wires real provider; joint conversion
  oracle; matrix asserts required routes exist.
- **F-006** — one-write epoch-opener carve-out carried through WO-0102 (no blanket "zero writes");
  "write-free" reserved for post-opener rejects; storage claims narrowed to attributable-rejection
  traffic (accepted signals rate-bounded, not globally finite).
- **F-007** — `POST /api/session/close` added to the §1a matrix as operator-only.
- **Extras** — boundary rejection precedes idempotent replay (01-schema §3); `SIGNAL_APPROVED`
  carries `record_id`.

## Path to clearing the gate — SUPERSEDED (spec locked; ADR-009 accepted)

**UPDATE 2026-07-14:** REV-0026 was staged but then **WITHDRAWN** — rather than run a fifth spec-only
round, Ameen **LOCKED the spec** (the remaining items were implementation-semantic, decided as
WO-time contracts) and **ACCEPTED ADR-009**, unfreezing WO-0102..0104. So the gate did **not** clear
via a REV-0026 verdict; it cleared by the human lock+accept decision after the REV-0022/0024/0025
review record. Do **not** wait on a REV-0026 packet — it does not exist as a live review. See
`docs/adr/ADR-009-signal-seat-boundary.md` Status, the `SIGNAL-SEAT-SPEC-LOCK` and `ADR-009-ACCEPTED`
ledger entries, and `work/review/REV-0026/request.md` (status WITHDRAWN).

(Original, now historical: "REV-0026 re-reviews this batch; the gate clears only on an ACCEPT /
ACCEPT-WITH-CHANGES disposition of REV-0026.")
