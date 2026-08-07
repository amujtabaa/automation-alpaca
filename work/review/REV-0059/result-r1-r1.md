# WO-0152 E3 R1 remediation 01 independent preflight result

Review base: `a2b84abc1914517cf591f27fb88f0b20b2a47ef7`
Branch: `codex/arch-reset-2026-07-r1`
Frozen R1 remediation 01 manifest SHA-256:
`4b3ae783f380260042b289060d95acc4d1c3c8611dd9553a29385f42881ec3c0`
Review mode: independent static and file-level inspection only

## Exact-candidate verification

- Evidence: `reproduced-live`. `HEAD` and branch matched the manifest. All 41
  manifest-listed inputs matched their SHA-256 values. The core remediation
  hashes were disposition
  `13464dcd872b25223146e8f3e810a822a087c2eda6ed28184c8a1fb3702c2c5a`,
  contract
  `c6caaa8bdfacc0ef9e4bbb414961cd1045ec3e693bb06ed72cff2947c431382c`,
  request
  `7e6020165ea72bee414b3d017ba0358cd2bd056d02fa6b3f6215d2f58e56cbfd`,
  and WO-0152
  `193d9976cf4e6437dcbb72e095304b8baf5cc3328e97af3868f8d0babf0ad980`.
- The retained R0 and R1 reviewer results matched
  `ae398751c5c64478748c4fd15a9a9a4124858c449a604d9052b2034f1e592b57`
  and
  `880a4f2f8874d9e14a77523301a400ef84d02893d421e48822dfb648aa249408`
  respectively. Neither retained result was edited.
- Before this reviewer-owned result was created, the tracked delta was exactly
  the eight manifest-listed documentation/governance paths: the ratification
  index, three PKL pages, WO-0151 retained closeout, ledger, WO-0152 draft, and
  REV-0058 implementation closeout. The untracked delta was exactly the three
  named REV-0058 records plus the thirteen retained/current REV-0059 packet
  records. The index was empty, `git diff --check` exited 0, and no production
  or existing test source was in either delta.
- `tests/execution_core/test_acquisition_stateful.py` and this result path were
  both absent at review start. No third setup fixture, new private production
  name, public API, production edit, existing-test edit, or operational
  capability is present in the frozen remediation delta.
- The records consistently retain run #741 as functional/static positive
  evidence and coverage-only negative evidence at 91.34% versus the unchanged
  93% gate. They keep WO-0151 effectively `REVIEW`, WO-0152 `DRAFT`, and both
  effective closeout and M1 completion dependent on a later paired exact-head
  Python 3.11/3.12 pass at 93%.

## Re-derived terminal-fixture repairs

- Evidence: `static-reasoning`. The copied-state exception is now literal and
  exact: one `copy.copy(authority)` and one
  `object.__setattr__(copied_authority, "venue", applied.book)`, after the
  private transition is APPLIED/CLOSED, with negative controls for a second
  site, dynamic target/name, original-authority write, or other field
  (`WO-0152-RED-CONTRACT-R1-R1.md:36-52,158-174`). This closes retained R1
  P1-1 without widening the original authority object.
- The reconciliation-clear substitute is source-supported. The specialized
  acquisition claim calls `_venue_reason(..., require_clear=True)` before
  claiming (`app/execution_core/authority.py:8350-8362`); its target exemption
  is available only while the requested effect has no reconciliation
  (`app/execution_core/venue.py:7636-7680`). Effect-reconciliation append paths
  return `RECONCILIATION_REQUIRED`, not APPLIED
  (`app/execution_core/recovery.py:733-771,1040-1081,1237-1312`). Therefore a
  fixture-owned, no-interleaving, exact clean-claim suffix whose every result
  is APPLIED cannot silently acquire target-effect reconciliation. The named
  reconciliation-injection and splice/order controls make that proof
  failure-capable.
- The revised terminal ordering is also source-supported. Canonical-fact
  currentness explicitly permits intervening venue transport/status
  observations (`app/execution_core/authority.py:4766-4819`), and the canonical
  fact registration atomically installs `transition.book` into authority
  (`app/execution_core/authority.py:6165-6279`). Thus terminal observation
  before the final flattening canonical fact and immediate
  `reduce_acquisition_controller` can realign controller, authority, venue,
  and execution before the private closure. This closes retained R1 P1-2
  without a private reconciliation reader or history scan.
- Generic target BUY refusal after bootstrap/currentness reservation is
  correctly pinned in production: an acquisition currentness entry refuses it,
  and the earlier bootstrap-bound target record independently refuses it before
  registration (`app/execution_core/authority.py:7690-7753`).

## Finding

### [P1] The canonical pre-bootstrap sibling history cannot be carried into the opaque authority through the permitted public surface

- Location: `work/review/REV-0059/WO-0152-RED-CONTRACT-R1-R1.md:139-151`;
  `work/queue/WO-0152-reset-kernel-e3-generation-conformance.md:79-82`;
  `app/execution_core/authority.py:633-674`;
  `app/execution_core/authority.py:4029-4075`;
  `app/execution_core/authority.py:9701-9769`;
  `app/execution_core/venue.py:13555-13579`;
  `app/execution_core/venue.py:13796-13863`.
- Requirement: The unrelated-symbol account history must be constructed before
  target bootstrap through public `CreateBrokerEffect(BUY)`, public claim,
  public venue discovery/status, and public canonical broker evidence, then the
  target must bootstrap from that bounded current sibling execution source.
  No private state replacement, extra fixture, existing-test helper, new public
  API, or post-setup production-object mutation is allowed.
- Evidence: `static-reasoning`. Public create and claim do return a replacement
  `ExecutionAuthorityState`, but later discovery, status, and canonical broker
  evidence go through `apply_venue_recovery_input`, which returns only a
  `VenueRecoveryTransition`; it does not return or update an authority state.
  `ExecutionAuthorityState` is opaque and its only copy-with-changes helper is
  private. The public authority dispatcher admits only its fixed authority
  command tuple and has no venue observation/recovery input. Target bootstrap
  then starts from `state.venue`, while the same-account-source gate requires
  that exact embedded book to match the sibling `ExecutionSnapshot` and its
  registry. After any public sibling discovery/status/canonical evidence, the
  evolved book cannot be installed into that state through the frozen public
  surface. The existing owning-slice witnesses solve this exact setup with the
  prohibited private `_forge_venue_predecessor`
  (`tests/execution_core/test_acquisition.py:1548-1579` and
  `tests/execution_core/test_authority.py:1795-1833`). I attempted to disprove
  the gap through every public authority/acquisition entry point: the only
  canonical-fact bridge is `reduce_acquisition_controller`, which requires an
  already initialized matching acquisition controller and therefore cannot
  install pre-bootstrap, non-acquisition sibling history.
- Impact: The intended nonempty sibling execution/venue-history premise for
  E3-01 cannot be constructed under the exact allowlist. Implementation must
  either use an unauthorized authority venue setter/private helper, omit the
  discovery/status/canonical history while still claiming the scenario, or add
  a new production/test seam. The first and third violate the freeze; the
  second weakens the required cross-symbol history control.
- Smallest complete resolution: Freeze the exact required sibling-history end
  state and choose one lawful boundary. If only public create/claim history is
  required, say so explicitly and remove the discovery/status/canonical-
  evidence and nonempty execution-history claim. If canonical sibling history
  is required, stop and obtain explicit human approval for one exact existing-
  fixture-owned copied-authority venue installation with literal-field,
  ordering, isolation, and negative controls. Do not add a third fixture,
  private call, or public production API under the current authorization.

## Evidence limits and activation disposition

No tests, fixtures, database/SQL/DDL, network, broker, credential, runtime, CI,
or coverage command was run. GitHub Actions run #741 was not queried; only its
frozen, hash-matched records were inspected. No production source, test source,
work order, PKL, ledger, request, manifest, candidate contract, disposition, or
retained result was modified.

Activation disposition: **STOP — WO-0152 remains DRAFT and no E3 test creation
or execution is permitted.**

Verdict: ACCEPT-WITH-CHANGES
P0: 0
P1: 1
P2: 0
Unverified: external GitHub Actions provenance for run #741; dynamic behavior
of the future absent E3 module, because this gate prohibited its creation and
all execution.
