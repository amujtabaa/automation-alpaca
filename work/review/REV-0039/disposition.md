---
type: Review Disposition
rev_id: REV-0039
verdict_received: ACCEPT-WITH-CHANGES
disposition_status: RESOLVED
date: 2026-07-22
remediated_by: "27bcfbd (F1 + F2 pins, tests-only)"
implementation_sha: "b87d464 (WO-0134 R4); pins 27bcfbd; re-verified at b9ebc9b"
---

# Disposition — REV-0039

REV-0039 (reviewer: Claude, independent of the Codex implementer) reviewed WO-0134's Signal Seat R4
model + dual-store persistence + replay-parity work and returned **ACCEPT-WITH-CHANGES**: the
implementation is correct and in scope — the committed `signal_records` DDL and `_migrate` guard
match the operator-approved package with **zero deviation**; both stores are atomic, restart-stable,
and replay-exact under fresh hostile probes; positions are structurally untouched (INV-1/INV-9); and
10 of 12 reviewer mutations were killed by committed pins. Two required tests-only changes:

- **F1** — the aggregate replay-parity registration was unpinned: removing
  `signals=project_signal_records(...)` from `project_read_models` left the suite green. Fix must add
  a `signals` perturbation to the comparator test and one aggregate parity test that ingests a real
  signal on both stores.
- **F2** — the memory `_atomic` signal-state rollback was unpinned: removing
  `self._signals = saved_signals` left the suite green. Fix must add a memory-store fault-injection
  twin of the SQLite atomicity test.

**Both remediated by `27bcfbd`** (tests-only; `git diff app/` over the pin range is empty):
`test_signal_ingest_participates_in_dual_store_readmodel_parity` +
`test_compare_read_models_detects_divergence` signals case (F1);
`test_memory_signal_event_and_record_rollback_together` (F2).

**Independently re-verified by the Claude seat at `b9ebc9b`** (pinned Python 3.12 venv, quiet
machine): baseline the three new pins pass; then the two reviewer mutations were re-applied —

- **M7a** (remove the `signals=` registration from `project_read_models`) → **both F1 pins RED**
  (the comparator no longer sees the diverging signal; the aggregate ingest projects empty
  `.signals`).
- **M4a** (remove `self._signals = saved_signals` from memory `_atomic`) → **F2 pin RED** (the
  injected post-write failure leaves the `SignalRecord` un-rolled-back).

Both source files restored byte-clean (`git diff` empty), tree clean. Both touched test files pass
in full on both stores; `ruff check`/`ruff format --check` clean on the new test code (the bounded
10-file exception did not expand).

F3–F6 remain recorded as **R5 planning inputs**, non-blocking for R4: F3 (hypothesis injectivity
strategy hardening), F4 (never-born-record projector no-op — pin or promote in R5), F5 (memory
snapshot shallow-copy constraint R5 must inherit), F6 (the R5 ingest route must copy EVERY raw
offending field into `raw_fields` or malformed proposals hash-collapse).

**REV-0039 disposition: RESOLVED.** Per P-1, this reviewer-authored result was not edited; this
disposition is a separate record.
