---
type: Work Order
title: M2-I3.5 anchored non-serving checkpoint closure
status: SUPERSEDED
work_order_id: WO-0168c
wave: M2-I3.5-R13-C
model_tier: strong
risk: critical
disposition: [SUPERSEDED, RESULT_SUMMARY_KEPT, ARCHIVED]
owner: Codex orchestrator and implementation seat; fresh-context reviewers required
created: 2026-08-23
predecessor: WO-0168h superseded after REV-0076 R5 BLOCK
branch: codex/m2-wo0168c-remediation-r1
preflight_review_id: REV-0077
implementation_review_id: REV-0078
execution_authority: Ameen Mujtabaa's serial-M2 authorization permits ordinary reversible work through M2 closeout and M3 preparation. REV-0077 accepted the exact R13 preflight at aa2f0225a0d0d85a41e5cfc5f6c8e530ed7c1a83 with P0=0/P1=0/P2=0. Exact named source/test paths below are released. Changed DDL remains static-only and no changed-DDL install or SQLite-bearing test may run until Ameen approves the exact candidate commit/tree, DDL SHA-256 and byte count, and named fresh-file test plan. No configured/in-memory database, migration, runtime composition, credentials, network, broker calls, orders, promotion, or merge to master is authorized.
allowed_paths:
  - work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md
  - work/completed/keep/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md
  - work/queue/M2-EXECUTION-2026-08-21/08-WO-0168C-FROZEN-ANCHORED-CHECKPOINT-CONTRACT.md
  - work/queue/M2-EXECUTION-2026-08-21/09-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R1.md
  - work/queue/M2-EXECUTION-2026-08-21/10-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R2.md
  - work/queue/M2-EXECUTION-2026-08-21/11-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R3.md
  - work/queue/M2-EXECUTION-2026-08-21/12-WO-0168C-R3-SQL-MANIFEST.md
  - work/queue/M2-EXECUTION-2026-08-21/13-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R4.md
  - work/queue/M2-EXECUTION-2026-08-21/14-WO-0168C-R4-SQL-MANIFEST.md
  - work/queue/M2-EXECUTION-2026-08-21/15-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R5.md
  - work/queue/M2-EXECUTION-2026-08-21/16-WO-0168C-R5-SQL-MANIFEST.md
  - work/queue/M2-EXECUTION-2026-08-21/17-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R6.md
  - work/queue/M2-EXECUTION-2026-08-21/18-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R7.md
  - work/queue/M2-EXECUTION-2026-08-21/19-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R8.md
  - work/queue/M2-EXECUTION-2026-08-21/20-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R9.md
  - work/queue/M2-EXECUTION-2026-08-21/21-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R10.md
  - work/queue/M2-EXECUTION-2026-08-21/22-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R11.md
  - work/queue/M2-EXECUTION-2026-08-21/23-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R12.md
  - work/queue/M2-EXECUTION-2026-08-21/24-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R13.md
  - work/queue/M2-EXECUTION-2026-08-21/25-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R14.md
  - work/queue/M2-EXECUTION-2026-08-21/26-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R15.md
  - work/queue/M2-EXECUTION-2026-08-21/27-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R16.md
  - work/queue/M2-EXECUTION-2026-08-21/28-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R17.md
  - work/queue/M2-EXECUTION-2026-08-21/29-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R18.md
  - work/queue/M2-EXECUTION-2026-08-21/30-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R19.md
  - work/queue/M2-EXECUTION-2026-08-21/31-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R20.md
  - work/queue/M2-EXECUTION-2026-08-21/32-CLAUDE-OPUS-M2-CONTINUATION.md
  - work/queue/M2-EXECUTION-2026-08-21/33-CLAUDE-M2-CONTINUATION-S2.md
  - work/queue/M2-EXECUTION-2026-08-21/34-M2-COMPLETION-DRIVE.md
  - work/review/REV-0077/**
  - work/review/REV-0078/**
  - work/review/REV-0079/**
  - work/review/REV-0080/**
  - work/review/REV-0081/**
  - work/review/REV-0082/**
  - work/review/REV-0083/**
  - work/review/REV-0084/**
  - work/review/REV-0085/**
  - work/review/REV-0086/**
  - work/review/REV-0087/**
  - work/review/REV-0088/**
  - work/review/REV-0089/**
  - work/review/REV-0090/**
  - work/review/REV-0091/**
  - work/review/REV-0092/**
  - work/review/REV-0093/**
  - work/review/REV-0094/**
  - work/review/REV-0095/**
  - work/review/REV-0096/**
  - work/review/REV-0097/**
  - work/review/REV-0098/**
  - work/review/REV-0099/**
  - work/review/REV-0100/**
  - work/review/REV-0101/**
  - work/review/REV-0102/**
  - work/review/REV-0103/**
  - work/review/REV-0104/**
  - work/review/REV-0105/**
  - work/review/REV-0106/**
  - work/review/FINDING-preexisting-suite-floor-2026-08-24.md
  - work/review/FINDING-protection-stateful-replay-disposition.md
  - work/review/FINDING-schema-approval-gate-is-self-approving.md
  - work/ledger.jsonl
  - app/execution_core/persistence/checkpoint_codec.py
  - app/execution_core/persistence/records.py
  - app/execution_core/persistence/repository.py
  - app/execution_core/persistence/schema.py
  - app/execution_core/venue.py
  - tests/execution_core/persistence_setup_support.py
  - tests/execution_core/test_persistence_checkpoint_codec.py
  - tests/execution_core/test_persistence_runtime_checkpoint_pure.py
  - tests/execution_core/test_persistence_runtime_checkpoint_sqlite.py
  - tests/execution_core/test_persistence_runtime_checkpoint_directness.py
  - tests/execution_core/test_persistence_schema.py
  - tests/execution_core/approved_schema_digest.py
  - tests/execution_core/test_persistence_directness.py
  - tests/execution_core/test_persistence_repository.py
  - tests/execution_core/test_persistence_write_capability.py
  - tests/execution_core/test_protection.py
  - tests/execution_core/test_venue_checkpoint_hardening.py
  - work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md
  - work/queue/M2-EXECUTION-2026-08-21/36-R16-MANUAL-RULE-RATIFICATION.md
forbidden_paths: []
---

# Work Order: WO-0168c — anchored checkpoint closure

> **Superseded 2026-08-26.** Twenty-seven review packets (REV-0079…REV-0105) failed to converge
> on the static write-capability scanner; REV-0105 returned BLOCK with P0=7/P1=5 against the
> scanner's own semantics, and P0 counts rose across the last three rounds. A blinded two-model
> architecture consultation (Claude Fable first-pass memo and ChatGPT ADEG-1.1 memo, recorded in
> `work/review/CONSULT-0001-wo0168c-architecture/`) independently reached the same root cause:
> the scanner's assurance claim — sound static verification of arbitrary Python — is unbounded
> and cannot converge. Ameen ratified the hybrid replacement on 2026-08-26:
> "Ratified: hybrid points 1–10; scanner deletion approved; prohibition re-scoped per point 5."
> **WO-0168d** (`work/active/WO-0168d-m2-i3-5-hybrid-gate-simplification.md`) succeeds this work
> order. The uncommitted scanner WIP (SHA-256 `2978d800…`) is abandoned, not finished. All product
> code accepted under this work order (checkpoint codec, records, repository, schema, held suites)
> remains valid. The changed-DDL HUMAN-GATE remains closed; its lifecycle is redefined by WO-0168d.
> The amendment chain below is preserved unchanged as treadmill evidence.

`[FABLE • FULL • spec-first/TDD • one provenance boundary • no external I/O]`

## Outcome

Replace the disproved standalone R13-H split with one exact preflight for a complete but
explicitly non-serving checkpoint boundary: canonical state bytes, pre-persistence selection
proof, immutable payload persistence, post-persistence load proof, and an inert restored
candidate. WO-0169 alone may establish restart eligibility and serving authority.

## Root design rule

Integrity bytes are not authority. Neither the encoder, decoder, repository, nor WO-0168c may
issue an existing serving proof/owner type. Repository selection must precede encoding; payload
persistence must precede kernel-head advance; loading must freshly authenticate the current head
and exact bytes. Selection never depends on facts unavailable to its issuer. Existing
history-shaped behavior commitments are not claimed reproducible from bounded checkpoint bytes.

## Documentation-only preflight

Before source authority is released, freeze one indivisible contract that specifies:

1. the exact state that must survive restart and whether each member is database-discoverable or
   payload-owned authenticated semantics;
2. canonical non-serving wire types, arrays, tags, ordering, finite limits, and commitments;
3. direct-key repository proof queries and exact absence/nonmembership evidence;
4. distinct pre-persistence selection and post-persistence load proofs with no circular identity;
5. exact execution/protection component bytes and inert venue cursor/bootstrap candidates without
   claiming existing history-shaped owner commitments are reproducible;
6. the public outer envelope and payload record/store/load contract without circular digests;
7. atomic current-head/payload/reverse-edge constraints and any exact static DDL bytes;
8. fresh-file SQLite tests held behind Ameen's exact changed-DDL gate; and
9. failure-capable tests that kill forged bytes, stale/spliced proofs, extra/missing selected
   state, unbounded reads, serving-type minting, reducer bypass, and partial persistence; and
10. the exact WO-0169 obligations for owner-locked serving conversion and bounded behavioral
    commitment cutover.

The contract must prefer accepted repository facts over duplicating history in checkpoint bytes.
It must use ordered sequences where order is semantic and keyed sets only where canonical key order
is semantic. It may narrow or delete unnecessary intermediate types; it may not introduce a second
engine, generic serializer, replay store, or alternate authority source.

## Gate and execution sequence

1. Author the exact contract and static candidate only.
2. Obtain fresh REV-0077 `ACCEPT` with `P0=0/P1=0`.
3. Amend this work order with exact source/test paths and release only the accepted implementation
   surface.
4. Implement pure codecs and static persistence changes without executing changed DDL.
5. Stop at the exact DDL human gate with candidate commit/tree, DDL digest/bytes, and named
   temporary-file test plan.
6. After Ameen's approval, run only the approved fresh-file SQLite gate, remediate within the same
   authority while re-gating every changed DDL byte, then complete full verification.
7. Obtain fresh REV-0078 `ACCEPT` with `P0=0/P1=0`, close, and publish.

## Accepted implementation release

REV-0077 R13 passed at the exact identity recorded in frontmatter. The implementation seat may
edit only the named `app/**` and `tests/**` paths above. Pure codec/binding/authenticity and static
source tests may run before the DDL gate. The SQLite-bearing runtime-checkpoint and schema tests
may be authored but must not run; no changed schema may be installed. The implementation must stop
with a static source candidate and return its exact commit, tree, `SCHEMA_DDL` SHA-256 and UTF-8
byte count, changed-DDL summary, and the exact fresh-`tmp_path` file test commands for Ameen's
approval.

## Exclusions

No configured or in-memory database, migration, runtime composition, credentials, external I/O,
broker call, order, promotion, PR, or merge to `master`. WO-0168b/M2-I4 remains separate and starts
only after this checkpoint substrate is accepted.

---

## Amendment — released paths extended under recorded authority (2026-08-24)

REV-0078 P1-5 found seven changed paths outside the released list. Each is named here with the
authority that produced it, so the canonical scope check can pass against the recorded intent.
Authority: Ameen's serial-M2 authorization (frontmatter) plus his explicit 2026-08-24 approvals in
session — the DDL correction, "address the findings" for the adversarial-pass and REV-0078
remediations, and the two finding-file authorizations ("You may open one", "Take them").

| Path | Rationale |
| --- | --- |
| `tests/execution_core/test_persistence_repository.py` | WO-0168c debt unmasked by the DDL fix: export pins and kernel-checkpoint fixtures for checkpoint reads this work order added. |
| `tests/execution_core/test_persistence_directness.py` | Self-approval removal (REV-0078 P0-1): fixture now reads the transcribed literal. |
| `tests/execution_core/test_persistence_write_capability.py` | Import-direction control correction (authorized 2026-08-24) and the P0-1 anti-tautology AST control. |
| `tests/execution_core/approved_schema_digest.py` | New: the single human-transcribed approval literal (P0-1). |
| `work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md` | The DDL gate bundle, its ratification amendment, and the P0-1 noncompliance record. |
| `work/queue/M2-EXECUTION-2026-08-21/36-R16-MANUAL-RULE-RATIFICATION.md` | Ameen's ratified resolution of the R15 §3 / R16 §2 conflict (P1-6). |
| `work/review/FINDING-protection-stateful-replay-disposition.md` | Authorized finding ("You may open one"): pre-existing defect recorded, not fixed. |
| `work/review/FINDING-schema-approval-gate-is-self-approving.md` | Authorized finding: the self-approving gate, tracked to closure before execution_core goes live. |
| `work/review/FINDING-preexisting-suite-floor-2026-08-24.md` | Authorized floor record: three pre-existing failures attributed to base. |
| `work/review/REV-0078/**` | The review packet itself: request, handoff, in-process pass, reviewer result (merged unmodified), disposition. |

The `app/**` and `tests/**` checkpoint paths already released by the accepted implementation
surface are unchanged. No path beyond this table has been touched since `344c32b`.

## Amendment — Codex remediation branch (2026-08-24)

The former Claude implementation handoff at `3b26c1cd636615cf0d85c13951eaebf099b88bdc` is
being remediated in the isolated Codex worktree on
`codex/m2-wo0168c-remediation-r1`. This records the active implementation identity only; it does
not widen the released paths, authorize any SQLite execution, or change the human DDL gate.

## Amendment — second fresh review route (2026-08-24)

REV-0079 reviewed `2f16f52` and returned two P1 findings. Its request and result are immutable
evidence; the implementation seat may remediate those root causes inside the already released
source/test paths. `work/review/REV-0080/**` is added solely for the fresh exact-head re-review
of that remediation. No SQLite execution, changed-DDL installation, or authority expansion is
created by this review-path addition.

## Amendment — REV-0081 exact remediation review route (2026-08-24)

REV-0080 reviewed `426935eee5808055796cba360d3be95a15ac55a3` and returned
`P0=0`, `P1=2`, `P2=1`. Its two P1 findings are remediated at
`9984232fcc6fce9b9261798858262e529c3729e2`, tree
`1f36eaf9b260a7182c5c6541833c236d8090685b`: selected mutable effect claims,
closures, and evidence are now bound to their proof-selected durable relations;
the static DDL gate audit now accepts only a direct, pre-open approval route.
The historical P2 whitespace in the reviewer-owned REV-0079 result remains
preserved and future evidence is scoped to the candidate paths it actually checks.

`work/review/REV-0081/**` is added solely for a fresh exact-head review of this
remediation. The source and test paths were already released by this work order.
This amendment creates no DDL change, SQLite execution authority, changed-DDL
installation, or expansion of the human gate.

## Amendment — REV-0082 exact remediation review route (2026-08-24)

REV-0081 reviewed `9984232fcc6fce9b9261798858262e529c3729e2` and returned
`P0=0`, `P1=4`, `P2=1`. Its P1 root remediations are frozen at
`7b240744a7399eb55b1d8e4bf0b41c1f11a0c95d`, tree
`bd0274f086c8d156bad6b6e1fc5fb45c43980df8`: INVALIDATED runtime
contradictions now equal the selected durable invalidation rows (owner,
observation, and ordinal order); NEVER_DISPATCHED additionally requires the
selected cancellation lifecycle; and the source-level DDL audit accepts only
the canonical, un-rebound approval accessor and direct runtime-safe SQLite
grammar. The negative controls prove the specific dynamic, alternate-import,
default-expression, duplicate, and splice failures rather than an unrelated
missing-gate failure. Direct, aliased, builtins, and namespace-recovered dynamic
SQLite imports are also refused without blocking unrelated fixture delegation.
The P2 unrelated bare `.install_schema()` false positive is covered by a passing
unrelated-source control.

`work/review/REV-0082/**` is added solely for a new independent exact-head
review of this remediation. The source and test paths were already released by
this work order. This amendment creates no DDL change, SQLite execution
authority, changed-DDL installation, or expansion of the human gate.

## Amendment — REV-0083 exact control review route (2026-08-24)

REV-0082 reviewed `7b240744a7399eb55b1d8e4bf0b41c1f11a0c95d` and returned
`P0=0`, `P1=5`, `P2=2`. Its test/provenance remediations are frozen at
`546471c86647637a277237a53cf949b66a6a955a`, tree
`f0aedb729b83136a021ce324dc2744ec8ad1325c`: selected INVALIDATION evidence
now has a two-owner/two-observation positive ordering witness and a swapped-order
failure; a selected claim cannot be re-described as NEVER_DISPATCHED after a
forged cancellation lifecycle; and the static DDL source grammar rejects nested
SQLite imports, `Connection` constructors, SQLite namespace recovery,
function-local dynamic imports, wildcard or module-based approval mutation, and
direct approval accessor namespace mutation. The retained unrelated bound
`.install_schema` source remains an explicit passing control. The existing
constructed-target `__import__` detector is now covered by its own control rather
than being credited without a failure-capable test.

`work/review/REV-0083/**` is added solely for a fresh, independent exact-head
review of these controls. The source and test paths were already released by this
work order. This amendment creates no DDL change, SQLite execution authority,
changed-DDL installation, or expansion of the human gate.

## Amendment — REV-0084 exact dynamic-acquisition review route (2026-08-24)

REV-0083 reviewed `546471c86647637a277237a53cf949b66a6a955a` and returned
`P0=0`, `P1=1`, `P2=0`: without a canonical approval import, direct dynamic or
namespace recovery could remain outside the SQLite-surface classifier. Its root
remediation is frozen at `4c98e4058d76cefc92d7b8aecf43d2b426722713`, tree
`db7135490b98666aa95ca1de18407787a7f6f501`. The source grammar now treats
direct dynamic-import factory results and direct namespace-map/module-registry
results as disallowed connection receivers even if no approval import is present;
it follows simple aliases of those values and folds literal string concatenation
for import targets. It does not claim to decide arbitrary metaprogramming. The
new controls prove constructed import targets, `globals`, `sys.modules`, simple
aliases, local import aliases, and `__builtins__` acquisition paths fail, while a
SQLite exception-construction-only source remains accepted.

`work/review/REV-0084/**` is added solely for a fresh, independent exact-head
review of this bounded grammar remediation. The source and test paths were
already released by this work order. This amendment creates no DDL change,
SQLite execution authority, changed-DDL installation, or expansion of the human
gate.

## Amendment — REV-0085 exact root-grammar review route (2026-08-24)

REV-0084 reviewed `4c98e4058d76cefc92d7b8aecf43d2b426722713` and returned
`P0=0`, `P1=2`, `P2=0`. Its two P1 findings are remediated at
`c918d281357c76806ec9a74a1efe2629d1c29dc4`, tree
`6aa7d7eecbd8f546010969fa8832013338f0200f`. The source-level DDL audit now
uses one bounded acquisition grammar: it follows only a unique direct
assignment in the current or module scope, recognizes known `importlib`/
`builtins` import routes and direct `globals`, `vars`, `sys.modules`, and
`__builtins__` map retrieval, then refuses a recovered SQLite module's
`.connect` or `.Connection` call. It does not infer SQLite provenance from an
arbitrary object's `import_module` method. Focused negative controls cover
`.get`, `.__getitem__`, nested builtins recovery, and simple aliases; the
passing custom-client control proves ordinary client naming is not swept in.

`work/review/REV-0085/**` is added solely for a fresh exact-head review of this
root correction. The source and test paths were already released by this work
order. This amendment creates no DDL change, SQLite execution authority,
changed-DDL installation, or expansion of the human gate.

## Amendment — REV-0086 exact alias-closure review route (2026-08-24)

REV-0085 reviewed `c918d281357c76806ec9a74a1efe2629d1c29dc4` and returned
`P0=0`, `P1=1`, `P2=0`. Its independently reproduced P1 route is remediated at
`4f70d1a0446ac7b19fd542febe34e3b91945c542`, tree
`0f7160ac5b22904a223a8db5087edce0e26ed57d`. The same bounded resolver now
handles a simple alias of a namespace factory (`globals`/`vars`), a proven map
lookup method (`.get`/`.__getitem__`), and an escaped bound recovered
`.connect`/`.Connection` attribute. It still requires a proven dynamic map or
known import route and retains explicit passing custom-client method controls.
The new controls fail on aliased `globals`, `vars`, `sys.modules`, nested
`__builtins__`, and bound connection references, rather than on an unrelated
missing import.

`work/review/REV-0086/**` is added solely for a fresh exact-head review of this
root correction. The source and test paths were already released by this work
order. This amendment creates no DDL change, SQLite execution authority,
changed-DDL installation, or expansion of the human gate.

## Amendment — REV-0087 exact provenance-grammar review route (2026-08-24)

REV-0086 reviewed `4f70d1a0446ac7b19fd542febe34e3b91945c542` and returned
`P0=0`, `P1=2`, `P2=0`. Its independently reproduced alias/data-flow findings
are remediated at `d9296eec74027e54c619a8d2186ea7761cd4317f`, tree
`d31f84547a15b88ab8c42121bc30c413726a42c7`. The prior receiver-specific
heuristics are replaced by one finite provenance grammar. It tracks lexical
captures, all prior simple rebindings in the nearest lexical scope, assignment
expressions, known `importlib`/`builtins` imports, direct namespace maps,
`dict.get`/`dict.__getitem__`, and statically named `getattr` access only when
the receiver is already a proven namespace map or recovered SQLite module.
Unknown or custom objects carry no SQLite provenance. The grammar is expressly
not an evaluator for arbitrary metaprogramming; its governed mechanisms and
their positive/negative controls are complete in the source test.

`work/review/REV-0087/**` is added solely for a fresh exact-head review of this
root correction. The source and test paths were already released by this work
order. This amendment creates no DDL change, SQLite execution authority,
changed-DDL installation, or expansion of the human gate.

## Amendment — REV-0088 lexical-capability boundary review route (2026-08-24)

REV-0087 reviewed `d9296eec74027e54c619a8d2186ea7761cd4317f` and returned
`P0=0`, `P1=3`, `P2=0`. Its independently reproduced routes show that the
provenance evaluator remains structurally incomplete: a late outer binding,
aliases of known `builtins`/`sys` capability primitives, and declared
`global`/`nonlocal` hand-offs can all evade receiver provenance. This reaches
the work order's repeated-remediation circuit breaker. The implementation seat
must not extend that evaluator with a fourth alias pattern.

The replacement is a smaller fail-closed lexical-capability boundary. A scope
which directly uses `globals`, `vars`, `__builtins__`, `__import__`, a known
`builtins`/`importlib`/`sys` capability member, or a direct import of such a
member is a dynamic-capability region. A noncanonical `.connect`/
`.Connection` endpoint, or a static lookup of either member, is refused in that
scope or a descendant. A dynamic source function declaring `global` or
`nonlocal` also marks its target enclosing scope(s), so declared sibling
hand-offs cannot escape. Canonical `sqlite3.connect` remains under the existing
direct pre-open gate grammar. Generic custom-client methods do not create a
dynamic-capability region merely because their names resemble a lookup or
import; an explicit unrelated-fixture control proves that distinction.

This is a test-side static-source correction only. It changes no DDL byte, no
SQL, no public export, no runtime composition, and no human-gate authority.
`work/review/REV-0088/**` is added solely for a new independent exact-head
review of this root correction. The source and test paths were already released
by this work order. SQLite execution and changed-DDL installation remain
forbidden until the separately required exact-head P0=0/P1=0 review and human
gate.

## Amendment — REV-0089 capability-escalation review route (2026-08-24)

REV-0088 reviewed `9a3b3367e032be92e5235e07d65b74b3c92d2c93` and returned
`P0=0`, `P1=5`, `P2=0`. The result exposes a material design limit in the
lexical-region rule: it is neither complete for statically recovered capability
members and escape paths nor precise for shadowed names and unrelated client
calls. No fourth local extension of the region predicate is authorized by this
work order's circuit breaker.

The next remediation must replace that predicate with one cohesive
capability-escalation grammar. It must resolve only lexically proven canonical
capability bindings; distinguish a complete one-shot static non-privileged
namespace lookup from a dynamic capability source; and escalate a real or
potential SQLite acquisition through the relevant enclosing ownership boundary
when it can escape. Connection endpoints must be recognized only as explicit
members or lexically proven member-lookup primitives, never merely because an
arbitrary call has a string argument. Generic custom objects and a shadowed
module spelling remain unknown, not SQLite. This is still a finite static
grammar, not arbitrary Python evaluation.

This amendment authorizes only a test-side source-guard redesign and focused
pure controls inside already released paths. It changes no DDL byte, SQL,
public export, runtime composition, or human-gate authority.
`work/review/REV-0089/**` is added solely for a new independent exact-head
review. SQLite execution and changed-DDL installation remain forbidden until
the separately required exact-head P0=0/P1=0 review and human gate.

## Amendment — REV-0090 exact lexical-binding review route (2026-08-24)

The `REV-0089` source candidate was not accepted. Fresh independent scrutiny
reproduced three ownership errors in its static source grammar: keyword-form
`import_module(name=...)` was not a known acquisition, shadowed `importlib` and
`sqlite3` spellings could be treated as privileged, and a static non-SQLite
import beside a canonical route could be refused by a broad source-level rule.
The next remediation is frozen at
`85648ce2a660f8077b07a6bb1029b33ed69d0010`, tree
`63a045f881f98ac19bebcc7915019eb12d0fd817`.

The static audit now resolves one finite lexical capability binding grammar for
known modules/members, import targets (including the `name=` form), direct
installer and approval provenance, current-global versus ordinary namespace
reflection, and explicit dynamic installer/connection surfaces. Generic custom
objects and locally shadowed spellings remain unknown. Its source-level controls
prove both refusal and acceptance of these boundaries; mutation controls prove
known-source detection, dynamic endpoint detection, lexical static-string
resolution, and parameter shadow binding each matter. This changes no DDL byte,
SQL, public export, runtime composition, or human-gate authority.

`work/review/REV-0090/**` is added solely for a fresh exact-head review of this
remediation. SQLite execution and changed-DDL installation remain forbidden
until a new independent result records `P0=0/P1=0` and Ameen separately approves
the exact candidate, tree, DDL identity, manifest, and fresh-file-only commands.

## Amendment — REV-0091 source-ownership review route (2026-08-24)

REV-0090 was not accepted: two fresh independent reviews reproduced
scope-ownership, module-map, relative-import, dynamic-code, installer-escape,
and approval-module gaps in its static audit. The root remediation is frozen at
0cf88d1a3831ae487140a7f8f75cad75bc57bf3f, tree
c75b1270dd0123fd2bf1019365c5a057b17e4cbe.

The audit now has one position-aware, finite lexical binding model. It owns
defaults/decorators in their enclosing scope, comprehension targets in their
implicit scope, class namespaces separately from method free-name lookup, and
declared global/nonlocal hand-offs at their actual owner. It preserves
module-map provenance for importlib, sys, builtins, schema, SQLite, and the
approval module; resolves static relative import_module targets; and rejects
known dynamic code, installer escapes, approval-token mutation, and schema
member recovery. Ordinary local shadows, local vars(), custom methods, and
same-scope ordinary rebindings remain ordinary.

This is a test-side source-guard correction only. It changes no DDL byte, SQL,
public export, runtime composition, or human-gate authority.
work/review/REV-0091/** is added solely for a new fresh exact-head review.
SQLite execution and changed-DDL installation remain forbidden until that
review records P0=0, P1=0 and Ameen separately approves the exact candidate,
tree, DDL identity, manifest, and fresh-file-only commands.

## Amendment — REV-0092 exact static-boundary review route (2026-08-24)

Before an independent REV-0091 result was treated as an acceptance input, the
implementation seat's own disproof pass reproduced four adjacent static-guard
routes at `0cf88d1`: schema module `__dict__` recovery, a `vars(schema)`
installer escape, an `operator.attrgetter` installer escape, and a lexical
built-in `setattr` mutation of a function-local approval-module import. These
are one bounded provenance issue: expressions or capability calls that resolve
to a governed value must be rejected at their real lexical owner, not only when
they have one of the previously enumerated AST shapes.

The root correction is frozen at
`4ca754d20ca330753a135378ce7138651fe1b81b`, tree
`e655bf165d3edbf07040f51b224b9a92b5d5e33b`. It adds the finite known built-in
`setattr` capability, refuses direct schema module namespace recovery, and
checks every expression resolved as an installer/dynamic-installer for a
non-direct escape. The new controls and three killed mutation controls prove
these rules individually. This changes test-side static audit code only; it
does not change DDL, SQL, public exports, runtime composition, or human-gate
authority.

`work/review/REV-0092/**` is added solely for a fresh review of that exact
candidate. REV-0091 remains immutable historical evidence and is not an
acceptance verdict for the new source head. SQLite execution and changed-DDL
installation remain forbidden until an independent exact-head result records
P0=0, P1=0 and Ameen separately approves the DDL gate packet.

## Amendment — REV-0093 approval-namespace ownership review route (2026-08-24)

REV-0092 was superseded before an independent verdict issued. A further
implementation-seat RED control reproduced the remaining root gap: the audit
recognized a direct approval module and a direct `setattr`, but did not own the
approval module's recoverable namespace or every ordinary attribute-mutator
form. In particular, `vars(gate).update(...)`, a literal
`sys.modules['approved_schema_digest']` route, `delattr`, and direct or
getter-recovered `__setattr__` could reach the approval token.

The root correction is frozen at
`fe88d0538ce2253a72cb09903e258488888b4a1d`, tree
`403fb99171f630c5a043857dab14257a1237afe1`. One finite provenance rule now
refuses every expression resolved as the approval module's namespace map. The
existing known-builtins grammar owns `setattr` and `delattr` as attribute
mutators; direct and static-getter-recovered bound module mutators are a
separate known capability that either mutates the exact token or cannot escape.
Literal approval lookup from the already modeled `sys.modules` map resolves to
the approval module before the same rule runs. No arbitrary Python evaluation,
generic module mutation ban, DDL, SQL, public export, runtime composition, or
human-gate authority was added.

`work/review/REV-0093/**` is added solely for a fresh review of that exact
candidate. REV-0092 remains immutable historical evidence, not an acceptance
verdict for this successor. SQLite execution and changed-DDL installation remain
forbidden until an independent exact-head P0=0/P1=0 result and Ameen's separate
exact DDL gate approval.

## Amendment — REV-0094 exact approval-provenance review route (2026-08-24)

REV-0093 was superseded before an independent verdict issued. Its fresh
reviewers supplied reproducible advisory routes, all reconciled through one
finite capability model rather than one-off denylists: direct `ImportFrom`
recovery of approval namespaces or bound mutators; approval
`__getattribute__`; `sys.modules` registry mutation/recovery via `setdefault`;
and `sys.modules['builtins']` recovery of a known mutator. The review also
identified a precision defect: the prior model treated `sys.modules` and
`sys.__dict__` as the same map, potentially classifying an unrelated sys
attribute as the approval module.

The root correction is frozen at
`970bf5113a33ac3e8b64d51e93c1a434cb24287f`, tree
`606f70edd5e3961b33a18b5f90dab86d132fb667`. It treats the approval module as
non-mutable through every recognized direct member, known mutator, bound
mutator, or recovered namespace route. It introduces one explicit
`module-registry` kind for `sys.modules`; ordinary `sys.__dict__` remains a
separate map. The registry owns a finite list of security-relevant module
identities and refuses non-read-only direct map operations. New RED/GREEN and
mutation controls prove the new direct-import, attribute, registry, and
builtins routes as well as the ordinary-sys false-positive boundary.

This remains test-side static audit only: no DDL byte, SQL, public export,
runtime composition, database activity, or human-gate authority changed.
`work/review/REV-0094/**` is added solely for a fresh review of that exact
candidate. All prior review packets remain immutable historical evidence.
SQLite execution and changed-DDL installation remain forbidden until an
independent exact-head P0=0/P1=0 result and Ameen's separate exact DDL gate
approval.

## Amendment — REV-0095 exact registry-ownership review route (2026-08-24)

REV-0094 was superseded before a reviewer-owned verdict issued. Fresh advisory
disproof of its source candidate found that direct `sys.modules[...]` stores
and deletes were not refused; it also found three ownership/precision gaps:
direct `sys`/`builtins` namespace imports lost provenance, escaped
`sys.modules` mutator references were unclassified, and a shadowed local
`dict` spelling could be mistaken for the builtin mapping primitive.

The root remediation is frozen at
`4dd24b5e3235cfff160923c31eee5922c6ed95fe`, tree
`6311752ec66cea80a0331ceb6918a0dc1172c584`. The finite model now distinguishes
the `sys.modules` registry from the `sys.__dict__` namespace: direct registry
stores/deletes and every recognized registry mutator are refused, while an
attempt to recover `modules` through the sys namespace is itself refused as a
separate dynamic namespace route. Direct `ImportFrom` provenance for
`sys.__dict__` and `builtins.__dict__` is preserved, and only a lexically
proven builtin `dict` can supply a static registry mutator. This keeps ordinary
sys attributes and locally shadowed `dict` values outside the privileged model.
Focused RED/GREEN controls and five independently killed mutations prove these
rules without broadening into an evaluator for arbitrary Python.

This remains test-side static audit only: no DDL byte, SQL, public export,
runtime composition, database activity, or human-gate authority changed.
`work/review/REV-0095/**` is added solely for a new exact-head independent
review. SQLite execution and changed-DDL installation remain forbidden until
that review records P0=0, P1=0 and Ameen separately approves the exact
candidate, tree, DDL identity, manifest, and fresh-file-only commands.

## Amendment — REV-0096 exact sensitive-value ownership review route (2026-08-24)

REV-0095 independently reviewed
`4dd24b5e3235cfff160923c31eee5922c6ed95fe` and returned BLOCK with three
distinct P0 findings, two P1 findings, and one P2 documentation finding. The
P0s proved that registry and sys-namespace-map mutations were owned by too few
surface spellings and that the canonical approval accessor could be rewritten
in place. The P1s proved a shadowed local `dict` was treated as the builtin and
that an ordinary direct registry read was rejected while its imported
equivalent passed. The P2 correctly noted that the REV-0095 request described
a multi-commit range as if it were a one-file source diff. REV-0095 remains
immutable evidence; its result records the independent reviewers' complete
findings.

The root remediation is frozen at
`d00903f9321b124723f6dad3d74f68b3214eb240`, tree
`be49d44033451513949ac338e7f502fa9ac2f135`. It makes mutation ownership
value-centered: the finite grammar distinguishes the sensitive module registry
and sys namespace map; follows known builtin-dict and operator mutator
functions through lexical aliases; owns stores, deletes, and augmented writes;
and allows only tracked map reads to preserve downstream provenance. The
approval accessor is now an unescapable capability except as its direct
canonical call, with explicit direct, known-mutator, reflection, and arbitrary
object-mutation controls. Map lookup now requires a lexically resolved builtin
`dict`, leaving a local shadow ordinary. Direct registry reads are no longer
rejected by spelling alone; their resulting proven module values remain governed.

The successor's review request names the exact one-file code range
`4dd24b5..d00903f`, separately from its documentation commits, resolving the
P2 without rewriting REV-0095. This remains test-side static audit only: no
DDL byte, SQL, public export, runtime composition, database activity, or
human-gate authority changed. `work/review/REV-0096/**` is added solely for a
new independent exact-head review. SQLite execution and changed-DDL
installation remain forbidden until that review records P0=0, P1=0 and Ameen
separately approves the exact candidate, tree, DDL identity, manifest, and
fresh-file-only commands.

## Amendment — REV-0097 disposition and REV-0098 root-cause review route (2026-08-24)

REV-0097 independently reviewed `b8709110d7e634b92d1af6262c28332fc25b5b93`
and returned BLOCK with `P0=5`, `P1=1`, and `P2=0`. Its fresh-context seats
reproduced three reflection/mutation escapes (the `sys` module registry,
`schema.install_schema`, and builtins import machinery), a helper-module
re-export route for the installer and approval accessor, deferred
function-global lookup timing, and an approval accessor that was structurally
pinned only to a private validator call rather than the validator's behavior.
REV-0097 and its result remain immutable evidence.

The one bounded root remediation is frozen at
`ec1fbf8f94a2e10f08a33ef5d3476f336d37ce13`, tree
`7974e3718ab1977d7eb640eea75f28e1f908607c`. It removes the arbitrary-token
private validator, structurally pins the full public fail-closed accessor,
models governed module mutation/reflection as value-owned capability routes,
uses conservative function-global timing, and adds a repository-wide finite
provenance pass that refuses re-export/recovery of the installer, approval
accessor, and their owning modules through direct imports, module namespaces,
maps, reflection, literal dynamic imports, and literal `sys.modules` lookup.
This changes only the already-released pure test/gate paths. It changes no DDL
byte, SQL, public runtime export, runtime composition, or human-gate authority.

`work/review/REV-0098/**` is added solely for a fresh independent exact-head
review of that remediation. The changed-DDL gate remains closed: no SQLite
execution, changed-DDL installation, migration, configured or in-memory
database, credentials, network, broker, order, promotion, or merge authority
is created by this amendment.

## Amendment — REV-0098 disposition and REV-0099 finite-provenance review route (2026-08-25)

REV-0098 independently reviewed
`ec1fbf8f94a2e10f08a33ef5d3476f336d37ce13` and returned BLOCK with
`P0=5`, `P1=2`, and `P2=0`. Its fresh-context seats reproduced governed-module
value escapes, missing canonical helper-recovery forms, a non-recursive source
inventory, a false whole-source GREEN claim, brittle diagnostic-count evidence,
an approval module whose builtin dependencies could be rebound, and ordinary
lexical false positives. REV-0098 and its result remain immutable evidence.

The root remediation is frozen at
`ce9c2b482605ff25144b193ab6783960530922c6`, tree
`43e7ff04b10e6025ad7b53e1c2d5f82123a88b20`. The approval control now pins the
complete executable module while preserving only the separately authorized
future literal-token edit. The single-file grammar owns governed module values
and every recognized builtins-map mutation. The repository topology uses one
finite lexical model for local/package/relative imports, relay aliases,
namespaces and mappings, canonical getter/importer primitives, module type
reflection, and recursive source discovery; local shadows and custom methods
remain ordinary. Controls prove each rejected and accepted route separately.

The same commit makes one behavior-preserving checkpoint-code validation
invariant explicit so mypy can prove the already-required closure evidence ID
is non-null before its direct-key lookup. It adds no cast or bypass and changes
no DDL, SQL, public export, runtime composition, or human-gate authority.

`work/review/REV-0099/**` is added solely for a fresh independent exact-head
review. SQLite execution and changed-DDL installation remain forbidden until
that review records `P0=0`, `P1=0` and Ameen separately approves the exact
candidate, tree, DDL identity, manifest, and fresh-file-only commands.

## Amendment — bounded protection-test path extension (2026-08-25)

REV-0099's value-ownership disproof showed that three pure protection-test
helpers pass the global `builtins` module through an ordinary mapping call or
dynamic getter. Keeping those helpers while exempting their filename would
weaken the same root rule under review. `tests/execution_core/test_protection.py`
is therefore released only to replace those dynamic module escapes with direct
read-only comparisons and a finite error-type mapping. No production path,
DDL, SQL, runtime composition, database authority, or public behavior is added.

## Amendment — REV-0099 root disposition and REV-0100 (2026-08-25)

REV-0099 returned `BLOCK` with P0=4, P1=1, and P2=1. The owning defects are
value provenance independent of local gate syntax, incomplete package/relative
identity, unowned helper-module and module-descriptor relays, lost provenance
after dynamic governed lookup, and flow-insensitive rebinding. The correction
must therefore remain one finite lexical model: package-aware identities,
governed-unknown propagation, explicit helper/module-type ownership, ordered
definite bindings with conservative conditional unions, and every parent
binding observable after a deferred function becomes callable. Filename
waivers and route-specific source exemptions remain forbidden.

`work/review/REV-0100/**` is released solely for a fresh independent review of
the replacement exact source target. The request must correct REV-0099's
approval-file provenance statement. Changed-DDL execution, SQLite imports or
connections, and all four held suites remain forbidden until REV-0100 records
P0=0/P1=0 and Ameen separately approves the exact HUMAN-GATE packet.

The replacement source target is
`97f316b934114f0b70f9fd2975c276a6b37e272b`, tree
`c5534f689a1571107b63f83f819c48763c15909d`. Its direct source commit changes
only `test_persistence_write_capability.py` and `test_protection.py`. Held-safe
evidence at that exact target is 761 pure/static tests on CPython 3.12.13 and
33 capability tests on CPython 3.14.5, with mypy, import boundaries, Ruff, OS
governance, cumulative scope, and whitespace checks green. The DDL digest,
178755-byte count, catalog digest, R4 manifest, and locked `None` approval
literal remain unchanged.

## Amendment — REV-0100 root disposition and REV-0101 (2026-08-25)

REV-0100 returned `BLOCK` with P0=3, P1=2, and P2=0. The replacement must own
derived governed attributes/maps and protected helper members/mutators; retain
package-prefix and every known static-string alternative; route `global` and
`nonlocal` bindings to Python's declared owner; and evaluate deferred parent
state at statically provable call sites without retaining states no call can
observe. The protection error oracle must use direct builtin-module identities.
These are one provenance-and-time model, not filename or spelling waivers.

`work/review/REV-0101/**` is released solely for the next fresh exact-source
review. All DDL/SQLite holds and the separate Ameen HUMAN-GATE remain binding.

## Amendment — REV-0101 exact finite-state candidate (2026-08-25)

The REV-0100 owning findings are remediated at
`2189d0fe6cf5428188b83255a5ef7725fac61174`, tree
`a068104c1f9363b6557f8f41b69c980dcb605976`. The direct source commit changes
only `test_persistence_write_capability.py` and `test_protection.py`.

The replacement uses one finite binding-state model across the single-file and
cross-file gates. Definite bindings replace older states; conditional bindings
remain alternatives; same-position bindings are all retained; deferred parent
state is evaluated at proven calls and conservatively from escape onward; and
`global`/`nonlocal` writes are routed to their declared owner. Static text
resolution carries both reachable literals and a completeness bit, so a known
protected alternative cannot disappear and an unknown alternative cannot be
reported as an exact singleton. Package prefixes, helper namespaces/maps,
module descriptors, and unmodeled governed attributes remain owned. A finite
allowlist identifies current ordinary read-only members of governed standard
modules; every unmodeled member fails closed. Protection assertions resolve
only explicitly named builtin identities and compare raised errors to direct
`builtins.TypeError`/`builtins.ValueError` objects.

Current exact-head evidence is source/static only: Ruff check and formatting,
AST parsing, mypy over 95 app files, all six import-linter contracts, AI Project
OS install/version/ledger/PKL/disposition checks, cumulative work-order scope,
and `git diff --check` pass. Source-text-only identity recomputation leaves the
DDL SHA-256, 178755-byte count, catalog digest, R4 manifest digest, and locked
`None` approval literal unchanged.

The prior `761 passed` CPython 3.12 and `33 passed` CPython 3.14 evidence belongs
to `97f316b9`, not this successor. An environment execution guard refused the
new import-based pytest rerun because it could not prove the transitive import
graph SQLite-free. That refusal is recorded as `NOT_RUN`, not routed around and
not represented as GREEN. REV-0101 is therefore a source-only exact-head
review. No SQLite import/connection, held suite, DDL install, migration, or
database activity is authorized. The changed-DDL HUMAN-GATE remains closed
until a fresh exact-head result records `P0=0` and `P1=0`, after which Ameen must
separately approve the exact DDL packet and named fresh-file commands.

## Amendment — REV-0101 disposition and REV-0102 callable-flow review route (2026-08-25)

REV-0101 independently reviewed
`2189d0fe6cf5428188b83255a5ef7725fac61174` and returned `BLOCK` with
P0=5, P1=1, and P2=0 after deduplication. The owning defects are expression-
level conditional execution, lambda/callable-alias observation time,
`ImportFrom` namespace-package prefixes, a mutable `sys.path` value incorrectly
classified as ordinary, and a conditional-target control that could remain
green after its intended alternative-propagation rule was removed. Passive
identity observations and simple local aliases were both symptoms of the one
callable-flow precision defect.

The successor must correct those roots in both finite source gates: model
short-circuit and conditional-expression execution; resolve named functions,
lambdas, and simple local callable aliases at proven call or real escape
positions; distinguish passive observations from value-flow escape; apply
module-prefix identity to imported namespace-package members; permit only exact
ordinary standard-module reads, never mutable import machinery; and assert a
provenance-specific diagnostic for the conditional-alternative mutation. No
filename waiver, broad dynamic evaluator, or route-specific exemption is
authorized.

`work/review/REV-0102/**` is released solely for the fresh exact-source review
of that root correction. All DDL/SQLite holds and Ameen's separate HUMAN-GATE
remain binding.

## Amendment — REV-0102 exact conditional/callable provenance candidate (2026-08-25)

The REV-0101 owning findings are remediated at
`501a86425c32ab8b099f897f23334cbbc0df5b36`, tree
`df69b207a0b4c060187deaf7e270ef334c0984aa`. The direct source commit changes
only `tests/execution_core/test_persistence_write_capability.py`.

Both finite source gates now distinguish definitely evaluated tests/first
operands from conditional Boolean, conditional-expression, statement,
context-managed-body, comprehension, match, and exception paths. Walrus targets
inside comprehensions are assigned to Python's real enclosing owner. Callable
observation follows named functions, lambdas, and simple assignment aliases at
proven direct calls; identity-only observations remain passive, while equality,
membership, argument/container storage, attribute/subscript flow, decorators,
and other real escapes conservatively retain the state observable from escape
onward. A walrus expression that itself flows outward is an escape, not a local
alias exemption. Namespace-package `ImportFrom` aliases retain package-prefix
identity, and mutable `sys.path` is no longer classified as an ordinary read.
The conditional-alternative controls assert the exact protected-provenance
diagnostic rather than accepting an unrelated violation.

Exact-candidate static evidence is clean: Ruff check/format, AST parsing, mypy
over 95 app files, all six import-linter contracts, AI Project OS install,
version, ledger, PKL, disposition, cumulative scope, and whitespace gates pass.
Pytest remains `NOT_RUN`: the execution guard refused the import-based pure
suite and was not routed around. Source-only recomputation leaves `SCHEMA_DDL`
at SHA-256 `2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5`
and 178755 UTF-8 bytes, `_SCHEMA_CATALOG_SHA256` at
`c717f6a6c84b37cb13773416c90b50d14f377e39928d7f9c626e769296e632d2`,
the R4 manifest at
`99aab5f40d43ea5dacce78e77ea47cad250cb9618223d9036a071d8a2704ed39`,
and the approval literal at `None`.

REV-0102 must independently review this exact source identity and return
`P0=0/P1=0` before the changed-DDL HUMAN-GATE may be presented. No SQLite
import/connection, held suite, changed-DDL execution, database activity, or
authority expansion is created by this amendment.

## Amendment — REV-0102 disposition and REV-0103 execution-semantics route (2026-08-25)

REV-0102 independently reviewed
`501a86425c32ab8b099f897f23334cbbc0df5b36` and returned `BLOCK`. After
deduplicating the two fresh Max seats by owning defect, the result is P0=5,
P1=2, P2=0. The source-position model still omitted match captures,
comparison/with-item conditional execution, and finite inline import-target
alternatives. More fundamentally, it treated lexical positions as runtime
timestamps across callable arguments, owner-routed writes, returned closures,
methods, generators, and coroutines. Governed `ImportFrom` members,
namespace-package maps, and interpreter-mutating `sys` members also lost
provenance. The two precision findings concern passively discarded walrus
aliases and truly unobservable local callables.

The successor must replace, not extend, the unsound callable timestamp rule.
Unproven deferred execution must fail closed through one explicit observation
state; only directly proven synchronous calls may narrow parent state, after
ordered argument evaluation. Generator/coroutine creation, returned closures,
methods, and owner-routed writes must not borrow the enclosing source line as an
execution time. Finite syntax handling must cover pattern captures, chained
comparisons, with-item phases, literal `IfExp`/Boolean unions, governed
`ImportFrom` members, module-prefix maps, and interpreter-mutating `sys`
surfaces without filename waivers or a general Python evaluator. Precision must
remain for passive local aliases and genuinely unobservable local bodies.

`work/review/REV-0103/**` is released solely for a fresh exact-source review of
that replacement. All DDL/SQLite holds and Ameen's separate HUMAN-GATE remain
binding.

## Amendment — REV-0103 runtime-provenance source candidate (2026-08-25)

The REV-0102 owning defects are replaced at
`6dd9396093a58f8e6025521146aa99534a74f01c`, tree
`ce749e17c1a31b141a871783136f53e803b2a62c`. Its direct parent is
`d4fca13bb68a470dd1b0b34fa151cad487e9e681`, tree
`a9b43fcaf32e4e5298e34d01fb424fcaeeff6131`. The source commit changes only
`tests/execution_core/test_persistence_write_capability.py`, blob
`11fe7ae71318c8da712ae42568a023f72513e036`.

Both finite source gates now use explicit runtime observation rather than
borrowing lexical source positions across execution boundaries. Conditional
bindings include match captures, comparison phases, with-item phases,
comprehensions, and exact `IfExp`/Boolean alternatives. Reads account for
test-before-branch conditional-expression order and augmented-assignment
write-after-read order. Proven direct synchronous calls observe state after
argument evaluation; owner-routed writes remain alternatives; returned or
nested callables, methods, generators, coroutines, and generator expressions
remain conservative when their activation time is not proven. A genuinely
unobserved local callable has an explicit non-executing state, while passive
local assignment and bare-walrus aliases remain precise.

Governed `ImportFrom` members retain fail-closed provenance; exact ordinary
standard-module reads remain allowed. Interpreter trace installation is limited
to a stable local callback whose finite body cannot import, call, mutate frame
namespaces, return another callback, or otherwise escape the modeled read-only
shape; the existing line-count callback and exact `gettrace` restoration remain
accepted. Namespace-package prefixes now preserve exact child, map,
reflection, mutation, and escape provenance, while packages with no protected
descendant remain ordinary. REV-0103 controls cover the cited findings plus
adjacent conditional-expression, augmented-assignment, generator-expression,
trace-return, prefix-map, prefix-mutation, and prefix-escape mutants.

Exact-source static evidence passes: Ruff check/format; import-free AST parsing
of the module and all 43 REV-0103 embedded snippets; mypy over 95 app files;
all six import-linter contracts; AI Project OS install, version, ledger, PKL,
disposition, cumulative scope, and whitespace gates. Pytest remains
`NOT_RUN`: the import-based suite was not routed around the execution guard.
Source-only recomputation leaves `SCHEMA_DDL` at SHA-256
`2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5`
and 178755 UTF-8 bytes, `_SCHEMA_CATALOG_SHA256` at
`c717f6a6c84b37cb13773416c90b50d14f377e39928d7f9c626e769296e632d2`,
the R4 manifest at
`99aab5f40d43ea5dacce78e77ea47cad250cb9618223d9036a071d8a2704ed39`,
and `APPROVED_EXECUTION_DDL_SHA256` at `None`.

REV-0103 must independently review the exact source commit above and return
`P0=0/P1=0` before the changed-DDL HUMAN-GATE may be presented. This amendment
creates no SQLite import/connection, held-suite execution, database activity,
DDL installation, or authority expansion.

## Amendment — REV-0103 disposition and REV-0104 root-remediation route (2026-08-25)

Two fresh Max seats independently reviewed
`6dd9396093a58f8e6025521146aa99534a74f01c` and returned `BLOCK`. After
deduplication by owning defect, REV-0103 records P0=6, P1=6, P2=0. The six P0
roots are assignment target/RHS phase order; local callable activation through
finite namespace maps; transitive helper provenance for child and governed
modules; callback self-replacement through owner-routed writes; literal dynamic
namespace-package import identity; and incomplete-import mutation ownership.

The precision/control roots are deferred objects created but never activated;
unguarded irrefutable whole-subject captures; an incomplete trace installation
and restoration lifecycle; ordinary namespace metadata losing precision;
independent trace import/call/escape/restoration mutation proof; and independent
Boolean/incomplete-target mutation proof. These must be corrected in the shared
execution/provenance model, not by filename waivers or route-specific ignores.

`work/review/REV-0104/**` is released solely for a fresh exact-source review of
that successor. The changed-DDL HUMAN-GATE remains closed. No SQLite import,
connection, held-suite execution, database activity, DDL installation, or
authority expansion is created by this amendment.

## Amendment — REV-0104 exact root-remediation source candidate (2026-08-25)

The replacement source candidate is commit
`cdf17715839d7d109dbf555cb4064488ae0beefe`, tree
`d6304912ca316552272d6379936cc6a1d661ade8`, parent
`e992136333573f2490ab5ac821c16402b8896176`. Its sole changed path is
`tests/execution_core/test_persistence_write_capability.py`, blob
`5b1367e08e723a9edac5b02f9b7e799b7d68602f`. The source comparison baseline
remains REV-0103 commit `6dd9396093a58f8e6025521146aa99534a74f01c`.

The candidate repairs all twelve REV-0103 roots in the shared finite execution
and provenance models. Assignment reads and writes now follow RHS-before-target
runtime phases; callable identity survives finite scope-map lookup and returned
factories; deferred creation is distinct from activation; irrefutable first-case
captures are definite; trace callbacks and exact restoration are immutable and
bounded; incomplete and prefix import provenance survives mutation; and
cross-file protected-carrier reachability is cycle-safe and transitive.

The implementation-seat disproof pass additionally found that statically
reflected `globals()`/`vars()` getters could activate a local callback without
retaining callable identity. The root correction recognizes direct and aliased
`getattr`, `object.__getattribute__`, and `operator.attrgetter` map-getter forms
in both source gates. Failure-capable controls pin those routes; no spelling or
filename waiver was added.

Exact-source static evidence at `cdf1771` is: 27/27 source-only controls pass;
the primary and topology scanners each cover 49 recursive execution-core Python
files with zero violations; the primary scan completes in 121.581 seconds and
the topology scan in 30.132 seconds; Ruff check/format pass; import-free AST
parsing passes for the module and 433 embedded snippets; mypy succeeds on 95
app files with `--no-incremental --no-sqlite-cache`; all six import-linter
contracts pass; AI Project OS install/version/ledger/PKL/disposition, cumulative
scope, and whitespace gates pass.

One initial mypy command inherited its configured SQLite cache and failed before
opening it with `sqlite3.OperationalError: unable to open database file`. The
successful rerun explicitly disabled that cache. No cache database was opened
or created, no project module or held test was imported, and no DDL was
installed or executed.

Source-only recomputation leaves `SCHEMA_DDL` at SHA-256
`2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5`
and 178755 UTF-8 bytes, `_SCHEMA_CATALOG_SHA256` at
`c717f6a6c84b37cb13773416c90b50d14f377e39928d7f9c626e769296e632d2`,
the R4 manifest at
`99aab5f40d43ea5dacce78e77ea47cad250cb9618223d9036a071d8a2704ed39`,
and `APPROVED_EXECUTION_DDL_SHA256` at `None`.

REV-0104 must independently review this exact source identity and return
`P0=0/P1=0` before the changed-DDL HUMAN-GATE may be presented. Pytest, all four
held suites, SQLite import/connection, database activity, changed-DDL execution,
and DDL installation remain `NOT_RUN` and unauthorized.

## Amendment — REV-0104 disposition and REV-0105 exact successor (2026-08-25)

REV-0104 independently reviewed source commit
`cdf17715839d7d109dbf555cb4064488ae0beefe` and returned `BLOCK`, with five P0
and two P1 roots after deduplication. The P0 roots were callable scope-map
returns, incomplete-import mutation through maps/bound mutators, unresolved
cross-file import carriers, package-prefix lookup through `sys.modules`, and a
trace-callback model that was lexical rather than effect-closed. The P1 roots
were a filename-specific schema-test waiver and controls that did not
independently kill the Boolean/completeness rules they claimed to prove.

The successor source candidate is commit
`fa260c77fb8d4b54fd915684254e1922eb9ae90a`, tree
`8599f65b3479f0f575b1b33da77d7fcefdd4e650`, parent
`369fb2c753c46a1a63b3fc2933476d9b8c573333`. Its exact changed paths and blobs
are:

- `app/execution_core/persistence/schema.py` —
  `537c6740746611dc18299aa4f7f3a5921774609c`;
- `tests/execution_core/test_persistence_schema.py` —
  `3791d5548069e151c5c1c7a162af842abaa99560`; and
- `tests/execution_core/test_persistence_write_capability.py` —
  `ecf67b9398b9bfa1e480596cfb55a88d6914d7d2`.

The root correction propagates finite callable returns and copied namespace
maps; preserves incomplete-import map/mutator ownership and unresolved imports
through the topology fixpoint; applies exact-or-prefix classification to module
registry lookups; and replaces the permissive trace walk with the closed grammar
needed by the repository's bounded line-count proof. Callback identity,
nonlocal integer-counter ownership, and the optional CPython frame-filename
filter are now structurally closed against later writes and aliases.

The filename waiver was removed. Digest mismatch is checked by the private pure
`_require_exact_approved_ddl_digest` guard, called immediately after deriving
the schema digest and before any connection access. The held schema test checks
that pure refusal; an import-free AST control pins the installer order. New
controls independently kill each REV-0104 root and the Boolean/incomplete-target
branches.

Exact-candidate static evidence is: 30/30 source-only controls pass in 0.790
seconds; the primary scanner covers 49 recursive execution-core Python files
with zero violations in 122.293 seconds; the topology scanner covers the same
49 files with zero violations in 27.904 seconds; Ruff check/format pass; mypy
succeeds on 95 app files with `--no-incremental --no-sqlite-cache`; and all six
import-linter contracts pass with `--no-cache`.

One ad hoc source-harness command accidentally selected top-level imports as
well as functions. Isolated Python stopped immediately with
`ModuleNotFoundError` reporting `No module named 'app'`; no project module
loaded and no SQLite or database capability was reached. The corrected
function-only harness produced the evidence above. This near-miss is retained
rather than silently omitted.

Source-only recomputation leaves `SCHEMA_DDL` at SHA-256
`2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5`
and 178755 UTF-8 bytes, `_SCHEMA_CATALOG_SHA256` at
`c717f6a6c84b37cb13773416c90b50d14f377e39928d7f9c626e769296e632d2`,
the R4 manifest at
`99aab5f40d43ea5dacce78e77ea47cad250cb9618223d9036a071d8a2704ed39`,
and `APPROVED_EXECUTION_DDL_SHA256` at `None`.

`work/review/REV-0105/**` is released solely for fresh exact-source review of
this successor. REV-0105 must return `P0=0/P1=0` before the changed-DDL
HUMAN-GATE may be presented. Pytest, all four held suites, project/SQLite
imports, connections, database activity, changed-DDL execution, and DDL
installation remain `NOT_RUN` and unauthorized.

## Amendment — REV-0105 disposition and root-simplification route (2026-08-25)

Two fresh Max seats independently reviewed source commit
`fa260c77fb8d4b54fd915684254e1922eb9ae90a` and returned `BLOCK`. After
deduplication by owning defect, REV-0105 records P0=7, P1=5, P2=0.

The P0 roots are: writes through scope maps do not update binding provenance;
general callable/deferred returns and map copies do not preserve capability
ownership; incomplete imports escape through dynamic member reflection;
regular package objects shadow protected descendants; reflected trace setters
do not enter the lifecycle grammar; callback/filter identity is lexical and the
filename filter does not prove the canonical `inspect` binding; and trace state
can be disabled inside the protected interval.

The P1 roots are: discarded deferred bodies can be reported as executed;
constant-truth Boolean short-circuiting is not modeled; the digest-order control
does not pin a pure exact comparison; the exact counter increment admits
non-integer values equal to `1`; and callback closure conflates unrelated
same-spelled names instead of resolved binding identity.

The successor must correct these shared semantic centers rather than enumerate
the reported spellings. In particular, scope-map writes require one binding
effect model; callable returns require one observation/activation model; module
objects require exact-plus-descendant topology; and trace safety requires one
identity-based closed lifecycle. `work/review/REV-0106/**` is released solely
for the next exact-source review after those root corrections are frozen.

The changed-DDL HUMAN-GATE remains closed. Pytest, all four held suites,
project/SQLite imports, connections, database activity, changed-DDL execution,
and DDL installation remain `NOT_RUN` and unauthorized.
