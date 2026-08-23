# REV-0075 R4 disposition

Author: Codex implementation/orchestrator seat  
Date: 2026-08-23

The independent R4 design result accepts the exact source candidate
`fd56983c31ce3f103bc981b67adc14a67eea5f04`. The independent R4 test-critic
result identifies one P1 test-strength gap in that same candidate. Both results
are preserved unchanged in `result-r4-design.md` and `result-r4-test-critic.md`.

## Root correction

The source already binds every declared field, but three integrated row-mutation
assertions can fail before the relevant record binding is reached. The corrective
test must exercise `_current_proof_optional_record_binding()` directly, mutate
each declared field of every closed optional row type, and require rejection.
That removes the unrelated relationship validator from the proof path and kills
an omission of any one field from the corresponding binding tuple.

The test-only remediation is intentionally a separate exact candidate and needs
its own fresh test-critic review. R4 is therefore not used as an implicit
acceptance of that later delta.

No SQLite activity, DDL execution, runtime composition, external I/O,
promotion, or merge is authorized by this disposition.
