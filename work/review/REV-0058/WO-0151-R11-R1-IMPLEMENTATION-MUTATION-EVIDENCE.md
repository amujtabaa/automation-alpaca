# WO-0151 R11 R1 implementation mutation evidence

Status: **RETAINED REMEDIATION EVIDENCE**

This record closes the failure-capability portion of the sole P1 in
`WO-0151-R11-R1-IMPLEMENTATION-ACCEPTANCE-RESULT.md`.  The campaign was limited
to the pure execution-core application and test paths authorized by WO-0151.
Every temporary mutation was applied to one exact source location, exercised
with a focused pytest control, and restored before the next mutation.  No
broker, network, credential, runtime, persistence, SQL/DDL, or database path
was used.

## Candidate and restored-state pins

The reviewed predecessor was the implementation manifest at SHA-256
`9d9a00bc9fa98e65fcd1d891f08ca860175c01b377d35049d0da6fa3b652e955`.
The relevant predecessor-to-remediation path hashes are:

| Path | Frozen predecessor | Restored remediation state |
| --- | --- | --- |
| `app/execution_core/acquisition.py` | `22326c338a6c5c0c3c6c3c98c24bcd3b95acb300eb064d168f1f060db3595985` | `3c9f86e191a807cb79b967fddfb47ae4a5fbbd1790d70c0f8823f9971e2893e7` |
| `app/execution_core/authority.py` | `5d9f22a77ba5e8ea38b126b2413f0c6a279c6a0a10e85d27d2358a4d2956d2c0` | `d59da7c2659f1decbd3ae30755813106af693ce89d6db91e47bc7489d3f2c4fb` |
| `app/execution_core/protection.py` | `cfdee0230980728f31feb746ccc578b63596b47988abc2388b876184fc80c609` | `cfdee0230980728f31feb746ccc578b63596b47988abc2388b876184fc80c609` |
| `tests/execution_core/test_acquisition.py` | `d158a568aea701ed6a7c2500fdc11f620b4fa6534d86e1dde1fa0011235323b9` | `d8156e007ef21584f8bc03081e60b8a79027a09ee9d8b4f0379458ef510f0f7c` |
| `tests/execution_core/test_protection.py` | `269ebeb2b1a5b87bec2685784843c78aab236179cbeb02a9fa8ccd0f80bbbffd` | `18c1ac5f50575fd36c2554b816c3313d9c6adcd4c98877fb9f879193d283f330` |

The protection production hash is unchanged.  The two production hash changes
are the focused inactive-successor fact-registration correction described
below; test changes add the missing fact-family matrix and failure controls.

## Named mutation campaign

Each row used
`.\.venv\Scripts\python.exe -m pytest -q <node-id> -p no:cacheprovider`.
`RED` means the temporarily weakened production path caused the named control
to fail for the expected semantic reason.  After restoration, the combined
focused set passed 17/17.

| ID | Temporary mutation | Failure-capable control | Observed RED reason |
| --- | --- | --- | --- |
| M01 | Removed the protection-owner semantic matcher from rebase admission. | `test_wo0151_r11_semantic_rebase_requires_the_protection_owner_matcher` | A forged projection became `APPLIED` instead of `REFUSED`. |
| M02 | Removed the semantic-no-change refusal from the public rebase projector. | `test_wo0151_r11_neutral_reprojection_is_owner_minted_and_transport_only` | A neutral transition incorrectly produced a semantic rebase projection. |
| M03 | Removed exact execution/cursor source linkage from the protection context. | `test_wo0151_protection_context_binds_the_exact_venue_cursor_source` | An authentic but wrong-cursor state incorrectly projected a context. |
| M04 | Removed the terminal no-work requirement from successor admission. | `test_wo0151_r11_successor_admission_requires_terminal_no_work` | A predecessor with live BUY work incorrectly admitted a successor. |
| M05 | Erased the protection-owned preemption purpose tag. | `test_wo0151_r11_r1_preemption_and_exit_intents_have_disjoint_owner_producers` | The sealed intent no longer identified `PREEMPT_BUY_ONLY`. |
| M06 | Removed the preemption intent's current-context revalidation. | `test_wo0151_r11_r1_preemption_rechecks_the_owner_intent_context` | A stale intent incorrectly produced an applied preemption. |
| M07 | Removed the waiting-BUY predicate from the preemption intent producer. | `test_wo0151_r11_r1_preemption_and_exit_intents_have_disjoint_owner_producers` | A released state incorrectly produced a cancel-only intent. |
| M08 | Suppressed goal-independent BUY preemption as though a SELL goal were required. | `test_wo0151_r11_r1_current_waiting_buy_stages_one_bounded_cancel` | A valid waiting-BUY preemption was refused. |
| M09 | Removed SELL-exit goal presence and owner-derived goal equality. | `test_wo0151_r11_r1_preemption_and_exit_intents_have_disjoint_owner_producers` | An authentic goal-less transition incorrectly produced a SELL-exit intent. |
| M10 | Removed the current transition/state-context binding for protection exit. | `test_wo0151_r11_r1_goal_owned_protection_exit_is_single_flight` | A stale released transition was accepted against a newer context. |
| M11 | Removed the one-cancel cap. | `test_wo0151_r11_r1_preemption_enforces_the_one_cancel_cap` | Duplicate cancellation advanced to a later map collision instead of stopping at the cap. |
| M12 | Suppressed the canonical-fact currentness/controller-head advance. | `test_wo0151_r11_current_correct_updates_direct_lineage_once` | The first authentic fact was refused instead of advancing exactly once. |
| M13 | Removed final-claim currentness revalidation. | `test_wo0151_r11_final_claim_revalidates_the_exact_currentness_head` | A pre-minted claim crossed a venue-neutral head advance and was applied. |

The initial M01 control based only on exact immutable replay survived because
authority's independent one-registration gate still rejected the replay.  The
test was therefore strengthened with a forged predecessor-context relation
that reaches and depends on the owner matcher.  M13 likewise uses a direct
pre-minted claim followed by an authentic venue-neutral currentness advance,
so the control fails only when the final revalidation fence is removed.

## Applied-fact matrix and root correction

The remediation adds controller-level current/follow-on and retired
`FILL`/`TRADE_CORRECT`/`TRADE_BUST` paths, including tail and non-tail source
reconciliation, ordinary and conservative protection dispositions, exact
single head/economics advancement, and replay inertness.  The matrix exposed
one production defect: a retired non-tail `TRADE_BUST` with no live successor
BUY reached the mixed-recovery preemption minter, which assumed an active BUY
must exist and refused the authentic fact.

The root correction makes `_mint_acquisition_fact_preemption` return no
preemption only for the exact authentic inactive slot whose retained
descriptor and predecessor effect match the fact relation.  The acquisition
composite then uses ordinary canonical-fact registration.  An active successor
BUY still takes the atomic fact-plus-preemption route; stale, forked,
cross-scope, mismatched, or otherwise ineligible inputs still fail closed.

## Restored verification

- The 13 temporary mutations were absent after restoration.
- The focused mutation controls passed 10/10 before matrix completion.
- The combined matrix and mutation controls passed 17/17 after formatting.
- The complete pure execution-core collection contains 1,353 tests.
- Ruff check/format verification and configured application mypy passed after
  restoration; the final complete pure-suite and governance reruns are pinned
  in the remediation candidate manifest.

This record is evidence for the focused P1 recheck only.  It does not close
WO-0151, satisfy exact-head CI, activate WO-0152, or authorize any later work.
