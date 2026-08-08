# WO-0148 Claude clean-room comparator handoff

Status: **NON-AUTHORITATIVE PRE-PRODUCTION COMPARATOR**

This packet supports the eighth WO-0148 RED re-gate. It is not the later authoritative
`REV-0050` implementation review, does not activate production work, and cannot accept or close
WO-0148. Do not create or overwrite `request.md`, `result.md`, or `disposition.md` from this packet.

## Repository state to inspect

- Repository: `automation-alpaca`
- Branch: `codex/arch-reset-2026-07-r1`
- Exact seventh RED freeze: `83b0a3ae4c3bb4ab32239b03e41e40b6bb4d6ce9`
- Activation base: `d75806b1a79d1769db25ae962c0977cd9388a886`
- Active work order: `work/active/WO-0148-reset-kernel-d-position-protection-hybrid-trailing.md`
- Primary oracle: `tests/execution_core/test_protection.py`
- Public-boundary oracle: `tests/execution_core/test_import_boundary.py`
- Production `app/execution_core/protection.py`: deliberately absent and barred until the RED
  contract receives a fresh zero-P0/P1 independent verdict.

The exact seventh freeze collected 245 tests in `test_protection.py`; the complete three-file
focused contract collected 262 and produced 214 expected RED failures / 48 passes with no errors.
The only failure classes were the deliberately absent protection module and resulting export/import
delta. All predecessor execution-kernel tests outside the RED files passed.

An independent seventh-freeze review found no P0 and nine P1 oracle gaps. The local implementation
seat is separately repairing the behavioral gaps and transitive bounded-map provenance. Claude's
clean-room assignment is limited to the four meta-oracle questions below.

## Read order and authority

1. `AGENTS.md`
2. `CLAUDE.md`, especially the always-on safety core
3. The complete active WO-0148, especially:
   - Normative design contract clauses 1-15
   - RED-first proof obligations
   - Required mutation controls
   - Independent seventh-freeze review and eighth re-gate
   - Stop conditions
4. The two test files named above
5. Only directly referenced execution-core source needed to understand those tests

Accepted ADRs, the active work order, current code, and current tests outrank this handoff if they
conflict. Do not reinterpret the architecture or introduce a new authority boundary.

## Clean-room questions

### C1. Passive nested lifecycle types

The lifecycle grammar accepts an exact-slotted `app.execution_core.*` class after an exact-type
guard and then permits slot reads. Determine the smallest static/runtime-independent proof that the
guarded class cannot execute custom attribute-access behavior. It must reject a custom
`__getattribute__` or `__getattr__` mutant before its payload executes, while accepting the exact
passive scalar, enum, and execution-core value types required by the frozen contract.

### C2. Runtime provenance of public entry points

The source oracle names exactly three public functions:

- `project_protection_venue(transition, mandate)`
- `initialize_position_protection(mandate, projection)`
- `reduce_position_protection(state, projection, occurrence)`

Design a bounded seal that detects wrappers, callable objects, closures, defaults, function
attributes, executable annotations, source/bytecode swaps, and post-definition module/package
rebinding without executing attacker-controlled payloads. Explain which identity properties are
semantically required and which would merely overfit one CPython function object.

### C3. Reject exact argument types before field reads

For every argument position of all three public functions, prove that a wrong exact type raises
`TypeError` before truthiness, equality, hashing, iteration, attribute access, descriptors, or
other protocols run. Supply a no-access tripwire design and a complete argument-position matrix.

### C4. Exhaustive one-leaf authenticity mutation

The existing oracle mutates only one representative nested dataclass field and appends to tuples.
Design a deterministic bounded generator that mutates every independent retained leaf of the
opaque protection state and bounded venue projection, one leaf at a time, while preserving all
siblings and container shape. It must cover nested dataclasses, tuple elements, frozenset elements,
exact scalars, enums, `None`, and empty containers. Do not enumerate the complete
`VenueRecoveryBook`; its private graph is large and belongs to M1C. State how completeness and
one-leaf-at-a-time behavior are themselves proven.

## Required evidence standard

A blocking finding must identify:

1. The exact accepted clause or safety invariant.
2. A concrete reachable bypass or failure-capable missing control.
3. The smallest root-level repair.
4. A mutant or counterexample that fails under the repair and would survive without it.

Speculative hardening, implementation preference, generic defense-in-depth, or CPython-specific
pinning without a demonstrated contract break is P2/advisory and cannot block the gate. Credible
authority, safety, integrity, or scope violations remain blocking.

## Deliverable

Return one self-contained clean-room report containing:

1. Verdict on whether C1-C4 are valid P1 gaps.
2. Clause-to-counterexample map.
3. The simplest coherent oracle design.
4. A unified diff or precise implementation sketch suitable for comparison, not automatic merge.
5. Failure-capable mutation matrix.
6. Explicit critique of overfitting, brittleness, or unnecessary complexity in the current oracle.
7. Unresolved questions and anything not verified.

If repository write access is explicitly granted, write only
`work/review/REV-0050/claude-clean-room-result.md`; otherwise return the report in chat. Do not edit
production code, existing tests, the active WO, accepted ADRs, PKL, ledger, or any authoritative
review artifact.

## Absolute boundaries

- No credentials or Alpaca activity.
- No broker, network, runtime wiring, persistence, SQL/DDL, or database initialization.
- No production implementation.
- No merge, PR, branch/worktree deletion, cleanup, or artifact deletion.
- No claim that a passing meta-test proves the production schema, runtime, or operational system.
- No self-acceptance of WO-0148.
