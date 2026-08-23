# REV-0075 R1 — owner-state checkpoint review result

Reviewer disposition: **ACCEPT-WITH-CHANGES**

Exact candidate reviewed: `1fd95518879a72aa79c2803fa6a24f3558016a2f`, tree
`08fff7b1fcadcbdab80a880244c2ce6090a99d69`, against base
`07173865c985895aecaf2fda7e1f0df70389198c`.

## Findings

### P1 — Direct execution proofs are self-consistent, not authenticated to retained state

Location: `app/execution_core/position.py:916`

`_m2_execution_state_from_direct_proof` verifies a self-derived state commitment but does not bind
the prior observation, root head, predecessor observation, or root claim to retained aggregate
state. A forged or cross-state revision slice can therefore reach `APPLIED` without proof that the
direct rows are current members of the retained registries. The smallest complete correction is an
opaque typed current-proof slice that binds and verifies the relevant direct rows against retained
root-head and seen-fact aggregate commitments, with substitution/cross-state mutation tests.

### P1 — Protection hydrator accepts a standalone stale or mis-profiled authority tuple

Location: `app/execution_core/protection.py:2524`

The supplied authority tuple type-checks but does not bind all of its selected application/profile,
scope, controller-currentness, and live-acquisition coordinates to the accepted proof context. An
otherwise authentic state payload can be hydrated with stale or wrong-profile authority selection.
The smallest complete correction is an opaque typed current-proof object that binds the envelope
selection, current controller/live-generation rows, and protection authority row, and verifies
every coordinate before hydration.

### P1 — M2 parity evidence omits required execution branches

Location: `tests/execution_core/test_position.py:174`

The first parity table omits a broker trade bust, SELL revision, fold/metadata mismatch, and
incoherent-snapshot bypass, while delegation is only source-text asserted. This leaves several
required public-to-owner branches unproven. The smallest complete correction is a behavior-level
delegation canary plus table-driven direct/public parity coverage of those branches.

## Verdict

**ACCEPT-WITH-CHANGES** — P0=0, P1=3, P2=0.

Unverified: the reviewer’s own full fill-suite invocation was interrupted before completion. The
findings above are source-derived and the final WO-0168a implementation review remains required.
