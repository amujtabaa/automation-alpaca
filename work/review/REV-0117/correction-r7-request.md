# REV-0117 R7 finite correction verification — WO-0169 checkpoint owners

Date: 2026-08-29

Status: **CORRECTION-ONLY REVIEW REQUIRED**

## Exact binding

- Canonical branch: `codex/m2-wo0169-startup-cold-recovery-r1`.
- Product correction: `ecee243d5627d06a55f7de1b89c59b9982e253fd`;
  tree `1f35f8204ebab2356885aea17ef19d2748e220b3`.
- Preserved R6 result commit: `8137050732af79efa01b64cb975de3c94aebfb6c`.
- Exact test-only correction candidate: `51c90ba480e8b61ea7e57d627f0b90cdb80191e1`.
- Candidate tree: `b1514e84c5fcb910520353e90115d6a0bb2de6ab`.
- Correction range:
  `8137050732af79efa01b64cb975de3c94aebfb6c..51c90ba480e8b61ea7e57d627f0b90cdb80191e1`.
- `unit_of_work.py` SHA-256, unchanged from R6:
  `12bb7ad3d25f1de23829010bf50bb5cb0ce26896f4696b200dd2744b8079295c`.
- Corrected pure UOW test blob: `d6d86111ee3e668b882cd2229f7a40dcbdf082a3`;
  SHA-256 `443db52fd83c09c0e148e3268beef18b6fb0bf1fa879c8a9e03a52477e80164a`.
- Active work-order blob: `7d8c9c7e3bd868a587750013545c9698a19fecf3`;
  SHA-256 `efac8450cba5d244921fe6cd5ccf60f0caf286ac10e908761350bfad3560bbc4`.
- Preserved R6 result SHA-256:
  `7f6cf42819a76d73e0f570b2f0f1f7d4ee0a1bb3caf00b715faccd16f651af2e`.

This request file is a later documentation-only commit and is outside the correction candidate.

## Accepted R6 finding and exact correction

R6 returned one P1 because the different-owner projection used an authentic genesis proof at
version N=1. The earlier target-version predicate rejected it before
`_m2_checkpoint_semantics_match`, so the test did not independently kill removal of the owner
comparison.

The correction changes tests and the active governance record only. It issues the active different
owner set under a new authentic successor proof that uses the retained application's exact
application/profile/head coordinates and targets version N+1. The control explicitly pins N+1,
then traces `_m2_checkpoint_semantics_match`. Exactly the different-owner case must invoke the
comparator once and refuse; stale head, wrong provenance, absent retained data, and the
predecessor-at-N projection must refuse earlier without invoking it.

## Evidence available to reproduce

- Direct corrected control: `1 passed in 0.58s`.
- Complete source-confirmed six-file pure slice: `552 passed in 32.36s`.
- Ruff check/format passes on the corrected test.
- Mypy still passes all 99 application files.
- Ledger, exact work-order scope, and whitespace checks pass.
- Production source is byte-identical to the R6 candidate. DDL, schema blob, held test, exact-false
  human flag, public surfaces, and startup architecture are unchanged.

## Finite review request

Verify only that the accepted R6 P1 is closed:

1. the different-owner projection is authentic and bound to the valid retained-N/projected-N+1
   relationship;
2. it reaches the owner-semantic comparator rather than an earlier guard;
3. removal/bypass of the comparator or acceptance of the mismatched owners fails the control; and
4. all other rejected cases retain their earlier owning guards without production or protected-
   identity drift.

Do not reopen the product design or unrelated accepted findings. Run the one corrected control or
the six-file pure slice if useful. Do not import or execute SQLite, create a database, run the held
test, or edit implementation/request files. Return findings only with exact P0/P1/P2 counts and
`BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`. The reviewer-owned result path is
`work/review/REV-0117/result-r7.md`.
