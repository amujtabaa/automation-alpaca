# Independent static preflight result - WO-0152 E3 R2-R4

[FABLE • FULL • verification: DIRECT • task: independent R2-R4 mandate-schedule preflight]

Review date: 2026-08-07  
Review seat: independent Codex review seat  
Mode: static-only exact-candidate preflight  
Branch: `codex/arch-reset-2026-07-r1`  
Review base / candidate HEAD: `e35ff07c42675646cc7a13f1949f80fdf108e516`  
Candidate contract: `work/review/REV-0059/WO-0152-RED-CONTRACT-R2-R4.md`  
Candidate contract SHA-256: `f2a59f1c4197aac851249a136d0a3a1761c7e365f4f34468acb842dc18e5866e`  
Manifest: `work/review/REV-0059/WO-0152-RED-CANDIDATE-R2-R4-MANIFEST.md`  
Manifest SHA-256: `a62df766a608c187c93efa8550c0fa06192f2c21b048c404738f136e0905005b`  
Isolated partial-test SHA-256: `e10e623230744f4a4c43cbc11cc0850562f32e8ee64286efb5ef0ba2ff3d6b79`

## Fable gate

```yaml
fable_gate:
  goal: "Independently decide whether the exact documentation-only R2-R4 replacement is constructible, failure-capable, bounded, and safe to activate for further E3 test implementation."
  assumptions:
    - claim: "The exact local branch, review base, and frozen manifest identify the complete candidate."
      status: VERIFIED
      evidence: "Branch and HEAD matched the manifest; 24/24 manifest rows re-hashed exactly."
    - claim: "The untracked partial E3 test is isolated baseline material, not candidate implementation or acceptance evidence."
      status: VERIFIED
      evidence: "The file remained the sole untracked test and retained SHA-256 e10e623230744f4a4c43cbc11cc0850562f32e8ee64286efb5ef0ba2ff3d6b79."
    - claim: "A required refusal control must use otherwise-valid public input that isolates the named refusal rule."
      status: VERIFIED
      evidence: "Fable failure-capability and the accepted successor contract require the test to distinguish nonadjacent stream reuse from duplicate mandate or binding refusal."
  approach: "Re-hash the exact packet and context, inspect only static Git/file/source evidence, re-derive the mandate and successor contracts bottom-up, and try to disprove each provisional finding."
  out_of_scope:
    - "Tests, test collection, database-capable fixtures, SQL/DDL, application or broker runtime, network, credentials, CI, and coverage."
    - "Production, test, ADR-body, work-order, PKL, ledger, request, manifest, remediation, commit, or push changes."
  done_when:
    - "Exact candidate identity, scope, retained chain, current records, and isolated baseline are reconciled."
    - "The 32-mandate schedule, private mint exception, and nonadjacent stream-reuse control are independently re-derived from source and accepted ADRs."
    - "A bottom-up disproof pass leaves only supported findings and an exact P0/P1/P2 verdict."
  blast_radius: "This reviewer-owned result file only."
```

## Outcome

`ACCEPT-WITH-CHANGES`. The fixed 32-entry positive schedule and its one lexical minter loop are
narrow enough to construct 32 distinct approved mandates without creating a production, public-API,
runtime, broker, database, or caller-configurable authority surface. The required nonadjacent
market-stream reuse control is not constructible under that same exception, however: every mandate
the fixture may mint must have a unique stream, while an authentic distinct A-stream-reuse probe
requires one additional sealed binding. Reusing the original A mandate produces a generic duplicate
mandate/binding refusal and cannot prove the stream rule.

## Exact candidate, hash, and scope verification

All observations below were made before this result file was created.

- `git branch --show-current` returned `codex/arch-reset-2026-07-r1`.
- `git rev-parse HEAD` returned `e35ff07c42675646cc7a13f1949f80fdf108e516`, exactly the manifest review base.
- The independently computed candidate-contract and manifest hashes are the exact values recorded
  above. The independently parsed manifest contained 24 SHA-256 rows: **24 matched, 0 missing,
  0 mismatched**.
- The retained R2-R3 manifest, contract, independent result, and reconciled activation disposition
  matched their frozen hashes: respectively `ee5554bf4e6b380fa7c687324adba7f93168e56168fb84cedf519115e4b7c3f6`,
  `881334b4af6acb566adc57c30a4199f0340129d244cc3d58536c8e7c109a9936`,
  `8752e20fa0aba82885d1d49ae8eabca9901218f5659073adcb4324fa9b189a59`, and
  `2ef88891b3e303833d93d36cd50a99132b24e6b8b994c822fcfa65b8ebf976b3`.
  Their worktree diff from `HEAD` was empty. Earlier packet artifacts transitively pinned by the
  retained manifest are unchanged; lifecycle/current records that legitimately evolved during
  activation are pinned at their current bytes by R2-R4.
- The R2-R4 disposition and request matched
  `162e4c8e029fd4cffd791a7f4ce7f73f2c459bca6b0a3818f73e84dab1b82a4a` and
  `638c1c16b14f653be15d07992312b147c8c79a6405ac31e868670cb453643238`.
  The active WO matched `82a06446b2d0dfb19efa4c994d0a77fabb78b7e26f8a81a6243158c262ab4a36`.
- Pre-output status contained exactly six expected tracked modifications and five expected
  untracked paths: the four R2-R4 packet inputs plus the isolated partial test. There were no staged
  paths, no extra production or existing-test changes, and `result-r2-r4.md`, `result-r2.md`, and
  `result-r2-r2.md` were absent.
- `git diff --check` exited 0 with no output. The ratification, PKL log, and ledger diffs were
  append-only (`+27/-0`, `+8/-0`, and `+1/-0`); the active WO, goals, and architecture map changes
  were limited to the current R2-R4 pause/re-gate posture. Accepted ADR bodies and frozen source
  matched the manifest.
- `tests/execution_core/test_acquisition_stateful.py` was inventoried only for isolation. It was the
  sole untracked test, contained the retained environment fixture and two already-permitted public
  boundary controls, and re-hashed to the exact isolated baseline above. It was not used as R2-R4
  acceptance evidence.

## Static re-derivation

### Positive 32-entry schedule and authority boundary

- `MarketStreamGenerationId` is a public exact immutable identity whose constructor enforces
  lowercase 64-hex text (`app/execution_core/identity.py:151-172`). Public `ProtectionMandate`,
  `EvidencePolicy`, and `AcquisitionMandate` values can therefore be assembled from the fixed
  literals.
- The sole unavailable public input is `DualMandateBinding`: its constructor is deliberately
  opaque, and `_mint_dual_mandate_binding` creates its authenticated seal
  (`app/execution_core/acquisition.py:1146-1167,1206-1299`). One direct call expression inside one
  ordinary loop can lawfully execute once for each of the 32 fixed entries.
- The candidate fixes the loop input, cardinality, ID and stream literals, public mandate
  correspondence, common scope/session/terms/compatibility, invocation phase, call target, control
  flow, and return surface (`WO-0152-RED-CONTRACT-R2-R4.md:32-100`). It also retains the complete
  R2-R3 outside-table prohibition. This is a bounded test configuration fixture, not a general
  private seam or hidden operating authority.
- The public aborted/no-root successor chain is a constructible way to exercise 32 distinct
  generations without spending the separately capped terminal-parent fixture
  (`WO-0152-RED-CONTRACT-R2-R4.md:102-107`).

## Finding

### [P1] The nonadjacent stream-reuse control has no authentic distinct probe mandate

- Location: `work/review/REV-0059/WO-0152-RED-CONTRACT-R2-R4.md:43-55,59-78,84-100,109-114`
- Requirement: ADR-020 R2 section 2 and ADR-021 R2 sections 3-4 require every successor to carry a
  distinct approved `MarketStreamGenerationId` and a distinct complete sealed dual-mandate binding.
  The R2-R4 control must expose nonadjacent A-stream reuse through public behavior, and a
  failure-capable control must isolate that rule rather than obtain `REFUSED` from another invalid
  coordinate.
- Evidence: **static-reasoning**. All 32 permitted schedule entries must have mutually distinct
  acquisition IDs, protection IDs, and streams, and the only private mint call may execute only in
  the loop over those entries. `DualMandateBinding` cannot be constructed publicly, and
  `AcquisitionMandate` rejects a binding that does not exactly seal its complete mandate
  (`app/execution_core/acquisition.py:1328-1382`). Reusing the original A mandate after B is not an
  isolating substitute: `begin_acquisition_generation` independently requires a fresh acquisition
  ID, protection ID, and binding before its stream comparison
  (`app/execution_core/acquisition.py:3952-3958`). Such a probe remains `REFUSED` even if the stream
  inequality is deleted. Conversely, a fresh-ID mandate reusing A's stream needs a newly minted
  authentic binding, which the candidate's exact schedule/loop rule forbids. Current source has no
  other acquisition-side `stream_generation` ownership path; its sole check compares the candidate
  only with the immediately prior mandate at lines 3957-3958.
- Impact: The named A -> B -> A-stream control can pass for the wrong reason and cannot distinguish
  the real nonadjacent-reuse defect from duplicate-mandate refusal. The current adjacent-only E2
  check can therefore survive the planned proof undiscovered, so the R2-R4 composite is not yet a
  constructible, failure-capable gate for the accepted no-reuse rule.
- Resolution: Retain the 32 positive schedule entries and their distinct streams, but explicitly
  authorize and statically pin one additional fixed pre-genesis negative-probe mandate with fresh
  acquisition/protection IDs and a fresh authentic binding that intentionally reuses A's stream.
  Bound its mint to the same zero-argument fixture and an exact lexical/cardinality rule (for
  example, one tagged extra entry in the fixed mint plan), expose it separately from the 32 positive
  chain, and add a sensitivity specimen showing that removal of the nonadjacent stream-ownership
  refusal makes this control fail. Do not use the original A mandate or add a caller-shaped factory.

## Bottom-up disproof and reconciled non-findings

- I started at the sealed binding and successor predicates rather than the contract prose.
  Authenticity ties the acquisition ID, protection ID, complete terms, protection commitment, and
  compatibility commitment into the binding. A public copy/replacement cannot create the needed
  fresh sealed probe.
- I tried the only schedule-provided A-stream value: the original A mandate. It is authentic, but
  it violates three independent freshness comparisons before the stream comparison. Removing the
  stream check still yields `REFUSED`, disproving it as a stream-specific negative control.
- I tried to derive the probe from another schedule entry. The candidate requires the actual public
  mandate to bind that entry's own distinct stream and separately tests all 32 returned streams for
  uniqueness; substituting A's stream violates both the fixture and its source/behavior controls.
- I tried a second fixture invocation, a public mandate replacement, and an extra private mint.
  Reinvocation deterministically recreates the same bindings; replacement fails binding
  authenticity; and any additional mint is rejected by the retained exact private-access table and
  the R2-R4 one-call/one-loop rule.
- I attempted to disprove the finding by reading the successor state from the bottom up. The
  generation registry and controller retain generation/binding provenance but no direct market-
  stream owner, and the only `stream_generation` reference in acquisition reduction is the
  immediate-predecessor inequality. This strengthens, rather than defeats, the need for an
  otherwise-valid nonadjacent probe.
- I found no second issue in the 32-entry positive schedule, the loop shape, retained R2-R3
  environment/terminal/boundedness rules, current records, append-only provenance, scope, partial
  baseline isolation, safety core, or deferred paired 93% gate. The bounded minter exception does
  not alter a production/public API or grant runtime, broker, persistence, execution, controller,
  claim, or actor authority.

## Evidence limits

This review intentionally used only static file/source inspection, SHA-256 re-hashing, Git
branch/status/diff inspection, and whitespace checking. I did **not** run tests, test collection,
database-capable fixtures, SQL/DDL, application/runtime commands, network, broker, credential, CI,
or coverage commands. I did not inspect or mutate database/broker state. The adjacent-only E2
behavior and the probe's inability to isolate it are source-derived static findings; no dynamic
transition was executed. The local `origin/codex/arch-reset-2026-07-r1` tracking ref matched HEAD,
but no live network ref query is claimed. Future RED/GREEN, mutation, runtime, and paired 93%
closeout evidence remain unverified and outside this gate.

```yaml
fable_done:
  task: "WO-0152 R2-R4 independent static preflight"
  done_when_results:
    - item: "Exact candidate identity, retained chain, current records, scope, and isolated test baseline are reconciled."
      status: MET
      evidence: "24/24 manifest rows matched; exact branch/base and isolated hash matched; no scope discrepancy."
    - item: "The positive 32-generation schedule and its private exception are constructible and bounded."
      status: MET
      evidence: "Public constructors plus one fixed 32-iteration lexical minter call construct exact sealed mandates without a production surface."
    - item: "Every required architecture control has a lawful failure-capable input."
      status: NOT_MET
      evidence: "The A -> B -> A-stream control lacks a distinct sealed duplicate-stream mandate under the exact exception."
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
  evidence:
    - "Static commands and decisive outputs are recorded above; prohibited dynamic checks were not run."
  status: VERIFIED
```

Verdict: ACCEPT-WITH-CHANGES  
P0: 0  
P1: 1  
P2: 0  
Unverified: tests, test collection, database/SQL/DDL, runtime, network/broker/credentials, CI,
coverage, dynamic transition behavior, mutation execution, and paired exact-head 93% closeout - all
prohibited or deferred by this static-only gate.
