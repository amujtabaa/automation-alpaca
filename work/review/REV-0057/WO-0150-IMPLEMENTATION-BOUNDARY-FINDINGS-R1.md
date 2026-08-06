# WO-0150 implementation boundary findings R1

Status: **FINDINGS ONLY — return to planning required — no contract amendment or
acceptance is implied.**

## Scope

This record preserves the two independent read-only reviews of the first local
GREEN candidate. It does not replace `result.md` or `recheck-result.md`, both of
which remain historical documentation-preflight evidence for their exact prior
candidates only.

## Reconciled findings

P0: 0

P1: 3

1. **The E1 receipt boundary was self-authenticating rather than E2-authenticated.**
   The reviewed candidate's private admission, initial-lineage, and late-fact
   receipt builders accepted raw coordinates and sealed them locally before the
   registry/index trusted them. A deterministic self-seal verifies internal
   consistency, not controller admission/currentness or canonical fact truth.
   The source spans reviewed were `app/execution_core/acquisition.py:810-922`,
   `983-1106`, and `1156-1242` in that candidate.

2. **Lineage mutation was not atomic with registered-generation and exact venue
   proof.** The reviewed binder accepted only an index and raw request/effect/
   owner/root/fact values. It could therefore route an unregistered generation
   or a same-account cross-symbol source. It did not consume the sealed direct
   `VenueAcquisitionCorrelation` bridge. The reviewed late-fact path likewise
   lacked canonical-root/fact predecessor proof.

3. **The failure controls did not disprove import laundering or the provenance
   gaps.** The original AST test covered only `from ... import ...`, allowing
   module-style local imports and private venue reach-through. The behavioral
   tests constructed the same caller-shaped receipt values that the production
   candidate trusted, so they could not establish the required E2 provenance.

## Architectural disposition

ADR-020 R2 and ADR-021 R2 require admission/currentness and lineage
classification to be produced by the later E2 composite reducer. The active
WO-0150 and its RED contract, however, require successful A-to-B-to-C registry
and index population plus late-fact mutation. This is a material conflict with
the WO's own stop rule: completing those transitions in E1 would require E1 to
decide or imitate E2 admission/currentness.

The safe correction is to narrow E1 to deterministic, non-authoritative
identity derivation; nonconstructable immutable view declarations; inert
read-only containers; the direct no-history venue correlation bridge; and a
failure-capable import/private-access guard. All successful registry/index/fact
mutation must move to WO-0151's later E2 composite transition, where exact
controller and canonical-fact proof exist.

No ADR change is needed, but WO-0150 and the RED contract need an explicit
human-authorized amendment and a fresh independent RED acceptance before this
work continues or closes.

## Current local state

The local worktree contains an uncommitted exploratory simplification that
removes the self-authenticating mutation helpers. Its original successful-route
tests now fail by design because they still assert the superseded, unamended E1
contract. It is not evidence of a completed or accepted WO-0150 result, and it
must not be committed, pushed, or treated as a replacement contract without the
required re-gate.
