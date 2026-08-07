# WO-0151 activation disposition

Status: **R11 R1 RATIFIED; DOCUMENTATION RE-GATE COMMIT PENDING**

[FABLE - FULL - verification: DIRECT plus independent review - task: WO-0151
activation and pure E2 implementation]

```yaml
fable_gate:
  goal: "Implement and independently close the pure WO-0151 E2 controller/recovery slice."
  assumptions:
    - claim: "WO-0150 is effectively CLOSED on its exact external CI head."
      status: VERIFIED
      evidence: "GitHub Actions run 31089203210, jobs 92575847934 and 92575848023."
    - claim: "R7/R8/R10 are retained activation provenance; the ratified R2--R11-plus-R11-R1 composite controls resumed implementation."
      status: VERIFIED
      evidence: "REV-0058 result-r10.md, result-r11.md (negative only), result-r11-r1.md, and the R11 R1 frozen manifest."
  approach: "Preserve the published activation record, reconcile the ratified R11/R11-R1 re-gate, write failure-capable RED controls, implement the smallest pure composite reducer, then run bounded and full acceptance gates."
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

## R10 ratification and controlling re-gate

The user ratified exact R10 contract
`081b0e7971912776f6722f037b89f907736b67367cafa340c98128a186a1bdd3`;
frozen manifest
`f8d25b3d32e23e3b672991a3d9538c9c5df2bbe2d439a7e4e9d75d8ecacf1f2b`;
and independent static `ACCEPT`, P0=0/P1=0/P2=0, result SHA-256
`dd91f3a1403658cf116767c534ad080daf47acc23458e899c6431db290d6c431`.
R10 controls the R2--R10 composite solely by replacing R9's impossible
copy-rejection control. R8 remains retained ratification provenance; R9 and
its initial acceptance remain retained but are not acceptance or ratification
authority. Scope and exclusions remain exactly those of the active work order.
No implementation, test, review, or external CI success is claimed by this
documentation-only reconciliation.

The exact documentation-only R10 re-gate commit is
`638c73cff1e02a8834309362cc5dc762b165871b`. It records only the frozen
packet and required current-posture/provenance reconciliation.

## R11 R1 ratification and controlling re-gate

The user ratified exact R11 body
`00f740561bceb036151ac984b45fd40ac6b4255e5b9c301d411ce7b90a7e526d`, exact R11 R1 correction
`d1931b28cad04f457d2e14233966d48789f758546950763e5a0417b07b80c2a9`, frozen manifest
`e31c34027be77f61eb027d9e5dd601bb2e95a0fb87ba6f73eae37b6eec9110c8`, and fresh independent
result `c3c04b6dd0b4c2c578b52ab49637be45bd31d3d79af6582c0949046993aa4d0b` (`ACCEPT`,
P0=0/P1=0/P2=0, affirmative route completeness).

R11 closes neutral refresh, terminality, applied-fact totality, combined retired-fact preemption,
and protection-exit constructibility. R11 R1 closes the initial R11 P1 by separating the private,
goal-independent `PREEMPT_BUY_ONLY` intent from fresh goal-bearing protective SELL exit. The
initial R11 `BLOCK` result remains retained negative evidence and is not an acceptance basis.
No new public authority source or policy writer is introduced. All existing scope and safety
exclusions remain in force. The exact documentation-only re-gate commit is pending.

## File-level check note

The new R7 and activation records pass whitespace checking. Older frozen
candidate manifests R0-R6 retain Markdown hard-break whitespace (and R5 its
existing terminal blank-line form) as part of their hash-pinned historical
evidence. They are intentionally not reformatted or rewritten.
