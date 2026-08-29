# REV-0116 R3 — same-seat compact-cutover correction verification

## Review binding

- Repository/branch: `automation-alpaca` / `codex/m2-wo0169-startup-cold-recovery-r1`
- Published HEAD: `7e5e448fcc3b3b2f21e9cfd7cd13a7dd517c0f1a`
- Corrected candidate: `47306fe81fb9f279e6190f00ae5241eef7f9203a`
- Candidate tree: `448cc6aabce8674e5e77f9b26521fc1894b222f6`
- R2 candidate: `54f9474b9277a4c69272df3c402e64e8058b4ac5`
- R2 tree: `3d14c2d40ab4594e0fc3383dd96ed8afa930b975`
- Corrected active-WO blob: `73e835944d516a5a38e8c1e9fa0f51091cdd53af`
- Corrected active-WO SHA-256: `759b3d386ce4aeca3c5e9f6292be14a570af68d4cc6a34f204eb4319639a389f`
- R2 result blob: `7670e04f466b99e9751511fb8d44648a3e17a541`
- R2 result SHA-256: `a17876c18da25638da0b03dda80f73ba789702c48a38165c7352fda7f55b8beb`
- Mode: read-only, correction-only static verification. No SQLite/database access, DDL execution,
  held suites, edits, commits, or pushes.

## Findings

No findings.

## Verification evidence

The accepted R2 P1 is closed:

- The corrected contract requires the normalized compact-owner successor and cold invalidation to
  commit and be reread before any serving-eligible `UnitOfWorkContext` exists
  (`WO-0169:167-168,181-184`). Exact sequence step 4 explicitly establishes C1 before M2-I4
  reconciliation, with rollback returning no context and ambiguous commit remaining non-serving
  until retry reloads the latest committed checkpoint (`WO-0169:221-224`).
- Reconciliation starts only after C1. Every applied venue-recovery operation consumes and returns
  the latest admitted successor context (`WO-0169:225-230`). This matches the unchanged M2-I4
  boundary: it authenticates the supplied owners against the retained checkpoint
  (`unit_of_work.py:567-584,665-683`), stores a successor when bounded state changes
  (`unit_of_work.py:1626-1672,2900-2994`), and returns that completed context
  (`unit_of_work.py:2987-2994`). A checkpoint-changing venue recovery follows that path
  (`unit_of_work.py:5162-5177`); a no-change recovery retains the admitted context
  (`unit_of_work.py:5043-5053`).
- The same private transition is invoked against the latest post-reconciliation context. It is
  exact replay with no head advance when invalidation remains current, or commits and rereads
  exactly one invalidated successor otherwise; source access remains forbidden until this barrier
  returns normally (`WO-0169:201-211,231-233`).
- The required failure-capable controls now explicitly cover C0 with checkpoint-changing
  unresolved recovery, initial-cutover rollback, commit ambiguity, final-barrier replay or advance,
  source-refusal/retry reload, and no extra checkpoint advance (`WO-0169:368-371`).

The disproof sequence is now closed: C0 must first become committed-and-reread C1; a
checkpoint-changing recovery advances from the latest admitted context through M2-I4; the final
barrier either replays without advancing or creates one successor if invalidation was displaced.
No branch authorizes compact owners to authenticate against C0, retains a context after initial
rollback or ambiguity, or permits source access before the final barrier.

The amendment is minimal. The R2-to-corrected-candidate range changes only the active work order,
ledger, and REV-0116 governance artifacts. The relevant production blobs are identical across both
candidates:

- `operations.py`: `21845a500363edf96f2c9fc06939830067469659`
- `checkpoint_codec.py`: `f05ab0ce60fc0eec75c593a8f4a6343b38b219c0`
- `repository.py`: `818613123fc63dcc6d2ac197c7264b0b0acf007e`
- `unit_of_work.py`: `176d6b4ac36ccd0036ad48fdee0e06317463043b`
- `schema.py`: `164de10ad9fef6ce37324840aff59b5b68c07d2a`

The public eight-member `M2Operation` union and public UOW exports remain unchanged
(`operations.py:2761-2770`; `unit_of_work.py:5674-5680`). No second mutation path, public
operation, DDL/table, replay store, callback/framework, adapter, or broader implementation scope
was introduced. DDL remains 190,705 bytes at SHA-256
`d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`.

Verdict: ACCEPT
P0: 0
P1: 0
P2: 0
Unverified: NONE
