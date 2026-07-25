---
type: Review Result
rev_id: REV-0041
title: "WO-0137 — Signal Seat R5a composition-root foundation"
reviewer_seat: Claude (independent review seat; implementer was Codex)
review_head_sha: d78e54fda6a780546cd6892078b209f9ae33438f
review_range: 47a0d9f4e8bba5abc0feff3d029b04c8ace82dd3..d78e54fda6a780546cd6892078b209f9ae33438f
branch: codex/signal-r5a-foundation
human_gated_surfaces: [auth-launcher, transport-bind]
verdict: ACCEPT-WITH-CHANGES
reviewed: 2026-07-24
---

# REV-0041 — result

## Method (three independent verifications)

This review re-derived the named properties from code and **fresh local evidence**, not the
author's reported numbers. Three independent passes:

1. **Review-seat direct** — fresh POSIX (`Linux`, `uvicorn==0.51.0`, `pytest 9.1.1`) run of the R5a
   corpus; two red-green control mutations (revert control → pin RED → restore → GREEN); one-use
   stability ×3; structural scope/leakage audit. (The launcher's real deployment target is POSIX,
   so this complements the author's Windows evidence from the other side.)
2. **Fresh-context capability-boundary auditor** — static trace **plus dynamic execution** of
   hand-written adversarial probes and the repo's own regressions against the reviewed code,
   including a genuine `uvicorn.Config(...).load()` reproduction of the three reacquisition vectors.
3. **Fresh-context test-integrity / disposition-boundary reviewer** — inert-pin sweep, D1 no-drift
   diff, D2 no-production-path check, authorized-edit confinement, TDD/evidence discipline.

Defensive assurance of the operator's own local paper-only application. Findings are reported at the
defect level; no reusable bypass procedures appear here. The feature flag remains OFF; this packet
authorizes review only — not enablement, merge, close-out, or beta reliance.

## Property verification

| # | Property (ADR-009 A-1/A-4, spec 04 §1, WO-0137) | Verdict | Independent evidence |
|---|---|---|---|
| 1 | Recognizer accepts only the exact `_LaunchCapability` type (not `isinstance`) | VERIFIED | `app/launch_guard.py:158,184`; live subclass rejection reproduced; defense-in-depth (see F1) |
| 2 | Host/UDS + 3 credential strings validated as exact `str`; budget/TTL exact `int` | VERIFIED | `app/launch_guard.py:52,58`, `app/config.py:443,455,460,478,484`; `EvilStr` subclass rejected at every position; `type(x) is int` rejects `bool`; **red-green: reverting `config.py:443`→`isinstance` turns `[operator-key]` RED** |
| 3 | Issuance tracked by exact object identity (id-keyed weak registry, `is`) | VERIFIED | `app/launch_guard.py:112-115,162-163`; `object.__new__` rejected; **red-green: neutering `:162` turns the identity pin RED** |
| 4 | Validate-and-retire atomic under one lock (no check-then-pop race) | VERIFIED | `app/launch_guard.py:115,180-189`; 16-thread barrier → exactly 1 success, ×3 consecutive (both reviewers) |
| 5 | Capability reacquisition via importable factory rejected (factory / bare-load / zero-arg) | VERIFIED | `tests/signal_seat_helpers.py:55-76`; live `uvicorn.Config(...).load()` on all three vectors raises before any `FastAPI` is built; positive control still returns a real app |
| 6 | Replay prevention: flag-off capability re-validated against current settings | VERIFIED | `app/launch_guard.py:166-174`; `consume_launch_capability` requires `settings` (no default); flag-off-minted public bind rejected under flag-on settings |
| 7 | Capability immutable + mint-token gate | VERIFIED | `app/launch_guard.py:79,91-95,100-101`; `cap._host=...`→`AttributeError`; wrong-token construct→`RuntimeError`; scope limit (not a sandbox vs hostile in-repo code) honestly disclosed at `:21-24` |
| 8 | Module-level `app` absent under the flag (bare-uvicorn fails pre-bind) | VERIFIED | `app/main.py:213-220` `globals().pop("app", None)` incl. reload-safety; POSIX launcher corpus (bare-uvicorn no-listener + exact `Attribute "app" not found`) green 9/9 |
| 9 | `validate_transport_bind` returns the A-1 reason for non-loopback/non-UDS under BOTH policies | VERIFIED | `app/launch_guard.py:40-73`; `0.0.0.0` rejected identically under `loopback` and `tailnet_serve`; UDS accepted under both; policy-name-agnostic by design (D-R5a-6) |
| S | Scope confinement — no R5b/R6/R7 leakage, no `.importlinter`/schema/event-log change | VERIFIED | Range touches only the 6 authorized impl files + the test corpus + README/WO/state; `.importlinter` untouched; the lone `X-Producer-Key` hit is an error-message string, not request-time wiring |

## Fresh execution evidence (this review, not the author's numbers)

- Review-seat POSIX: `test_signal_seat_config.py` 23 · `test_signal_seat_launcher.py` 9 ·
  `test_signal_seat_launch_guard.py` 18 · `test_import_boundaries.py` 6 → **56 passed**.
- Red-green (control ↔ pin): identity control `launch_guard.py:162` and exact-`str` control
  `config.py:443` each turn their named regression RED when reverted, GREEN when restored.
- One-use control: exactly-one-success across 3 consecutive isolated runs.
- Capability-boundary auditor (separate sandbox, real uvicorn 0.51.0): config 23 · launcher 9 ·
  guard 18 green, incl. live reproduction of all three factory-reacquisition vectors rejecting.

## Findings (defect level; all ACCEPT-WITH-CHANGES — none meets a BLOCK condition)

**C-1 — non-decisive regression pin is structurally inert (test quality; MEDIUM).**
`tests/test_signal_seat_launch_guard.py:117-133` — `assert is_sanctioned(CapabilitySubtype()) is False`
(line 133) passes regardless of whether the exact-type control at `app/launch_guard.py:158` exists,
because the unregistered subtype is also rejected by the identity check at `:162`. The security
*property* (no subtype is sanctioned) holds via defense-in-depth, and the `BindText` half of the same
test (`:127-132`) IS tied to `validate_transport_bind`'s exact-`str` host check — but the exact-type
control lacks an isolated decisive pin. *Resolves by:* registering the subtype instance in
`_ISSUED_CAPABILITIES` (or otherwise forcing the identity lookup to succeed) before asserting
rejection, so the exact-type check is the thing under test. Independently corroborated: a review-seat
mutation of `:158`→`isinstance` did **not** move this test.

**C-2 — `signal_transport_policy` validated with `isinstance`, not exact `str` (uniformity; LOW).**
`app/config.py:490` uses `isinstance(settings.signal_transport_policy, str)` while every other
credential/config field in the same function uses `type(x) is str`. Currently **inert** — the policy
value never drives the bind decision (`validate_transport_bind` is policy-name-agnostic, property 9),
only closed-set membership + message interpolation — so a spoofing subclass has nothing behavioral to
exploit today. D-R5a-4's string-hardening clause names `signal_transport_policy`; the Part-B execution
step narrowed to the three credentials, so this is a residual of the broader clause. *Resolves by:*
aligning `:490` to `type(x) is str` and extending the str-subclass config test to cover the policy
position — **before** any future (R5b) policy-value-dependent branching — or recording the accepted
rationale in the WO. Independently found by two reviewers.

**C-3 — FIX-block evidence wording overstates committed-test verification (evidence integrity; LOW-MED).**
`work/active/SIGNAL-R5a-STATE.md` FIX blocks (attempts 2/3 of the capability hardening) carry
`red_green_verified: true`, while the hardening landed in `a410546` (2026-07-23 12:39, no test file
touched) and the formal regression tests landed in `d78e54f` (~14.6h later). This is **not a
fabrication** — each block's `evidence` field honestly discloses the RED was shown by *live controls*
("`RED_PUBLIC_REUSE True ACCEPTED`", "independent disproof … 16-worker pre-fix consume admitted more
than one caller"), i.e. a real live red→green cycle, and the retro-add of committed regressions was
authorized by the operator's Part-B/D1 disposition (a security find→fix→lock sequence). But
`red_green_verified: true` reads as "a committed test pre-existed the fix." *Resolves by:* qualifying
those blocks as `verification: live-control (committed regression added in d78e54f)` so the ledger
does not overstate. No code change.

**C-4 — disposition record should enumerate the full authorized-edit surface (traceability; LOW).**
The "exactly three staged-test edits (D-R5a-3, D1, D2)" framing describes only the *modifications to
immutable staged tests*. The range also contains authorized **additive** work: the new adversarial
regression tests (under D-R5a-4/D-R5a-7 + Part-B) and the `test_import_boundaries.py`
`_SANCTIONED_*` hunk (pre-authorized by D-R5a-1/D-R5a-10). All traceable to `SIGNAL-R5a-STATE.md`;
none alters or weakens an existing staged assertion. *Resolves by:* enumerating all authorized-edit
classes in the close-out disposition rather than "three edits."

## Forward-looking (R5b — not an R5a finding, record as a requirement)

**R5b-N1 — producer-map container type.** `validate_signal_seat_settings` checks
`isinstance(producer_keys, Mapping)` at the container level (keys/values are exact-`str`-checked via
`.items()`). `load_settings()` always builds a plain `dict`, so construction-time validation is
sound. However, a directly-injected hostile custom `Mapping` could present `.items()` differently
from whatever request-time lookup (`.get()`/`in`) authenticates `X-Producer-Key` — and that consumer
is **R5b**. R5b must validate the producer map as an exact `dict` (or re-derive a trusted `dict`)
at the request-time auth seam. Recorded here as an R5b requirement; out of scope for R5a's
construction-time boundary.

## Disposition-boundary confirmations (no drift)

- **D1** — `tests/test_signal_seat_launcher.py` diff is confined to `import os`, semantically
  identical assert reformatting, `_sanitized_child_env()` (exact-removal `{OPERATOR_API_KEY,
  STATE_STORE, MARKET_DATA_FEED, ENABLE_TAPE_RECORDER}` + prefix-removal `("SIGNAL_","BROKER_",
  "ALPACA_")`), and `timeout=15`. No bind/UDS/exit-code/no-listener/diagnostic assertion changed.
- **D2** — `_IN_PROCESS_TEST_AUTHORITY = object()` lives only in `tests/`; zero `app/` references;
  all `build_flag_on_app` call sites pass it explicitly. No production authority path.
- **D3** — only the 11 R5a-owned Python files formatted; the 10 inherited baseline files recorded
  in `SIGNAL-R5a-STATE.md` are untouched; the R2 oracle runs via the CI module invocation, content
  unchanged.

## Not independently reproduced by this review (disclosed)

- The full-suite non-regression (4,327 tests, exit 0): the review ran the R5a subset (56) green and
  reasoned flag-off byte-equivalence from `app/main.py:213-220`; the full suite was not re-run here
  and is relied on from the author's exit-0 plus the flag-off construction path.
- `lint-imports` contract gate: the review ran the import-boundary *test* (6 green); the standalone
  `lint-imports` (6 kept / 0 broken) is relied on from the author's evidence + CI.
- REV-0027 F-1/F-2/F-3 (request-time principal binding, quarantine normalization, malformed-identity
  namespace) are R5b/R7 surfaces; none appears in this range (no scope leakage).

## Verdict

**ACCEPT-WITH-CHANGES.**

The R5a construction-time launch/capability boundary — the human-gated safety surface this packet
protects — is **sound**. All six named defect classes (exact-type recognition, identity-based
issuance, atomic one-use, factory-reacquisition, replay-prevention, immutability/mint-gate) and the
module-`app`-absence and dual-policy bind properties hold under independent static trace **and** fresh
live execution across three verifications, including genuine `uvicorn` reproduction of the
reacquisition vectors. Scope is confined; no R5b/R6/R7/`.importlinter`/schema/event-log leakage; the
flag stays off.

No finding meets a BLOCK condition: no safety-invariant breach, no enabled construction without exact
fresh one-use authority, no non-private enabled bind, no selectable unauthorized factory, no weakened
or inert **decisive** regression (C-1's inert pin is redundant defense-in-depth; the decisive control
is separately pinned), no unapproved scope expansion, and completion evidence **was** reproduced.

The four ACCEPT-WITH-CHANGES items (C-1 isolate the exact-type pin; C-2 exact-`str` transport policy;
C-3 FIX-block wording; C-4 authorized-edit enumeration) are bounded quality/evidence/documentation
follow-ups for the implementer seat; they do not gate the security boundary but should land before
the D-2a milestone relies on this foundation. R5b-N1 is recorded as an R5b requirement.
