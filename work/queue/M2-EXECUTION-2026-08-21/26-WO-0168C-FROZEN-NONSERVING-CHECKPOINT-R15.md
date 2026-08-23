# WO-0168c frozen non-serving checkpoint contract — R15 direct selected-state projection

Status: **PREFLIGHT REMEDIATION CANDIDATE — DOCUMENTATION ONLY; NO DDL OR DATABASE AUTHORITY**

Date: 2026-08-23

R15 incorporates accepted R13 and supersedes R14 after both R14 reviewers returned
`ACCEPT-WITH-CHANGES` (`P0=0`, `P1=2`). R15 replaces R14's owner-access rule and reconciles the
additional authority/lineage ambiguities found while deriving the implementation. All unchanged
R13/R12 recursive authority remains in force.

## 1. Work is proportional only to selected current state

Projection must not call `VenueRecoveryBook._validate_full`, any whole-history materializer, or
walk any persistent radix node/whole order. Venue adds two derived, package-private direct indexes:

- `_checkpoint_effect_source_ordinal_by_id`, keyed exactly like `_effect_by_id`; and
- `_checkpoint_owner_source_ordinal_by_leg`, keyed exactly like `_owner_by_leg`.

Each value is the immutable zero-based insertion ordinal already represented by `_effect_order` or
`_owner_order`. The reducer installs the ordinal atomically with the corresponding first current
row and preserves it thereafter. Empty construction, hydration/rebuild, every immutable transition,
and full-audit validation maintain exact key/cardinality/ordinal agreement. The indexes are derived
lookup accelerators: they do not alter any serving commitment or authority decision.

The projector performs direct lookups only for proof-selected effect IDs, owner leg keys, roots,
scopes, generations, streams, and lineage identities. Selected venue effect order is the direct
effect ordinal restricted to the selected set and must agree with strictly increasing selected SQL
`VenueEffectRecord.created_ordinal`; selected owner order is the direct owner ordinal restricted to
the selected set. Dense projected ordinals are assigned `0..n-1`. Unrelated history, including more
than 65,535 terminal entries, is neither touched nor counted. Family caps apply after selection.

## 2. Exact restart-required venue subset

The venue wire contains only restart-required current rows reachable by selected keys:

- authority epochs, execution snapshots, bootstrap targets, protection cursors, and coverage
  provenance by selected scope;
- effects, claims, acceptance proof/contradictions, owners/current attempts, closure heads, and
  economic high waters by selected effect/owner identities;
- acquisition correlations and current human/broker coverage by selected roots; and
- reconciliation or execution-reconciliation rows only when their input ID is directly referenced
  by one of those selected current closure/coverage rows.

The projector resolves every such input ID through the owner's direct by-input map and requires
exact current-map equality. Append-only ledger rows, registry-transition proofs, and terminal rows
not directly referenced by the selected current subset are audit history and are omitted. Top-level
registry/reconciliation counters and heads, selected execution checkpoints, and coverage provenance
remain the compact current summaries. Missing, extra, duplicate, stale, or cross-scope referenced
rows fail. This rule replaces any implication that a whole owner ledger is checkpoint state.

## 3. Effectless manual flatten is directly reachable

For every selected scope, authority projection queries `_manual_flatten_by_scope` directly. A
present flatten ID must resolve through `_manual_by_id`, match the selected scope and current phase,
and be unique. Effect-backed manual IDs discovered through selected authorizations must equal that
scope index. No older manual row is retained. The number of discovered current manuals must equal
both current-index map cardinalities after accounting for selected scopes; any unselected-scope
entry is a splice/integrity refusal because the selection contains every application scope.

Pure controls include authentic zero-cancel `WAITING` and terminal-cancel `READY` states, plus
missing, duplicated, stale, and cross-scope index mutants.

## 4. Authority authenticity and commitments are domain-separated

Projection performs exact deep validation of each reached authority member and proves reached-key
cardinality against every authority current map; shallow `_validate_authority_state` alone is not
sufficient. The 14-member authority row's final commitment is exactly:

`K("execution-core/m2-authority/checkpoint/v1", canonical row without final member)`.

The projected-envelope owner preimage uses a distinct source-projection commitment:

`K("execution-core/m2-authority/source-owner/v1", canonical row without final member)`.

The latter binds the exact deeply authenticated source projection; it is not a serving proof and is
not interchangeable with the checkpoint-integrity commitment. This replaces the unauthorized
`execution-core/m2-authority/state/v1` domain and resolves the absence of a pre-existing whole-state
authority commitment.

## 5. Lineage integer grammar and live-generation shape

The lineage source-binding rows are corrected to encode SQL surrogate IDs as integers:

- REQUEST/EFFECT: `["m2.acquisition.LineageEffectSource/v1",A(effect_external)]`;
- OWNER: `["m2.acquisition.LineageOwnerSource/v1",I(scope_id),A(owner_id)]`;
- ROOT: `["m2.acquisition.LineageRootSource/v1",I(root_fill_key_id)]`; and
- FACT: `["m2.acquisition.LineageFactSource/v1",I(fact_id)]`.

No integer-to-text or invented durable-atom coercion is admitted. The lineage route identity remains
the canonical durable request/effect/leg/root/fact identity, and each source binding must agree with
the exact selected SQL record. For an authentic `AcquisitionControllerState`, the controller's live
generation member is mandatory `A(live_generation_id)`, not nullable; decoder and projector reject
the unreachable null form.

## 6. Controls and scope

Pure/static controls kill whole-history materialization, `_root`/radix traversal, reflection,
missing rank lookup, SQL-order substitution for owner order, integer-to-atom coercion, the two wrong
authority commitment domains, shallow-only authority validation, and omission of the manual-scope
route. A noise-invariance control retains an over-cap quantity of unrelated terminal history while
an in-cap selected subset produces identical bytes and succeeds through only direct lookups.

Implementation may additionally edit `app/execution_core/venue.py` and
`tests/execution_core/test_venue_checkpoint_hardening.py` solely for the two derived source-ordinal
indexes and their invariants. R15 changes no SQL, DDL byte, public export, transaction rule, runtime
composition, or serving authority. Fresh REV-0077 review must return exact R15 `ACCEPT` with
`P0=0/P1=0` before these source additions or the nonempty projector implementation proceed.
