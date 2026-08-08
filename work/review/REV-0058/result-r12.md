# Independent R12 RED-contract preflight result

Review posture: fresh, static-only, independent review of the exact immutable
R12 candidate. Any earlier partial R12 review is superseded. Repository
artifacts, not conversation history or author working notes, were used as
authority.

## Exact target and integrity gate

- Branch: `codex/arch-reset-2026-07-r1`
- Review base and `HEAD`: `4e7e5807833acc604cf75231e2719078965e8ba6`
- Manifest:
  `work/review/REV-0058/WO-0151-RED-CANDIDATE-R12-MANIFEST.md`
- Exact manifest SHA-256:
  `a36ff8dcae2bcfeb41bd312960439885cf0b46fcda8a4b0309d075cbb84ca8d0`
- R12 contract SHA-256:
  `36c7995deb480400a6573e005d47cc8c4878c8638eb8212a4227fa394a47c13e`
- Frozen E3 observation SHA-256:
  `d018c2bddeec79fd624d1fbcb80dde91e49b5535f5db737120d88deb750c6ee7`
- Frozen detector snapshot SHA-256:
  `1a7e685f954dc8de4424ad926285d993e0e9958eae2ce1a2f60af5b03689eb22`

Before substantive review, I independently recomputed and matched every one
of the 24 SHA-256 rows in the manifest. The manifest itself matched the exact
hash above; the branch and `HEAD` matched the stated base; `result-r12.md` was
absent; no tracked `app/` or `tests/` path differed from the base; and the sole
untracked source was the manifest-listed frozen E3 detector. It was read only
after the governing packet and was neither changed nor executed.

## Findings

No P0, P1, or P2 finding was identified.

## Required disproof results

### Private direct route is constructible, bounded, and minimal

The current `GenerationRegistry` already owns one opaque persistent direct
record map, an exact empty constructor, record lookup, nonempty sealing,
initial insertion, exact record replacement, and serial successor replacement/
insertion (`app/execution_core/acquisition.py:311-472`). R12 adds exactly one
parallel private persistent sub-index and one private sealed route value. Its
fixed-size domain-separated key, one direct lookup/insert operation, and
combined registry seal fit those existing owner-local transitions without a
new controller, writer, service, history fold, or public action seam.

The empty case can retain the existing empty-domain seal while a nonempty R12
registry binds both map commitments under a new versioned domain. Adding the
new private field to registry authenticity makes a pre-R12 nonempty value that
lacks it fail closed; no M1 hydration, upgrade, persistence migration, or
backfill is implied (`WO-0151-RED-CONTRACT-R12.md:23-57`).

The existing export, public-method, and function-signature pins are already
failure-capable (`tests/execution_core/test_acquisition.py:4151-4252` and
`:4790-4878`). R12 requires those exact public signatures and methods to stay
unchanged and adds neither a public route type nor a reader. The implementation
scope excludes `authority.py`, and the contract expressly forbids an
authority-side duplicate and a controller retired-generation collection
(`WO-0151-RED-CONTRACT-R12.md:13-21,88-91,130-144`).

### A -> B -> duplicate-A-stream rejects before registration

The frozen public trace constructs A and B with distinct complete mandates and
streams, then constructs a probe with fresh acquisition identity, protection
identity, and sealed dual-binding commitment, exact scope/session/terms/equal
compatibility, and A's stream rather than B's. Its public refresh, bootstrap,
admission, head, and ordinal inputs are current. The probe therefore removes
the alternate identity, binding, terminality, compatibility, and immediate-
predecessor refusal paths and isolates nonadjacent stream reuse.

Current source confirms the defect boundary: successor validation compares the
candidate stream only with the current B mandate at
`app/execution_core/acquisition.py:3950-3963`; authority successor registration
does not begin until `:3987`. R12 places the candidate direct lookup between
those exact-source gates and registration (`WO-0151-RED-CONTRACT-R12.md:63-74`).
An exact retained A route or a malformed entry under A's derived key therefore
returns before registration. The existing refusal constructor preserves the
predecessor state plus the supplied refresh authority, venue, execution, and
protection references and creates no receipt, effect, or claim
(`app/execution_core/acquisition.py:2126-2165`).

The ordinary A -> B -> C positive path remains constructible from the existing
successor-mandate fixture and serial control
(`tests/execution_core/test_acquisition.py:312-334,1392-1477`). Three fresh
routes require only one new insert per successful successor and preserve at
most one LIVE record.

### Absent and malformed candidate-route semantics are total

The contract gives the private helper an exact total result boundary:
`None` means only that the fixed derived key is absent; an entry present under
that key must authenticate and match its key, stream, and bound generation or
raise `ValueError` (`WO-0151-RED-CONTRACT-R12.md:46-57`). After current-state
authenticity succeeds, successor admission catches only that candidate-route
failure and returns the exact nonmutating refusal. It cannot reinterpret a
wrong-type, noncanonical, key-rebound, stream-mismatched, or binding-mismatched
entry as a fresh stream. An authentic route produces the same refusal; only an
actual absence continues to successor registration.

This split is testable through the one named owner-local lookup seam without a
broad map monkeypatch or source rewrite. Existing focused tests already use
scoped direct-helper replacement and restore semantics for comparable sealed
owner results (`tests/execution_core/test_acquisition.py:3991-4038`).

### Missing or malformed current route is invalid state, not refusal

R12 extends controller-state authenticity to resolve the current mandate's
stream and match the exact current binding, application generation, scope,
ordinal, and binding commitment (`WO-0151-RED-CONTRACT-R12.md:71-86`). The
current authenticity owner is `_controller_state_is_authentic`, which already
directly resolves the LIVE generation record and is the prerequisite for every
published state and refused-successor result
(`app/execution_core/acquisition.py:1931-1976,2126-2140`).

Consequently, a missing or malformed current route makes the predecessor state
unauthentic. `begin_acquisition_generation` cannot manufacture an ordinary
`REFUSED` transition from it because the refusal constructor re-authenticates
the predecessor and raises/rejects the invalid input. No authority
registration or other state transition is reached.

### Immutable value-equivalent copies remain valid

The route is sealed from canonical values and the exact binding commitment;
controller authenticity compares the derived key/stream/binding relation, not
Python reference identity (`WO-0151-RED-CONTRACT-R12.md:80-86`). The existing
binding and record views are frozen value objects with field-derived
commitments and seals (`app/execution_core/acquisition.py:1472-1615`). A copied
route and copied binding with the same canonical fields, commitments, and seal
therefore remain semantically equivalent. The required control explicitly
guards this behavior, so an implementation using `is` where value/commitment
equivalence is required turns RED
(`WO-0151-RED-CONTRACT-R12.md:110-117`).

### Record replacement cannot erase prior stream ownership

All current record replacement is centralized in
`_registry_with_replaced_record`, which directly replaces one record and
rebuilds the registry without enumeration
(`app/execution_core/acquisition.py:409-431`). The canonical fact path creates
one replacement record and invokes that helper at `:4450-4472`. R12 requires
the stream-route map to be passed through unchanged on that path and on every
semantic rebase, preemption, exit, or normal state rebuild; only genesis and a
successful successor may add a route, and no path may delete, reassign, or
replace one (`WO-0151-RED-CONTRACT-R12.md:61-86`).

The required late-fact/replacement test can use the existing canonical-fact
fixtures and direct record assertions, then attempt a fresh candidate carrying
the replaced generation's stream. The expected refusal depends on retained
direct provenance, not on the record object, a predecessor walk, or a scan.
The second named mutation can pollute/drop only that map pass-through and must
make the retention/authenticity control turn RED before restoration
(`WO-0151-RED-CONTRACT-R12.md:106-124`).

### No scan, duplicate authority, or controller collection is introduced

The proposed semantic center is the existing separate `GenerationRegistry`,
not `SymbolAcquisitionController`. The controller remains constant-shape; the
registry retains the unavoidable one direct provenance row per generation,
and live decisions use one fixed-key lookup. R12 explicitly prohibits map
enumeration, predecessor walking, fixed-last-N caching, audit/owner/effect/
closure scans, controller history, and authority duplication. Current
acquisition registry access is direct `get`/`insert_new`/`replace_existing`,
and the reviewed source contains no registry iteration or materialization
(`app/execution_core/acquisition.py:311-472`).

### RED and mutation controls are constructible and failure-capable

The existing E2 test seams can mint distinct complete mandates, initialize A,
advance A -> B -> C, route current and retired canonical facts, inspect exact
record replacement, forge retained sealed fields, copy immutable values, pin
public signatures/exports, and use scoped helper mutations. R12 assigns those
seams six focused controls: nonadjacent refusal, fresh C success, replacement
retention, current-route authenticity including value-copy equivalence,
malformed candidate refusal, and two independent lookup/retention mutations
(`WO-0151-RED-CONTRACT-R12.md:93-127`).

The lookup-bypass mutation is diagnostic because the otherwise-valid A-stream
probe then reaches the current immediate-predecessor-only behavior and applies.
The replacement pollution/drop mutation is diagnostic because reuse of the
replaced generation's stream either becomes falsely absent or the state loses
authenticity. Both mutations are local, reversible, and tied to different
owning rules.

### E3 remains paused and the paired 93% gate remains unchanged

WO-0152's current `implementation_authority` is explicitly `PAUSED`; its
FR-08 section freezes the public trace and prohibits further test expansion or
production change until accepted R12 implementation lands
(`work/active/WO-0152-reset-kernel-e3-generation-conformance.md:15,124-146,367-379`).
The retained WO-0151 record keeps R12 implementation authority ungranted and
retains the paired E2/E3 exact-head Python 3.11/3.12 93% condition
(`work/completed/keep/WO-0151-reset-kernel-e2-controller-rollover-recovery.md:29-32,474-485`).
The ratification index, PKL posture, and append-only ledger agree; no coverage
exception, threshold reduction, E3 resumption, runtime/persistence, broker, or
M2 authority is introduced.

## Frozen public E3 trace verdict

The frozen E3 trace remains valid negative evidence of the existing E2 defect:
under the reviewed base it expected `REFUSED` and recorded `APPLIED` for an
otherwise-valid A -> B -> fresh-binding-with-A-stream successor. R12 directly
addresses that owning provenance gap. After implementation, the same public
trace must return `REFUSED`, but it may be rerun only at the contract's later
authorized confirmation gate and cannot replace the E2-owned RED and mutation
controls. This preflight neither claims the implementation exists nor accepts
future GREEN evidence.

## Evidence limits

This review used only read-only file, SHA-256, Git relationship/diff, and static
source/contract inspection. I did not execute tests, application code, a
database or SQL/DDL path, broker/network/credential activity, CI, coverage, or
runtime work. R12 source/test implementation, future mutation runs, frozen E3
reconfirmation, and paired exact-head 93% CI remain subsequent unverified
gates.

## Verdict

**ACCEPT**

Affirmative conclusion: the exact R12 contract is the smallest constructible
root correction for controller-lifetime nonadjacent market-stream reuse. Its
direct private route is bounded per lookup, preserves provenance across record
replacement, adds no public or duplicate authority surface, and keeps every
existing safety, pause, scope, and closeout gate intact.

- P0: **0**
- P1: **0**
- P2: **0**
- Unverified: future R12 implementation/tests/mutations, permitted post-fix E3
  confirmation, and paired exact-head 93% CI only.
