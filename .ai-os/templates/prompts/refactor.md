# Refactor Prompt

```text
You are performing a behavior-preserving refactor.

Goal:
Improve clarity or reduce duplication without changing behavior.

Required:
1. Identify the behavior-preserving reason for the refactor.
2. Run existing tests before changes if practical.
3. Make the smallest diff.
4. Do not rename or move public interfaces without explicit approval.
5. Run the same tests after changes.
6. Return DONE with before/after evidence.

Stop if:
- Tests are missing for affected behavior.
- Refactor requires behavior change.
- Scope expands into unrelated cleanup.
```
