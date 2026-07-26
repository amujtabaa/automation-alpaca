---
type: Review Disposition
rev_id: REV-0043
verdict_received: ACCEPT
disposition_status: RESOLVED
date: 2026-07-25
outcome: WO-0139 CLOSED (R5b-2 operator enforcement, route authorization, principal-bound audit, and cockpit credential plumbing delivered; D-2a remains OFF pending R6 + R7)
implementation_sha: "330ca0a79f28f9a8894974e747996b30bccbe371"
---

# Disposition — REV-0043

REV-0043 independently reviewed the Signal Seat R5b-2 operator-enforcement surface. The first pass
returned **ACCEPT-WITH-CHANGES** against `d540258`; reviewer-owned addendum 01 re-reviewed the
bounded remediation at `330ca0a79f28f9a8894974e747996b30bccbe371` and returned the final verdict
**ACCEPT**, clearing the human-gated review gate.

## F-1 and F-2 — resolved

- **F-1 — missing `/fills` negative pin:** every existing `/fills` call supplied `X-Actor`, so
  weakening that invariant-9 canonical-fill route from `get_required_actor` to `get_actor` survived
  the entire full suite. A single parametrized flag-off regression now covers both recovery routes,
  requires `422` with no `X-Actor`, pins the canonical header location, and makes the `/fills`
  weakening mutation fail.
- **F-2 — canonical header alias drift:** `get_required_actor` had dropped `alias="X-Actor"`,
  changing both the flag-off 422 location and OpenAPI parameter name from `X-Actor` to `x-actor`.
  `alias="X-Actor"` is restored, and the same parametrized regression pins the exact
  `("header", "X-Actor")` location for both recovery routes.

## Close-out items

- **F-3:** `flag_on_settings` now explicitly pins `enable_dev_routes=True`.
- **F-5:** the lifecycle text now extends mutation-free effective-status projection to
  existing-record ingest echoes.
- **F-7:** the Signal Seat PKL records R5b-2's delivered operator-enforcement, route-matrix,
  principal-attribution, cockpit-credential, and mutation-free-read scope.

## F-4 — operator ruling recorded

On 2026-07-25, Ameen selected option (a): the `detected_by:"conversion"` token is explicitly
acknowledged and retained in `docs/spec/signal-seat/02-lifecycle.md:51`. The token expresses already
ratified conversion semantics; it is intentionally declared-but-unemitted in this rung. R7 owns the
emitter with the atomic A-2 conversion command. No code or spec reversion is required, and the
event-log-vocabulary stop condition is satisfied by the explicit acknowledgement.

## Carry-forward register

- **F-6 → R6 (record only):** the fixed `operator:authenticated` principal and colon-composed
  `principal:label` value are not losslessly separable once producer principals exist. R6 must
  consume this as planning input; WO-0139 does not change the current actor format.
- **F-8 → R6 (record only):** `StoreBackedSignalFacade.list_signals` projects before status
  filtering, so `GET /api/signals` materializes the full stored scope; neither facade nor store
  accepts a limit. R6 must consume this as planning input when it establishes the bounded rails
  posture; WO-0139 does not implement pushdown or pagination.

WO-0139 closes with `[RESULT_SUMMARY_KEPT, PKL_UPDATED]`. D-2a remains OFF pending R6, R7, and
their joint enablement gate. No rails, producer release, conversion emitter, merge, PR, or flag
enablement is included in this close-out.

Per P-1, the reviewer-authored `result.md` and `result-addendum-01.md` were not edited; this
disposition is a separate close-out record.

**REV-0043 disposition: RESOLVED (initial ACCEPT-WITH-CHANGES remediated; final verdict ACCEPT;
F-4 acknowledged; WO-0139 CLOSED).**
