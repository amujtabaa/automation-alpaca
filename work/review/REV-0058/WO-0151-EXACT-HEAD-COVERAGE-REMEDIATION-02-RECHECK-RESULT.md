# WO-0151 exact-head coverage remediation 02 focused recheck result

## Review boundary and exact candidate

This was a fresh, bounded exact-delta review of the local coverage-remediation
candidate at branch `codex/arch-reset-2026-07-r1`, parent HEAD
`ec69b0d80a073d981d583a9193b181d5f4cb2255`. I did not reopen the accepted
R2-R11-R1 architecture or inspect unrelated production lanes.

The frozen inputs matched their required SHA-256 values:

| Input | Verified SHA-256 |
| --- | --- |
| Candidate manifest | `faddebfdac50609d9f051de3145aaba5529d402fdeb4a0da258e526e8842fb2d` |
| Recheck request | `6e17b9cc3c4220530fe4e87998ba3ffae6ae76a782f867d5c3b1c7d7fc612ae2` |

The candidate was exactly the three named tracked paths and hashes:

| Path | Verified SHA-256 | Delta from parent HEAD |
| --- | --- | --- |
| `app/execution_core/authority.py` | `eb48ef34f41000a26fc60851610e7bdf22812b090d7baf26531d81efe02a8f19` | 21 additions, 0 deletions |
| `app/execution_core/protection.py` | `1a93e5ce2bbc0f4c91c9038e73722dc7c484420080e6feb52fab9ad298d8371e` | 17 additions, 0 deletions |
| `tests/execution_core/test_acquisition.py` | `2301c656b6f378280e4e9ebe4f29b22e44a9e4ff4d203ecb4af96db055188ffb` | 461 additions, 0 deletions |

Total tracked delta: 499 additions, 0 deletions. `git diff --check` passed.
The manifest and request were the only additional untracked packet files when
the review began.

## Root-defect re-derivation

### 1. Truthy non-boolean commitment collision

The affected protection commitments encode boolean coordinates as `1 if value
else 0`. Before this candidate, an opaque copied state or venue projection
could replace `True` with a truthy non-`bool` while preserving the same cached
commitment. The authenticity functions did not first require those retained
coordinates to be exact booleans.

The correction is owner-local and fail-closed:

- `_projection_is_authentic` now rejects non-exact booleans for all six
  projection boolean coordinates before recomputing its seal
  (`app/execution_core/protection.py:2060`).
- `_state_is_authentic` now rejects non-exact booleans for all five state
  boolean coordinates before recomputing the state commitment
  (`app/execution_core/protection.py:2372`).

The checks do not change a valid reducer-produced state or projection. They
only prevent an invalid runtime shape from exploiting the commitment's
canonical boolean encoding. Opposite exact-booleans remain rejected through
the recomputed commitment, while truthy objects are rejected by exact type.

### 2. Stale cached BUY-economic digest

`AcquisitionEffectPermit` commits the nested `AcquisitionEffectTerms.commitment`.
Before this candidate, a copied terms object could retain that cached digest
while a nested quantity or price leaf was changed. Recomputing only the permit
commitment would then reproduce the unchanged outer commitment.

The new `_acquisition_effect_terms_is_authentic` reconstructs the exact terms
from quantity, limit price, order type, and evaluation time, causing the terms
constructor to revalidate the economic leaf and derive a new commitment
(`app/execution_core/authority.py:183`). The permit authenticator now requires
that check before recomputing its own commitment and seal
(`app/execution_core/authority.py:1803`). A copied `Quantity` or
`ReportedPrice` with changed economics therefore either fails exact economic
validation or derives a different terms commitment. The correction is private,
deterministic, I/O-free, and adds no authority: direct terms remain data, while
only an authentic authority-minted permit can serve.

## Bypass and control analysis

The deterministic field-mutation helper checks every retained dataclass field
of the selected owner values (`tests/execution_core/test_acquisition.py:90`).
For exact booleans it performs both the opposite valid boolean and a truthy
wrong-type substitution. For nested dataclasses it copies the value and alters
one leaf while retaining cached outer digests. This makes the two corrected
defects observable: removing either new production check lets its corresponding
forgery survive.

The helper also proved RED-capable independently: a checker deliberately made
to accept every value caused the helper to raise its expected assertion. The
focused owner-boundary tests cover acquisition state/lineage, authority
currentness and permits, protection state/projections, venue fact relations,
and direct-construction/subclass refusal
(`tests/execution_core/test_acquisition.py:4266`).

The following realistic bypasses were not reproduced:

- A truthy non-boolean cannot retain serving protection authenticity.
- Type-faithful mutation of a committed boolean, integer, digest, identity,
  enum, economic leaf, or nonempty retained container changes or invalidates
  its owner commitment.
- A nested quantity or price cannot diverge from the cached BUY terms digest,
  and a permit containing such terms is rejected.
- Caller construction and subclassing remain refused for the named opaque
  owner-minted boundaries (`tests/execution_core/test_acquisition.py:4545`).
- Copied currentness registrations and sealed commands reject retained-field
  mutation. Existing complete matchers continue to revalidate their current
  authority, execution, venue, protection, fact, and controller sources.
- Raw cross-owner source carriers are not incorrectly promoted into recursively
  minted authority. The tests use type-only substitutions for those raw
  carriers and separately exercise their owner authenticator or complete
  serving matcher.

For optional coordinates whose sampled value is `None`, the generic helper
uses a deterministic wrong-type substitution rather than inventing an
annotation-dependent valid alternative. I statically traced those retained
coordinates through their existing owner commitment or complete matcher; this
does not expose an uncommitted serving coordinate in the reviewed delta.

## Scope and fresh evidence

No public name or signature, export, runtime wiring, persistence path,
database path, broker/network path, credential path, CI workflow, or unrelated
production behavior was added. The only new production symbol is the private
terms authenticator; the protection change tightens two existing private
authenticators.

Fresh review-seat evidence:

- Nine focused pure acquisition/currentness/protection/venue controls: **9/9
  passed**, exit 0.
- Mutation-helper RED probe: **passed**, exit 0.
- Ruff check on all three candidate paths: **passed**.
- Ruff format check on all three candidate paths: **passed**.
- Mypy on both changed production paths: **passed**.
- Exact three-path `git diff --check`: **passed**.

I did not run R2 or the full repository suite because those may instantiate
database-capable fixtures and were prohibited for this seat. I did not
independently verify GitHub Actions run `31174280408`; its historical result is
not relied upon for this focused verdict. The repository-wide 93% ratchet and
the clean exact-head Python 3.11/3.12 result remain pending the authorized
external CI gate.

## Findings and verdict

- P0: **0**
- P1: **0**
- P2: **0**

The exact candidate closes the two reviewed authenticity defects without
widening authority or changing accepted acquisition/protection semantics. Its
field-mutation controls are failure-capable for the corrected paths, and the
remaining layered source checks preserve owner boundaries.

**ACCEPT**
