---
type: Review Result
rev_id: REV-0025
reviewer_model: GPT-5 Codex
reasoning_effort: Highest-scrutiny adversarial review available in this session; independent launch, rails, and propagation subreviews reconciled by the primary reviewer
environment: Windows PowerShell; Python 3.12.13; Uvicorn 0.51.0
reviewed_commit: 209496d3812648376920a7dacccea6664eb5def8
date: 2026-07-14
verdict: BLOCK
---

## Verdict

**BLOCK.** The third-pass text closes the lifespan-off route-work bypass, adds the missing
dead-on-arrival debit and lifecycle keys, and makes WO-0102's ordinary route tests runnable. It still
does not close REV-0024-F-001 or F-004 as the binding text defines them. A lifespan-off bare Uvicorn
process may now accept plain-HTTP connections on the forbidden non-loopback listener and return 503;
that is fail-closed at ASGI dispatch, but it is not a proxy-private bind or failure before serving.
The launcher proof can still pass for an unrelated startup guard. A-4 still lacks a specified
linearization point and an exact restart/replay oracle for consumed budget. Joint enablement and
several propagation statements also remain inconsistent, so ADR-009 cannot clear acceptance.

## Findings

### REV-0025-F-001 — P1 — the 503 fallback leaves the forbidden backend listener reachable (`reproduced-live`)

**File:line:** `docs/adr/ADR-009-signal-seat-boundary.md:119-132,161-194`;
`docs/spec/signal-seat/04-auth-and-api.md:9-32`;
`work/queue/WO-0102-signal-ingestion-endpoint.md:78`;
`work/review/REV-0025/request.md:28-35,58-62,70-74`;
`constraints.txt:101`.

**Evidence:** The binding invariant says the backend listener itself stays loopback/UDS, a
non-loopback bind fails fast, and a same-network client can never hit the plain-HTTP port. The new
lifespan-off exception instead says bare Uvicorn starts on `0.0.0.0` and every request receives 503,
then calls that "nothing reachable." With the pinned Uvicorn 0.51.0, a live synthetic ASGI guard
under `lifespan="off"` accepted a TCP connection and returned
`HTTP/1.1 503 Service Unavailable`. An ASGI guard necessarily runs after the socket has accepted and
the server has parsed enough HTTP to dispatch the scope. The exact fixed command's environment did
not spoof `app.state`; the contradiction exists even with a perfect sentinel.

**Why it matters:** Returning a fail-closed response prevents route work, but it does not enforce a
proxy-private listener or the packet's pre-serve-failure criterion. A same-network client can still
reach and consume the plain-HTTP server/parser/connection surface outside the TLS proxy. The new
clause silently weakens the reviewed transport boundary while the ADR, spec, and request retain the
stronger guarantee.

**What resolves it:** Reject enabled unsanctioned app construction/import before Uvicorn can create
an accepting listener. The sanctioned launcher can establish an opaque, one-shot, code-owned
capability before importing the module-level app (or use a separate factory module); no environment
switch, importable pre-authorized app, or zero-argument authorized factory may mint it. Keep the
request guard as defense in depth, and make the hostile subprocess oracle prove connection refusal/no
listener. Alternatively, obtain an explicit human decision to replace the proxy-private invariant
with the weaker reachable-503 posture and reconcile every contradictory acceptance statement.

### REV-0025-F-002 — P1 — the launcher proof can still false-green behind unrelated startup guards (`reasoned-only`)

**File:line:** `work/queue/WO-0102-signal-ingestion-endpoint.md:77-81`.

**Evidence:** The new lifespan-off case has a targeted request-time oracle, but the sanctioned
non-loopback launcher case and lifespan-on bare-Uvicorn case still accept generic pre-serve failure.
The same work order requires startup failure for missing credentials and missing rails. Its fake
rails/sentinel fixture is assigned to constructed `TestClient` route tests, not these literal
subprocess launches. Removing bind validation or the lifespan provenance check can therefore leave
both exit assertions green because an unrelated required guard supplies the failure.

**Why it matters:** The required proof is not mutation-sensitive as currently specified. It permits
a human-gated transport boundary to be declared verified while the target protection is absent.

**What resolves it:** Satisfy every unrelated startup precondition, assert the exact A-1-specific
failure reason, and include a same-config sanctioned-loopback positive control that reaches a ready
listener. Mutation/removal of each A-1 check must make its test fail. If real rails are required,
explicitly assign the subprocess proof to the joint milestone. Under the current weaker
lifespan-off design, probe public `GET /api/health` and assert a provenance-specific response rather
than a route-auth failure; if F-001's binding invariant is preserved, the correct oracle is no
accepting listener at all.

### REV-0025-F-003 — P1 — the invalid-budget ceiling is not linearizable or crash-atomic (`reasoned-only`)

**File:line:** `docs/adr/ADR-009-signal-seat-boundary.md:270-280,295-320`;
`docs/spec/signal-seat/03-rails.md:41-48,102-112`;
`work/queue/WO-0104-signal-rails.md:64,78-80`.

**Evidence:** Generic StateStore rules already require multi-row mutation plus audit writes to be
atomic (`app/store/base.py:16-17`), but A-4 never assigns the budget decision, terminal append, and
epoch transition to one signal-specific store operation or states how requests already admitted at
step 2 recheck/reserve a slot at step 4. No delayed-body/final-slot concurrency or fault test is
required. With one slot left, concurrent requests can all pass step 2 before any step-4 debit; an
implementation can then append beyond the cap. More strongly, a producer can admit requests at the
refill cadence while slow-streaming their bounded bodies, then complete them as invalid after
exhaustion; those requests never revisit step 2 under the written algorithm. If the budget is stored
separately from the events, a crash boundary is likewise unspecified. The edge text is itself
contradictory: `03-rails.md:45` calls the epoch-opening request “write-free,” while lines 47-48 and
109-112 require its `PRODUCER_QUARANTINED` append.

**Why it matters:** The asserted `<= invalid_budget` terminal-event ceiling and “nothing appended
post-quarantine” property do not follow under concurrency, delayed bodies, or interruption. This
reopens the same unbounded-log class A-4 is meant to close.

**What resolves it:** Specify a linearizable admission/reservation/recheck design that preserves the
human-pinned rule that the last-slot terminal append completes normally and only the next ingest
opens the epoch, while preventing already-admitted requests from appending after zero. If budget
state is separate, its debit and terminal event must share one memory lock/SQLite transaction; if it
is event-derived, the atomic append is the debit. Add dual-store delayed-body concurrency,
final-slot race, duplicate epoch-open/release, and crash-injection tests. Pin the opener to one
event/status and reserve “write-free” for subsequent rejects; any necessary change to the pinned
step-2 transition needs human approval.

### REV-0025-F-004 — P1 — restart proof pins the configured limit but not consumed budget (`reasoned-only`)

**File:line:** `docs/adr/ADR-009-signal-seat-boundary.md:289-324`;
`docs/spec/signal-seat/02-lifecycle.md:41-50,91-105`;
`docs/spec/signal-seat/03-rails.md:49-57`;
`work/queue/WO-0104-signal-rails.md:64,78-80`.

**Evidence:** The third-pass rule now makes the cycle's configured limit persistent and
restart/replay-stable, and WO-0104 tests that a mid-cycle config change leaves that limit unchanged.
It never explicitly requires already-consumed or remaining slots to survive. A compliant-looking
implementation can pin `limit=50`, consume 49, restart with the same pinned limit but `used=0`, and
pass a literal “limit unchanged” assertion. The lifecycle replay contract reconstructs signal and
producer-quarantine state, but no event payload records the cycle's historical pinned limit or an
explicit used count. Use could be derived from terminal events, but that fold is not assigned or
tied to the historical limit, so the text does not say how memory replay or SQLite reopen restores
the binding remaining budget.

**Why it matters:** A restart can silently grant a fresh budget without changing the pinned numeric
limit, allowing repeated pre-quarantine log growth without `PRODUCER_RELEASED`. That violates the
binding reset-only-on-human-release rule while evading the newly named oracle.

**What resolves it:** Define pinned limit and consumed/remaining count as one durable producer-rail
state, restored before serving and updated atomically with each terminal append. Specify how replay
learns the historical limit (event payload or equivalent durable rail record). In both stores, prove:
consume 49/50 slots, close/reopen or replay under raised and lowered config, permit exactly one final
terminal append, then have the next ingest append exactly one quarantine event; after human release,
the new config starts the next cycle.

### REV-0025-F-005 — P1 — joint enablement and flag-on test ownership are contradictory (`reasoned-only`)

**File:line:** `docs/adr/ADR-009-signal-seat-boundary.md:329-349`;
`docs/spec/signal-seat/03-rails.md:66-89`;
`work/queue/WO-0102-signal-ingestion-endpoint.md:17-19,77-81,89-93`;
`work/queue/WO-0103-signal-approval-surface.md:17-20`;
`work/queue/WO-0104-signal-rails.md:18,66,81`.

**Evidence:** The sanctioned fake-rails/sentinel fixture now makes WO-0102's standalone mounted
route tests runnable and closes that earlier test-feasibility concern. The release contract still
declares an all-three-WO gate while the runtime startup condition enumerates rails only. WO-0104 may
run in parallel with unfinished WO-0103, calls itself the first change where the flag can start, and
defines its flag-on suite as WO-0102+WO-0104 authorization/flood coverage. No joint mounted-app test
requires the WO-0103 atomic conversion capability or even the approve route. The rails guard checks
only that an injected object satisfies the Protocol; the sole production distinction for the
permissive conforming fake is “never a production default.”

**Why it matters:** The work-order/deployment gate may be intended to enforce the WO-0103 half, but
the current text simultaneously says WO-0104 is the first flag-on point and supplies no conversion
oracle. A Protocol-presence test cannot distinguish full enforcement from a permissive/no-op
conforming provider; without a binding production-construction rule, that portion is discipline
dressed as a guard.

**What resolves it:** Make the explicit sequencing/deployment dependency and joint test owner
binding, and require the joint mounted-app suite against real rails to prove ingest -> operator
approval -> exactly one atomically linked intent. Confine both fake rails and synthetic launch
authorization to test-only construction that production config/environment cannot select, and test
that the production entrypoint wires WO-0104's provider. If the desired WO-0103 guarantee is
runtime-structural rather than a release gate, add a conversion-capability startup check only with
human approval. The route matrix must assert required routes exist, not merely classify those that
happen to be mounted; “lift the guard” must mean satisfy a permanent guard, not delete it.

### REV-0025-F-006 — P1 — A-4 propagation remains internally contradictory (`reasoned-only`)

**File:line:** `docs/adr/ADR-009-signal-seat-boundary.md:224-229,270-280,308-327`;
`docs/spec/signal-seat/03-rails.md:41-64,102-129`;
`pkl/architecture/signal-seat.md:55-60`;
`work/queue/WO-0102-signal-ingestion-endpoint.md:79`.

**Evidence:** The third pass correctly adds dead-on-arrival `SIGNAL_EXPIRED` to the normative debit
rule. WO-0102 still says steps 1-2 reject with zero store writes, omitting A-4's required single
epoch-opening append. The spec's final-slot paragraph likewise calls the opening request
“write-free” at line 45 while lines 47-48 require its `PRODUCER_QUARANTINED` append. Finally,
Option E admits accepted-signal volume is only rate-bounded and unbounded over indefinite time, but
the ADR, spec, and PKL still describe total/event-log volume as constant or bounded while including
pre-quarantine accepted signals. A rate bound over an indefinitely un-quarantined interval is not a
constant storage bound.

**Why it matters:** An implementer can follow WO-0102 and omit the one permitted epoch-opening
write, or follow the spec's “write-free” label and contradict its event count. The surviving global
finite-storage language also contradicts the human-approved Option-E scope correction.

**What resolves it:** Carry the exact one-write carve-out through every normative order/WO
statement and reserve “write-free” for rejects after the epoch opener. Narrow every storage
assurance and flood oracle to attributable terminal-at-ingest traffic between human releases, while
explicitly retaining the accepted decision that valid accepted traffic is only rate-bounded over
indefinite time.

### REV-0025-F-007 — P1 — the fail-closed authorization matrix omits a mounted mutating route (`reasoned-only`, beyond the narrow re-remediation)

**File:line:** `docs/adr/ADR-009-signal-seat-boundary.md:139-150`;
`docs/spec/signal-seat/04-auth-and-api.md:68-91`;
`app/api/routes_system.py:48-63`; `app/main.py:153`.

**Evidence:** The normative table classifies public health and operator-only “session reads” for
`routes_system`, but the mounted router also exposes `POST /api/session/close`. That command expires
candidates, cancels CREATED orders, snapshots positions, and closes the session. It is not a read
and has no explicit row.

**Why it matters:** The table claims every mounted route is classified and is the source for a
fail-closed test. As written, the test must either fail or invent policy outside the binding table;
a coarse implementation can leave this state-changing route outside the operator-only matrix.

**What resolves it:** Add `POST /api/session/close` explicitly as operator-only and include all four
credential cases in the mounted-route matrix test.

## Closure assessment

| Review question | Status | Assessment |
|---|---|---|
| F-001 backend-owned launch | **Not closed** | The request guard closes route work when lifespan is disabled, and no env-only `app.state` spoof was reproduced for the exact command. It still leaves the forbidden listener reachable, contradicts the proxy-private/pre-serve criterion, and the launcher proof can false-green behind unrelated guards. |
| F-004 finite invalid/conflict audit | **Not closed** | The counter fixes the original sequential paced-invalid model; DOA coverage, release reset, and cycle-limit pinning landed. The contract still lacks final-slot linearization and an exact consumed-budget restart/replay proof. |
| Propagation | **Incomplete** | Reads-included wording, interim-ceiling withdrawal, lifecycle keys, and the DOA debit landed, but the zero-write carve-out, global storage wording, joint conversion oracle, and one mounted authorization route remain inconsistent. |
| A-2 / A-3 regressions | **No direct amendment regression found** | Their binding algorithms were not changed. The work-order text does not consistently assign or prove the declared all-three-WO enablement milestone. |

## Verification evidence

- Frozen review state: `209496d3812648376920a7dacccea6664eb5def8`; tracked tree clean before this result was written.
- Reviewed `413da3813191fe31fabf51e9a7247670a45ec561..209496d3812648376920a7dacccea6664eb5def8`, the full target documents/work orders, prior REV-0024 closure criteria, and the as-built FastAPI/Uvicorn seams.
- Uvicorn probes: `UVICORN_HOST=0.0.0.0` + `UVICORN_LIFESPAN=off` parsed as requested and suppressed lifespan; under the proposed request-guard shape, the listener was reachable and returned `HTTP/1.1 503 Service Unavailable`.
- Python 3.12.13 gates: `ruff check .` passed; `mypy app/` reported no issues in 54 source files; `lint-imports` kept all 5 contracts.
- Full supported-runtime suite at `e3fba0b` (the same application/tests as the reviewed tip): 2,049 collected; 2,044 passed, 5 skipped; exit 0 in 221.6 s. The later through-`209496d` delta changes only specifications, work-order/request text, and no application or test file.
- AI Project OS checks passed: install, version consistency v0.9.1, ledger, PKL, and work-order disposition.
- `git diff --check 413da3813191fe31fabf51e9a7247670a45ec561..HEAD` passed.

## Could not verify

- No Signal Seat implementation exists yet, so the launcher, sentinel, rails capability, atomic
  budget command, replay durability, and joint flag-on HTTP behavior cannot be exercised against
  production code. Findings other than the Uvicorn listener observation are contract-level
  re-derivations.
- `request.md` remains `status: QUEUED` / `commit_range: SET-ON-DISPATCH`; this result freezes the
  reviewed SHA and does not edit the request.

## Verdict token

**BLOCK** — resolve REV-0025-F-001 through REV-0025-F-007 before ADR-009 acceptance or WO-0102..0104 activation.
