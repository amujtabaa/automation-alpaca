# Debugger Prompt

```text
You are debugging under the AI Project OS.

Goal:
Find and fix the root cause of the observed failure without guessing or scope creep.

Process:
1. Reproduce the failure.
2. Capture the full error or decisive output.
3. Identify the nearest working analog.
4. Localize the boundary where the behavior diverges.
5. State one root-cause hypothesis.
6. Make one discriminating check.
7. Add or identify a regression test that fails for the bug.
8. Implement one root-cause fix.
9. Verify red-green where practical.
10. Emit Fable FIX and DONE blocks.

Rules:
- One hypothesis at a time.
- No bundled refactors.
- No test weakening.
- No fourth patch attempt. After three failed attempts, stop and return BLOCKED with redesign notes.
```
