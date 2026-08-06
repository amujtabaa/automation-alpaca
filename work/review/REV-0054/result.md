# Independent static preflight — WO-0149 R2 scoped-bootstrap amendment

Review target: `PROPOSED-WO-0149-R2-SCOPED-BOOTSTRAP-AMENDMENT.md` only.

Evidence mode: `static-reasoning`. Per the request, no application code, tests, database/SQL,
network, broker, or Git operation was run. This result does not ratify the draft or authorize an
implementation.

## Findings

### [P1] A retained true-FLAT protection state makes the successor's own first fill self-preempt

- Location: `work/review/REV-0054/PROPOSED-WO-0149-R2-SCOPED-BOOTSTRAP-AMENDMENT.md:15-26,85-109`
- Requirement: The domain specification requires a new mandate for a later unrelated acquisition
  and says that its first BUY fill instantiates `FLOOR_ONLY`; a late fact from the prior owned
  lineage after `FLAT` instead restores `HARD_BAIL` under the original mandate
  (`work/queue/ARCH-RESET-2026-07/03-domain-specification.md:243-269,313-320`). WO-0149 also
  requires the first-fill integration and late-fill-after-FLAT controls
  (`work/active/WO-0149-reset-kernel-e-acquisition-cross-side-integration.md:374-383,420-427`).
- Evidence: R2 requires a same-symbol successor to retain the exact predecessor
  `PositionProtectionState` (draft:85-86). With the required exact-flat, closed, reconciled
  predecessor, the current protection reducer creates `FLAT` and records `_flat_origin()`
  (`app/execution_core/protection.py:1294-1305,1399-1415`). Its next positive raw quantity is
  unconditionally `late_positive`, therefore `HARD_BAIL` (`app/execution_core/protection.py:1278-1310`).
  A successor first fill is exactly such a positive aggregate projection; it has no acquisition
  lineage input that could distinguish it from an old correction. The composite acquisition
  reducer then latches preemption for a positive `HARD_BAIL`, moves the newly working acquisition
  into cancellation, and mints an exit capability (`app/execution_core/acquisition.py:944-990`).
  The shared state's execution commitment must also equal the successor projection for the state
  to remain authentic (`app/execution_core/acquisition.py:363-371`), so retaining a stale,
  non-FLAT state is not a valid escape hatch.
- Impact: An otherwise valid successor BUY fill necessarily loses normal acquisition progression
  and self-preempts/enters `CANCELING`. Conversely, resetting the one shared state so that the
  successor gets `FLOOR_ONLY` removes the existing proof that a later old-lineage fact is a late
  positive requiring `HARD_BAIL`. R2 cannot satisfy both accepted behaviors with the unchanged
  aggregate protection reducer.
- Resolution: Do not ratify same-symbol succession as written. A human architecture decision is
  required to define a sealed acquisition-generation/lineage discriminator at the M1E--M1D
  protection boundary: successor-first-fill must retain the accepted `FLOOR_ONLY` behavior, while
  an exact old-root `FILL`/`CORRECT`/`BUST` must retain `HARD_BAIL` under the shared mandate. That
  discriminator, its replay/currentness semantics, and its no-duplicate-authority proof require
  an ADR amendment before a WO can implement it. If the intended policy is instead to start every
  same-protection successor in `HARD_BAIL`, that is likewise an explicit change to the accepted
  first-fill rule and requires an ADR.

### [P1] The direct tombstone has no legal current-interface path to update shared protection after an old-bound fact

- Location: `work/review/REV-0054/PROPOSED-WO-0149-R2-SCOPED-BOOTSTRAP-AMENDMENT.md:49-68,96-109`
- Requirement: Only bounded, sealed venue/currentness authority may drive M1E; a bound venue
  transition contributes only to its exact dual binding, with no private venue path or retained
  transition/history (`work/active/WO-0149-reset-kernel-e-acquisition-cross-side-integration.md:300-372,374-383`).
  Canonical corrections and busts remain valid after terminal closure and must advance their
  indexed terminal-closure head rather than disappear (`docs/adr/ADR-020-current-state-execution-kernel.md:71-107`).
- Evidence: The existing composite reducer obtains an acquisition projection for the live
  acquisition binding before it updates protection (`app/execution_core/acquisition.py:900-958`).
  `project_acquisition_venue` rejects a transition carrying the old dual binding when asked for
  the successor binding (`app/execution_core/venue.py:5917-5962`). Applying the old transition to
  the old state instead cannot replace the live record: registration accepts only a head whose
  predecessor is the retained live head (`app/execution_core/authority.py:891-940`). R2 names no
  opaque cross-lineage transition/projection or atomic reducer that can (a) locate an old root,
  (b) update its current economics, (c) advance the one shared protection state and successor
  currentness, and (d) stale an already-created successor BUY before final claim.

  The tombstone wording is also internally incomplete: it is called immutable while it seals the
  old owned quantity/notional and terminal commitments (draft:55-62), but a later old fact is
  required to "advance[] the old tombstone's acquisition economics" (draft:98-101). It does not
  define the separate directly indexed mutable current-head record needed for that update, nor
  how `A -> B -> C` retains direct routing for a later fact of `A` as well as `B` without a scan.
- Impact: On a late old `FILL`/`CORRECT`/`BUST`, the current public path either refuses before the
  protection update, incorrectly attributes the fact to successor capacity, or relies on a new
  undeclared private/authority shortcut. The promised invalidation/preemption of a successor
  effect then has no sealed successor head for existing create/claim revalidation to compare.
- Resolution: After the ADR decision above, specify the exact atomic, sealed cross-lineage route
  and its ownership. Retain immutable provenance per retired acquisition, plus a direct
  `(scope, old binding, effect/root identity) -> current lineage head/economics` index that can be
  replaced only by the linked canonical successor fact. Define how that route advances the shared
  protection/current successor head, invalidates old and successor claim capabilities, and
  supports more than one retired lineage without materialization. Add RED controls for
  `A -> B -> C` with a late `A` correction, and for a created-but-unclaimed successor BUY racing
  every old-lineage update.

## Verdict

Verdict: **ACCEPT-WITH-CHANGES** — not eligible for the requested P0=0/P1=0 preflight or human
ratification.

P0: 0

P1: 2

P2: 0

Unverified: Runtime behavior and test evidence were intentionally not executed under the review
boundary. The first-scope, different-symbol scoped-bootstrap case is not the finding: it can stay
a bounded WO-level correction. The same-symbol shared-protection successor is the unresolved
architecture boundary described above.
