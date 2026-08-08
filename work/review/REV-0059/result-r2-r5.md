# Independent static preflight result - WO-0152 E3 R2-R5

[FABLE • FULL • verification: DIRECT • task: independent R2-R5 duplicate-stream-probe preflight]

Review date: 2026-08-07  
Review seat: independent Codex review seat  
Mode: static-only exact-candidate preflight  
Branch: `codex/arch-reset-2026-07-r1`  
Review base / candidate HEAD: `e35ff07c42675646cc7a13f1949f80fdf108e516`  
Candidate contract: `work/review/REV-0059/WO-0152-RED-CONTRACT-R2-R5.md`  
Candidate contract SHA-256: `79c734b7c0a929d43aeca83ef00e797b7afc8d97754eb30f1c812b1dd5b3221e`  
Manifest: `work/review/REV-0059/WO-0152-RED-CANDIDATE-R2-R5-MANIFEST.md`  
Manifest SHA-256: `3fbcffbec46dd43248a1a8b569df39880c96e9d539d5a84a07cf58fde19be946`  
Isolated partial-test SHA-256: `e10e623230744f4a4c43cbc11cc0850562f32e8ee64286efb5ef0ba2ff3d6b79`

## Fable gate

```yaml
fable_gate:
  goal: "Independently decide whether the exact documentation-only R2-R5 replacement is constructible, failure-capable, bounded, and safe to accept for resumed E3 test work."
  assumptions:
    - claim: "The branch, review base, and immutable manifest identify the exact candidate."
      status: VERIFIED
      evidence: "Branch and HEAD matched; all 29 manifest SHA-256 rows matched independently computed hashes."
    - claim: "The partial E3 module is isolated retained baseline material, not R2-R5 implementation or acceptance evidence."
      status: VERIFIED
      evidence: "It remained the sole untracked test path and retained SHA-256 e10e623230744f4a4c43cbc11cc0850562f32e8ee64286efb5ef0ba2ff3d6b79."
    - claim: "A refusal control is failure-capable only if every coordinate other than nonadjacent stream reuse is independently valid."
      status: VERIFIED
      evidence: "Accepted ADR-020 R2/ADR-021 R2 require fresh sealed successor authority and prohibit market-stream reset/reuse; current source has separate mandate, binding, and immediate-predecessor stream checks."
  approach: "Re-hash the frozen composite, inspect only static Git/file/source evidence, re-derive binding and successor behavior bottom-up, and attempt to disprove each acceptance claim."
  alternatives_considered:
    - "Reuse mandate A: rejected because three independent freshness checks would refuse it even without a stream-ownership rule."
    - "Put the negative probe in the positive schedule: rejected because it invalidates the required 32-entry all-unique positive trace."
    - "Use a caller-shaped factory or public copy: rejected because it broadens the seam and cannot create an authentic sealed binding."
  out_of_scope:
    - "Tests, test collection, database-capable fixtures, SQL/DDL, application or broker runtime, network, credentials, CI, and coverage."
    - "Production, test, ADR-body, work-order, PKL, ledger, request, manifest, disposition, commit, or push changes."
  done_when:
    - behavior: "Exact candidate identity, retained chain, current records, scope, and isolated baseline are reconciled."
      test: "Static SHA-256, Git status/diff, append-only, and path inspection."
      command: "Get-FileHash; git status --short; git diff --check; git diff --numstat."
    - behavior: "The separate fixed probe and exactly two minter sites are constructible and bounded."
      test: "Static constructor, seal, call-shape, contract, and bypass analysis."
      command: "Read-only source and contract inspection."
    - behavior: "The public A-to-B-to-duplicate-A-stream control isolates reuse and has an honest E2 stop."
      test: "Bottom-up comparison of all successor predicates and direct stream-ownership paths."
      command: "Read-only source search and full-function inspection."
  blast_radius: "This reviewer-owned result file only."
  rollback: "Preserve the immutable candidate and prior packet chain; a supported P0/P1 would leave E3 paused for a replacement re-gate."
```

## Outcome

No P0, P1, or P2 finding was identified. R2-R5 preserves the valid 32-entry positive schedule and
adds the smallest bounded authentic negative input: one fixed zero-argument fixture, one literal
non-loop private mint site, fresh mandate/protection/binding identities, and A's literal stream.
The two private mint sites have distinct, closed lexical shapes and are surrounded by exact-set,
literal-relation, call-order, consumer-separation, and named bypass controls.

The public A -> B -> duplicate-A-stream control is failure-capable. Current source statically
admits that final successor because it compares the candidate stream only with immediate
predecessor B, not retained A. That is not concealed by this contract: R2-R5 requires the exact
trace to stop E3 and return bounded E2 remediation, without an E3 guard, history scan, expected
failure, oracle weakening, or production edit. The re-gate is therefore **ACCEPT** at
P0=0/P1=0/P2=0.

## Exact candidate, hash, retention, and scope verification

All observations in this section were made before creating this reviewer-owned result.

- `git branch --show-current` returned `codex/arch-reset-2026-07-r1`; `git rev-parse HEAD` returned
  `e35ff07c42675646cc7a13f1949f80fdf108e516`, exactly the manifest review base.
- The independently computed candidate-contract and manifest hashes are the exact values recorded
  above. All **29/29** SHA-256 rows parsed from the R2-R5 manifest matched; there were **0 missing**
  and **0 mismatched** inputs.
- The retained R2-R3 manifest, contract, independent result, and activation disposition matched
  `ee5554bf4e6b380fa7c687324adba7f93168e56168fb84cedf519115e4b7c3f6`,
  `881334b4af6acb566adc57c30a4199f0340129d244cc3d58536c8e7c109a9936`,
  `8752e20fa0aba82885d1d49ae8eabca9901218f5659073adcb4324fa9b189a59`, and
  `2ef88891b3e303833d93d36cd50a99132b24e6b8b994c822fcfa65b8ebf976b3`.
- Every retained R2-R4 artifact matched its R2-R5 manifest pin. In particular, the R2-R4 contract,
  manifest, and independent result remained
  `f2a59f1c4197aac851249a136d0a3a1761c7e365f4f34468acb842dc18e5866e`,
  `a62df766a608c187c93efa8550c0fa06192f2c21b048c404738f136e0905005b`, and
  `48079e3b54beedddbb56382de2b05f49e6f887e2173c17d24e6131de0bce1889`.
- The R2-R5 disposition and request matched
  `718de4f3a618bc7ee7a8fcf1a2ed4e8073d5aedd9241e3b366bc33ff6ac6fa59` and
  `d4d13fd0c9bf48f30306a7cbab7ea2ed2b44b581e8374e2c38f2e26d05e890df`.
- Before output, status contained exactly six expected tracked modifications and ten expected
  untracked paths: the isolated partial test, five retained R2-R4 packet paths, and four R2-R5
  candidate paths. There were no staged paths, no production-source or existing-test changes, and
  `result-r2-r5.md`, `result-r2.md`, and `result-r2-r2.md` were absent.
- `git diff --check` exited 0 with no output. Ratification, PKL log, and ledger changes were
  append-only at `+52/-0`, `+18/-0`, and `+2/-0`; current goals, architecture-map, and active-WO
  edits only reconcile the R2-R4 result and R2-R5 pause/re-gate posture.
- Every frozen production/source and accepted ADR-body hash matched. The only untracked test path
  remained `tests/execution_core/test_acquisition_stateful.py`, and it re-hashed to the isolated
  baseline above. Its 349 lines contain only the retained R2-R3 environment fixture and two public
  boundary controls; it contains no schedule, mandate minter, probe, serial chain, replay, mutation,
  or boundedness expansion and was not used as R2-R5 acceptance evidence.
- Active WO-0152 remains `ACTIVE` but explicitly pauses further E3 implementation for exact R2-R5
  acceptance (`work/active/WO-0152-reset-kernel-e3-generation-conformance.md:15-17,84-114`). Its
  machine-readable scope names this result and every candidate path; production, accepted ADR-body,
  runtime, broker, database, SQL/DDL, and CI paths remain forbidden. WO-0151 remains effectively
  `REVIEW`, and the paired unchanged 93% Python 3.11/3.12 exact-head closeout remains mandatory.

```yaml
evidence:
  phase: MANUAL_QA
  command: "Static Get-FileHash, Git status/diff/check/numstat, source search, and full governing-artifact inspection only."
  result: PASS
  decisive_output: "HEAD matched; 29/29 manifest rows matched; partial baseline matched; no staged/source expansion; append-only records and whitespace check passed."
```

## Static re-derivation

### The separate probe is the smallest authentic bounded construction

- `DualMandateBinding` has no public constructor; it raises on construction
  (`app/execution_core/acquisition.py:1146-1167`). The private minter seals the complete acquisition
  terms, protection mandate, and compatibility (`app/execution_core/acquisition.py:1206-1299`), and
  `AcquisitionMandate` rejects a reused or mismatched seal
  (`app/execution_core/acquisition.py:1328-1382`). A public copy or replacement therefore cannot
  make a fresh-ID A-stream probe authentic.
- Reusing mandate A is not an isolating substitute. `begin_acquisition_generation` independently
  requires a fresh acquisition-mandate ID, protection-mandate ID, and binding commitment before its
  stream comparison (`app/execution_core/acquisition.py:3950-3958`). Original A would remain
  `REFUSED` even if all stream-ownership enforcement were absent.
- R2-R5 leaves the positive fixture and its 32-entry unique-stream schedule unchanged, then adds
  one separate zero-argument helper whose own literal descriptor supplies fresh IDs and a literal
  stream equal to A and unequal to B (`WO-0152-RED-CONTRACT-R2-R5.md:30-86`). The probe is returned
  separately and cannot enter the positive tuple or 32-generation chain. This preserves the
  positive proof and creates exactly the otherwise-valid sealed negative candidate that R2-R4
  lacked.

### Exactly two private minter sites remain closed

- The retained schedule site is one direct call expression inside one ordinary loop over the exact
  literal 32-entry schedule. The added probe site is one direct unconditional call expression in
  the exact zero-argument helper, outside every loop, branch, exception handler, context manager,
  lambda, wrapper, alias, dynamic lookup, or nested function.
- The composite globally fixes the total at two call expressions and prohibits every other
  invocation, reference, alias, wrapper, or dynamic resolution. It also fixes literal probe IDs,
  A/B stream relations, positive/probe separation, and pre-genesis ordering
  (`WO-0152-RED-CONTRACT-R2-R5.md:121-152`). Named failure-capable source specimens cover a second
  or parameterized helper, third/outside/aliased minter, derived stream, reused A mandate/binding,
  duplicate IDs, positive-tuple or positive-chain contamination, and post-genesis invocation.
- These shapes are statically decidable from one module AST: exact function signature and return,
  exact `ast.Call` targets and enclosing constructs, literal descriptor values, fixed call-site
  order, exact consumer set, and absence of forbidden private/dynamic operations. No production
  seam, caller configuration, controller, runtime, effect, claim, broker, persistence, or actor
  authority is created.

### The public control isolates stream reuse and honestly returns E2

- Accepted ADR-020 R2 requires a serial successor's new ADR-023 state to use a distinct approved
  stream and forbids acquisition-generation reuse of market-stream authority
  (`docs/adr/ADR-020-current-state-execution-kernel.md:47-60`). ADR-021 R2 requires a distinct
  complete binding and stream at successor admission and explicitly requires evidence for no
  market-stream reset/reuse (`docs/adr/ADR-021-position-protection-liquidity-execution.md:74-105,211-217`).
  The ratification index records the controlling model as forbidding market-stream reset/reuse
  (`docs/adr/ARCH-RESET-2026-07-RATIFICATION.md:229-241`).
- The control builds the schedule and probe before genesis, initializes A, applies the public
  aborted/no-root A -> B successor, then recomputes public current refresh/bootstrap/admission
  inputs for B -> probe. Immediately before the final call it must independently prove fresh
  acquisition/protection IDs and binding commitment against every schedule member; exact A stream,
  non-B stream, scope, session, terms, compatibility, controller head, ordinal, bootstrap,
  admission, and current authority; and absence of generic BUY, terminal/private closure, mutation,
  or history scans (`WO-0152-RED-CONTRACT-R2-R5.md:88-112`). Those checks remove the alternate
  refusal paths that made the R2-R4 control non-diagnostic.
- Refusal is publicly observable as exact predecessor component identity with no generation,
  effect, claim, or authority mutation; the reducer's refusal constructor retains those objects
  (`app/execution_core/acquisition.py:2126-2165`).
- Bottom-up source inspection found no retained-stream ownership lookup in authority or venue.
  `begin_acquisition_generation` compares the candidate stream only to the immediately prior
  mandate (`app/execution_core/acquisition.py:3842-3965`). Because the fixed probe stream equals A
  but differs from B, otherwise-valid current source reaches successor registration. The planned
  refusal assertion will therefore fail for its intended reason. R2-R5 explicitly requires that
  exact natural disagreement to freeze the minimized trace and stop for bounded E2 remediation
  (`WO-0152-RED-CONTRACT-R2-R5.md:107-119`); it neither misstates current behavior nor permits an E3
  workaround.

## Bottom-up disproof and reconciled non-findings

- I began with the opaque seal and successor predicate rather than the candidate narrative. A
  fresh-ID public mandate carrying A's stream cannot authenticate with A's or another schedule
  member's binding. Exactly one separately bounded mint is necessary; a broader factory is not.
- I tried the original A mandate. Its acquisition ID, protection ID, and binding all fail before
  the stream comparison, so it cannot make the reuse test sensitive. The R2-R5 probe removes all
  three confounders and behavior-checks their actual commitments.
- I tried placing the probe in the 32-entry positive schedule or feeding it to the long chain. That
  destroys positive stream uniqueness. Exact tuple/consumer controls and dedicated negative
  specimens reject both constructions.
- I tried a third minter, alias, wrapper, dynamic attribute, schedule-derived stream, copied
  mandate, second helper, caller parameter, conditional mint, and post-genesis call. The exact
  global call count, lexical parent shapes, literal relation checks, outside-table prohibition,
  consumer restrictions, and named source specimens reject each route without overblocking the
  retained loop site.
- I tried to obtain final refusal through duplicate binding, scope/session/compatibility mismatch,
  stale head/ordinal, nonterminal work, or malformed bootstrap/admission instead of stream reuse.
  The required pre-final public assertions independently make each coordinate fresh, equal, current,
  or valid as appropriate; refusal remains sensitive only to retained nonadjacent stream ownership.
- I attempted to disprove the E2-stop claim by searching every frozen acquisition, authority, and
  venue stream-generation reference. The only acquisition successor check is immediate-predecessor
  inequality. Current admission of A -> B -> A-stream is therefore a real owning-slice E2
  disagreement, and the R2-R5 stop/remediation rule exposes it directly.
- I found no hidden relaxation in retained R2-R3/R2-R4 fixtures, the sixteen-member boundedness
  tripwire, current provenance, append-only records, partial-baseline isolation, source scope,
  safety core, or paired 93% closeout.

## Findings

No P0, P1, or P2 findings.

## Evidence limits

This review intentionally used only read-only static source, file, SHA-256, Git status/diff, path,
and whitespace inspection. I did **not** run tests, test collection, database-capable fixtures,
SQL/DDL, application/runtime commands, network, broker, credential, CI, or coverage commands. I did
not inspect or mutate database/broker state. The present admission behavior and future control's
ability to expose it are source-derived static conclusions; no dynamic transition was executed.
The future schedule, probe, self-source checker, negative specimens, and public control do not yet
exist and therefore remain implementation/evidence obligations. Run #741 and 91.34% are retained
frozen evidence only; future RED/GREEN, mutation, exact-head CI, and paired 93% closeout remain
unverified. No file was edited by this seat except this result.

```yaml
fable_done:
  task: "WO-0152 R2-R5 independent static preflight"
  done_when_results:
    - item: "Exact candidate identity, retained chain, current records, scope, and isolated baseline are reconciled."
      status: MET
      evidence: "29/29 manifest rows matched; exact branch/base and isolated hash matched; no source expansion or path discrepancy."
    - item: "The separate fixed probe and exactly two private minter sites are constructible and bounded."
      status: MET
      evidence: "One retained fixed 32-iteration site plus one fixed non-loop site can construct the positive schedule and one authentic fresh-ID A-stream probe without a general seam."
    - item: "The public control isolates nonadjacent stream reuse and preserves the owning-slice stop."
      status: MET
      evidence: "All alternate successor coordinates are independently valid; current immediate-predecessor-only source admits the probe; exact E2 remediation is mandatory."
    - item: "R2-R4 retention, append-only provenance, partial baseline, safety exclusions, and paired closeout remain exact."
      status: MET
      evidence: "Frozen hashes, static diffs, active scope, and current records reconciled without dynamic execution."
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
  debt_check: "clean"
  deferred:
    - "Future E3 RED/GREEN, self-source specimens, mutation evidence, and exact-head paired 93% closeout."
    - "Bounded E2 remediation if the implemented public probe reproduces the statically identified admission."
  status: VERIFIED
```

Verdict: ACCEPT  
P0: 0  
P1: 0  
P2: 0  
Unverified: tests, test collection, future AST/source controls, dynamic transition behavior,
database/SQL/DDL, runtime, network/broker/credentials, CI, coverage, mutation execution, E2
remediation, and paired exact-head 93% closeout - all prohibited, not yet implemented, or deferred
by this static-only gate.
