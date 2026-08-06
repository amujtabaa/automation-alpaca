# REV-0056 — acquisition-generation architecture decision: recovery and Fable gate

Status: **DRAFT ONLY — NOT RATIFIED, NOT IMPLEMENTATION AUTHORITY**

## Purpose and boundary

This packet answers one bounded architecture question: whether the reset beta may support repeat
same-symbol acquisitions through serial acquisition generations, rather than permanently refusing
a PositionScope after its first lifecycle. It is a documentation-only decision candidate.

It does not change accepted ADRs, the active work order, application code, tests, persistence,
runtime wiring, broker behavior, credentials, network state, branches, or retained evidence. The
partially implemented WO-0149 material remains preserved evidence and is not ratified by this
packet.

## Recovery record

| Check | Result |
|---|---|
| Local HEAD | 192056d4e050517ad9b92bfb5f17bf2780e23a47 — docs(architecture): freeze WO-0149 public contract |
| Remote head | origin/codex/arch-reset-2026-07-r1 is the same SHA |
| Ahead / behind | 0 / 0 |
| Tracked dirty paths | Only preserved WO-0149 application/test paths plus the active WO; no architecture-packet path was previously tracked-dirty |
| Untracked material | Preserved partial acquisition.py, its tests, review packets, and retained evidence; none is altered here |
| Diff hygiene | Existing tracked diff passed git diff --check before this packet was created |

The intentionally dirty worktree is therefore not silently normalized, reset, committed, or
otherwise changed. Any later implementation gate must re-establish its own exact candidate
baseline.

## Evidence reconciliation

| Evidence | Finding / disposition |
|---|---|
| REV-0053 | P1: exact empty-account genesis has no safe post-history bootstrap. It establishes the need for a bounded target-scope bootstrap. |
| REV-0054 | P1.1: retaining a true-FLAT protection state makes B's own first fill self-preempt; P1.2: an immutable tombstone lacks a direct mutable economics/currentness route for late A facts and A -> B -> C. This is the controlling contradiction. |
| REV-0055 | Unreviewed R3 draft. Its never-before-used-scope bootstrap may be retained as a narrow subset, but it explicitly deferred same-scope rollover and is not acceptance evidence. |
| Side-chat R4 | Not adopted. It retired authority needed for old facts and did not define a valid common emergency authority for distinct protection mandates. |

No P0 was found in those static reviews. The unresolved P1s are not waived: this candidate
must close them by design and then receive a fresh exact-candidate independent preflight.

## Governing authority and predecessor hashes

The authoritative baseline is the accepted ADR set, domain specification, active WO-0149,
architecture map, PKL, ledger, and preserved review evidence—not this narrative.

| Authority | Current SHA-256 | Proposed disposition |
|---|---|---|
| ADR-020 R1 | 35c6782ff7c09ec125b2acad859b4080302660531004db47b8c544b4cf2a5838 | Versioned ADR-020 R2 proposal |
| ADR-021 R1 | ca822fe682bc2ccca32b5a7915ea4f07bd4ad2319e62d48312edd12c3f8f44f0 | Versioned ADR-021 R2 proposal, preserving ADR-023 overlay |
| ADR-022 R1 | 93f2c55b77e832687e1d1ac8256f34ad4442b4a4072a8b79c7a1d8294c558798 | No body change proposed |
| ADR-023 R1 | 9a61d4f952079b5f78da7a8f1a17f70dc3099d20fb359596923c5938cc421eaf | No body change proposed if acquisition and market-stream identities stay orthogonal |
| Ratification index | 02f7637df0712f8d38017e9ba4502b8d2c8519e3487b9e2fca2ef5f89d0d7085 | New entry only after human ratification |

## Fable v3 full gate

### GATE — authority, scope, and stop conditions

- **Authority:** The user authorized architecture decision, proposed ADR amendments, static
  preflight, downstream analysis, and an exact ratification packet only.
- **Allowed paths:** This new work/review/REV-0056 documentation packet only.
- **Forbidden:** application/test implementation, active-WO amendment or activation, accepted ADR
  edits, PKL/ledger mutation, SQL/DDL, database or runtime activity, network/broker/credential
  activity, push/merge/delete/cleanup.
- **Stop:** If a design requires concurrent acquisition generations, independent protection
  controllers, generic policy composition, history scans, caller-shaped authority, an unbounded
  collection in the live transition, or a contradiction with accepted safety rules, it is rejected
  or escalated for a new ADR; it is not implemented here.

### RED — failure-capable decision obligations

The candidate must make each of the following fail if a named guard is removed:

1. B first fill after a valid A retirement must classify LIVE_FIRST_ROOT and produce
   FLOOR_ONLY, not a late-positive hard bail.
2. A late FILL, TRADE_CORRECT, or TRADE_BUST after B or C exists must route directly to A,
   change canonical aggregate economics once, never replenish B/C capacity, and enter one
   symbol-wide mixed recovery/hard-bail path.
3. A late A fact racing B's created-but-unclaimed BUY must advance the controller head and make
   B's final claim stale; no transition may make more than one broker-facing protection action
   eligible.
4. Nonflat state, OPEN/INVALIDATED/unknown ownership, unresolved reconciliation, forged or
   forked generation, reused binding, cross-scope root, stale controller head, changed recovery
   compatibility, or a potentially executable old BUY must refuse successor admission.
5. A -> B -> C plus a late A correction must use a direct index with no predecessor walk or
   audit/history materialization; replay and restart must preserve the same route.

### DESIGN / FIX — proposed root-level solution

The selected candidate is specified in the remaining documents. It replaces the missing
lineage discriminator, not the existing safety model: one aggregate exposure, one symbol
controller, one active normal protection authority, canonical fact-first economics, and
controller-head revalidation remain mandatory.

### DONE — conditional only

This packet is ready to request a focused independent static preflight once the candidate hashes
are frozen. It is not DONE as an architecture decision until a human ratifies exact reviewed
hashes. No implementation authority follows from a preflight acceptance alone.

