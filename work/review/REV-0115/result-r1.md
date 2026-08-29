Review was read-only. No SQLite/database was opened or created; no DDL was installed or executed; no configured path was used; no `tests_gated`/held suite was executed.

### P1 — O1–O8 fault ratchet bypasses every catalogued write boundary

- Location: [tests/execution_core/test_persistence_unit_of_work.py:2921](G:/dev-hdd/automation-alpaca/tests/execution_core/test_persistence_unit_of_work.py:2921), [tests/execution_core/test_persistence_unit_of_work.py:3094](G:/dev-hdd/automation-alpaca/tests/execution_core/test_persistence_unit_of_work.py:3094)
- Violated clause: [request-r1.md:51](G:/dev-hdd/automation-alpaca/work/review/REV-0115/request-r1.md:51), [frozen contract:329](G:/dev-hdd/automation-alpaca/work/queue/M2-EXECUTION-2026-08-21/06-WO-0168A-FROZEN-OPERATION-STATE-CONTRACT.md:329), and [WO-0168:193](G:/dev-hdd/automation-alpaca/work/active/WO-0168-m2-i4-atomic-unit-of-work-effects.md:193) require failure-capable controls at the actual catalogued write boundaries.
- Evidence: `[reproduced-live]` All 193 focused remediation cases passed. An independent negative control then installed traps on every repository mutator and invoked all 173 named fault cases; all passed while observing exactly zero mutator calls. Each case replaces `_execute_prepared` with the same generic throwing body, and its “after” simulation merely appends the boundary label to a synthetic journal before throwing.
- Evidence: `[reasoned-only]` A row-specific mutant that catches or mishandles an exception after an actual semantic, checkpoint, receipt, outcome, or outbox write leaves the static call table unchanged and is never exercised by these controls. The suite therefore proves generic outer rollback and lease retirement, not the claimed per-boundary ratchet.
- Impact: A boundary-specific atomicity or lease-retirement regression can survive while the advertised 173-boundary control remains green.
- Smallest root correction: inject before/after faults through each actual catalogued call path, assert that the named call was reached and later calls were not, then prove journal rollback and capability retirement. Preserve explicit optional-family and duplicate-call negative controls.

Verdict: ACCEPT-WITH-CHANGES
P0: 0
P1: 1
P2: 0
Unverified: executable SQLite/DDL agreement; configured-path behavior; tests_gated/held-suite results; end-to-end database crash/restart and actual per-write fault behavior for O1-O8
