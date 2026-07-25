---
type: Review Disposition
rev_id: REV-0042
verdict_received: ACCEPT
disposition_status: RESOLVED
date: 2026-07-25
outcome: WO-0138 CLOSED (R5b-1 ingest-only producer surface delivered; flag remains OFF pending R5b-2 + R6 + R7)
implementation_sha: "472de422c67cb14a9d0d21517031cdfe619e74b4"
---

# Disposition — REV-0042

REV-0042 independently reviewed the Signal Seat R5b-1 producer-ingest boundary. The first pass
returned **BLOCK** against `23603ed` on F-1. Reviewer-owned addendum 01 re-reviewed the bounded
remediation at `472de422c67cb14a9d0d21517031cdfe619e74b4` and returned the final verdict
**ACCEPT**, clearing the human-gated review gate.

## F-1 — resolved

- **Cause:** `expires_at` was computed before the future-skew test, so an `issued_at` within its TTL
  of `datetime.max` overflowed before a typed outcome could be recorded. The validation-fallback
  path admitted the same timestamp and reached the same ordering defect.
- **Fix:** `issued_at` is UTC-normalized and bounded on the wire to the datetime domain that is safe
  for every accepted Signal TTL addition. The validation-fallback path shares that predicate, so
  out-of-range timestamps become attributable validation quarantines. `app/store/` was untouched.
- **Verification:** the reviewer reproduced the previously failing valid and validation-fallback
  paths, confirmed recorded 422 outcomes with one event, killed the bound with a control mutation,
  and restored the 49-case route corpus and full suite to green.

## Seven added review pins

1. **F-2:** reserved malformed-identity namespace and over-length `signal_id` values remain 422.
2. **F-3:** the dotless-i symbol class exercises the pre-normalization ASCII guard.
3. **F-4:** an unknown top-level field remains a validation quarantine.
4. **F-5:** a numeric-string `issued_at` remains a validation quarantine.
5. **F-6:** a non-finite suggested limit price sent as raw JSON remains a validation quarantine.
6. **F-7:** empty thesis and provenance entry/value caps remain enforced.
7. **F-9:** a conflict response must equal the original response in full.

## Carry-forward register

- **F-8 → R7:** re-evaluate the 409 response fields once approval/conversion is mounted, including
  possible exposure of `approved_by` and `converted_*`.
- **F-10 → R5b-2:** reconcile the duplicate `SignalIngestResult` name and the exempt
  `app.api → app.store.base` dependency edge.
- **F-11 → R5b-2:** add route-level SQLite parity; the R5b-1 route corpus is memory-store only.

WO-0138 closes with `[RESULT_SUMMARY_KEPT, PKL_UPDATED]`; the Signal Seat changelog and append-only
ledger record this ingest-only rung. Facade reads, operator enforcement, lazy expiry, real rails,
and conversion remain later work. The Signal Seat flag remains OFF.

Per P-1, the reviewer-authored `result.md` and `result-addendum-01.md` were not edited; this
disposition is a separate close-out record.

**REV-0042 disposition: RESOLVED (initial BLOCK remediated; final verdict ACCEPT; WO-0138 CLOSED).**
