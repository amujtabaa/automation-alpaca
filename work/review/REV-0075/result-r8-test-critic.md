# REV-0075 R8 test-critic result

Exact candidate reviewed: `09195eea5a14fa2c350c789adb72a5f07d3be760`, tree
`9a00865fe59d4b4904f3fa7b3ec817b9b1669c7f`.

## P1 — State-commitment membership was not mutation-pinned

Location: `tests/execution_core/test_position.py:356`.

Mutating `_m2_execution_state_commitment` to omit `raw_quantity` or
`tail_fold_input` left the pure suite green. Add valid wire-member mutations
that retain the original commitment and must be rejected.

## P1 — New enum tags and one fixed order remained self-referential

Location: `tests/execution_core/test_position.py:332`.

Paired encoder/decoder mutations of the new enum tags, and a paired swap of
the equal-valued integrity slots, passed the existing controls. Pin literal
enum arrays, invalid values, and a distinguishable slot-order control.

## P1 — Canonical null variants were untested

Location: `tests/execution_core/test_position.py:316` and `:395`.

The existing cases did not exercise absent optional execution-state forms.
Add real flat and reconciliation-pending state round trips, and verify the
tail-fold boundary admits only a complete bounded predecessor proof.

## P1 — Encoder admission checks had no failure-capable control

Location: `app/execution_core/persistence/checkpoint_codec.py:237` and `:187`.

Removing the execution-state type/authenticity guard or the tail-fold exact-type
guard left the suite green. Add copied-shape, post-construction mutation, and
non-`FoldInput` rejection controls.

## P2 — Exception and final canonicality gates were weakly specified

Location: `tests/execution_core/test_position.py:391` and `:438`.

The tests accepted broad exception classes and partial messages, and did not
prove each decoder's final re-encode comparison executes. Pin exact error
classes/messages and use targeted encoder substitutions to prove both final
canonicality gates.

## Verdict

**ACCEPT-WITH-CHANGES** — P0=0, P1=4, P2=1.

Unverified: clean-checkout/full-CI evidence. The reviewer ran the candidate's
108 pure tests; no SQLite, network, or runtime composition was invoked.
