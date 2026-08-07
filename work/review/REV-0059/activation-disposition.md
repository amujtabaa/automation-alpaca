# WO-0152 activation disposition

Status: **R2-R3 ACCEPTED — DOCUMENTATION-ONLY ACTIVATION PENDING EXACT SHA RECONCILIATION**

[FABLE - FULL - verification: DIRECT plus independent review - task: activate the bounded test-only E3 proof layer]

```yaml
fable_gate:
  goal: "Activate only the frozen WO-0152 test-only E3 conformance work."
  assumptions:
    - claim: "WO-0151 remains effectively REVIEW after functional/static run #741 failed only the unchanged 93% coverage gate at 91.34%."
      status: VERIFIED
      evidence: "Run #741 / ID 31185454392, exact SHA a2b84abc1914517cf591f27fb88f0b20b2a47ef7."
    - claim: "The exact R2-R3 RED composite independently ACCEPTed with no P0/P1."
      status: VERIFIED
      evidence: "Contract 881334b4af6acb566adc57c30a4199f0340129d244cc3d58536c8e7c109a9936; manifest ee5554bf4e6b380fa7c687324adba7f93168e56168fb84cedf519115e4b7c3f6; result 8752e20fa0aba82885d1d49ae8eabca9901218f5659073adcb4324fa9b189a59."
  approach: "Publish this documentation-only lifecycle move, then record its immutable Git SHA before creating the single permitted E3 test module."
  out_of_scope:
    - "Production/API changes, runtime wiring, persistent database or SQL/DDL, broker/Alpaca/network activity, credentials, CI workflow changes, M2, master merge, PR, deletion, cleanup, force-push, and rebase."
  done_when:
    - behavior: "The active work order, current posture, provenance, ledger, and exact activation SHA agree."
      test: "Static scope, disposition, ledger, PKL, hash, and diff checks."
      command: "Recorded after the documentation-only commit and SHA reconciliation."
  blast_radius: "WO-0152 lifecycle/provenance records only; no source or test implementation."
  rollback: "Preserve the activation commit and all frozen preflight evidence; do not begin E3 source work if the SHA cannot be reconciled."
```

## Reconciled prerequisites

- Local branch: `codex/arch-reset-2026-07-r1` at base
  `a2b84abc1914517cf591f27fb88f0b20b2a47ef7` before this activation delta.
- The R2-R3 contract, manifest, and independent result hashes are exact as listed in the Fable gate.
- `tests/execution_core/test_acquisition_stateful.py` was absent before this activation change.
- The R2-R3 result is an independent static `ACCEPT`, P0=0/P1=0/P2=0. It does not itself claim
  dynamic E3 evidence, CI success, WO-0151 closure, M1 completion, or operating authority.
- A non-mutating live remote query was unavailable in this environment because Git reported
  `SEC_E_NO_CREDENTIALS`; the local remote-tracking ref matches the local base, but no live remote
  claim is made here. A normal authorized branch push will be attempted after the local activation
  commit without any credential workaround.

## Activation boundary

This change moves WO-0152 to `work/active/` and grants only its frozen test-only E3 scope after
the exact activation commit is recorded. The four named test-only helpers and their lexical limits
remain controlling. The single allowed test module remains absent in this change. Nothing here
changes production source, public APIs, accepted ADR bodies, runtime behavior, database behavior,
or the unchanged paired E2/E3 93% closeout gate.

## Exact activation SHA

This field is intentionally pending until the documentation-only activation commit exists:
`PENDING_DOCUMENTATION_ONLY_ACTIVATION_SHA`. A follow-up documentation-only reconciliation must
replace it with the exact local commit SHA before any E3 test source is created or run.

## File-level check note

The scoped cached whitespace check for the active WO and current lifecycle/provenance records
passes. A full cached `git diff --check` emits only existing Markdown hard-break or terminal blank
line diagnostics in retained, hash-pinned REV-0058/REV-0059 artifacts. Those frozen artifacts were
independently re-hashed before activation and are not reformatted; their historical byte identity is
more important than normalizing pre-existing presentation whitespace.
