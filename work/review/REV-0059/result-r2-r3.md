# Independent static preflight result - WO-0152 E3 R2-R3

Review date: 2026-08-07  
Review seat: independent Codex review seat  
Mode: static-only exact-candidate preflight  
Branch: `codex/arch-reset-2026-07-r1`  
Review base / candidate HEAD: `a2b84abc1914517cf591f27fb88f0b20b2a47ef7`  
Manifest: `work/review/REV-0059/WO-0152-RED-CANDIDATE-R2-R3-MANIFEST.md`  
Manifest SHA-256: `ee5554bf4e6b380fa7c687324adba7f93168e56168fb84cedf519115e4b7c3f6`

## Outcome

No P0, P1, or P2 finding was identified. The exact R2-R3 composite preserves the stopped R2 and
R2-R2 candidates as unaccepted evidence, preserves the R2-R1 result as negative preflight
evidence, replaces current activation authority with exact R2-R3 independent acceptance, and
corrects the static exception table without broadening implementation or operating authority.

The four privileged helpers remain bounded to the three inherited setup exceptions and the one
public boundedness tripwire. The tripwire is statically constructible as fourteen property-shaped
and two method-shaped class-member replacements, and its required live-decision matrix is
nonvacuous. No production or public-API change is required by this candidate.

Activation disposition: **ACCEPT - the R2-R3 documentation/preflight gate is satisfied at
P0=0/P1=0.** This result does not itself activate WO-0152, implement E3, close WO-0151, satisfy the
paired 93% gate, or authorize any excluded activity.

## Exact candidate and hash verification

All observations in this section were made before creating this reviewer-owned result.

- `git branch --show-current` returned `codex/arch-reset-2026-07-r1`.
- `git rev-parse HEAD` returned `a2b84abc1914517cf591f27fb88f0b20b2a47ef7`.
- The independently computed manifest SHA-256 was
  `ee5554bf4e6b380fa7c687324adba7f93168e56168fb84cedf519115e4b7c3f6`, exactly the requested
  frozen identity.
- I parsed and independently re-hashed all 42 SHA-256 rows in the R2-R3 manifest: **42/42
  matched; 0 missing; 0 mismatched**.
- I also parsed all 55 rows in the transitively pinned R2-R2 manifest. All 49 unchanged rows,
  including every retained R0 through R2-R2 packet artifact, still match. The other six rows are
  the expected mutable WO/ratification/PKL/ledger documents evolved by R2-R3; each is re-pinned at
  its exact current hash in the R2-R3 manifest.

| R2-R3 candidate input | Recomputed SHA-256 |
| --- | --- |
| `WO-0152-RED-R2-R3-REMEDIATION-DISPOSITION.md` | `9c2d1b99316ac4d6cbf9e1e4e588570b49e885cc8788c034a3d79a44754b72a2` |
| `WO-0152-RED-CONTRACT-R2-R3.md` | `881334b4af6acb566adc57c30a4199f0340129d244cc3d58536c8e7c109a9936` |
| `request-r2-r3.md` | `0b924f38ba2e5f2ad116384e1a8d9b048548b30046cde9c3da50ffaa375ec2d8` |
| `work/queue/WO-0152-reset-kernel-e3-generation-conformance.md` | `fb94b8a3a1f1954d2710f9c989e1d1f7f5b2b943b2f072610d1d749ecd606dce` |
| `docs/adr/ARCH-RESET-2026-07-RATIFICATION.md` | `6b2ea299c81f4856c54e3a05caf765630f0a139b241d2c9fe831a09530f8118c` |
| `pkl/project/goals.md` | `90d0e2f37d35a5e396e5cd384e869f79f16abadabedba1ba2cf1281fa1a66ef4` |
| `pkl/architecture/architecture-map.md` | `4ec2766b0ea7b3530d6b36a71ab1bc970d790ee85118228f05885c08379f7cc8` |
| `pkl/log.md` | `1b2f62fa92596850207e708e85b2d1f8e1dfc70ddda4c230bee89062cd09fc77` |
| `work/ledger.jsonl` | `e401f2ace3173c0f79d360258601f65fe48c3589652746b7f1f2cb4d76c617cf` |

- Before reviewer output, all required absent paths were absent:
  `tests/execution_core/test_acquisition_stateful.py`,
  `work/review/REV-0059/result-r2.md`,
  `work/review/REV-0059/result-r2-r2.md`, and
  `work/review/REV-0059/result-r2-r3.md`.
- The exact pre-output status contained **8 tracked modifications and 34 untracked files**, with
  **0 staged paths**. Every one of the 42 status paths belongs to the R2-R3 manifest or its
  transitively pinned R2-R2 chain; there was no extra path.
- The tracked delta is limited to the manifest-listed ratification, PKL, retained WO-0151 evidence,
  append-only ledger, current WO-0152 draft, and REV-0058 closeout documents: 642 insertions and
  78 deletions across 8 files. No production source or existing test file is modified.
- The ledger diff contains 9 appended records and no removed record. It adds or amends no `INV-*`
  entry.
- `git diff --check` exited 0 with no output.

## Static re-derivation

### Retained evidence and exact activation ordering

- The manifest accurately records the first R2 candidate and R2-R2 as stopped before verdict, with
  `result-r2.md` and `result-r2-r2.md` absent
  (`WO-0152-RED-CANDIDATE-R2-R3-MANIFEST.md:17-23`). The hash-identical R2-R1 result remains
  `ACCEPT-WITH-CHANGES`, P0=0/P1=1/P2=0. No R2 or R2-R2 verdict is invented.
- Current authority is exact: the WO metadata and status section require fresh exact R2-R3
  acceptance before activation
  (`work/queue/WO-0152-reset-kernel-e3-generation-conformance.md:4-16,49-60`); the replacement
  contract requires this exact immutable R2-R3 manifest and fresh `ACCEPT` at P0=0/P1=0, with no
  earlier result substitutable (`WO-0152-RED-CONTRACT-R2-R3.md:27-37`).
- The current PKL posture is aligned at `pkl/project/goals.md:35-45,68-74,139-149` and
  `pkl/architecture/architecture-map.md:40-52,71-76`. The latest PKL log entry
  (`pkl/log.md:406-415`), ratification entry
  (`docs/adr/ARCH-RESET-2026-07-RATIFICATION.md:412-428`), and ledger row 165 carry the same exact
  R2-R3 condition. Earlier R2 and R2-R2 predicates remain only in clearly dated, superseded
  provenance entries.
- The unchanged 93% condition is not relaxed. The current WO, contract, manifest, PKL,
  ratification, and ledger all retain run #741 as 91.34% coverage-only negative evidence and keep
  paired E2/E3 exact-head Python 3.11/3.12 success at 93% as a later closeout gate.

### Coherent static exception table

- The complete table at `WO-0152-RED-CONTRACT-R2-R3.md:39-59` permits all and only the inherited
  exact operations. The environment predecessor retains exactly two `copy.copy` calls and seven
  literal setters; the approved-mandate fixture retains its one lexical private minter call; the
  terminal-parent fixture retains its fixed proof types, one private reducer site, one literal
  temporary certification-hook patch, one copy, and one literal venue setter. The public suffix
  row grants no private access.
- The boundedness helper alone receives the new `ExitStack`-scoped `patch.object` allowance. The
  table and outside-table rule jointly reject aliases, wrappers, loops, dynamic targets/names,
  instance patching, started/returned patchers, broad setters/copies, private access, and
  production-object mutation. This resolves R2-R2's accidental ban without creating a broader
  bypass.
- The inherited R2/R2-R1 six-step same-account OTHER-symbol lifecycle, pre-install guards, one
  copied literal venue installation, target-bootstrap assertion, terminal certification limits,
  and negative controls remain controlling (`WO-0152-RED-CONTRACT-R2-R3.md:20-25`).

### Exact sixteen-target boundedness tripwire

- The sixteen table rows at `WO-0152-RED-CONTRACT-R2-R3.md:61-86` resolve to real public class
  members in the frozen source. Twelve `VenueRecoveryBook` members are true `@property`
  descriptors (`app/execution_core/venue.py:4269-4392`), while `SeenFactIndex.entries` and
  `RootHeadIndex.entries` are true properties (`app/execution_core/fills.py:1082-1097,1461-1476`).
- The remaining two targets are correctly method-shaped:
  `VenueRecoveryBook.effect(self, effect_id)` at `app/execution_core/venue.py:6710-6719` and
  `SeenFactIndex.observation_at(self, index)` at `app/execution_core/fills.py:1482-1493`.
  `effect` must remain trapped: it calls `_contradictions_for`, whose retained persistent sequence
  is converted to a tuple (`app/execution_core/venue.py:4262-4267,6710-6719`), so a keyed lookup
  still materializes per-effect contradiction history.
- Static precedent confirms class-level property and method patching restores through context
  managers (`tests/execution_core/test_venue_binding_recovery.py:131-187,516-550`). R2-R3 makes
  that precedent stricter by requiring sixteen explicit calls rather than a dynamic loop and by
  fixing the two method signatures.
- The deliberately unpatched readers are bounded direct-map lookups: venue correlation/binding/
  owner/attempt/closure readers (`app/execution_core/venue.py:6721-6808,6959-6967,7358-7366`),
  `GenerationRegistry.record` (`app/execution_core/acquisition.py:343-358`), lineage routes and
  their direct `_PersistentKeyMap.get` implementation
  (`app/execution_core/acquisition.py:522-580,725-746`), and `SeenFactIndex.get` /
  `RootHeadIndex.get` (`app/execution_core/fills.py:1099-1101,1478-1480`). They are therefore
  correctly excluded from the trap.
- The required execution is nonvacuous: after construction and while all traps are active, the
  same scope must exercise and assert `refresh_acquisition_context`,
  `project_acquisition_admission`, and `reduce_acquisition_controller` on an authenticated current
  or retired canonical transition (`WO-0152-RED-CONTRACT-R2-R3.md:88-99`). Setup and inspection
  are outside the context, every replacement must raise, restoration is required on normal and
  exceptional exit, and negative source specimens must reject missing, changed, private, dynamic,
  out-of-scope, or misplaced traps (`WO-0152-RED-CONTRACT-R2-R3.md:109-116`).
- Frozen source inspection shows those live entry points use bounded shape validation and direct
  indexes rather than the trapped views: authority validation is constant-work
  (`app/execution_core/authority.py:697-722`), admission uses direct per-scope maps
  (`app/execution_core/authority.py:3143-3266`), refresh uses direct venue bindings and scoped
  checkpoints (`app/execution_core/authority.py:4029-4165`), and canonical reduction routes by
  direct lineage/registry readers (`app/execution_core/acquisition.py:4082-4176,4438-4515`).

### Scope, safety, and public surface

- WO-0152 remains `DRAFT`, owner-unassigned, and `implementation_authority: NOT_GRANTED`. Its
  future implementation path remains the one absent test module plus lifecycle/evidence records;
  production paths and existing tests remain forbidden.
- The safety core remains intact: paper-only beta, submitted is not filled, only first-occurrence
  canonical FILL/predecessor-linked broker-authoritative TRADE_CORRECT/TRADE_BUST revisions change
  quantity, UI never calls Alpaca, kill switch blocks new intent, and one writer remains
  authoritative (`CLAUDE.md:27-53`). The candidate changes no implementation surface.
- Existing module-public authority readers and the exported acquisition reducer already express
  the three trapped decisions; `VenueRecoveryBook`, `SeenFactIndex`, and `RootHeadIndex` are already
  public package types (`app/execution_core/__init__.py:3-18,48-75,137-162,306-354`). No production
  API or architecture change is necessary.

## Bottom-up disproof and reconciled non-findings

- I traced the two method-shaped traps from their implementations upward, then the fourteen
  properties, unpatched direct readers, and the three mandatory live entry points. I found no
  missing target, false property shape, direct-reader overblock, hidden history access, or need for
  a production seam.
- I attempted to make the trap proof vacuous by moving setup or inspection inside the context,
  omitting a target, changing a target or shape, using a dynamic name/loop, and invoking no
  authenticated live reducer. The exact-set/shape control, required three-decision assertion, and
  named negative source specimens reject those constructions.
- I attempted to bypass the exception table through an alias, wrapper, extra setter/copy, private
  target, instance patch, dynamic lookup, returned/started patcher, or another helper. The complete
  table plus the outside-table prohibition rejects each path while still allowing the inherited
  environment setters, private mandate minter, and terminal certification hook.
- I searched the current WO, current PKL sections, latest ratification/log/ledger records, and R2-R3
  packet for an activation predicate satisfiable by R2, R2-R1, or R2-R2. None survived. Older
  predicates are dated retained history and are explicitly non-substitutable.
- I attempted to find a scope, safety, or coverage relaxation in the full tracked delta. No
  production/test source changed; no human-gated implementation surface changed; no result claims
  test execution; paired unchanged-93% closeout remains mandatory; and all database, SQL/DDL,
  runtime, broker/network, credential, CI, M2, merge, deletion, and cleanup exclusions remain.

## Findings

No P0, P1, or P2 findings.

## Evidence limits

This review intentionally used only read-only static source, file, SHA-256, Git status/diff, and
whitespace inspection. I did **not** run tests, test collection, database-capable fixtures,
SQL/DDL, application/runtime commands, network, broker, credential, CI, or coverage commands. I
did not inspect or mutate database/broker state. Dynamic execution and coverage were therefore not
reproduced; run #741 and its 91.34% result are retained frozen evidence only. Static source proves
the plan is constructible and bounded, but future RED/GREEN execution, mutation evidence, exact-head
CI, and paired 93% closeout remain activation/implementation obligations. No file was edited by this
seat except this result.

Verdict: ACCEPT  
P0: 0  
P1: 0  
P2: 0  
Unverified: tests, database/SQL/DDL, runtime, network/broker/credentials, CI, coverage, and dynamic
execution - all prohibited by this static-only gate.
