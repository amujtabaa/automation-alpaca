# REV-0075 R10 — independent result

Exact source candidate reviewed: `341498c55af7a7f807c11be7287bd243c57aa8b8`, tree
`890015aa5816938d255893ba4ebd21da4b26fea3`.

## P1 — Public checkpoint envelope survives the R13-R1 non-serving boundary

- Location: `app/execution_core/persistence/checkpoint_codec.py:30`, `:544`
- Mechanism: `RuntimeCheckpointEnvelope` remains a public exported symbol, despite R13-R1
  reserving every public envelope surface to R13-C.
- Impact: Reopens a prohibited checkpoint-payload API surface before complete owner hydration is
  defined.
- Smallest complete root correction: Remove the envelope class/export from the R13-S surface and
  add a pure non-export control.
- Evidence: `reasoned-only`

## P1 — Deferred directness fixture still calls retired APIs and omits capabilities

- Location: `tests/execution_core/test_persistence_directness.py:97`, `:220`, `:245`
- Mechanism: The candidate removes public `store_kernel_checkpoint`,
  `advance_kernel_checkpoint`, and `load_kernel_checkpoint`, but this allowed fixture still
  references them. Its remaining repository mutator calls also omit the now-required
  `capability=` keyword.
- Impact: The deferred directness suite will fail with missing attributes and cannot validate the
  required setup-capability boundary.
- Smallest complete root correction: Update this fixture to use the named setup-support issuer for
  every remaining mutator, and remove/rederive checks for the intentionally retired
  kernel-header APIs.
- Evidence: `reasoned-only`

## Verdict

**ACCEPT-WITH-CHANGES** — P0=0, P1=2, P2=0.

Unverified: SQLite-bearing schema/repository/directness tests and static DDL execution; Ruff,
format, and mypy. No runtime composition, network, credentials, broker, or order paths were
invoked. The permitted pure pytest command passed.
