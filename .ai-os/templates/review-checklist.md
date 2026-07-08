# Review Checklist

## Spec compliance

- [ ] Diff satisfies the work order.
- [ ] No extra behavior was added.
- [ ] Done-when items are individually met.

## Scope

- [ ] Changed files are within allowed paths.
- [ ] Forbidden paths were not changed.
- [ ] No drive-by refactors.

## Tests

- [ ] New behavior has tests.
- [ ] Bug fixes have red-green regression proof.
- [ ] Required commands were run fresh.
- [ ] No skipped/weakened tests without approval.

## Architecture

- [ ] Domain logic is not in routes/controllers.
- [ ] Boundaries match ADRs and PKL pages.
- [ ] No unapproved dependency or microservice extraction.

## Security / sensitive surfaces

- [ ] Inputs validated at trust boundary.
- [ ] AuthZ checked where required.
- [ ] No secrets in code, logs, or diff.
- [ ] File paths/network/shell operations are safe.

## Fable evidence

- [ ] GATE exists for FULL task.
- [ ] Evidence lines include command output.
- [ ] FIX block exists for bugs.
- [ ] DONE block status is valid.

## Verdict

`APPROVE | REQUEST-CHANGES | BLOCK`
