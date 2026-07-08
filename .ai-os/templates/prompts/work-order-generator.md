# Work Order Generator Prompt

Use this when the human gives an intent that is not yet implementation-ready.

```text
You are generating an AI Project OS work order.

Input intent:
<PASTE USER INTENT>

Repository/PKL context available:
<LIST ONLY RELEVANT FILES OR PAGES>

Produce a work order that includes:
1. Title
2. Goal
3. Non-goals
4. Assumptions, each marked VERIFIED or UNVERIFIED
5. Prompt type
6. Recommended model tier
7. Fable mode
8. Context packet
9. Allowed paths
10. Forbidden paths
11. Acceptance criteria
12. Required tests
13. Verification commands
14. Stop conditions
15. Human approval gates

Rules:
- Do not implement.
- Do not ask for broad repo review unless needed.
- Use exact paths where possible.
- If required information is missing and cannot be safely assumed, mark NEEDS-INPUT.
- Keep the work order short enough to paste into an agent session.
```


## Retention guidance

Write work orders as temporary execution tickets. Do not include unnecessary background, chat history, or broad project summaries. Link to PKL pages instead of copying them.

At the end of the work order, include a placeholder for completion disposition:

```text
Completion disposition: one or more values from rules/ai-os-rules.yaml (valid_work_order_dispositions)
```

For routine or low-value tasks, set the expected disposition to `DELETED` unless the task reveals durable knowledge.
