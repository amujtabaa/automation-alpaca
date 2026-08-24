# Claude continuation — finish WO-0168c (R20 §2 then §4), then serial M2 closeout

Status: **ACTIVE CONTINUATION PROMPT — supersedes `32-CLAUDE-OPUS-M2-CONTINUATION.md` for the
remaining WO-0168c work.** Documentation only; it grants no authority beyond what WO-0168c and the
accepted R20 contract already record.

Scope note: `work/queue/M2-EXECUTION-2026-08-21/**` is enumerated file-by-file in WO-0168c's
`allowed_paths` (08 through 32), so adding this file is a deliberate scope extension. Ameen
authorized it explicitly on 2026-08-24; the work order's `allowed_paths` is amended in the same
commit to record it.

Self-contained continuation prompt. Treat repository files and exact Git objects as
authority; do not infer authority from prior chat. Verify every identity below BEFORE
writing code. If an identity does not match, STOP and report the mismatch.

## Mission and seat

You are the implementation and first-pass fresh-review seat. Finish WO-0168c from its
accepted R20 contract, then proceed serially through WO-0168b (repo `WO-0168`), WO-0169,
WO-0170, terminal M2 closeout, and documentation-only M3 preparation. Codex retains the
governor seat for changed-DDL validation, disputed high-risk findings, and terminal M2 review.

Root-cause corrections are required. Avoid band-aids and avoid complexity with no contract
clause and no failure-capable test behind it. Never claim a work order complete from prose
or inherited evidence.

## Exact identities to verify first

```
Repository : https://github.com/amujtabaa/automation-alpaca.git
Branch     : codex/claude-opus-m2-wo0168c-r1
HEAD       : 8042dd8644561cbba21f571e17e3b9350f644d1a
Tree       : 87051511e4b0ee7bcb62ee07184eaa3342f1e8dc
```

Ancestry that must hold (`git merge-base --is-ancestor`):
```
a6bba249912d81dac0862030e294a2970a76ecf2  R20 contract commit  (tree 72c0fa4a576afa1f9e70ca544e89f6c67940282f)
cd759c2e8b7ae61d1eb52abad0c9e68a7d90e781  REV-0077 ACCEPT P0=0/P1=0 (result-r20.md)
9284bd90497a470dcaa23c7f246735b73286fb42  pre-existing WIP base (tree b0581f92fc2b457d4e7a73e879c47d97ab7ff8c7)
1fabe5da44879c7fe66a01d9dc156a81932837c6  handoff commit; this session's work starts here
```

File digests (SHA-256):
```
4bee617d48ee0f0dbcfc6b9109b6a4aaf73d9ce6c335573e7914793d83e6a40e  work/queue/M2-EXECUTION-2026-08-21/31-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R20.md
29a03a90f8f91b5d902ffd15c78198bb144ca00aa534fccf2b4cf9d6c867e807  app/execution_core/persistence/checkpoint_codec.py
eaee705f2327d61bb98bda35e2d2c169f401b7d6d8c623f6fbb15d1da1d1a800  tests/execution_core/test_persistence_runtime_checkpoint_pure.py
```

Changed-DDL gate (STILL CLOSED — must remain byte-identical until Ameen opens it):
```
SCHEMA_DDL   : 178,791 UTF-8 bytes, sha256 73dce64aa76172a9123a51819b668013d13850b86d40d7f19c678bb3171e9c88
_GATE_DIGEST : 2dc33ba1af41d7516b2cde43cac85ea6644dc9ab904501065aae1c77b14d3859  (intentionally unchanged; it pins
               the PRE-change DDL, which is exactly why the gate is still owed)
```

Expected starting test state — the four permitted pure files collect **125**, with **123 passed
and exactly 2 failed**. The two failures are the open R20 §4 obligations, not regressions:
```
test_venue_checkpoint_hardening.py::test_r19_checkpoint_projection_has_no_source_order_or_rank_dependency
test_venue_checkpoint_hardening.py::test_r19_selected_authority_families_do_not_require_whole_superset_cardinality
```

## What is already done (do NOT redo, do NOT revert)

- `ff1404b` — R20 §1. Venue owner provenance is the distinct
  `K("execution-core/m2-venue/source-owner/v1", venue row without final member)`. The wire-integrity
  commitment `.../m2-venue/state/v1` stays the row's final member and is what the authority `VenueRef`
  consumes. The history-shaped `venue._protection_commitment` no longer participates in the owner preimage.
- `ebbd374` — R20 §3. Manual flatten rows are projected from each selected scope through
  `_acquisition_scope_key` → `_manual_flatten_by_scope` → `_manual_by_id`, flatten-ID ordered and
  duplicate-free. `m1.authority.BeginManualFlatten/v1` is registered at arity 9 (tag + 8 fields)
  because the frozen row embeds that command and the nested validator admits only registered tags.
- `8042dd8` — fixes from an independent refutation review (3 P0 / 8 P1 confirmed):
  identity agreement, both-maps cardinality, exact `_FlattenPhase` check, and the authority
  commitment domains. See "Invariants" below — these are the patterns to reuse, not one-offs.

## Immediate task — R20 §2 (authority families)

Implement the three remaining authority collections in `_encode_runtime_checkpoint_authority`,
removing each family from the blanket refusal tuple ONLY as it becomes genuinely projected:

| Family | Wire tag | Needs |
| --- | --- | --- |
| Effect authorizations | `m2.authority.EffectAuthorizations/v1` | a new `AcquisitionClaimPermit` encoder (22 members) for the `ClaimAcquisitionEffect` variant; `ClaimEffect` and `BrokerEffectRequest` encoders already exist |
| Acquisition descriptors | `m2.authority.AcquisitionDescriptors/v1` | a new `AcquisitionEffectPermit` encoder |
| Acquisition slots | `m2.authority.AcquisitionSlots/v1` | a new `AcquisitionCurrentness` encoder (15 semantic members + tag = 16), plus descriptor Active/Inactive and active Active/Inactive variants |

Layout authority is `work/queue/M2-EXECUTION-2026-08-21/07-WO-0168H-FROZEN-OWNER-STATE-WIRE-CONTRACT.md`
§4.2, as amended by R2 (10-), R5 (15-), R6 (17-), R15 (26-), R17 (28-), R18 (29-), R20 (31-).
Cross-check every layout against the actual declared field order in `app/execution_core/authority.py`;
derived `commitment` / `_seal` fields are ABSENT from the wire and re-derived.

R20 §2 ordering (do not substitute repository vector order here — these are owner-map projections):
effect authorizations by canonical effect ID; manuals by flatten ID; descriptors by effect ID; slots by
`PositionScope` canonical durable-atom bytes. Claims stay nested beneath their effect authorization.
Input order and whole-map order are never consulted.

R20 §2 also states the four permitted supersets — `_effect_authority_by_id`, `_claim_by_effect`,
`_claim_by_occurrence`, `_acquisition_descriptor_by_effect` — never receive whole-map cardinality
checks. Every OTHER map must have its cardinality proved (see Invariant 2).

R20 §3 terminal-reference rule, still binding: terminal IDs nested in a reached current manual are
bounded owner semantics. A terminal cancel effect omitted by the frozen OPEN/INVALIDATED selection
is valid owner-only history and does NOT require a selected `VenueEffectRecord`; but if a referenced
effect IS in the repository-selected effect family, its owner authorization and selected record must
agree exactly.

## Then R20 §4 (venue) — the larger half

Remove `_validate_full`, `_effect_order`, `_owner_order`, source-rank and whole-history dependencies
from projection, and project all 15 frozen venue families by proof-selected direct key.

R17 §1 (`28-...-R17.md`) is decisive and settles the design: the repository-authentic selection proof
is the SOLE selected-row membership and order witness. Each collection uses its already frozen
SQL/vector canonical order (effects by `(created_ordinal, effect_id)`, owners by the exact Q4b/Q5
vector keys). Projection performs only direct current-owner lookups for those proof-selected keys,
deeply validates equality to each selected record, and emits rows in proof order with DENSE
checkpoint ordinals (0..n-1, decoupled from source order). The R15/R16 rank maps are deleted from the
contract and must not be implemented.

Closing §4 correctly is what makes the two failing guards go green. See Trap 3.

## Invariants earned this session — carry them into every remaining family

1. **Identity agreement.** Every reached owner value must be proven to own the key and the scope that
   reached it. A review reproduced a manual whose command named a different flatten ID, symbol and
   actor; the forged row sealed and decoded clean because the projector emitted it verbatim. Apply the
   same proof to authorizations, claims, descriptors and slots.
2. **Cardinality against EVERY current map, not one of a pair.** R15 §4: "proves reached-key cardinality
   against every authority current map". Checking `_manual_by_id` but not `_manual_flatten_by_scope`
   silently dropped a dangling slot entry. Paired index maps must BOTH be proved, except the four
   permitted supersets named above.
3. **Distinct source-owner domain per family.** Wire-integrity commitment ≠ owner provenance, even over
   the same preimage; separation is by domain. Venue and authority both do this now
   (`.../m2-venue/source-owner/v1`, `.../m2-authority/source-owner/v1`). Any new family follows suit.
4. **Exact-type check every row member.** `phase` was the single member without one, and any object
   exposing a `str .value` encoded as a valid enum and reached the wire outside its frozen alphabet.
5. **Fail closed, never emit empty over real state.** A family that is not yet projected must keep
   refusing explicitly. Emitting an empty collection while owner state exists is silent loss and is
   strictly worse than the refusal.
6. **Never satisfy a static source pin by adding a string or deleting a guard.** See Trap 3.

## Traps already paid for — do not rediscover these

1. **The winning authority top row is R2's `m2.authority.Checkpoint/v1`, NOT contract-07's
   `m2.authority.State/v1`.** R6 (`17-...-R6.md`:32-33) explicitly disqualifies the contract-07 top.
   Contract-07's own authority top is evidence for the CHILD rows only. Implementing against it
   produces a wrong 14-member top.
2. **`_PersistentKeyMap` exposes only `get(key)` and `size` — there is no iteration.** Proof-selected
   direct-key projection is therefore structurally forced, not merely preferred.
3. **The two failing guards are static source-string pins.** They can only be closed by implementing
   the real projections. Removing the `_effect_order`/`_owner_order` guard without the venue projection
   would make the encoder accept nonempty venue state and emit empty collections — silent loss. Adding
   `_claim_by_occurrence` as a bare string without projecting the family is gaming the test.
4. **`tests/execution_core/test_persistence_write_capability.py::test_setup_issuer_and_support_imports_have_the_frozen_direction`
   is ALREADY RED at base `9284bd90`**, because `test_persistence_runtime_checkpoint_sqlite.py` imports
   `persistence_setup_support` and is outside the frozen allow-list. This is NOT yours. Do not add a
   second importer, and do not "fix" it — the allow-list lives in a file outside this work order's
   `allowed_paths`. Put new fixtures directly in an allowed test file.
5. **Forged-state tests must pass `forged.venue`**, not the original book: `deepcopy` gives the forged
   state a copied venue and the projector's `authority.venue is venue` identity check trips first,
   masking the refusal you meant to prove.
6. **`execution-core/m2-authority/state/v1` is the unauthorized domain** (R15 §4). Already corrected to
   `.../checkpoint/v1` for the row and `.../source-owner/v1` for the owner preimage. Do not revert.

## Gates, scope, and forbidden actions

`allowed_paths` are enumerated in `work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md`.
Editing anything outside them requires a checkpoint BEFORE the edit.

STOP and return to Ameen/Codex before any SQLite-bearing test or changed-DDL install, with:
exact candidate commit and tree; exact `SCHEMA_DDL` byte count and SHA-256; changed-DDL summary; and
the exact fresh-`tmp_path` file-database commands including the held runtime-checkpoint and schema
tests. Every DDL byte change needs a new exact candidate and a new approval.

NEVER run `tests/execution_core/test_persistence_runtime_checkpoint_sqlite.py` or
`tests/execution_core/test_persistence_schema.py`. Never use a configured database or `:memory:`.

Forbidden without a new exact gate: changed-DDL execution, migration, credentials, broker/network
calls, orders, production runtime composition, promotion, merge to `master`, M3 implementation,
rebase / force-push / history rewrite, branch deletion, or weakening a test or contract to get green.

## Verification (this environment is Linux; the contract's PowerShell commands do not apply)

```bash
# fresh clone only — creates .venv, collect-only smoke, touches no database
/usr/bin/python3.12 harness/bootstrap.py

export PYTHONDONTWRITEBYTECODE=1
.venv/bin/python -m pytest -q -p no:cacheprovider \
  tests/execution_core/test_persistence_checkpoint_codec.py \
  tests/execution_core/test_persistence_runtime_checkpoint_pure.py \
  tests/execution_core/test_persistence_runtime_checkpoint_directness.py \
  tests/execution_core/test_venue_checkpoint_hardening.py
.venv/bin/python -m ruff check <changed paths>
.venv/bin/python -m ruff format --check <changed paths>
.venv/bin/python -m mypy app/
git diff --check
```

Interpreter here is CPython **3.12.3**, not the 3.12.13 named in the prior handoff. Record that as an
environmental deviation rather than silently normalising it.

## Working rhythm

RED before implementation, failing for the intended reason. Behavioural fixtures over static
source-string pins — build owner state through the real public reducer and forge only environment
proof. Commit and push each verified slice separately; keep the worktree clean and local equal to
origin. Report a checkpoint bundle in the format of
`work/queue/M2-EXECUTION-2026-08-21/00-CHECKPOINT-ORCHESTRATION-PROTOCOL.md` at RED,
GREEN-CANDIDATE, scope pressure, or completion. State unrun and unverified items honestly as
`NOT_RUN` / `NOT_EVALUATED`.

Run a fresh-context review that did not author the patch before declaring a slice done; the last one
found three P0s in work that already had green tests.

## Definition of done — WO-0168c

R20 §2 and §4 implemented at the root; both R19 guards green because the projections are real; DDL
gate stopped at with the full bundle; after Ameen's approval, only the approved fresh-file SQLite gate
run, with RED/GREEN collected before broadening; fresh REV-0078 exact-head `ACCEPT` with P0=0/P1=0;
then close-out shipped IN THE FINISHING COMMIT — status flip, disposition, `work/ledger.jsonl` line,
lifecycle move out of `work/active/`, and any invalidated doc/PKL/ADR claim refreshed. A green change
without that ratchet is still open, and CI fails a completed order parked in a live folder.

## Definition of done — M2 (the end objective)

Per `01-M2-M3-EXECUTION-MAP.md`, M2 completes only when all six M2 orders are independently accepted
on exact heads and the combined candidate proves: one sequenced writer and one pure semantic owner;
direct bounded current proof with no serving-time history fold; one atomic fact/state/effect/claim/
receipt boundary; no blind resend after ambiguity or restart; fail-closed owner lock, startup,
reconciliation and market-source recovery; exact profile-scoped authority with Alpaca Paper the sole
M2–M8 mutation profile; fresh temporary-database fault and restore evidence with the required
boundedness controls; and every unrun operational, broker, soak, promotion and R16 gate left honestly
unpassed. WO-0170's mandatory 24-hour soak, if it cannot complete, stays `NOT_RUN` — do not fabricate it.

Remaining chain after this order: WO-0168b (transaction-generation lease, one atomic unit of work,
outbox/claim/receipt boundary) → WO-0169 (startup owner lock, reconciliation, ADR-023 cold recovery,
owner-locked conversion of the inert checkpoint to serving authority; fake capabilities only) →
WO-0170 (crash/restore/fault/boundedness closeout) → terminal M2 combined exact-head review and
self-contained closeout manifest → M3 preparation only (reconcile queued WO-0171/WO-0172 entry
contracts against accepted M2; do NOT implement M3).

Each successor starts on a FRESH branch cut from the exact accepted predecessor head:
`codex/claude-opus-m2-wo0168b-r1` → `...-wo0169-r1` → `...-wo0170-r1` → `...-terminal-r1`.
Do not start a successor before its exact predecessor is independently accepted and closed.

## Start here

Verify the identities above, confirm the 123/2 baseline, then begin R20 §2 with the
`AcquisitionClaimPermit` encoder — it unblocks the effect-authorization family, which is the larger
of the two remaining authority halves. Do not begin §4 while §2 has an unresolved design or review
finding.
