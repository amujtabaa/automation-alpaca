---
type: Review Result
rev_id: REV-0070
reviewer_model: Codex (GPT-5)
verdict: ACCEPT-WITH-CHANGES
date: 2026-08-21
---

## Verdict

The exact M2-I1 candidate is not yet acceptable. The implementation is bounded and its broad test
evidence is green, but two durable-contract defects and one checkpoint-boundary violation require
correction and fresh review.

P0: 0
P1: 3
P2: 0

## Findings

### P1-1 — Unreduced fractions are accepted and silently normalized

- **Location:** `app/execution_core/durable_codec.py:254-260`,
  `app/execution_core/durable_codec.py:501-508`, and
  `tests/execution_core/test_durable_codec.py:580-609`
- **Evidence level:** `reproduced-live`
- **Evidence:** `DurableAtom("1", "_fraction", ("2", "4"))` constructs successfully. Wrapping it
  in an `exact_basis` atom and calling `decode_m1_value` returns `Fraction(1, 2)`. The validator
  checks integer spelling and positive denominator independently but never checks that numerator
  and denominator are relatively prime. The malformed-ratio parameterization omits an unreduced
  pair.
- **Why it matters:** WO-0165 FR-3 requires the persisted numerator/denominator to be reduced and
  FR-8 prohibits silent repair. The current path permits multiple durable spellings of one value
  and lets `Fraction` normalize malformed persisted input during decode.
- **Smallest resolution:** reject non-reduced fraction components on both ordinary construction and
  forged decode paths, including a canonical zero rule, and add decisive negative tests such as
  `2/4` (and noncanonical zero forms) that fail against the current implementation.

### P1-2 — The frozen public API exports additional helpers and implementation names

- **Location:** `app/execution_core/profiles.py:29-36`,
  `app/execution_core/profiles.py:317-379`, and `app/execution_core/durable_codec.py:25-75`
- **Evidence level:** `reproduced-live`
- **Evidence:** Neither new module defines `__all__`. The non-underscored profile namespace includes
  `execution_payload`, `market_source_payload`, three domain constants, and imported
  `dataclass`, `field`, `sha256`, and `unicodedata`, in addition to the five profile API names.
  The codec likewise exposes imported owning types and `CONTRACT_VERSION` in addition to its three
  frozen API names. The two payload helpers are locally defined public functions and are direct
  duplicates beneath the approved preimage wrappers.
- **Why it matters:** WO-0165 lines 99-114 freeze exactly eight public names and explicitly prohibit
  export-count expansion. Unapproved helpers can become accidental dependencies and enlarge a
  contract that later M2 work is supposed to treat as immutable.
- **Smallest resolution:** make implementation-only helpers/constants/import aliases private,
  declare the exact approved exports for both modules, and add an exact-export test that fails on
  any extra or missing name.

### P1-3 — A frozen preparation file was edited without the required Codex checkpoint

- **Location:** `work/queue/M2-EXECUTION-2026-08-21/02-CURRENT-SOURCE-INVENTORY.md:3-22`, governed by
  `work/active/WO-0165-m2-i1-durable-codec-contract.md:197-199`
- **Evidence level:** `reproduced-live`
- **Evidence:** The candidate rewrites the status/head and regeneration prose in
  `02-CURRENT-SOURCE-INVENTORY.md`. The active work order says queued preparation paths are
  read-only after the saved preparation baseline and requires a Codex checkpoint before changing
  a preparation contract. The older merge gate says to regenerate the inventory in that file,
  creating an authority conflict, but no Codex checkpoint resolving the conflict was recorded
  before the edit. The complete regenerated hashes and no-drift evidence are already recorded in
  the new append-only `04-I1-ACTIVATION-CHECKPOINT.md`.
- **Why it matters:** This bypasses the checkpoint governor and mutates a hash-bound planning
  baseline even though the implementation evidence has a proper append-only home. Passing the
  mechanical allowed-path checker does not satisfy the narrower semantic authority.
- **Smallest resolution:** restore `02-CURRENT-SOURCE-INVENTORY.md` byte-for-byte from the accepted
  base and retain the fresh regeneration evidence in `04-I1-ACTIVATION-CHECKPOINT.md`; alternatively,
  obtain and record an explicit Codex amendment before changing the frozen preparation file.

## Reproduced evidence

- Candidate identity: commit `35721bf5a980639a18ab12e0383f9f382716ed28`, tree
  `a8e95f1d2b0eff31f0709eaa6f7b87c3c653b82a`, clean worktree before review artifacts.
- Exact base-to-candidate inventory contained the expected eight paths; `git diff --check` passed.
- Supported CPython 3.12.13 full `tests/execution_core` run reached 100% and exited `0`.
- Focused value/import/codec/profile run passed 273 tests on the host interpreter.
- `ruff check .`, changed-file `ruff format --check`, and `mypy app/` passed.
- Repository install, ledger, PKL, disposition, and scope checks passed; context hygiene had zero
  violations and eight pre-existing advisory size findings.
- Independent identity inventory found 29 concrete exact identities and 29 codec mappings, with no
  missing or extra mapping.
- No candidate diff touched SQL/DDL, database, runtime, credential, broker/network, order,
  promotion, or merge surfaces.

## Unverified or intentionally not claimed

- The broader repository test suite was not run; WO-0165's bounded execution-core suite was used
  after inspection established that it cannot open a database or call a broker/network surface.
- No configured database, broker, credential, order, runtime, schema, restore, soak, promotion, or
  M2-I2 check was run or is represented as passing.
- The author's exact `1,589 passed, 1 skipped` summary was not separately printed by the review
  invocation because repository `-q` plus command-line `-q` suppressed the terminal summary; the
  independently observed full-suite result was 100% with process exit `0`.

ACCEPT-WITH-CHANGES — P0: 0, P1: 3, P2: 0
