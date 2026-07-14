---
type: Review Result
rev_id: REV-0024
reviewer_model: GPT-5 Codex
reasoning_effort: Highest-scrutiny adversarial review available in this session; no literal UI effort selector is exposed to the agent
environment: Windows PowerShell; Python 3.14.5; git 2.43.0
reviewed_commit: 413da3813191fe31fabf51e9a7247670a45ec561
date: 2026-07-14
verdict: BLOCK
---

## Verdict

**BLOCK.** Amendments A-2 and A-3 now close REV-0022 F-002/F-003. A-1 and A-4 do not yet close F-001/F-004 as implementable, internally coherent contracts. The transport text requires an actual-listener guarantee that the specified ASGI application seam cannot observe at startup, while the audit design still grows the execution log without bound when hostile attributable requests are paced at or below the token-refill rate. Two remaining propagation contradictions also leave the spec/work-order package lawyerable.

## Findings

| Finding | Severity | Evidence | Why it matters | Required action |
|---|---:|---|---|---|
| REV-0024-F-001 | P1 | ADR-009 A-1 requires startup to verify the actual bind and fail on every non-loopback/non-socket listener (`docs/adr/ADR-009-signal-seat-boundary.md:107-116`). WO-0102 assigns that guard to `app/main.py`/`app/config.py` and asks for a startup test (`work/queue/WO-0102-signal-ingestion-endpoint.md:36-52,74`). The as-built launch path is `uvicorn app.main:app --reload` (`README.md:132`); `create_app` only loads application settings and constructs the FastAPI app (`app/main.py:67-76,146-169`). Uvicorn owns `--host`/`--uds` outside the application, and an ASGI lifespan scope does not expose the listener address; the address appears only on per-request HTTP scopes, after startup. | A guard that compares a new application setting can be green while the real process is launched with `uvicorn app.main:app --host 0.0.0.0`, because CLI server configuration is independent and takes precedence. That violates A-1's stated proxy-bypass defense while still satisfying the current WO's app-level test. The desired security rule is good, but it is not implementable through the bounded seam as written. | Make the backend own one non-bypassable server-launch path (for example, a programmatic Uvicorn entrypoint whose bind comes from the validated setting), forbid/deprecate the direct `uvicorn app.main:app` path when the seat is enabled, add the launcher/docs paths to WO-0102 scope, and prove it with a subprocess test that attempts a prohibited `0.0.0.0` bind and observes process startup failure before requests are served. Alternatively define an equally enforceable server/process-manager control; an app-setting-only assertion is insufficient. |
| REV-0024-F-002 | P1 | A-4 says every authenticated ingest debits a token bucket and claims validation-quarantine events are therefore bounded (`docs/adr/ADR-009-signal-seat-boundary.md:225-238`). The policy refills at 60/hour with burst 10; each attributable validation failure appends `SIGNAL_QUARANTINED` (`docs/spec/signal-seat/01-schema.md:23-31`), and each new conflicting payload hash may append `SIGNAL_DUPLICATE_CONFLICT` (`docs/spec/signal-seat/01-schema.md:70-84`). Quarantine starts only when the bucket is empty (`docs/spec/signal-seat/03-rails.md:6-19`; `work/queue/WO-0104-signal-rails.md:59-64`). A direct semantic probe at one request/minute for seven days produced `10080` validation events, `quarantined=False`, with the bucket never below 9 tokens. | A rate bound is not a storage bound. A hostile producer can remain exactly at the refill rate forever, append one audit event per invalid or novel-conflict request forever, and never open the quarantine epoch whose constant-row rule A-4 relies on. This is the same indefinite-hostility failure class as REV-0022 F-004, and it also invalidates A-2's Option-E deferral premise that A-4 makes signal volume finite. | Add a finite per-producer invalid/conflict budget that does not refill within an open producer epoch and triggers quarantine after a bounded total, or move/coalesce attributable rejection detail outside the append-only execution log after a fixed number of events. Add model/property tests that pace invalid and novel-conflict requests at or below the normal refill rate over arbitrarily many windows and assert a constant event-row ceiling—not merely that a burst eventually exceeds the rate limit. |
| REV-0024-F-003 | P1 | The spec's top-level feature-flag contract still says flag-on activates operator enforcement on all **mutating command routes** (`docs/spec/signal-seat/00-overview.md:33-41`). A-1 and the detailed auth spec require the operator credential on every sensitive route, reads included (`docs/adr/ADR-009-signal-seat-boundary.md:123-135`; `docs/spec/signal-seat/04-auth-and-api.md:31-45`). The overview itself declares every ADR/spec disagreement a defect (`docs/spec/signal-seat/00-overview.md:3-6`). | This is the exact reads-versus-commands boundary F-001 required the remediation to close. The detailed matrix is correct, but an implementer using the overview's feature-flag paragraph can preserve unauthenticated reads while claiming the two flips landed together. | Change the overview to say that flag-on activates operator enforcement on **every sensitive route, reads included**, and point directly to the fail-closed mounted-route matrix. |
| REV-0024-F-004 | P1 | WO-0102 correctly says its interim ceiling is audit-free and that `PRODUCER_QUARANTINED`/`PRODUCER_RELEASED` epoch machinery belongs to WO-0104 (`work/queue/WO-0102-signal-ingestion-endpoint.md:75,79`), but the same required-behavior list still requires post-quarantine handling and coalesced audit in WO-0102 (`work/queue/WO-0102-signal-ingestion-endpoint.md:78`). Separately, the normative order is auth → rails → bounded read → parse (`docs/spec/signal-seat/03-rails.md:44-51`), yet the rate-limit section says breach occurs only at an “otherwise-valid ingest” (`docs/spec/signal-seat/03-rails.md:16-19`), which cannot be known before the mandated no-body rails decision. | WO-0102 cannot both omit epoch machinery and prove behavior for already-quarantined producers. The “otherwise-valid” qualifier also invites parsing before the rate decision, defeating A-4's pre-body resource defense and its promise that every authenticated invalid request debits the bucket. | Remove the post-quarantine/epoch requirement from WO-0102 or mark it explicitly as a WO-0104 acceptance test rather than WO-0102 behavior. Define bucket debit/breach on every authenticated request before body read, with no parse-validity qualifier, and align the 403/429 audit wording with the interim-versus-full-rails split. |

## Closure assessment against REV-0022

| Prior finding | Status | Rationale |
|---|---|---|
| F-001 — credential/transport/read boundary | **Not closed** | Credential lifecycle, principal-derived actor, reads-included route matrix, docs classification, and flag-off posture are now substantively specified. The actual-bind guarantee is not enforceable through the stated launch/app seam, and the overview still narrows enforcement to mutating routes. |
| F-002 — atomic approval→intent conversion | **Closed** | A-2 now mandates one dedicated dual-store atomic command, one lock/transaction, no await between checks and writes, signal state in the memory snapshot, all-or-nothing approval/event/intent creation, idempotent retry, and crash/interleaving coverage. The as-built split-await facade is explicitly forbidden. |
| F-003 — server-owned freshness and classification | **Closed** | The deadline formula, skew bounds, hard TTL cap, injected clock, persisted restart-stable deadline, conversion-time re-check, and exactly-once outstanding-exposure formula are implementable. The universal Active/Reducing exposure ceiling preserves the INV-7 asymmetry without double-counting ORDERED intents. |
| F-004 — finite audit/backpressure | **Not closed** | Post-quarantine traffic is constant-row, and the interim over-ceiling path is audit-free, but indefinitely paced invalid/conflict traffic never breaches the refilling bucket and continues appending forever. The staged WO contract also still contradicts itself about which wave owns quarantine epochs. |

## Verification evidence

- Frozen review state: `413da3813191fe31fabf51e9a7247670a45ec561`; a final `git fetch` confirmed the remote branch still pointed to the same SHA before this result was written.
- Scope diff re-derived from the REV-0022 authority SHA `25590a76656d2e4393609ffc3cf37e27feb71d53`; full target files and the as-built FastAPI/facade/store seams named by `request.md` were read.
- Paced-hostility semantic probe: a 60/hour token bucket with burst 10, fed one attributable invalid request per minute, yielded `10080` appended validation events over seven days without quarantine; tokens remained at 9.
- AI-OS checks: install, version consistency, ledger, PKL, and disposition checks all passed.
- Full local pytest at the reviewed checkout: 3 failed, 2035 passed, 6 skipped on Python 3.14.5. All three failures were `ResourceWarning`/`PytestUnraisableExceptionWarning` from unclosed SQLite connections surfacing during unrelated tests. No application or test files changed in the reviewed range, and no signal-seat implementation exists, so this is environment/runtime evidence—not signal-remediation evidence—and the suite is not claimed green.
- `ruff`, `mypy`, and `lint-imports` were unavailable in this local interpreter and remain unverified for this pass.

## Could not verify

- No signal-seat implementation exists, so the mounted-route matrix, real server-bind failure, dual-store atomic conversion, and paced-flood invariants cannot yet be executed against production code.
- `request.md` remains `commit_range: SET-ON-DISPATCH`; this result freezes the reviewed SHA in its own frontmatter and does not edit `request.md`.

## Verdict token

**BLOCK** — resolve REV-0024-F-001 through REV-0024-F-004 before ADR-009 acceptance or WO-0102 activation.
