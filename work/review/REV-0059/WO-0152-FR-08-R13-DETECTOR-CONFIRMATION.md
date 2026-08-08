# WO-0152 FR-08 R13 detector confirmation

## Exact prerequisite

- Branch: `codex/arch-reset-2026-07-r1`
- Local HEAD before the rerun:
  `2208119083632ce26e58f966f6d7c3f3775f4aa7`
- Accepted R13 implementation manifest SHA-256:
  `b8fa0ab942ca32ec1a4aabb3c3f8d352ff33980437e72b456f26b5695ad11b8c`
- Independent R13 implementation result SHA-256:
  `2fead31818a1d826a3211a4dd2fa707656646d7a72cfb8a90f84c3b4f139b8fe`
- Verdict: `ACCEPT`, P0=0/P1=0/P2=0.

## Unchanged detector

- Path: `tests/execution_core/test_acquisition_stateful.py`
- SHA-256 before and after:
  `c89dc011c359d104d9a2ae851f0a649926e04ac596acf6da444eecbea1774186`
- Test:
  `test_e3_late_a_fill_after_b_first_fill_preserves_b_generation_authority`
- Command:
  `.\.venv\Scripts\python.exe -m pytest -q tests/execution_core/test_acquisition_stateful.py -k "late_a_fill_after_b" -p no:cacheprovider`
- Result: exit 0; one selected test passed.

The frozen public trace now confirms the bounded R13 root correction: B's
first canonical fill arms B protection, and a later retired-A fill is accepted
without replacing B's live generation authority. The detector was neither
edited nor staged for this confirmation.

## Disposition

The FR-08 B-first-fill stop is resolved locally. WO-0152 may resume only its
already accepted test-only E3 scope. WO-0151 and WO-0152 remain short of
effective closeout until the paired unchanged 93% exact-head Python 3.11 and
3.12 gate succeeds. This record grants no runtime, persistence, database,
broker, network, credential, M2, master-landing, deletion, cleanup, force-push,
or rebase authority.
