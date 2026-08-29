---
type: Review
review_id: REV-0115-R1
work_order_id: WO-0168
review_mode: fresh-context exact-source remediation re-review
status: REVIEW
authoritative_diff: 7c0e52b26cf0bc1b82bbfa04ffc4131e80161145..55c4698236858fd1f9a92fc8e50134b8161c1843
---

# REV-0115 R1 — WO-0168 root-remediation re-review

Return findings only. Do not edit, commit, push, or implement fixes. Re-derive the result from the
exact source and tests; do not trust the author disposition. This is the single correction-only
re-review permitted by the active work order. Do not reopen accepted taste or alternate-design
questions without a violated contract clause or demonstrated failure.

## Exact binding

- Repository: `https://github.com/amujtabaa/automation-alpaca.git`.
- Branch: `codex/m2-wo0168-atomic-uow-r1`.
- Original reviewed source: `7c0e52b26cf0bc1b82bbfa04ffc4131e80161145`.
- Remediation source candidate: `55c4698236858fd1f9a92fc8e50134b8161c1843`.
- Candidate tree: `6b6c4dda85e56c9648fb545b806c12bce5d42b0b`.
- Review the exact remediation diff above. Later commits on the branch may add only this request,
  disposition, work-order evidence, and ledger metadata; verify that no source/test drift occurred.
- `authority.py` blob: `174c1b40926e53e54314b276779f59bc4e908966`.
- `unit_of_work.py` blob: `105d5189a75d0d2044752a71ece1d893db146f65`.
- Pure UOW test blob: `3d03e30043bb1b9edffc0b82c3f2cc5a1208789b`.
- Original reviewer result blob: `b3deaca61f32a248a6cf580a399397fd440d0d4d`;
  raw SHA-256 `ff9400ab02c3ccb2fed1dfc07d41f76aeeeac6d8b6579a1ee6657e7b40a3293e`.
- DDL remains 190,705 UTF-8 bytes at
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`;
  schema blob `164de10ad9fef6ce37324840aff59b5b68c07d2a`; human flag exact `False`.

## Read order

1. `AGENTS.md`, the safety core in `CLAUDE.md`, and the active WO-0168 contract.
2. `work/review/REV-0115/result.md` and `disposition.md`.
3. Exact remediation diff, prioritizing the locations named below and their immediate call chains.
4. The frozen operation-state contract section 3 and fault-edge section 9.

## Mandatory disproof lenses

1. **Manual human authority:** Try to make an unbound, terminal, wrong-scope, wrong-symbol, forged,
   or omitted manual observation authorize `CreateBrokerEffect`. Confirm the public route and UOW
   route use one shared reducer and that a missing UOW proof fails closed.
2. **Route-less revisions:** Trace both fill→correct and fill→bust with no route. Confirm exact
   predecessor/root proof remains required, broker economics and quarantined controller advance,
   no route/owner/acquisition authority appears, replay/conflict still short-circuit, and no stale
   caller context is published as changed authority.
3. **O1-O8 ratchet:** Compare `_M2_C6_WRITE_TABLE` with the frozen rows and actual static repository
   call sites. Try missing, extra, reordered, dynamic, wildcard, optional-family, and duplicate-call
   mutations. Confirm every catalogued semantic/checkpoint/receipt/outcome/outbox boundary has a
   failure-capable old-complete rollback and retired-lease control.
4. **Regression and scope:** Inspect the complete remediation diff for a new safety violation,
   bypass, second decision engine, generic framework, DDL/test-gate drift, or scope creep. Style or
   preferred redesign without a demonstrated contract failure is nonblocking.
5. **Evidence critic:** A passing assertion must be able to fail for its named mutant. Distinguish
   reproduced-live from reasoned-only and perform a disproof pass before retaining a finding.

Static/read-only and targeted ordinary pure tests are allowed. Do not open SQLite, create a
database, install DDL, execute `tests_gated/**`, access a configured path, or alter the checkout.

For each retained P0/P1/P2 finding provide severity, exact file:line, violated clause or concrete
counterexample, real-world impact, and smallest root correction. End exactly with:

```text
Verdict: BLOCK | ACCEPT-WITH-CHANGES | ACCEPT
P0: <count>
P1: <count>
P2: <count>
Unverified: <exact list or NONE>
```

`ACCEPT` requires zero open P0/P1. State explicitly that no SQLite/database/held-suite execution
occurred in this review.
