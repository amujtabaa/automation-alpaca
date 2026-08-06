# WO-0151 activation disposition

Status: **R7 ACTIVATION RECORDED; R8 RE-GATE RECONCILED AT EXACT DOCUMENTATION COMMIT**

[FABLE - FULL - verification: DIRECT plus independent review - task: WO-0151
activation and pure E2 implementation]

```yaml
fable_gate:
  goal: "Implement and independently close the pure WO-0151 E2 controller/recovery slice."
  assumptions:
    - claim: "WO-0150 is effectively CLOSED on its exact external CI head."
      status: VERIFIED
      evidence: "GitHub Actions run 31089203210, jobs 92575847934 and 92575848023."
    - claim: "The R7 contract is retained activation provenance; the ratified R8 contract controls resumed implementation."
      status: VERIFIED
      evidence: "REV-0058 result-r7.md, result-r8.md, and the R8 frozen manifest."
  approach: "Preserve the published activation record, reconcile the ratified R8 re-gate, write failure-capable RED controls, implement the smallest pure composite reducer, then run bounded and full acceptance gates."
  alternatives_considered:
    - "Do not bypass the activation record or use a draft-contract implementation path."
  out_of_scope:
    - "Runtime wiring, persistent database, SQL/DDL, broker/network activity, credentials, M2, master merge, deletion, cleanup, rebase, and force-push."
  done_when:
    - behavior: "Every WO-0151 functional requirement is covered by a failure-capable RED-to-GREEN control."
      test: "Focused, execution-core/R2, generated/stateful, branch-coverage, and independent-review gates."
      command: "Recorded only after each authorized gate runs."
  blast_radius: "The six execution-core source files and six named test files in the active work order, plus required lifecycle records."
  rollback: "Preserve exact commits and retained review evidence; refuse invalid inputs without state mutation."
```

## Reconciled prerequisites

- The tracked worktree is clean. The only pre-activation delta is the retained
  `REV-0058` documentation packet; no source, test, ADR, PKL, ledger, or
  lifecycle record was changed during its static review.
- `HEAD` and `origin/codex/arch-reset-2026-07-r1` are both
  `f1a40d69f301ad7f594a61f202d3bd380607b98a` before this activation delta.
- WO-0150 is effectively `CLOSED`: GitHub Actions run `31089203210` (#726)
  completed `success` on exact SHA
  `f1a40d69f301ad7f594a61f202d3bd380607b98a`; job `92575847934` (Python
  3.11) and job `92575848023` (Python 3.12) both completed `success`.
- The immutable R7 contract SHA-256 is
  `c82ab206d154cdcccf06794e139966724f7a814d4d2201a4fdf27bf3d7cbcb1e`.
  Its manifest SHA-256 is
  `4c4f4d7387c0ab27358fbf3b63dfc1049c81cfbd0eaeca065568db6dab019b99`.
  `result-r7.md` SHA-256 is
  `d4f95b2b454b9f80ebd30382a7cfca3f5ad1ea68cf6e37fb8fdc420d89923794` and
  records independent `ACCEPT`, P0=0/P1=0/P2=0.
- WO-0152 remains DRAFT/inactive. WO-0154 is a separate filesystem-cleanup
  work order in REVIEW; it grants no M1 product authority and no cleanup work
  is included here.

## Activation scope

The user's explicit remaining-M1 authorization activates only this exact
WO-0151 under its R2+R3+R4+R5+R6+R7 contract and its enumerated allowed paths.
The implementation is pure, deterministic, I/O-free E2 only. RED tests must
precede production changes. R7 does not authorize a new architecture, runtime
wiring, persistence, SQL/DDL, broker or Alpaca activity, credentials, M2,
master merge, deletion, or cleanup.

The exact documentation-only activation commit is
`466e712b6f507ee165a7fc0c80e826fa8a35a710`. It was pushed and then verified
against the live `refs/heads/codex/arch-reset-2026-07-r1` ref before this
append-only reconciliation. No implementation or test execution may begin
until this record is committed.

## R8 ratification and controlling re-gate

On 2026-08-06, the user ratified the exact R8 contract SHA-256
`d6a0295f14652222d9fa05e1f826e77ecd306c07dbf1b8faf4525976396eec1f` and
authorized the corresponding WO-0151 R8 re-gate. Its independent static
pre-flight result, retained at `result-r8.md`, is `ACCEPT` with P0=0, P1=0,
and P2=0; the exact candidate manifest is
`b6faddc624a227382f80ebefe57044ce2e2e372328df3528e027fc4bcd924311`; the
review result SHA-256 is
`5dc43bcaab99af837ee89e83880a1484cb79f649ea67e7218e5a2dd798699e80`.

R8 now controls the active RED/test/production path. R7's accepted contract
and the documentation-only activation commit remain historical provenance, but
they do not authorize a different bootstrap representation. The only new
semantic authority is the frozen R8 body: an owner-sealed target-local
`UNBOUND_BOOTSTRAP`, its neutral checkpoint proof, first specialized-request
promotion, and generic `CreateBrokerEffect(BUY)` refusal while the bootstrap
record is active. The pre-existing source/test WIP is not acceptance evidence;
it remains subject to R8 RED controls and the later independent review. No
SQL/DDL, database, runtime, broker/network, credentials, M2, merge, deletion,
cleanup, force-push, rebase, or later work-order activation is authorized.

The exact documentation-only R8 re-gate commit is
`07f169bb6630753b4e12960738e4fb0533686ada`. Its delta contains only the frozen
R8 packet and required active-WO, PKL, ledger, and activation-disposition
reconciliation. It contains no source or test implementation and does not
constitute implementation acceptance evidence.

## File-level check note

The new R7 and activation records pass whitespace checking. Older frozen
candidate manifests R0-R6 retain Markdown hard-break whitespace (and R5 its
existing terminal blank-line form) as part of their hash-pinned historical
evidence. They are intentionally not reformatted or rewritten.
