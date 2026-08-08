# Independent exact-delta review — ADR-023 derived-identity setter

Review target: `17accddabd1defa14176f00b0328a300d936ae3c..157c7d43c11c9323cd9e7aba7ed5168cc0f8132e`

The candidate and parent objects exist, the candidate has the stated parent, `git diff --check`
is clean, and the immutable delta contains only the two declared paths. The application tree and
`tests/execution_core/test_protection.py` are unchanged in the candidate. The new immutable
failure-capable control passes when loaded directly from the candidate object and rejects its seven
declared wrong-owner/lifecycle/receiver/field/constructor/hash-input/duplicate variants. Static
inspection also confirms that the new write-effect exception is limited to the direct exact
`MarketOccurrence.__post_init__` setter expression; other `object.__setattr__` calls remain subject
to the existing unauthenticated-write rejection.

## [P1] The correction leaves a second RED oracle rejecting the required canonical lifecycle

**Locations:** `tests/execution_core/test_protection.py:3155`,
`tests/execution_core/test_protection.py:3211`,
`tests/execution_core/test_protection.py:3217`,
`tests/execution_core/test_protection.py:3343`, exercised at
`tests/execution_core/test_protection.py:4702`,
`tests/execution_core/test_protection.py:4920`, and
`tests/execution_core/test_protection.py:12815`; the incomplete feasibility claim is recorded at
`work/active/WO-0148-reset-kernel-d-position-protection-hybrid-trailing.md:1386`.

**Evidence:** The immutable candidate's `_assert_passive_lifecycle` still sends every
`__post_init__` body to `_assert_passive_post_init_statements`. That oracle admits validation
`if` blocks, `raise`, `return None`, docstrings, and `pass` only. The canonical implementation
necessarily starts with a `preimage = ...` assignment, which reaches line 3217 and fails as
`unsupported lifecycle statement: Assign`. Even if that assignment alone were admitted, the
required `object.__setattr__(...)` expression reaches lines 3211–3215 and fails because it is not a
docstring. Three public/value/passivity contract tests independently invoke this unchanged oracle
for `MarketOccurrence`.

As corroboration only, because the working tree contains explicitly excluded uncommitted
application work, a focused pure run of `tests/execution_core/test_protection.py` reproduced these
same three failures at line 3217. Six additional failures from that run concern the excluded
working-tree application state and are not candidate findings.

**Proof and production impact:** The candidate correctly re-derives the first contradiction: the
old write-effect oracle made the sole frozen-derived-field setter impossible, and its new exception
does not show a direct broadening bypass in the reviewed wrong-shape cases. But the accepted RED
contract remains structurally impossible as a whole. Therefore the reported 7/7 focus is not
sufficient evidence that GREEN can satisfy the complete frozen contract, and production work
cannot rely on this re-gate yet. Rebinding and unrelated assignments remain rejected only because
the second oracle currently rejects *all* assignments; that is not a usable proof of the intended
narrow positive path.

**Smallest root correction:** Reconcile the owning passive-lifecycle oracle, preferably through one
shared structural recognizer, to consume exactly the canonical `MarketOccurrence.__post_init__`
tail: one exact `preimage = _market_occurrence_preimage(...)` binding followed by one exact
`object.__setattr__(self, "occurrence_id", _MarketOccurrenceId(_sha256(preimage).hexdigest()))`.
Continue rejecting every other assignment or expression. Add failure-capable variants for wrong
owner/lifecycle/receiver/field/constructor/hash input, duplicate setter, `self`/dependency/preimage
rebinding, reordered or noncanonical preimage construction, and an unrelated assignment/mutation;
then run all three passive-lifecycle consumers as part of the immutable feasibility re-gate and
correct the work-order evidence claim.

## Verdict

**ACCEPT-WITH-CHANGES**

- P0: 0
- P1: 1
- P2: 0

Not verified: exact-head Python 3.11/3.12 CI or the author-side full 7/7 claim against a committed
GREEN application head. The application implementation is uncommitted and outside this immutable
candidate, so it was not used as review authority.
