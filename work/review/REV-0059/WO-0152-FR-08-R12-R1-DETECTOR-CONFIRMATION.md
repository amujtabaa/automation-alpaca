# WO-0152 FR-08 detector confirmation after WO-0151 R12-R1

Status: **confirmed -- permits only the already active test-only E3 scope to resume**

## Preserved frozen inputs

| Artifact | SHA-256 before and after the run |
|---|---|
| `tests/execution_core/test_acquisition_stateful.py` | `1a7e685f954dc8de4424ad926285d993e0e9958eae2ce1a2f60af5b03689eb22` |
| `work/review/REV-0059/evidence.md` | `d018c2bddeec79fd624d1fbcb80dde91e49b5535f5db737120d88deb750c6ee7` |

The source module retains exactly three test functions. No source or evidence
artifact changed during this confirmation.

## Exact confirmation

- WO-0151 accepted remediation commit:
  `a3c15aa79d5b3ac17b8cc7d850eea8da8d2fb972`.
- Follow-on reconciliation base:
  `d3dab4f8b13c761beadbc88a40e2b1019b7e6bb0`.
- Command:

  ```powershell
  .\.venv\Scripts\python.exe -m pytest -q tests\execution_core\test_acquisition_stateful.py -p no:cacheprovider
  ```

- Result: exit code `0`; the three frozen public-contract controls all passed
  (`...` at 100%). The previously failing nonadjacent duplicate-stream
  successor control now returns the required refusal through the public path.

## Scope and disposition

This is a single unchanged rerun required by WO-0152 FR-08. It confirms the
bounded WO-0151 correction and permits only the existing test-only E3 work to
resume. It does not modify or re-freeze the detector, establish external CI,
satisfy the paired E2/E3 93% threshold, close WO-0151, authorize M2, or widen
runtime, database/SQL/DDL, broker/network, credential, merge, deletion,
cleanup, force-push, or rebase scope.
