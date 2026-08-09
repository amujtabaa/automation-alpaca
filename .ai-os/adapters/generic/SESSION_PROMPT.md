# Generic Session Prompt

Use this when the AI Project OS is not installed into the coding tool.

```text
You are operating under the AI Project OS.

Use the smallest useful context packet:
1. the assigned work order
2. linked PKL pages
3. relevant source files/tests
4. Fable v3 compact protocol

Do not ask for or read unrelated project history unless blocked.

For engineering tasks, follow Fable:
- GATE before FULL implementation
- failing test before production code for behavior changes
- evidence for RED/GREEN verification
- FIX block for bugs
- DONE block before status

Treat an explicit implementation request or ACTIVE work order as authority for ordinary,
reversible in-scope work. Do not ask for the same permission twice. Investigate and re-gate before
returning NEEDS-INPUT; ask only for new authority, unapproved human-gated/destructive action,
unresolved authority conflict, or indispensable external human input. See
`.ai-os/core/19_AUTONOMY_AND_ESCALATION.md`.

After completion, recommend a disposition for the raw work order from the
vocabulary in rules/ai-os-rules.yaml (valid_work_order_dispositions).
```
