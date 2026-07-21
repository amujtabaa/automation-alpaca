# WO-0128 Signal Corpus Slice Map

Status: **RED BY DESIGN** on `codex/signal-tests-staging`. This branch is not mergeable until
each listed implementation WO turns its owned slice green. The red corpus was rebased against the
WO-0127 Proposed text; archive review identifiers remain provenance only.

| Test asset | Primary owner | Preconditions / green condition |
| --- | --- | --- |
| `tests/test_signal_seat_models.py` | R4 — model/store | Add the signal model vocabulary and FILL-only safeguards. |
| `tests/test_signal_ingest_store.py` | R4 — model/store | Add dual-store ingest/dedupe, event writes, and projector/replay registration. |
| `tests/test_signal_projector_forward_compat.py` | R4 — model/store | Add the signal read-model fold with forward compatibility. |
| `tests/test_signal_quarantine_totality.py` | R4 — model/store | Rebuild the planner constants and total quarantine behavior from the amended ADR. |
| `tests/test_signal_facade_reads.py` | R5 — endpoint/auth/launcher | Wire the typed signal facade to the R4 store seam with injected-clock expiry. |
| `tests/test_signal_malformed_input_matrix.py` | R5 — endpoint/auth/launcher | Mount the body-blind endpoint and flag/key matrix; R6 rails remain a prerequisite for success paths. |
| `tests/test_signal_routes.py` | R5 — endpoint/auth/launcher | Mount routes, schemas, auth and cockpit plumbing; R6/R7 behavior remains a prerequisite for later cases. |
| `tests/test_signal_seat_config.py` | R5 — endpoint/auth/launcher | Add the approved flag/key/transport configuration parsing. |
| `tests/test_signal_seat_launch_guard.py` | R5 — endpoint/auth/launcher | Add the construction-time capability and bind guard. |
| `tests/test_signal_seat_launcher.py` | R5 — endpoint/auth/launcher | Add `app.server` / `python -m app` with loopback/tailnet policy. |
| `tests/test_cockpit_operator_header.py` | R5 — endpoint/auth/launcher | Ship X-Operator-Key cockpit plumbing in the same enforcement flip. |
| `tests/signal_seat_helpers.py` | R5 then R6 | Helper composes the R5 application seam and R6 real dual rails. |
| `tests/test_import_boundaries.py` hunk | R5 — endpoint/auth/launcher | Add only the `app.server` / `app.__main__` composition-root allowlist entries with launcher code. |
| `tests/test_phase6_facade_foundations.py` two-test hunk | R5 — endpoint/auth/launcher | Make authenticated `get_actor` authoritative and sanitize audit sublabels. |

## Red evidence

2026-07-21 OS-temp collection reported 51 already-collectable tests:
cockpit header (4), import boundaries (6), facade foundations (21), and signal config (20).
The remaining ten imported test modules stopped only on missing planned implementation symbols:
`app.facade.signal_rails`, `app.facade.signals`, `app.events.projectors.project_signal_records`,
signal TTL constants, `app.server`, `app.launch_guard`, and signal model vocabulary. These
ImportErrors are the intended R4/R5 implementation boundary, not fixture or syntax failures.

No implementation, documentation, CI, or master-branch files were altered. Do not weaken these
tests; merge each slice only with the corresponding green implementation WO.

