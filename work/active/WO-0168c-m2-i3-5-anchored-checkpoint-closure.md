---
type: Work Order
title: M2-I3.5 anchored non-serving checkpoint closure
status: ACTIVE
work_order_id: WO-0168c
wave: M2-I3.5-R13-C
model_tier: strong
risk: critical
disposition: []
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
  - tests/execution_core/test_venue_checkpoint_hardening.py
  - work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md
  - work/queue/M2-EXECUTION-2026-08-21/36-R16-MANUAL-RULE-RATIFICATION.md
forbidden_paths: []
---

# Work Order: WO-0168c — anchored checkpoint closure

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
