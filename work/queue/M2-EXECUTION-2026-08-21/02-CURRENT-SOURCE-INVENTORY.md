# M2-I1 current-source, member, and typed-route inventory

Status: **REGENERATED AT IMPLEMENTATION START — SOURCE HEAD `abcefca` — NO DRIFT**

## Exact heads

- Implementation-start head:
  `codex/m2-i1-durable-codec-r1@abcefca80d1a16ae86f7982d27ba6212a9504bfa`, tree
  `e52f5e6345049388db1544a164ae99f30e057724` (the exact merged documentation-only
  preparation baseline `master` head; recorded in
  `04-I1-ACTIVATION-CHECKPOINT.md`).
- Accepted source head: `master@177ea5fcd959b9e7d7d5a3172070f90f89ece963`.
- Accepted source tree: `99338a7832509645f17ed4f51c511e7dffb6c41f`.
- Ratified preparation branch before this packet:
  `codex/m2-regeneration-gate-a-r1@163ebf7db4025c0e9e8fcd743eb43ce7d10ce285`.
- `master...163ebf7` changes no `app/**` or `tests/**`; the execution source bytes therefore remain the
  accepted-source bytes below.

The implementation-start checkpoint regenerated this inventory from the exact merged
preparation `master` head before the first RED test: all twelve SHA-256 values below were
recomputed at `abcefca` and match exactly. No source drift; no c9 application hash or old
WO-0159-0163 inventory was reused.

## Hash-bound source surfaces

| Path | Lines | SHA-256 |
| --- | ---: | --- |
| `app/execution_core/__init__.py` | 357 | `63e8e1cae1d0bdcd502b4ef207df9d330e34e431c875b21eb7f4e6d6c201ea85` |
| `app/execution_core/values.py` | 116 | `372370dfd7bac68cd52d0f7ba0670652bc16712ca8ef7a4c15d685e03169afa3` |
| `app/execution_core/identity.py` | 343 | `8f4b8472fe1de766cd3eea38472dae97ce9766ac0d93c79553eccee382f1781a` |
| `app/execution_core/fills.py` | 1,610 | `6d9f5dcf0c9bc6b04304f3eab4f5822560a8f1f0a2afededb3f5530f4e5f6e4c` |
| `app/execution_core/position.py` | 2,024 | `b59971afddcc52c725a8ed5de3ab84c5e49ab58b8621250e39fcd169e8a2e767` |
| `app/execution_core/authority.py` | 9,885 | `6e028f3c80c0d27af5b5cb4a5ec6336a0bdff9c876d11ce670c6369c840e118a` |
| `app/execution_core/venue.py` | 14,611 | `b10e0a5e8c55dbbedbfdb7156a5a6f8d9bef83867212f12299575aa67bf7dedb` |
| `app/execution_core/protection.py` | 4,641 | `1a93e5ce2bbc0f4c91c9038e73722dc7c484420080e6feb52fab9ad298d8371e` |
| `app/execution_core/acquisition.py` | 5,673 | `09cd9bb33fff2dcdcfadb68da837ea9afa108aac2fe75fface73b5121f07e0e0` |
| `app/execution_core/recovery.py` | 1,553 | `684003e1ca480e1c6cd7bf2e2e8c864732bb2e0f67809acb3a550a814fddd40c` |
| `tests/execution_core/test_values.py` | 703 | `5cf3db0e51b885cb735c2d23461f6e087b67a32f182a7920cb188a4e1661770b` |
| `tests/execution_core/test_import_boundary.py` | 8,071 | `1ffda4dd5655401c95ec1eee20e25e0e424929ea7dfdd007b37ac49881b7e0d0` |

## M2-I1 member boundary

Existing exact scalar/value targets:

```text
Quantity
PriceUnits
PriceScale
TickMetadata
ReportedPrice
ExactBasis
```

Existing identity targets are every concrete `_ExactIdentity` subtype in `identity.py`, including
the stricter 64-lowercase-hex `MarketOccurrenceId`, `MarketStreamGenerationId`, and
`AcquisitionGenerationId`. The codec must persist only each identity's public exact value and type;
private caches or seals are re-derived by the owning constructor.

Existing composite identity keys are `ExecutionFactKey`, `RootFillKey`, and `VenueLegKey`. They are
included only as typed field compositions; their fill/venue semantics remain owned by current
reducers.

## New M2-I1 surfaces currently absent

```text
app/execution_core/profiles.py
app/execution_core/durable_codec.py
tests/execution_core/test_profiles.py
tests/execution_core/test_durable_codec.py
```

`ExecutionConnectionProfile` and `MarketDataSourceProfile` exist only as accepted ADR-024
contracts at this head. No production profile class, durable value codec, SQLite reset repository,
or schema exists in `app/execution_core/`.

## Typed-route refusal boundary

M2-I1 may add pure construction, encode, decode, and commitment-verification functions. It must not
route an input through `apply_execution_authority_input`, `apply_venue_recovery_input`, acquisition,
position, protection, broker, store, startup, or dispatch code. It must not alter any existing
reducer, effect, position, fill, venue, or currentness result.
