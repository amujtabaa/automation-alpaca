# WO-0150 RED contract R1 — E1 identity, inert readers, and direct venue bridge

Status: **EXACT-COMMIT REVIEW CANDIDATE — R1 — documentation only**

This is the active replacement RED contract for WO-0150 under its authorized
narrow E1/E2 boundary correction. It does not activate WO-0151, implement E2,
or grant a persistence, runtime, database, broker, network, or credentials
capability. The original `WO-0150-RED-CONTRACT.md` remains retained historical
evidence and does not satisfy this R1 gate.

## Scope and governing distinction

ADR-020 R2 and ADR-021 R2 assign controller admission/currentness, successful
generation registration, lineage classification, and canonical-fact mutation to
the E2 composite reducer. E1 owns only deterministic data shapes which E2 will
later consume. A seal re-derived from raw caller data proves only consistency;
it is not E2 provenance.

The R1 implementation MUST provide only:

1. deterministic `AcquisitionGenerationId` encoding and strict coordinate
   validation;
2. nonconstructable, immutable, schema-neutral `GenerationBindingView`,
   `GenerationRecordView`, and `GenerationRouteView` declarations;
3. opaque, non-enumerable empty `GenerationRegistry` and
   `AcquisitionLineageIndex` readers; and
4. the exact-type, nonconstructable, current-book-derived
   `VenueRecoveryBook.acquisition_correlation` read projection implemented from
   direct venue indexes, including broker-correlated human roots.

It MUST NOT provide a successful E1 admission, registrar, binder, route writer,
late-fact updater, raw-to-receipt factory, or test-only construction seam.
Before E2 supplies a fully authenticated composite transition, all registry and
lineage lookups MUST return `None`, never infer a current generation, and never
make a generation serving.

## Frozen identity wire contract

`AcquisitionGenerationId` is a 64-character lowercase SHA-256 hexadecimal
identity with the same exact-type, decoded-byte, and sealed-value discipline as
`MarketStreamGenerationId`. A raw instance is data only and is never authority.

Its private derivation is exactly the SHA-256 digest of `_pack_parts` with domain
`execution-core/acquisition-generation-id/v1` and these ordered byte parts:

1. `_encode_text(application_generation_id.value)`;
2. `_encode_position_scope(position_scope)`;
3. `_encode_int(successor_ordinal)`;
4. the exact 32-byte `dual_mandate_binding_commitment`;
5. the exact 32-byte predecessor controller-head or canonical genesis-head
   commitment; and
6. the exact 32-byte `emergency_recovery_compatibility_commitment`.

For a first-controller coordinate, E1 exposes a private helper to derive the
canonical genesis candidate with domain
`execution-core/acquisition-controller-genesis-head/v1`, the application
generation text, and exact position scope. For a successor coordinate, part
five is an opaque controller-head commitment supplied by E2. The derivation
accepts any otherwise well-formed 32-byte predecessor/genesis coordinate; it
cannot determine controller admission, currentness, or whether ordinal zero
uses the canonical candidate. The first ordinal is zero; an ordinal is an exact
`int`, not `bool`, in `0..2**64-1`. E1 may validate exact type, range, and byte
length only. A changed but well-formed coordinate MUST derive a different,
non-authoritative data identity, not an E1 admission failure. E1 MUST NOT parse,
compare, approve, or interpret the policy content of the three opaque
commitments. `_acquisition_generation_id_is_canonical` proves wire integrity
only; it does not prove reducer admission.

## Frozen public surface

The exact `app.execution_core.acquisition.__all__` set is
`GenerationServingClass`, `GenerationRouteKind`, `GenerationBindingView`,
`GenerationRecordView`, `GenerationRouteView`, `GenerationRegistry`, and
`AcquisitionLineageIndex`. The established `app.execution_core` package root is
broader and remains so. Relative to the R1 activation parent, WO-0150's exact
additive package-root export delta is those seven names plus
`AcquisitionGenerationId` and `VenueAcquisitionCorrelation`; all predecessor
root exports remain intact. No other package-root export may be added, omitted,
renamed, or repurposed by this R1 correction.

```python
class AcquisitionGenerationId(_ExactIdentity): ...

class VenueAcquisitionCorrelation:  # opaque/read-only
    application_generation_id: ApplicationGenerationId
    position_scope: PositionScope
    request_occurrence_id: RequestOccurrenceId
    effect_id: EffectId
    leg_key: VenueLegKey | None
    root_key: RootFillKey | None
    correlation_commitment: bytes

class VenueRecoveryBook:
    def acquisition_correlation(
        self,
        request_occurrence_id: RequestOccurrenceId,
        effect_id: EffectId,
        *,
        leg_key: VenueLegKey | None = None,
        root_key: RootFillKey | None = None,
    ) -> VenueAcquisitionCorrelation | None: ...

class GenerationServingClass(Enum):
    LIVE = "LIVE"
    RETIRED_UNSERVING = "RETIRED_UNSERVING"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"

class GenerationRouteKind(Enum):
    REQUEST = "REQUEST"
    EFFECT = "EFFECT"
    OWNER = "OWNER"
    ROOT = "ROOT"
    FACT = "FACT"

class GenerationBindingView:  # opaque/read-only
    generation_id: AcquisitionGenerationId
    application_generation_id: ApplicationGenerationId
    position_scope: PositionScope
    successor_ordinal: int
    dual_mandate_binding_commitment: bytes
    predecessor_or_genesis_head_commitment: bytes
    emergency_recovery_compatibility_commitment: bytes
    binding_commitment: bytes

class GenerationRecordView:  # opaque/read-only
    binding: GenerationBindingView
    economics_head_commitment: bytes
    serving_class: GenerationServingClass
    closure_summary_commitment: bytes

class GenerationRouteView:  # opaque/read-only
    route_kind: GenerationRouteKind
    source_commitment: bytes
    generation_id: AcquisitionGenerationId

class GenerationRegistry:
    @classmethod
    def empty(cls) -> GenerationRegistry: ...
    def record(self, generation_id: AcquisitionGenerationId) -> GenerationRecordView | None: ...

class AcquisitionLineageIndex:
    @classmethod
    def empty(cls) -> AcquisitionLineageIndex: ...
    def route_request(self, request_occurrence_id: RequestOccurrenceId) -> GenerationRouteView | None: ...
    def route_effect(self, effect_id: EffectId) -> GenerationRouteView | None: ...
    def route_owner(self, leg_key: VenueLegKey) -> GenerationRouteView | None: ...
    def route_root(self, root_key: RootFillKey) -> GenerationRouteView | None: ...
    def route_fact(self, fact_key: ExecutionFactKey) -> GenerationRouteView | None: ...
```

No package-root change beyond the exact nine-name additive delta, public mutation
method, iterator, mapping escape hatch, or venue private accessor is permitted.

`VenueAcquisitionCorrelation` MUST reject normal construction and subclassing.
It is a current-book-derived output-only read projection, never a transferable
proof or capability. Query arguments are selectors only. There MUST be no
module-level raw-field correlation factory: the sole production construction
site is inside `VenueRecoveryBook.acquisition_correlation` after its exact
direct-index checks (or an exact private checked relation confined to that
method). A raw, copied, subclassed, or field-reassigned lookalike grants no E1
authority. Future E2 must re-query the authenticated current
`VenueRecoveryBook` inside its composite transition and MUST NOT accept a
caller-, persistence-, or test-supplied correlation object by itself.

Its `correlation_commitment` is exactly `_commit_parts` with domain
`execution-core/venue-acquisition-correlation/v1` and these ordered parts:

1. `_encode_text(application_generation_id.value)`;
2. `_position_scope_index_key(position_scope)`;
3. `_request_occurrence_index_key(request_occurrence_id)`;
4. `_effect_index_key(effect_id)`;
5. `_leg_index_key(leg_key)`, or `_commit_parts` with domain
   `execution-core/venue-acquisition-correlation/no-leg/v1` when `leg_key` is
   absent; and
6. `_coverage_root_index_key(root_key)`, or `_commit_parts` with domain
   `execution-core/venue-acquisition-correlation/no-root/v1` when `root_key`
   is absent.

The private seal is exactly `_commit_parts` with domain
`execution-core/venue-acquisition-correlation-seal/v1` and the correlation
commitment. The commitment and seal are deterministic field-integrity checks
which bind every exposed relation field; they are not producer authentication.

## Functional requirements

- **FR-01 — exact identity data.** `AcquisitionGenerationId` MUST remain a
  lowercase 64-character SHA-256 value derived from the previously frozen domain
  and ordered coordinate encoding. The derivation MUST validate exact types,
  32-byte commitments, and a non-bool ordinal in `0..2**64-1`; it MUST NOT
  itself admit or register a generation. A substituted but well-formed
  predecessor/genesis, mandate, or compatibility commitment produces only a
  different data identity; E2 alone decides whether any coordinate is admitted
  or current.
- **FR-02 — opaque inert readers.** All three view classes MUST reject normal
  construction and subclassing. `GenerationRegistry.empty()` and
  `AcquisitionLineageIndex.empty()` MUST be exact-type, immutable,
  non-enumerable, authority-free values. Valid lookup input MUST yield `None`;
  malformed input MUST refuse without mutation.
- **FR-03 — no false provenance.** `acquisition.py` MUST NOT expose or retain a
  successful private helper that transforms raw identifiers, commitments,
  classifications, roots, facts, or caller-built objects into an input trusted
  for registry/index mutation. Every successful registry/index/fact operation is
  deferred to WO-0151 E2.
- **FR-04 — direct venue bridge.**
  `VenueRecoveryBook.acquisition_correlation` MUST return a correlation only
  when the supplied request, effect, application generation, exact
  `PositionScope`, and every supplied owner-bearing selector form one unique
  direct relation. At least one selector (`leg_key` or `root_key`) MUST be
  supplied; an absent pair MUST return `None`. The request-to-effect map, the
  effect record, a selected root entry, and the selected leg owner (including a
  root-derived leg) must agree exactly. A zero match, contradictory dual
  selector, same-account/different-symbol scope, owner, request, effect, leg,
  or root mismatch MUST return `None`; it MUST never choose an arbitrary direct
  relation. The normal-broker and broker-correlated-human-root paths are both
  required. The result is an output-only current-book read projection, not a
  caller-provided or transferable provenance input. The method MUST NOT inspect
  audit/materialized/effective-state readers or expose private book state.
- **FR-05 — closed static E1 boundary.** `acquisition.py` MUST have no
  `ast.Import` node and every `ast.ImportFrom` node must occur directly in the
  module body, contain no wildcard alias, and match exactly one of these
  `(level, module, imported_name, alias)` entries:

  ```python
  {
      (0, "__future__", "annotations", None),
      (0, "dataclasses", "dataclass", "_dataclass"),
      (0, "dataclasses", "field", "_field"),
      (0, "enum", "Enum", "_Enum"),
      (0, "hashlib", "sha256", "_sha256"),
      (1, "fills", "PositionScope", "_PositionScope"),
      (1, "fills", "_commit_parts", None),
      (1, "fills", "_encode_int", None),
      (1, "fills", "_encode_position_scope", None),
      (1, "fills", "_encode_text", None),
      (1, "fills", "_pack_parts", None),
      (1, "identity", "AcquisitionGenerationId", "_AcquisitionGenerationId"),
      (1, "identity", "ApplicationGenerationId", "_ApplicationGenerationId"),
      (1, "identity", "EffectId", "_EffectId"),
      (1, "identity", "ExecutionFactKey", "_ExecutionFactKey"),
      (1, "identity", "RequestOccurrenceId", "_RequestOccurrenceId"),
      (1, "identity", "RootFillKey", "_RootFillKey"),
      (1, "identity", "VenueLegKey", "_VenueLegKey"),
      (1, "identity", "_acquisition_generation_id_is_canonical", None),
  }
  ```

  The checker MUST run that literal allowlist against the actual production
  module, not only synthetic snippets. Its top-level class names must be exactly
  `GenerationServingClass`, `GenerationRouteKind`, `GenerationBindingView`,
  `GenerationRecordView`, `GenerationRouteView`, `GenerationRegistry`, and
  `AcquisitionLineageIndex`; its top-level function names must be exactly
  `_require_exact`, `_require_commitment`, `_require_ordinal`,
  `_acquisition_controller_genesis_head`, `_derive_acquisition_generation_id`,
  `_registry_is_authentic`, `_empty_route_result`, and `_lineage_is_authentic`.
  The views expose only `__init__` and `__init_subclass__`; the registry exposes
  only `__init__`, `__init_subclass__`, `empty`, and `record`; the index exposes
  only `__init__`, `__init_subclass__`, `empty`, `route_request`, `route_effect`,
  `route_owner`, `route_root`, and `route_fact`. Any extra state-bearing or
  mutation-capable class, function, method, iterator, mapping escape hatch, or
  `object.__new__` construction of a view is rejected. `object.__new__` and
  `object.__setattr__` are permitted only to mint the two empty containers inside
  their exact `empty` class methods.

  `acquisition.py` MUST have no venue import, dynamic import, `getattr`
  reach-through, private dependency renaming, or direct/private mutation seam.
  Both absolute and relative forms of authority, protection, recovery,
  persistence/runtime, clock, randomness, and dynamic import dependencies MUST
  reject. The following venue private names are forbidden even through an alias
  or `getattr`: `_current_effect`, `_effect_by_request_occurrence`,
  `_effect_by_id`, `_owner_by_leg`, `_acquisition_correlation_by_root`, and
  `_audit_hydrate_book`.

## Required RED and acceptance controls

1. **Identity known answers and structural refusals (FR-01).** Literal first and successor
   coordinates reproduce their frozen values; independently changing each
   coordinate changes the value. Invalid exact types, invalid commitment sizes,
   and invalid ordinals refuse. A changed but well-formed predecessor/genesis,
   mandate, or compatibility coordinate derives a different data identity and
   does not demonstrate admission. These controls demonstrate data encoding
   only, never admission.
2. **Inert-reader controls (FR-02/FR-03).** Empty containers reject normal
   construction/subclassing, expose only their frozen reader methods, and return
   `None` for every valid source/generation key. A raw identity, copied
   commitment, or caller-built view cannot create a record, a route, or serving
   state. The actual `acquisition.py` AST must have the exact closed structural
   surface in FR-05; synthetic raw-to-trusted mutation helpers remain
   failure-capability controls rather than the only proof.
3. **No-fallback control (FR-02).** Missing/unbound request, effect, owner,
   root, and fact remain `None`, including same-account/same-symbol values. No
   current-generation fallback or inferred serving classification is permitted.
4. **Venue directness and output-only provenance (FR-04).** Normal-broker and
   broker-correlated-human roots both produce an exact immutable,
   nonconstructable correlation while audit and effective-state readers are
   tripwired. The correlation commitment/seal must bind every exposed field for
   integrity. A source-level control proves that there is no raw-field factory,
   the query is the sole production construction site, and no production
   consumer accepts a correlation as standalone authority. Missing selectors,
   request/effect mismatch, same account with a different symbol/scope, wrong
   owner, mismatched leg/root, and zero-or-ambiguous direct relation each return
   `None`.
5. **Boundary controls (FR-05).** A narrow AST checker must reject both import
   styles, any deviation from the literal actual-module allowlist, forbidden
   local modules, unsafe standard-library dependencies, private venue access,
   extra class/function/method state or mutation surface, and public
   mapping/iteration escape hatches. Synthetic code snippets must demonstrate
   failure for relative and absolute forbidden imports, module aliases,
   randomness/time imports, dynamic imports, private venue attributes and
   `getattr`, an extra `items` reader, raw view construction, and an extra
   raw-to-trusted helper.

The former A-to-B-to-C registration/binding/late-fact controls are not removed
from the architecture. They are explicit WO-0151 E2 acceptance controls, where
one authenticated composite transition can atomically bind controller
currentness, venue correlation, source scope, canonical fact provenance, and
the registry/index state.

## Explicit exclusions

This R1 contract MUST NOT add controller admission/currentness, protection or
claim policy, canonical-fact interpretation, registry/index mutation,
persistence, SQL/DDL, runtime wiring, broker/network activity, credentials,
CI-workflow changes, master merge, deletion, cleanup, or later work-order
activation.

## Candidate freeze and review record

The R1 documentation candidate is isolated from the uncommitted application and
test exploration. Its exact source set contains only:

- `work/active/WO-0150-reset-kernel-e1-generation-lineage.md`;
- `work/review/REV-0057/CORRECTION-02.md`;
- `work/review/REV-0057/CORRECTION-03.md`;
- `work/review/REV-0057/CORRECTION-04.md`;
- `work/review/REV-0057/WO-0150-IMPLEMENTATION-BOUNDARY-FINDINGS-R1.md`;
- this R1 contract;
- `pkl/project/goals.md`, `pkl/architecture/architecture-map.md`, and
  `pkl/log.md`; and
- `work/ledger.jsonl`.

Before independent review, the implementation seat MUST write a detached
manifest recording the exact parent commit, this exact path set, and SHA-256 for
each path. The separate preflight request and result MUST name that manifest
hash. Only the accepted documentation set and its review evidence may be staged
and committed for the R1 activation record; no application or test path is part
of this review freeze.

## Review and stop conditions

The R1 candidate requires a fresh independent exact-candidate review with
P0=0/P1=0 before implementation resumes. Stop and return to planning if the
R1 controls require E1 to admit a generation, decide controller currentness,
interpret fact truth, scan retained history, expose mutable storage, add a
public mutation seam, or change any accepted ADR.
