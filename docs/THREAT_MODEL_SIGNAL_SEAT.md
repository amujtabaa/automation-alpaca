# Signal Seat Threat Model — WO-0136

**Status:** advisory analysis for R5; not an ADR/spec amendment.  
**Evidence posture:** VERIFIED against accepted ADR/spec text and local fallback review corpus on 2026-07-22.  
**Scope:** the first external-input surface for Signal Seat ingestion and operator approval.  
**Non-goals:** no code changes, no spec/ADR edits, no penetration testing, no new dependencies, and no approval of Option C / ADR-013. Option C is sized as future ADR work only.

## 1. Source packet and trust assumptions

The controlling accepted decision is ADR-009, accepted 2026-07-21, which defines signal producers as untrusted advisors over authenticated HTTP and preserves the human-gated Spine v2 execution path. The document relies on the signal-seat specs, especially rails and auth/API route classification. ADR-013 remains Proposed and is therefore only a future-internet-ingress sizing input.

Standing ratifications used here:

- D-SIG-1: Option A is localhost producer for V1.
- D-SIG-3: `loopback` default, `tailnet_serve` as a later config flip, Funnel/public exposure forbidden.
- D-SIG-4: construction-time bind guard at the backend-owned launcher seam.
- D-SIG-5: when the seat is enabled, all sensitive reads require operator credentials.
- D-SIG-6: env-injected static keys with overlap rotation/restart revocation.
- D-HOST-1: localhost is load-bearing; VPS/public exposure waits for an auth/deployment ADR.

## 2. Assets and trust boundaries

| Asset / boundary | Threat value | Existing control or disposition |
|---|---|---|
| Producer keys | Bind requests to an authenticated producer and isolate producer namespaces. | A-1 key lifecycle requires env-injected secrets, redaction, constant-time comparison, overlap rotation, revocation by removal, and principal-derived identity. |
| Operator key | Protects every sensitive read and all human-gated commands once `signal_seat_enabled` is on. | A-1 route matrix requires the operator credential for sensitive reads and commands, with producer keys limited to `POST /api/signals`. |
| Event-log integrity | Append-only audit truth for received/quarantined/approved/rejected/released facts. | ADR-009 makes lifecycle events first-class; A-4 bounds hostile attributable-rejection growth without hiding facts. |
| Approval→conversion chain | Crown jewel: a signal must never execute without human approval. | ADR-009 L0 trust ladder requires per-signal human approval; approval emits a normal order intent through the A-2 atomic conversion command and then loses any special authority. |
| Host/port exposure | Decides whether an untrusted process can reach the API. | A-1 loopback/tailnet policy forbids public bind, public reverse proxy, Funnel, and plain HTTP over network boundaries; launcher guard verifies the actual bind. |
| Cockpit availability | Operator must retain browser-first ability to read, approve/reject, release, kill switch, and flatten. | ADR-009 requires cockpit credential plumbing in the same change as enforcement to avoid an operator lockout window. |
| Browser ↔ cockpit ↔ API | Header plumbing can leak or omit operator credentials. | A-1 requires every sensitive route to be classified and fail-closed; R5 GAPs below require cockpit header proof. |
| Env key custody | Static-key beta custody can leak through process/env/logging. | A-1 accepts env-injected static keys as interim custody; ADR-013 must revisit custody for internet ingress. |

## 3. Attacker profiles

| Profile | Capability | Primary objective | Boundary posture |
|---|---|---|---|
| Malicious/compromised local producer | Has a valid producer key and local reach to FastAPI. | Forge identity, learn positions/orders, flood audit log, induce stale/spoofed approval. | Treated as untrusted; only `POST /api/signals` is authorized; rails and human approval are mandatory. |
| Non-producer local process | Local host reach but no valid key. | Probe reads/mutations or exploit body parsing/DoS. | Authentication happens before body read; all sensitive routes fail closed. |
| Tailnet node under Option B | Tailnet reach to `tailscale serve`; may or may not possess app keys. | Treat tailnet identity as sufficient, or reach non-loopback backend directly. | Tailnet identity is transport auth only; app credentials remain mandatory; backend stays loopback/socket-bound. |
| Internet attacker | Public internet reach, no tailnet/app key. | Hit webhook/API directly, enumerate docs, exploit public bind. | Structurally excluded today by loopback bind, construction-time bind guard, Funnel/public exposure prohibition; ADR-013 must answer future receiver design. |
| Compromised operator browser context | Can read or inject cockpit requests while operator is logged in. | Abuse operator key/header, approve malicious payloads, exfiltrate thesis/provenance. | Thin-client boundary remains; R5/R7 need rendering/header tests and operator confirmation payload rules. |
| Operator misuse | Human fat-fingers approval of stale/spoofed thesis. | Accidentally turns advice into an order intent. | TTL/deadline, atomic conversion re-check, advisory-only producer sizing, and explicit operator qty/price confirmation reduce but do not eliminate this risk. |

## 4. STRIDE table by surface

Termination legend: **CONTROL** = accepted control with source anchor; **GAP-n** = requirement in §7; **RISK** = explicitly accepted risk.

| ID | Surface | STRIDE | Threat | Termination |
|---|---|---|---|---|
| T-01 | `POST /api/signals` | Spoofing | Producer supplies another producer's `producer_id` or collides bare `signal_id` to poison dedupe/quarantine provenance. | **CONTROL:** server derives identity from credential; body `producer_id` mismatch is rejected; dedupe key is `(producer_id, signal_id)`. |
| T-02 | `POST /api/signals` | Tampering | Producer changes thesis/provenance or suggested sizing after a duplicate ID to smuggle a different proposal. | **CONTROL:** duplicate-conflicting/self-contradictory signals quarantine; payload hash conflict detection is required by schema/lifecycle specs. |
| T-03 | `POST /api/signals` | Repudiation | Producer later denies submitting a signal or claims the API lost a terminal ingest fact. | **CONTROL:** every lifecycle fact is appended as first-class events, with terminal-at-ingest recording under A-4. |
| T-04 | `POST /api/signals` | Info disclosure | Validation errors, docs routes, or read routes expose positions, sessions, producers, thesis, or API shape to producers. | **CONTROL:** docs routes disabled/gated; every sensitive read is operator-key-only; producer key authorizes only ingest. |
| T-05 | `POST /api/signals` | DoS | Unauthenticated or oversized requests consume memory/CPU before auth. | **CONTROL:** A-4 order is authenticate → rails → 64 KiB capped body read → parse; steps 1-2 reject with no body processing/store writes except threshold opener. |
| T-06 | `POST /api/signals` | DoS | Paced invalid/conflict traffic stays below a refill bucket forever while growing the append-only log. | **CONTROL:** A-4 non-refilling invalid/conflict budget with hard cap, one quarantine epoch opener, write-free post-quarantine rejects. |
| T-07 | `POST /api/signals` | DoS | Concurrent/slow requests with one invalid-budget slot each append because the budget is non-linearizable or not durable. | **CONTROL:** A-4 requires one memory lock / SQLite transaction for check-reserve-debit + append, durable rail state, replay reconstruction. |
| T-08 | `POST /api/signals` | Elevation | Producer-suggested quantity/price flows into a real order without operator confirmation. | **CONTROL:** ADR-009 says producer sizing is display-only; approval payload carries operator-confirmed quantity/limit; conversion uses the normal risk path. |
| T-09 | Operator read/list routes | Spoofing / Info disclosure | Producer or unauthenticated caller omits key or uses producer key to read positions, orders, sessions, signal queues, producer states, or other producers' theses. | **CONTROL:** A-1 flag-on matrix requires operator credential for all sensitive reads and commands; fail-closed mounted-route matrix test catches omissions. |
| T-10 | Operator approve/reject routes | Elevation | Producer key approves/rejects a signal or invokes manual controls by omitting auth. | **CONTROL:** approval/rejection are operator-only; producer key is structurally limited to ingest. |
| T-11 | Operator approve route | Tampering / Elevation | Approval races expiry, kill switch, reducing-state checks, or exposure changes; stale signal becomes an order intent. | **CONTROL:** conversion is A-2 atomic and re-checks TTL/session/risk/kill-switch/exposure in the same transaction; signal-sell details are R7-owned. |
| T-12 | Operator approve route | Tampering | Producer-supplied display text tricks the operator through stale/spoofed thesis or unsafe rendering. | **GAP-05:** R5 must render thesis/provenance as untrusted text only and never as executable/unsafe markdown or HTML. |
| T-13 | Producer-release route | Elevation | Producer self-releases from quarantine, resetting budgets and reopening audit flood. | **CONTROL:** release is operator-only and browser-accessible; budget resets only on human `PRODUCER_RELEASED`. |
| T-14 | Producer-release route | Repudiation | Release summary loses how many post-quarantine requests were suppressed. | **CONTROL:** A-4 requires saturating out-of-log counter and one release summary; post-quarantine rejects remain write-free. |
| T-15 | Launcher/bind path | Spoofing / Elevation | Running bare `uvicorn app.main:app --host 0.0.0.0` bypasses app-setting checks and exposes the API. | **CONTROL:** A-1 backend-owned launcher derives/re-validates bind and construction-time capability makes bare app import leave no listener-capable app. |
| T-16 | Launcher/bind path | DoS / Info disclosure | A request-time 503 guard still accepts TCP on a forbidden public interface. | **CONTROL:** A-1 rejects reachable-503 as insufficient and requires construction-time refusal before any socket serves. |
| T-17 | Launcher/bind path | Elevation | `tailnet_serve` is interpreted as permission to bind non-loopback or use Funnel. | **CONTROL:** backend remains loopback/socket-bound; Funnel/public bind/public reverse proxy are forbidden and negative-tested. |
| T-18 | Key custody/rotation | Spoofing | Stolen/blank/misconfigured operator or producer key leaves the system enabled but insecure or operator-locked out. | **CONTROL:** key presence startup guard fails fast; env injection, compare_digest, redaction, overlap rotation, revocation are accepted. |
| T-19 | Key custody/rotation | Repudiation | `X-Actor` spoofing overwrites true authenticated principal in audit records. | **CONTROL:** principal derives from authenticated credential; `X-Actor` is only an optional sub-label. |
| T-20 | Event log/audit | Tampering / Repudiation | Accepted signal cannot be traced to the order intent it influenced. | **CONTROL:** `SIGNAL_APPROVED` carries candidate/sell-intent id and created intent carries `(producer_id, signal_id)` back-reference. |
| T-21 | Event log/audit | DoS | Valid but malicious high-volume signal stream grows log indefinitely while never violating invalid budget. | **RISK:** accepted signals are explicitly rate-bounded, not constant-storage-bounded; L0 human approval and per-producer rate limit are the accepted beta trade-off. |
| T-22 | Cockpit header plumbing | DoS / Elevation | Enforcement flips before cockpit sends operator key, locking the operator out of kill switch/manual flatten/read surfaces. | **CONTROL:** ADR-009 requires cockpit credential plumbing in the same change; **GAP-01** requires R5 same-change mounted-app proof. |
| T-23 | Route matrix | Info disclosure / Elevation | New mounted route, including `POST /api/session/close`, is omitted from auth matrix. | **CONTROL:** A-1 explicitly includes session close and requires fail-closed route-introspection coverage; **GAP-02** requires R5 proof against actual mounted routes. |
| T-24 | Internet ingress / ADR-013 | Spoofing / DoS / Info disclosure | Public webhook receiver shares the trading API or relies only on static keys across the internet. | **GAP-07:** ADR-013 must define a separate internet receiver that never exposes the trading API and must decide transport auth, key custody, replay resistance, rate limits, and audit isolation before Option C. |

## 5. Appendix A — ADR-009 A-1 / A-4 clause traceability

| Clause | Mitigates threat rows | Finding if uncovered? |
|---|---|---|
| A-1.1 transport policy: loopback default, `tailnet_serve`, forbidden Funnel/public exposure, launcher verifies bind | T-15, T-16, T-17, T-24 | None. |
| A-1.2 key lifecycle: env secrets, redaction, compare_digest, overlap rotation, revocation, principal-derived identity | T-01, T-18, T-19 | None. |
| A-1.3 route authorization matrix, reads included, producer key only for ingest, fail-closed mounted-route coverage | T-04, T-09, T-10, T-23 | None. |
| A-1.4 credential-presence startup guard | T-18, T-22 | None. |
| A-1.5 auto-docs disabled/gated and classified | T-04 | None. |
| A-1.6 backend-owned launcher + construction-time launch-provenance capability | T-15, T-16, T-17 | None. |
| A-4 normative order: authenticate, rails, 64 KiB capped read, parse/validate | T-03, T-05 | None. |
| A-4 rate bucket debits every authenticated ingest and breaches before body read | T-05, T-06 | None. |
| A-4 non-refilling invalid/conflict/DOA expiry budget with hard cap and cycle pinning | T-06, T-07 | None. |
| A-4 exhausting append co-opens quarantine epoch; one `PRODUCER_QUARANTINED` per epoch | T-06, T-07, T-13 | None. |
| A-4 linearizable check-reserve-debit + terminal append, durable producer-rail state, replay reconstruction | T-07 | None. |
| A-4 human release resets budget, release summary, write-free post-quarantine backpressure | T-13, T-14 | None. |
| A-4 rails-presence startup guard and joint enablement with R5/R6/R7 | T-06, T-11, T-22 | None; implementation ownership split into GAP-01/GAP-03/GAP-04. |

## 6. Appendix B — pre-found attacks

| Attack corpus row | Threat rows | Accepted control or GAP |
|---|---|---|
| REV-0022 F-001 (master): unauthenticated reads / transport-credential boundary | T-04, T-09, T-10, T-23 | **CONTROL:** ADR-009 A-1 requires transport policy, key lifecycle, reads-included route auth matrix, credential startup guard, docs gating, launcher guard. |
| archive REV-0024 @ origin/archive/claude-wo-0001-install-checks-2x5ys8: ASGI-seam bind-guard unenforceability | T-15, T-17 | **CONTROL:** backend-owned launcher and construction-time capability; app setting alone is not trusted. |
| archive REV-0024 @ origin/archive/claude-wo-0001-install-checks-2x5ys8: paced-hostility hole, 10,080 events / 7 days at 1 req/min without breaching refill bucket | T-06 | **CONTROL:** non-refilling invalid/conflict/DOA-expiry budget with hard cap and human-reset epoch. |
| archive REV-0025 @ origin/archive/claude-wo-0001-install-checks-2x5ys8: reachable-503 listener | T-16 | **CONTROL:** request-time 503 is insufficient; construction-time refusal before any socket serves is required. |
| archive REV-0025 @ origin/archive/claude-wo-0001-install-checks-2x5ys8: non-mutation-sensitive launch proof | T-15, T-17 | **CONTROL:** no listener without backend-owned launch provenance; route mutation alone cannot prove bind safety. |
| archive REV-0025 @ origin/archive/claude-wo-0001-install-checks-2x5ys8: non-linearizable/non-durable budget | T-07 | **CONTROL:** one lock/transaction for debit+append and durable producer-rail replay state. |
| archive REV-0025 @ origin/archive/claude-wo-0001-install-checks-2x5ys8: joint-enablement contradiction | T-22, T-11 | **GAP-03 / GAP-04:** R6 and R7 must satisfy rails/conversion before enablement; R5 must not independently make the flag enable-able. |
| archive REV-0025 @ origin/archive/claude-wo-0001-install-checks-2x5ys8: `POST /api/session/close` missing from auth matrix | T-23 | **CONTROL:** ADR-009 A-1 now explicitly includes `POST /api/session/close`; R5 must prove mounted-route coverage. |

## 7. GAP register — downstream requirements

| Gap | Owner | Testable requirement |
|---|---|---|
| GAP-01 | R5 | R5 must land the operator-auth enforcement flip, cockpit `X-Operator-Key` plumbing, and mounted-app proof in the same change, and must demonstrate that kill switch, manual flatten/session controls, and sensitive reads do not become unusable for an operator with the configured key. |
| GAP-02 | R5 | R5 must fail closed for every mounted route when `signal_seat_enabled=true`: unauthenticated and producer-key callers must receive 401/403 on all sensitive reads/commands, producer keys must authorize only `POST /api/signals`, and the route-introspection test must fail if any mounted route is absent from the matrix, including `POST /api/session/close`. |
| GAP-03 | R5 | R5 must keep `signal_seat_enabled` un-enable-able unless the rails-presence contract is satisfied by the R6 provider; a stub, counting-only ceiling, or missing release path must refuse startup rather than expose `POST /api/signals`. |
| GAP-04 | R5 | R5 must implement the backend-owned launcher/construction-time bind guard so `loopback` and `tailnet_serve` start only on loopback or same-host socket, and any public/non-loopback bind, Funnel/public reverse proxy mode, bare ASGI app launch, or request-time-503-only guard opens no listener. |
| GAP-05 | R5 | R5 must treat submitted `thesis` and `provenance` as hostile display text: cockpit/API rendering must not execute HTML/script/unsafe markdown, must preserve verbatim audit content, and must not leak credentials in validation or display errors. |
| GAP-06 | R5 | R5 must derive producer identity solely from the authenticated producer key, reject body `producer_id` mismatches before namespace accounting, and prove dedupe, rate-limit, invalid-budget, quarantine, and audit provenance are keyed by the authenticated producer namespace. |
| GAP-07 | ADR-013 | ADR-013 must specify any future Option-C internet receiver as a separate ingress that does not expose the trading API, and must decide transport authentication, replay resistance, key custody/rotation, rate limiting, body-size limits, webhook authenticity, event-log isolation, and operator-visible failure modes before any internet producer is approved. |
| GAP-08 | R6 | R6 must provide a real dual-rail provider with refilling per-producer bucket, non-refilling durable invalid/conflict/DOA-expiry budget, atomic debit+append, one quarantine opener per epoch, saturating suppressed counter, and human release reset across memory and SQLite. |
| GAP-09 | R7 | R7 must prove signal approval consumes exactly one approval in an atomic conversion command, re-checks TTL/session/risk/kill-switch/exposure in the same transaction, uses operator-confirmed quantity/limit rather than producer suggestions, and preserves `(producer_id, signal_id)` correlation into the created intent. |
| GAP-10 | operator NEEDS-INPUT | The operator must decide the signal-sell versus envelope relationship and the multi-exit/single-flight relaxation before R7 implements sell-direction conversion. |

## 8. Option C sizing — future only, not approved

Option C introduces an internet attacker with cheap global reach, replay capability, credential-stuffing pressure, bot-rate abuse, webhook-origin spoofing, schema enumeration, and operational credential-custody demands unlike localhost/tailnet. Today it is structurally excluded: loopback bind, construction-time bind guard, backend-owned launcher, no Funnel/public reverse proxy, and ADR-013 Proposed-only status. ADR-013 must therefore answer at least GAP-07 before any receiver exists, and must preserve the trading API as non-public even if a webhook receiver is deployed.

## 9. Self-audit: zero-orphan proof

| Check | Result |
|---|---|
| Every threat row T-01..T-24 terminates in exactly one of CONTROL, RISK, or numbered GAP. | VERIFIED. |
| Every ADR-009 A-1 clause maps to at least one threat row. | VERIFIED in Appendix A. |
| Every ADR-009 A-4 clause maps to at least one threat row. | VERIFIED in Appendix A. |
| Every mandatory pre-found attack row is represented. | VERIFIED in Appendix B. |
| Archive findings are cited with archive-ref provenance form, not bare ids. | VERIFIED in Appendix B and threat rows. |
| P0-equivalent hole in accepted text found? | UNVERIFIED as a live implementation property because R5/R6/R7 are not built; no accepted-text P0-equivalent hole was found. |
