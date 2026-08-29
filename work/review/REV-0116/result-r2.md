# REV-0116 R2 — fresh correction-only architecture review

## Review binding

- Repository/branch: `automation-alpaca` / `codex/m2-wo0169-startup-cold-recovery-r1`
- Published HEAD: `469bc2e077a34e93d74f14dccd02abafe0a9d5e6`
- Reviewed candidate: `54f9474b9277a4c69272df3c402e64e8058b4ac5`
- Candidate tree: `3d14c2d40ab4594e0fc3383dd96ed8afa930b975`
- Accepted predecessor: `c390c1b1de7ee0f88f6c8a3b4419e8fa122aec51`
- Predecessor tree: `de844054db45d03c73889d986185cab651cbc386`
- Corrected active-WO blob: `d2ff4b90bae5d635d8bbe30735ccf44035de526f`
- Corrected active-WO SHA-256: `93a278f12ac712f42379c9504645a266bc12236540c25a95a34e46bcd585d0fd`
- Mode: read-only static architecture review. No SQLite access, database creation, DDL execution,
  held suites, edits, commits, or pushes.

Git-object verification showed that the correction commit changes only the active WO and adds
`root-correction-r2.md`. The accepted predecessor files and the three inspected source seams are
byte-identical between predecessor and candidate. `operations.py` is also unchanged. `schema.py`
retains blob `164de10ad9fef6ce37324840aff59b5b68c07d2a`; the accepted predecessor binds that blob to
190,705 DDL bytes at SHA-256
`d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`.

### [P1] R2 schedules reconciliation before an admissible compact UOW context exists

- Location: `work/active/WO-0169-m2-i5-startup-reconciliation-cold-recovery.md:152`
- Requirement: The accepted predecessor makes the checkpoint non-serving, does not claim that
  history-shaped commitments are reproducible, and assigns WO-0169 the bounded behavioral-
  commitment cutover (`WO-0168c:123-134,145-153`). WO-0168 additionally requires an
  operation-keyed direct proof before a reducer reads omitted owner state
  (`WO-0168:103-118`).
- Evidence (`static-reasoning`):
  - The predecessor conflict is independently reproduced. A loaded envelope remains inert and has
    no owner preimage (`checkpoint_codec.py:1210-1299`), while the execution component retains
    seen-fact and map commitments but not the corresponding historical entries
    (`checkpoint_codec.py:5565-5595`). Byte-identical reconstruction of the former serving owner is
    therefore unavailable without replay or a digest/default-empty bypass.
  - R2 correctly requires compact non-serving owners and says no restored candidate is authority
    before the compact cutover commits and is reread
    (`WO-0169:154-182`).
  - Nevertheless, exact sequence step 4 applies queried venue-recovery items through M2-I4
    (`WO-0169:216-220`), while the compact cutover and invalidation do not occur until step 6
    (`WO-0169:221-223`).
  - The accepted M2-I4 path projects the supplied owners and refuses unless the resulting bytes
    exactly equal the retained checkpoint (`unit_of_work.py:567-584,665-683`). R2 compact owners
    intentionally derive new commitments, so they cannot satisfy that C0 equality.
  - An applied `VenueRecoveryOperation` can mutate relational authority and must store a successor
    checkpoint in its own transaction (`unit_of_work.py:5019-5177`). It therefore cannot simply be
    deferred while step 6 later performs the supposedly atomic compact-cutover/invalidation
    successor.
  - The only newly authorized private transition applies the compact cutover plus invalidation
    together (`WO-0169:186-204`); the contract defines no pre-step-4 private reconciliation seam
    that closes this ordering gap.
- Impact: A valid C0 checkpoint with an unresolved effect whose targeted query returns an applied
  venue-recovery item has no conforming route. Compact owners fail the retained-C0 authentication;
  preserving the unreconstructable old commitment restores the bypass R2 was meant to remove; and
  allowing reconciliation to persist the compact successor first breaks the required atomic
  cutover-with-invalidation boundary. Startup therefore remains non-serving for a central
  FR-4/CR-09/CR-10 recovery case. This is caused by R2: removing R1's byte-identical owner premise
  removed the context on which the unchanged pre-cutover reconciliation ordering depended.
- Resolution: Amend the exact sequence so a compact checkpoint is committed and reread before the
  first M2-I4 reconciliation mutation. Preserve a final idempotent cold-invalidation boundary after
  reconciliation and before any source call—for example, invoke the private compact-cutover/
  invalidation bridge before reconciliation and re-invoke its invalidation check after
  reconciliation, with exact replay when nothing changed. Add a failure-capable C0-plus-unresolved
  case whose venue-recovery item produces `checkpoint_changed=True`, together with rollback,
  commit-ambiguity, and source-refusal/retry controls.

Verdict: ACCEPT-WITH-CHANGES
P0: 0
P1: 1
P2: 0
Unverified: NONE
