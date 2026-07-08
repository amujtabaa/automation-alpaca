# Work Retention Policy

Default dispositions:

- Major feature: PKL_UPDATED + RESULT_SUMMARY_KEPT
- Architecture decision: ADR_CREATED; delete raw prompt after ADR
- Important bug: PKL_UPDATED or error/drift log + RESULT_SUMMARY_KEPT
- Sensitive change: RESULT_SUMMARY_KEPT
- Routine typo/import/formatting: DELETED
- Placeholder: DELETED
- Duplicate: DELETED or SUPERSEDED
- Superseded raw plan: SUPERSEDED, then DELETED after successor is linked

Do not keep raw prompts unless they contain durable knowledge not captured elsewhere.
