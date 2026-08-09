# Prompt Router

Use this router to choose the smallest prompt template that fits the task.

| User intent | Prompt template | Default Fable mode | Model floor |
|---|---|---|---|
| Create/clarify task scope | `work-order-generator.md` | FULL | medium |
| Implement scoped feature | `implementation.md` | FULL | medium |
| Fix failing behavior | `debugger.md` | FULL | strong if ambiguous |
| Review diff or PR | `reviewer.md` | REVIEW | medium/strong |
| Add tests only | `test-hardener.md` | FULL or LITE | medium |
| Simplify code without behavior change | `refactor.md` | FULL | medium |
| Decide architecture boundary | `architecture-review.md` | FULL | strong |
| Update PKL after merge | `pkl-curator.md` | LITE | cheap/medium |
| Resume or transfer work | `handoff.md` | FULL | medium |
| Improve a prompt/work order | `prompt-improver.md` | LITE | medium |

Routing rules:

1. Prefer the narrowest template.
2. If the task touches auth, authorization, data deletion, irreversible migration, financial execution, secrets, or production deployment, verify that the exact human-gated action is already approved. Request approval only when it is absent; model choice does not create authority.
3. If the task is ambiguous, generate or revise a work order before implementation.
4. If the task already has a work order, do not replace it with a broad prompt.
5. If the agent encounters surprise scope, investigate and classify it first. Continue with a necessary root correction when it remains inside the authorized outcome and safety boundaries; reroute or ask only for material authority expansion.
6. Inherit the current capable model by default. Use a model override only for a concrete task reason; never require a named-model escalation ladder.
