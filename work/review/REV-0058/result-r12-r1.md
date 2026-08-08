# Independent R12-R1 presence-aware RED-contract preflight result

Review posture: fresh, documentation/static-only independent review of the
exact R12-R1 candidate. Repository artifacts, not prior conversation reasoning
or author conclusions, were used as authority. The uncommitted
`app/execution_core/acquisition.py` and
`tests/execution_core/test_acquisition.py` changes were inspected only as
explicitly unaccepted constructibility context; this result does not accept or
claim an implementation.

## Exact target and integrity gate

- Branch: `codex/arch-reset-2026-07-r1`
- Review base and `HEAD`: `6cd32a5f56d8ad3a303ef69b137dc43d4ffad9ce`
- Manifest:
  `work/review/REV-0058/WO-0151-RED-CANDIDATE-R12-R1-MANIFEST.md`
- Exact manifest SHA-256:
  `fd187177bc5815ef901b29e760eb7aa0c75dc4338e8866f541ccdc82ea216543`
- R12-R1 contract SHA-256:
  `9cab228aa392292bc44a8758c60317201cf78388d6ec61848edcb3d1f0497a25`
- R12-R1 disposition SHA-256:
  `97eb57755e9cfdd597004b1e083c6fd8fad44abe0d25f3cd83a4ecf3c086ea03`
- Review request SHA-256:
  `048a3bde94f619fe0d7a4acdeda225811798c1f05340bc211ce5f1ce6addbbd0`

Static integrity evidence:

- All 24 SHA-256 rows in the manifest were independently recomputed and
  matched.
- The checked-out branch and `HEAD` matched the manifest base, and that object
  resolved as a commit.
- `result-r12-r1.md` was absent before this reviewer wrote it.
- No path was staged.
- The tracked working delta was exactly the two manifest-listed unaccepted
  former-R12 paths plus the seven listed current-record reconciliations. The
  frozen E3 detector and the three R12-R1 candidate documents were the only
  other untracked paths before the manifest itself and this result were
  considered.
- The frozen E3 evidence and detector matched their listed hashes
  `d018c2bddeec79fd624d1fbcb80dde91e49b5535f5db737120d88deb750c6ee7`
  and
  `1a7e685f954dc8de4424ad926285d993e0e9958eae2ce1a2f60af5b03689eb22`.
  They were inspected statically and neither edited nor executed.

## Findings

No P0, P1, or P2 finding was identified. There is therefore no finding-level
impact or corrective resolution required before the records-only activation
gate. The affirmative evidence and attempted disproofs follow.

## Required disproof results

### The absent-versus-present-`None` ambiguity is real and exact

Evidence: `static-reasoning`.

`_PersistentKeyMap.get()` follows the requested key through the radix and
returns `None` for a missing child or a terminal node with `has_value ==
False`; it also returns the stored value directly, so a terminal node with
`has_value == True` and `value is None` produces the same result
(`app/execution_core/fills.py:433-444`). `_set()` currently uses only
`existing is None` to distinguish insert from replacement
(`app/execution_core/fills.py:446-458`). A present-`None` key can therefore be
mistaken for absence: duplicate insertion is admitted, replacement is called
missing, and the former R12 candidate-stream reader can treat malformed
presence as a fresh stream.

This is not merely a prose-only state. A radix terminal separately retains
`has_value`, `value`, and `value_commitment`; its node commitment binds the
presence bit and supplied value commitment, not Python object identity
(`app/execution_core/fills.py:351-372`). Replacing an existing route value with
`None` while retaining its stored route commitment can therefore preserve the
map commitment and registry seal while leaving a physically present malformed
value. The R12 premise that `get() is None` proves absence is consequently
nonconstructible without a presence-aware primitive.

### `_lookup()` is the minimal direct bounded root correction

Evidence: `static-reasoning`.

The proposed `_PersistentKeyMap._lookup(key) -> (present, value)` can reuse the
existing radix walk exactly once and return `(False, None)` only when a child
or terminal value is absent, while preserving `(True, None)` for malformed
presence. `get()` can delegate and preserve its existing `None`-on-absence
behavior; `_set()` can use the presence bit to reject duplicate insertion and
permit exact replacement. Existing invalid-key behavior remains pinned by the
map-owner controls.

The work is bounded independently of registry history. The stream route key is
one domain-separated SHA-256 commitment
(`app/execution_core/acquisition.py:417-423`), so lookup follows one fixed
32-byte radix path. Each path step uses the existing bounded child lookup
(`app/execution_core/fills.py:375-390,433-444`). The proposal adds no map
iterator, length/keys/values/items surface, collection return, predecessor
walk, last-N cache, or audit/owner/effect/closure scan. `_PersistentKeyMap` and
`_lookup` both remain private, and the existing public `GenerationRegistry`
reader set stays exactly `empty()` and `record()`.

Putting the primitive in `fills.py`, the existing owner of the shared map, is
the smallest complete correction. Reconstructing radix presence inside
`acquisition.py` would duplicate container authority or reach through private
node representation. A route-specific sentinel would leave `_set()`'s
presence defect in place.

### Candidate refusal occurs only after authentic current state

Evidence: `static-reasoning`.

Controller-state authenticity directly resolves the retained current
mandate's stream route and requires it to match the LIVE generation record,
application generation, position scope, ordinal, and dual-mandate binding
(`app/execution_core/acquisition.py:2115-2171`). Successor admission includes
that complete authenticity check in `sources_are_exact`
(`app/execution_core/acquisition.py:4092-4167`) before the candidate route
lookup (`:4168-4188`), which itself precedes successor authority registration
(`:4205-4223`). The R12-R1 outcomes are therefore total:

- absent candidate key: `_lookup()` returns `(False, None)` and the existing
  fresh-successor path may continue;
- present authentic candidate route: the helper returns the route and the
  exact predecessor components are returned as `REFUSED`;
- present `None`, wrong-type, noncanonical, key-mismatched, binding-mismatched,
  or record-mismatched candidate route: presence is not collapsed to absence;
  the helper raises `ValueError`, and successor admission catches only that
  candidate-route error and returns the same ordinary `REFUSED` result;
- missing or malformed current route: controller-state authenticity is false,
  so the candidate-specific branch is not reached. The refusal constructor
  re-authenticates the predecessor and rejects invalid input rather than
  manufacturing a transition from unauthentic state
  (`app/execution_core/acquisition.py:2321-2360`).

The ordinary refusal is nonmutating and creates no receipt, effect, or claim.
It retains the exact state plus the supplied current refresh authority, venue,
execution, and protection references. No registration call occurs before this
decision.

### Registry ownership, sealing, and replacement stay direct

Evidence: `static-reasoning`.

The retained R12 design adds one private `_market_stream_routes` map beside
the existing direct generation-record map. Registry authenticity requires
both exact map types, equal cardinality, and the combined registry seal
(`app/execution_core/acquisition.py:330-408`). The empty case retains the E1
empty-domain identity; every nonempty registry uses the v3 domain binding both
map commitments (`:426-441`). Genesis creates exactly one record and route
(`:517-556`). A valid successor directly retires/replaces one record, inserts
one successor record, and inserts one fresh stream route (`:593-656`).

Record/economics replacement preserves the identical stream-route map object
and reseals the registry with its commitment (`:559-590`). A late fact can
therefore replace a retired generation record without releasing that
generation's stream. A later candidate carrying that stream resolves the
retained route directly and refuses; no record-map enumeration, predecessor
walk, or history reconstruction is needed.

The route type blocks ordinary construction and subclassing and is allocated
only in the initial-record and successor-record registry owners
(`app/execution_core/acquisition.py:312-326,517-556,593-656`). It is not in
`acquisition.__all__`; no public route reader is added. `authority.py` receives
no stream index, so the replaceable authority-currentness map cannot become a
duplicate owner of retired provenance.

### Value-equivalent immutable copies remain semantically valid

Evidence: `static-reasoning`.

The route seal binds the canonical stream and the authentic generation
binding commitment (`app/execution_core/acquisition.py:444-484`). Direct route
validation compares the derived key, stream value, and record binding by value
(`:487-514`), and controller authenticity likewise uses value equality
(`:2152-2168`). It does not use Python reference identity. The generation
binding's commitment and seal cover generation, application, scope, ordinal,
dual-mandate commitment, predecessor/genesis head, and emergency compatibility
(`:1614-1729`).

Accordingly, a frozen route/binding copy with the same canonical fields,
commitments, and seals remains valid. Altering its stream, derived key, binding
relation, scope, ordinal, or commitment fails the owning route, record, or
controller check. The required copy control is diagnostic against an
incorrect `is`-based implementation without granting caller-shaped authority.

### The four-path implementation scope is necessary and sufficient

Evidence: `static-reasoning`.

- `app/execution_core/fills.py` owns the ambiguous shared container and is the
  only correct place for `_lookup()` and `_set()` presence semantics.
- `tests/execution_core/test_fill_position.py` already owns direct persistent-
  map controls and can distinguish absent, present `None`, duplicate insert,
  and replacement behavior without an application fixture.
- `app/execution_core/acquisition.py` owns the one private stream-route
  consumer and the current-versus-candidate disposition split.
- `tests/execution_core/test_acquisition.py` already owns serial A/B/C,
  registry replacement, authenticity forgery, immutable-copy, public-surface,
  and scoped mutation seams.

No change is required in `authority.py`, public exports, import-boundary
contracts, protection/venue/runtime code, or the E3 detector. Expanding to any
of those paths would duplicate authority or exceed the bounded root
correction; omitting either map-owner path would leave the shared presence bug
or its owner-level control unaddressed.

### The required RED and mutation controls are failure-capable

Evidence: `static-reasoning`; future execution is `unverified`.

The map control distinguishes all four decisive states: absent lookup,
present-`None` lookup, duplicate insert against present `None`, and replacement
of present `None`. It fails if `_lookup()` reuses the old value-only result or
if `_set()` continues to call `get()` for presence.

The acquisition controls separately isolate:

1. authentic A -> B -> fresh binding with A's retained stream;
2. the A -> B -> C distinct-stream positive path;
3. route retention across generation-record/economics replacement;
4. present-`None`/forged candidate refusal after authentic current state;
5. present-`None`/forged current-route invalid-input rejection; and
6. value-equivalent-copy acceptance with altered-relation rejection.

The lookup-bypass mutation makes the otherwise-valid nonadjacent probe reach
the immediate-predecessor-only path and apply, so the reuse control turns RED.
Dropping or polluting the route map during record replacement either makes a
retired stream falsely absent or destroys route authenticity, so the
retention/authenticity control turns RED. The mutations own different rules
and must restore their exact targets. The frozen E3 detector remains external
public confirmation only and cannot substitute for these E2-owned controls.

### Frozen E3 trace and paired closeout verdict

Evidence: `static-reasoning`; no rerun was performed.

The frozen public E3 trace remains valid negative evidence. It constructs A
and B with distinct complete mandates/streams, then an otherwise-valid fresh
probe with distinct acquisition/protection/binding identities and A's stream;
immediately before B -> probe it proves current refresh, authentic bootstrap
and successor admission, equal scope/session/emergency compatibility, and
`probe.stream == A.stream != B.stream`
(`tests/execution_core/test_acquisition_stateful.py:556-727`). The frozen
evidence records `APPLIED` where the trace requires `REFUSED`. R12-R1 preserves
R12's direct controller-lifetime correction and only makes the malformed-
present candidate case constructible; it does not weaken or replace that
public trace.

WO-0152 remains `ACTIVE` but explicitly paused at FR-08. Its detector and
evidence remain frozen and may not be changed or rerun until R12-R1 semantic
and activation gates plus focused implementation acceptance complete
(`work/active/WO-0152-reset-kernel-e3-generation-conformance.md:124-175,414-424`).
The unchanged paired E2/E3 exact-head Python 3.11/3.12 93% coverage condition
remains mandatory before either effective closure or M1 completion
(`work/completed/keep/WO-0151-reset-kernel-e2-controller-rollover-recovery.md:409-425,546-564`).
The ratification index, PKL records, and ledger retain the same pause,
detector, operational exclusions, and paired threshold.

## Evidence limits

This review used only read-only file inspection, SHA-256 computation, Git
branch/object/status inspection, and static source/contract reasoning. It did
not run tests, application code, a database, SQL/DDL, broker/network/credential
activity, CI, coverage, or runtime work. It did not edit the candidate,
source/tests, work orders, ADRs, PKL, ledger, ratification, E3 evidence, or E3
detector.

R12-R1 source/test implementation, the named RED/mutation executions,
records-only activation delta, documentation activation/exact-SHA
reconciliation, focused implementation acceptance, unchanged frozen E3
confirmation, and paired exact-head 93% CI remain subsequent unverified gates.

## Verdict

**ACCEPT**

Affirmative conclusion: R12-R1 is the smallest constructible root correction
for the retained R12 absent-versus-present-malformed stream-route ambiguity.
The proposed private presence-aware lookup is direct and bounded, restores the
shared map's insert/replace semantics, preserves sealed controller-lifetime
stream provenance across record replacement, introduces no public or duplicate
authority surface, and keeps the E3 pause and paired closeout gate unchanged.
This verdict authorizes neither implementation nor closeout.

- P0: **0**
- P1: **0**
- P2: **0**
- Unverified: future R12-R1 implementation/tests/mutations; records-only
  activation and exact-SHA publication; focused implementation review; frozen
  E3 confirmation; paired exact-head Python 3.11/3.12 93% CI.
