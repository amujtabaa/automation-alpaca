# WO-0152 E3 — nonadjacent market-stream disagreement evidence

Status: FROZEN E3 STOP — bounded E2 remediation required  
Date: 2026-08-07  
Owning semantic center: WO-0151 E2 acquisition-generation admission

## Exact local candidate

- Branch HEAD before this test-only RED change:
  `4e7e5807833acc604cf75231e2719078965e8ba6`.
- Untracked E3 test candidate:
  `tests/execution_core/test_acquisition_stateful.py`.
- Exact SHA-256 after adding the minimized control:
  `1a7e685f954dc8de4424ad926285d993e0e9958eae2ce1a2f60af5b03689eb22`.
- Test entry point: `test_e3_public_nonadjacent_duplicate_stream_successor_is_refused`
  at line 556; decisive refusal assertion at line 727.

## Reproduction

Command:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/execution_core/test_acquisition_stateful.py
```

Result: `2 passed, 1 failed`.

The test constructs before target genesis:

1. a fixed valid A/B positive mandate pair with distinct streams;
2. a fresh, sealed probe with distinct acquisition ID, protection ID, and dual-binding
   commitment but the exact retired-A stream; and
3. an authentic public same-account sibling-history bootstrap, public A genesis, and
   public aborted/no-root A-to-B successor transition.

Immediately before B-to-probe, the test proves current refresh, authentic bootstrap and
successor admission, matching scope/session/terms/emergency compatibility, fresh probe
identity/binding, and `probe.stream == A.stream != B.stream`. It uses no generic BUY,
terminal fixture, private closure, post-setup object mutation, or history scan.

Expected result: `REFUSED`, retaining B's state, authority, venue, execution, protection,
and no effect/claim.

Observed result: `APPLIED` at the refusal assertion. The public reducer therefore admits a
new successor that reuses a retired generation's market-stream authority.

## Static attribution and disposition

`begin_acquisition_generation` compares candidate stream identity only with the immediate
predecessor at `app/execution_core/acquisition.py:3957-3958`; it has no direct bounded
all-generation stream-ownership representation. The B-to-probe stream differs from B, so
the current gate admits it even though it duplicates retired A. This conflicts with the
serial non-reuse requirements in ADR-020 R2 and ADR-021 R2 and is a P1 E2 semantic defect.

Per WO-0152 FR-08 and R2-R5, E3 stops here. This evidence does not authorize a production
change, weaken the RED assertion, mark it expected failure, reuse a stream in the positive
chain, or introduce an E3-only guard. The next action is a bounded E2 re-gate that keeps
stream ownership in a direct sealed index/provenance relation rather than scanning retained
history.
