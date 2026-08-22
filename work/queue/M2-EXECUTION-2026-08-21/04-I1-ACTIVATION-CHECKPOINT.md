# M2-I1 implementation activation checkpoint (append-only)

Status: **START CHECKPOINT RECORDED — IMPLEMENTATION ACTIVATED FOR WO-0165 ONLY**

Recorded by: local coding LLM implementation seat (ox-alpha)

Recorded at: 2026-08-21

This checkpoint satisfies the WO-0165 pre-implementation hold requirement that
`base_sha` be recorded in an append-only activation checkpoint before source or
test edits. It records facts only; no authority boundary is changed by this
file.

## Exact implementation base

| Item | Exact value |
| --- | --- |
| Active work order | `WO-0165` (M2-I1 immutable durable codecs) only |
| Branch | `codex/m2-i1-durable-codec-r1` |
| Base commit | `abcefca80d1a16ae86f7982d27ba6212a9504bfa` |
| Base tree | `e52f5e6345049388db1544a164ae99f30e057724` |
| Upstream | `origin/codex/m2-i1-durable-codec-r1` at `abcefca80d1a16ae86f7982d27ba6212a9504bfa` (in sync) |
| Worktree | Clean before any edit |
| Preparation manifest | `work/queue/M2-EXECUTION-2026-08-21/PREPARATION-MANIFEST.sha256`, SHA-256 `ec7809b0cdcf17b0e0800ce3b5dd5b7d08145fb25aae974f1e5c923582436d68` (recomputed locally, exact match) |

The base commit is the exact merged documentation-only preparation baseline
`master` head named by the activation prompt. The branch descends from it with
zero additional commits at activation time.

## Regenerated inventory result (no drift)

The source/member/typed-route inventory was regenerated from this base per
`03-PREPARATION-MERGE-GATE.md`. All twelve hash-bound surfaces in
`02-CURRENT-SOURCE-INVENTORY.md` were re-hashed from working-tree bytes and
match exactly:

```text
63e8e1cae1d0bdcd502b4ef207df9d330e34e431c875b21eb7f4e6d6c201ea85  app/execution_core/__init__.py
372370dfd7bac68cd52d0f7ba0670652bc16712ca8ef7a4c15d685e03169afa3  app/execution_core/values.py
8f4b8472fe1de766cd3eea38472dae97ce9766ac0d93c79553eccee382f1781a  app/execution_core/identity.py
6d9f5dcf0c9bc6b04304f3eab4f5822560a8f1f0a2afededb3f5530f4e5f6e4c  app/execution_core/fills.py
b59971afddcc52c725a8ed5de3ab84c5e49ab58b8621250e39fcd169e8a2e767  app/execution_core/position.py
6e028f3c80c0d27af5b5cb4a5ec6336a0bdff9c876d11ce670c6369c840e118a  app/execution_core/authority.py
b10e0a5e8c55dbbedbfdb7156a5a6f8d9bef83867212f12299575aa67bf7dedb  app/execution_core/venue.py
1a93e5ce2bbc0f4c91c9038e73722dc7c484420080e6feb52fab9ad298d8371e  app/execution_core/protection.py
09cd9bb33fff2dcdcfadb68da837ea9afa108aac2fe75fface73b5121f07e0e0  app/execution_core/acquisition.py
684003e1ca480e1c6cd7bf2e2e8c864732bb2e0f67809acb3a550a814fddd40c  app/execution_core/recovery.py
5cf3db0e51b885cb735c2d23461f6e087b67a32f182a7920cb188a4e1661770b  tests/execution_core/test_values.py
1ffda4dd5655401c95ec1eee20e25e0e424929ea7dfdd007b37ac49881b7e0d0  tests/execution_core/test_import_boundary.py
```

## Absence proof for new I1 surfaces

At the base commit the following paths do not exist (verified):

```text
app/execution_core/profiles.py        ABSENT
app/execution_core/durable_codec.py   ABSENT
tests/execution_core/test_profiles.py ABSENT
tests/execution_core/test_durable_codec.py ABSENT
```

`app/execution_core/` contains exactly the ten inventory files. No production
profile class, durable codec, SQLite reset repository, or schema exists.

## Interpretation notes binding this implementation

1. `unicodedata` must join `_ALLOWED_STDLIB_ROOTS` in
   `tests/execution_core/test_import_boundary.py`: ADR-024 rules 2 and 4 make
   already-NFC text a fail-closed contract for profile construction, and the
   Python standard library's only NFC facility is `unicodedata`. The module is
   deterministic, I/O-free, clock-free, randomness-free, and side-effect-free;
   adding it does not weaken any forbidden-root refusal. This edit is a direct
   I1 import pin within the allowed-path note for `test_import_boundary.py`.
2. ADR-024 rule 3 enumerates the opaque 32-byte hex fields as `*_profile_id`,
   `credential_handle_fingerprint`, and `deployment_identity`;
   `application_generation` is deliberately absent from that enumeration and is
   therefore implemented as ordinary canonical text under rule 2 (nonempty,
   NFC, no ASCII control), contributing its exact UTF-8 bytes to preimages.
3. Durable atoms refuse non-NFC and ASCII-control-bearing identity text at both
   encode and decode per EC-2, symmetrically, without normalization. Such M1
   identities remain constructible in unchanged M1 code; they simply have no
   durable representation in v1 of this contract (fail closed).

## Scope reminder

Only WO-0165 is activated. No SQL/DDL, database creation/access, migration,
runtime composition, credentials, broker/network calls, orders, promotion,
M2-I2+ work, or merge to `master` is authorized. Queued work orders remain
read-only inputs.
