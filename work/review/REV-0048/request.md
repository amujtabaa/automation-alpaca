---
type: Review Request
rev_id: REV-0048
title: "Reset M1B pure venue ownership and recovery kernel"
status: AWAITING_REVIEW
targets: [WO-0146, RESET-M1B, ADR-020, ADR-021, ADR-012]
human_gated_surfaces: [execution-fact authority, venue ownership, ambiguity quarantine, operator recovery, position quantity]
commit_range: dfb8ed30ebed788f1158d7f8be49b44d505c355b..ba9e1268e4645ec36f620f14d361f709916aa690
implementation_head: ba9e1268e4645ec36f620f14d361f709916aa690
created: 2026-08-01
amended: 2026-08-01
---

## Your Role

You are the **independent review seat**. You did not author this implementation or its in-process
review prompts. Follow `AGENTS.md`, `.ai-os/core/15_CROSS_MODEL_REVIEW.md`,
`pkl/process/review-hardening.md`, and the accepted reset authority identified below. Produce
findings only. Do not edit any reviewed file or this request; write only `result.md` in this folder.

Before reading the implementation, pre-register in `result.md` the system properties you will
attack from the authority and work-order contract. Then inspect the implementation. Use three
hostile perspectives: production saboteur, context-free maintainer, and safety/data-integrity
reviewer. Converge them into one deduplicated findings table.

The prior Saboteur/New-Hire/Safety passes and the three checkpoint/restart/provenance passes were
in-process filters. They do **not** satisfy this independent gate and must not be treated as proof.

## Frozen Object Under Review

Review the exact implementation object and its complete reset-slice history:

```text
base:   dfb8ed30ebed788f1158d7f8be49b44d505c355b
target: ba9e1268e4645ec36f620f14d361f709916aa690
diff:   git diff dfb8ed30ebed788f1158d7f8be49b44d505c355b..ba9e1268e4645ec36f620f14d361f709916aa690
```

WO-0146 introduces a pure, deterministic venue-effect/attempt ownership and recovery semantic
center under `app/execution_core/`. It is intentionally not wired into application runtime,
persistence, adapters, broker access, or UI/API flows. Review both the diff and the whole affected
semantic boundary; a defect outside the changed lines still counts if it bypasses a claimed safety
property.

The target advanced from `7f4f428059427dad17df6d01110d5e9d08e835a1` only through Ruff's canonical
formatter after the initial pre-registration draft. The reviewer-owned draft remains preserved and
the verdict must cover the exact amended target above.

No credential discovery/use, Alpaca or other broker activity, network access, SQL/DDL, database
engine/client/fixture, ORM/schema/migration tool, runtime wiring, PR, merge, push, deletion, or
cleanup is permitted or necessary. Pure in-memory Python tests and static inspection are permitted.
Do not use any prohibited R1 DDL result as evidence.

## Controlling Context — Read in This Order

1. `AGENTS.md`, especially Safety core and Architecture reset lane.
2. `work/active/WO-0146-reset-kernel-b-venue-ownership-recovery.md`.
3. `docs/adr/ADR-020-current-state-execution-kernel.md`, sections governing transition ownership,
   execution facts, projections, and recovery.
4. `docs/adr/ADR-021-position-protection-liquidity-execution.md`, venue ownership/recovery clauses.
5. `docs/adr/ADR-012-operator-authorized-reconciliation.md` if present; otherwise the accepted
   ADR-012 clauses mapped by the reset packet and WO-0146.
6. `work/queue/ARCH-RESET-2026-07/06-roadmap.md`, M1 item 2 only.
7. Changed `app/execution_core/` source and its tests.

Treat the accepted ADRs and work order as authority. Historical Spine v2 implementation is
read-only evidence, not a design source for this replacement semantic center.

## INV-* Delta Since REV-0047

- **ADDED:** none.
- **AMENDED:** none.
- **Preserved/implemented, not redefined:** Spine `INV-1` through `INV-9`, with this slice directly
  exercising `INV-1`, `INV-2`, `INV-3`, `INV-4`, `INV-5`, `INV-6`, `INV-8`, and `INV-9` through the
  already accepted reset mapping.

Because no catalogued invariant statement changed, PROC-0001's new-ID coverage set is empty for
this packet. Still perform and record fresh counterexample probes against the safety properties
below; rerunning a pinning test alone is not a fresh probe.

## Negative-Space Review Questions

Enumerate every public or constructible path—not just named happy paths—by which:

1. an acknowledgement, status, closure, release, human fact, corroboration, correction, bust, or
   catch-up could change position quantity or become accepted without exact source authority;
2. one effect could lose, overwrite, duplicate, or silently close one of multiple concrete broker
   acceptances;
3. ambiguity could stop contributing to `symbol_may_execute` before exact leg and parent closure;
4. a forged, reordered, stripped, aliased, cross-owner, cross-scope, or stale checkpoint could mint
   or retain human/operator authority;
5. account-registry catch-up could skip independently advanced same-symbol truth, hide a conflict,
   or strand a valid snapshot;
6. sibling fills or revisions could bypass effect-wide capacity, long-only arithmetic, occurrence
   uniqueness, lineage, tail mapping, or first-occurrence deduplication;
7. terminal or operator-final state could survive later contradictory evidence, invalidation,
   unresolved reconciliation, binding-integrity failure, or incomplete closure;
8. a no-leg or never-dispatched effect could self-finalize or later refuse a real acceptance instead
   of entering the required uncertainty state;
9. cumulative status quantity could be mistaken for canonical fills-only economic truth; or
10. a public helper, constructor, dataclass replacement, import alias, or retained mutable object
    could bypass the intended atomic transition seam.

For each path, identify the choke point and either demonstrate an exploit/counterexample or provide
a file-and-line keyed unreachability argument. Narrative confidence is not closure.

## Required Fresh Probes

Run at least three new pure in-memory scenarios that are not merely calls to an existing named test.
Record each scenario, exact outcome, and the invariant/property it attacks in `result.md`. Include:

- one construction/provenance forgery probe;
- one late/conflicting evidence or closure-order probe; and
- one cross-effect, cross-symbol, sibling-capacity, or registry-catch-up probe.

Also perform at least one failure-capability check of a new safety pin using a reversible runtime
monkeypatch, a one-off public-API counterexample, or a written mutation-to-failing-test mapping that
you verify against the recorded WO mutation evidence. Do not modify the frozen source object.

## Mechanical and Reproduction Gates

At minimum, independently reproduce:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/execution_core/test_fill_position.py tests/execution_core/test_import_boundary.py tests/execution_core/test_venue_ownership.py tests/execution_core/test_venue_recovery.py tests/execution_core/test_venue_binding_recovery.py tests/execution_core/test_venue_checkpoint_hardening.py tests/execution_core/test_venue_provenance_hardening.py --maxfail=1
.\.venv\Scripts\python.exe -m pytest -q tests/execution_core/test_fill_position_stateful.py --maxfail=1
.\.venv\Scripts\python.exe -m pytest -q tests/execution_core/test_venue_stateful.py --maxfail=1
.\.venv\Scripts\python.exe -m ruff check app/execution_core tests/execution_core
.\.venv\Scripts\python.exe -m mypy app/execution_core
git diff --check dfb8ed30ebed788f1158d7f8be49b44d505c355b..ba9e1268e4645ec36f620f14d361f709916aa690
```

Attempt to disprove the following rather than accepting their recorded PASS lines:

- the package import boundary is pure and cannot import legacy store, broker, event, API, UI, or
  runtime modules;
- every externally meaningful outcome has an exact retained direct source, and semantic aliases
  cannot replace or point forward to that source;
- immutable history validation is bounded/indexed rather than implemented by retained-history
  materialization or a linear terminal scan;
- all constructor/evolution paths preserve registry, position, root, closure, reconciliation, and
  provenance bindings; and
- the changed path set stays inside WO-0146's allowed or activation-only paths.

Full repository/R2 and external Python 3.11/3.12 CI are later implementation-seat closeout gates;
do not report them as verified unless you actually obtained exact-head evidence. Their absence at
this review stage is a disclosed deferred gate, not by itself an implementation defect.

## Evidence and Severity Contract

- Cite exact `file:line` evidence for every finding.
- Label findings P0/P1/P2 according to `AGENTS.md`.
- P0 includes any safety-invariant violation, bypass on a human-gated surface, or completion claim
  you cannot reproduce.
- P1 includes an untested behavior change, bypassable/incomplete fix, boundary violation, or scope
  creep.
- State what you could not verify.
- End with exactly one verdict: `BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`.
- `ACCEPT` requires no unresolved P0/P1; P2 observations may remain only if they do not weaken a
  declared safety or completion claim.

## How to Respond

Create `work/review/REV-0048/result.md` and no other file. Preserve this request and all reviewed
content byte-for-byte. Findings only—do not implement fixes.
