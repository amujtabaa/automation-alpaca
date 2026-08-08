# WO-0149 specification and activation preflight

Status: **INDEPENDENT PLANNING / ACTIVATION REVIEW**

Candidate: `work/queue/WO-0149-reset-kernel-e-acquisition-cross-side-integration.md`

Activation base: `2462fb557172dd28a7475a763eca0b440c0298e3`

This is a review of a documentation-only candidate. WO-0149 application and test
implementation is explicitly not authorized. Review the exact file independently; conversation
summaries are orientation only and never evidence.

## Required authority packet

Read the smallest useful packet:

1. `AGENTS.md` and the permanent safety core in `CLAUDE.md`;
2. the candidate work order above;
3. accepted ADR-020 through ADR-023 and
   `docs/adr/ARCH-RESET-2026-07-RATIFICATION.md`;
4. the acquisition and side-symmetric executor sections of
   `work/queue/ARCH-RESET-2026-07/03-domain-specification.md`;
5. completed WO-0145 through WO-0148, limited to their public contracts, allowed paths, and
   closeout obligations; and
6. current public `authority.py`, `protection.py`, `venue.py`, `position.py`, and `identity.py`
   only as needed to assess whether the specified seams are bounded and feasible.

## Required disproof pass

Attempt to invalidate the candidate before accepting it. In particular, determine whether it
would permit any of the following:

1. caller-shaped generic `CreateBrokerEffect(BUY)` admission, creation, or final claim;
2. one overloaded or opaque mandate identity standing in for distinct acquisition-owner and
   protection-authority identities;
3. publication of a first owned BUY fill without the same sequenced transition updating
   acquisition and protection;
4. a protection exit that is stale, copied, or overtaken by a BUY between creation and final
   claim;
5. use of `VenueRecoveryBook.effects`, an audit collection, private state, or a test-only seam
   for hot-path cross-side authority;
6. residual sizing from net position or non-canonical economics, terminal-acquisition revival, or
   unsafe late-fill/correction/bust recovery;
7. persistence, broker/runtime action, human authentication, database work, or another M2+ concern
   hidden in the proposed pure-M1 boundary; or
8. an accepted-ADR conflict that requires a new architectural decision rather than a bounded
   public projection.

Assess the Fable M1--M4 war-game, future RED/mutation controls, allowed-path list, stop conditions,
and WO-0148 evidence-reconciliation rules. Confirm that a later implementation seat could
unambiguously distinguish an activation-complete work order from implementation authorization.

## Boundaries and output contract

This is a findings-only review. Do not edit source, tests, work orders, accepted authority,
ratification, PKL, ledger, or this request. Do not execute tests, application code, SQL/DDL,
database tooling, broker/Alpaca/network activity, or Git mutation. Do not commit, push, merge,
delete, or clean.

Write only `work/review/REV-0051/result.md`. Every finding must include priority, exact location,
requirement/evidence, concrete effect, and smallest complete resolution. Clearly separate a
supported finding from a concern that the candidate already addresses. End exactly with:

```text
Verdict: BLOCK | ACCEPT-WITH-CHANGES | ACCEPT
P0: <count>
P1: <count>
P2: <count>
Unverified: <items or none>
```

Activation may proceed only with `ACCEPT`, P0=0, P1=0, and no unresolved authority or scope
conflict. An ACCEPT authorizes no implementation.
