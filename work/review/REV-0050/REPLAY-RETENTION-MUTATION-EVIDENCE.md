# WO-0148 occurrence-receipt failure-capability evidence

`[FABLE - FULL - verification: DIRECT fail/restore controls - task: durable market-occurrence receipts]`

## Boundary and point-in-time restoration

These controls exercise only the pure `app.execution_core.protection` reducer and its isolated
tests. They used no broker, credentials, network, runtime wiring, persistence, SQL, DDL, or
database path. Each temporary production edit was applied to the allowed `protection.py` path,
the named focused tests were run with pytest cache disabled, the edit was reversed, and the same
tests were rerun green.

Immediately after the five mutation controls, the restored files exactly matched their
pre-control values:

- `app/execution_core/protection.py`: SHA-256
  `3A969AB9729C15A4846A4E8B1B10E61C565BBF3C107AAB766FD1B7B8E74A09B6`, Git blob
  `e6ad45456e412761843fb2b49e76b4f6afb080e6`.
- `tests/execution_core/test_protection.py`: SHA-256
  `D4F031877F7F6A45A66D9BA8B748FB85E7F05B3D4A370031C68AE71EA2028786`, Git blob
  `6add21100ec4f815ce577824a011a9ca4d09ce30`.
- `tests/execution_core/test_protection_stateful.py`: SHA-256
  `FE851C3EF90248A04F38DF4B5BF79D3083CFED5478B0D077751D1E9892637DD0`, Git blob
  `2f15b8c52964c6062bb54bc238d9a54995e48231`.

These are point-in-time restoration hashes, not the later successor-freeze hashes. A subsequent
stateful generator correction changed only `test_protection_stateful.py`; the final pre-freeze
hash is `BDE0E57055437CEDC6AB34B8264842E15DEAC3E55037D3C95CF4A32B12D8F421` (Git blob
`9e0df600ecce0fbc28df2169955f6c7d37639347`). The production and deterministic-test hashes did
not change. The successor evidence record identifies all final pre-freeze inputs.

## Controls

| ID | Temporary mutation | Decisive focused result | Restored result |
|---|---|---|---|
| RR-M01 | Start every insertion from an empty persistent map, reducing retention to the latest occurrence. | 4/4 failed: non-last BID/TRADE replays returned `APPLIED`, non-last changed-payload reuse was not `REFUSED`, and the trail replay was reapplied. | 4/4 passed. |
| RR-M02 | Discard the newly built receipt map on every contextually ineligible return. | 3/3 failed: stale and step-ineligible facts could be redelivered, and a crossed quote identity could be corrected after first delivery. | 3/3 passed. |
| RR-M03 | Replace retained receipts with an empty map on every venue/economic projection. | 3/3 failed: formula restoration, flat/late-positive recovery, and trigger ratchet histories no longer classified older facts as exact replays. | 3/3 passed. |
| RR-M04 | Include `evaluation_time` in the authoritative occurrence payload digest. | 6/6 failed: changed local evaluation context became false payload equivocation for BID/TRADE with present or absent source sequence, including non-last histories. | 6/6 passed. |
| RR-M05 | Remove the receipt-map commitment from `PositionProtectionState.commitment`. | 1/1 failed at the exact `_seen_occurrence_receipts` mutation path: a forged receipt registry advanced instead of being refused. | 1/1 passed. |

The controls prove five independent obligations: aggregate-history lookup, receipt-before-
eligibility, receipt retention through reducer-owned resets, exclusion of delivery context from
source payload identity, and authenticated binding of the immutable receipt registry into state.

## Exact commands

RR-M01 mutant and restored runs:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --junitxml=work/review/REV-0050/evidence/replay-retention-mutation-01-last-only/mutant.junit.xml tests/execution_core/test_protection.py::test_nonlast_sequence_absent_replay_cannot_rebuild_hard_bail_evidence tests/execution_core/test_protection.py::test_nonlast_occurrence_identity_equivocation_is_refused tests/execution_core/test_protection.py::test_nonlast_sequence_absent_replay_cannot_rebuild_trail_exit_evidence
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --junitxml=work/review/REV-0050/evidence/replay-retention-mutation-01-last-only/restored.junit.xml tests/execution_core/test_protection.py::test_nonlast_sequence_absent_replay_cannot_rebuild_hard_bail_evidence tests/execution_core/test_protection.py::test_nonlast_occurrence_identity_equivocation_is_refused tests/execution_core/test_protection.py::test_nonlast_sequence_absent_replay_cannot_rebuild_trail_exit_evidence
```

RR-M02 mutant and restored runs:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --junitxml=work/review/REV-0050/evidence/replay-retention-mutation-02-ineligible-drop/mutant.junit.xml tests/execution_core/test_protection.py::test_stale_first_delivery_cannot_become_fresh_when_redelivered tests/execution_core/test_protection.py::test_step_invalid_first_delivery_cannot_become_eligible_after_anchor_moves tests/execution_core/test_protection.py::test_crossed_first_delivery_reserves_identity_against_payload_correction
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --junitxml=work/review/REV-0050/evidence/replay-retention-mutation-02-ineligible-drop/restored.junit.xml tests/execution_core/test_protection.py::test_stale_first_delivery_cannot_become_fresh_when_redelivered tests/execution_core/test_protection.py::test_step_invalid_first_delivery_cannot_become_eligible_after_anchor_moves tests/execution_core/test_protection.py::test_crossed_first_delivery_reserves_identity_against_payload_correction
```

RR-M03 mutant and restored runs:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --junitxml=work/review/REV-0050/evidence/replay-retention-mutation-03-reset-clear/mutant.junit.xml tests/execution_core/test_protection.py::test_formula_loss_discards_market_evidence_and_restores_a_fresh_branch tests/execution_core/test_protection.py::test_late_owned_buy_after_flat_restores_hard_bail_and_alert tests/execution_core/test_protection.py::test_trigger_ratchet_cannot_reuse_evidence_from_the_old_trigger
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --junitxml=work/review/REV-0050/evidence/replay-retention-mutation-03-reset-clear/restored.junit.xml tests/execution_core/test_protection.py::test_formula_loss_discards_market_evidence_and_restores_a_fresh_branch tests/execution_core/test_protection.py::test_late_owned_buy_after_flat_restores_hard_bail_and_alert tests/execution_core/test_protection.py::test_trigger_ratchet_cannot_reuse_evidence_from_the_old_trigger
```

RR-M04 mutant and restored runs:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --junitxml=work/review/REV-0050/evidence/replay-retention-mutation-04-evaluation-context/mutant.junit.xml tests/execution_core/test_protection.py::test_changed_delivery_context_replay_is_exact_for_every_occurrence_form tests/execution_core/test_protection.py::test_nonlast_sequence_absent_replay_cannot_rebuild_hard_bail_evidence
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --junitxml=work/review/REV-0050/evidence/replay-retention-mutation-04-evaluation-context/restored.junit.xml tests/execution_core/test_protection.py::test_changed_delivery_context_replay_is_exact_for_every_occurrence_form tests/execution_core/test_protection.py::test_nonlast_sequence_absent_replay_cannot_rebuild_hard_bail_evidence
```

RR-M05 mutant and restored runs:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --junitxml=work/review/REV-0050/evidence/replay-retention-mutation-05-state-commitment/mutant.junit.xml tests/execution_core/test_protection.py::test_every_reducer_owned_state_field_is_authenticated_before_advancement
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider --junitxml=work/review/REV-0050/evidence/replay-retention-mutation-05-state-commitment/restored.junit.xml tests/execution_core/test_protection.py::test_every_reducer_owned_state_field_is_authenticated_before_advancement
```

## Preserved JUnit artifacts

Each directory contains `mutant.junit.xml` followed by `restored.junit.xml`:

| Evidence directory | Mutant SHA-256 | Restored SHA-256 |
|---|---|---|
| `replay-retention-mutation-01-last-only` | `BAE0E8DDA025C50D4630142E885E723DB3F85678EDF6CBDC453B6A761A95AD22` | `5E1A741D5C38619DACB2757B81D098435AF9AD061FF833A653528B30BD756172` |
| `replay-retention-mutation-02-ineligible-drop` | `ABAAA3799D935C0F5D6081CA69281F87F772B8F7D757E1A2AD58FC8FE516B4E5` | `83E5AAA5A3CD72BBBC3D5311554535F80A73BD09C36C66B9F06FC439A8F95AD9` |
| `replay-retention-mutation-03-reset-clear` | `FD2861B3A6574894BF8338B102AC20C32B762A0009D6B27977BCD0B3CD97D80A` | `8A7CE5EA0D251005FD70B9B9B4573E746DE084DC5205F360E41DC944F6A8F9DE` |
| `replay-retention-mutation-04-evaluation-context` | `85D7BDFF40F6231DF5174A3AFE9BBCE40D4EC32C1FAA0532C1251C6C9D462293` | `8A4B6E3ADEB83C7FCF32B9C60E7E589A6A05C575C683EFF7B61C4F2C0B48936C` |
| `replay-retention-mutation-05-state-commitment` | `971AF8DCE103AD1394AD70AA75D26F324F651DA42067737194DE31540187FBD1` | `BAD445B4ADBF17984E7ADE254FD6916A3C0E350FE354C399758A0E0F38A976A3` |

This is working-copy failure-capability evidence, not independent acceptance or WO-0148
closeout. The successor candidate still requires the complete gates and a fresh exact-candidate
review with zero unresolved P0/P1.
