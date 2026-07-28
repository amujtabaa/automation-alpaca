---
type: Review Result Addendum
rev_id: REV-0045
addendum: 02
title: "WO-0140 R6a-R truth-model remediation: round-2 independent reassessment"
reviewer_seat: Codex (independent cross-model review seat)
base_sha: b48235e
head_sha: 68c71fe
verdict: BLOCK
delta_p0_count: 1
delta_p1_count: 0
cumulative_p0_count: 5
cumulative_p1_count: 3
reviewed: 2026-07-27
---

# REV-0045 addendum 02 — **BLOCK**

Independent round-2 review of `b48235e..68c71fe`. The R6a gate does **not** clear.

The remediation fixes P0-1, P1-2, and P1-3, and it fixes the specific malformed-owner,
upper-bound, open-close, exact-next, and shared-release-validator checks previously recorded under
P1-1/P0-3/P0-4. It does not fix P0-2, P0-3, or P0-4 at root cause. One new P0 was found: the
ratified release-key mint and parser do not round-trip every valid producer ID, creating a
live/replay/restart divergence on both stores.

The full battery is green, including the coverage ratchet. That does not offset direct evidence that
the same append-only history can produce different class-A results across live, replay, restart,
memory, and SQLite.

## New blocking finding

### P0-5 — the release-key parser is not an inverse of the ratified mint

- **Cause:** `signal_dedupe_key()` length-prefixes arbitrary string parts and joins them with `|`,
  but `sequence_from_release_dedupe_key()` first splits the encoded body on every `|`. A producer ID
  containing that permitted character is therefore minted successfully but cannot be parsed.
  Configuration accepts every non-blank, valid UTF-8 producer ID; it does not reserve `|`.
- **Impact:** Both stores can open and release the producer successfully in live state, then
  `project_read_models()` and a fresh store restart mark that same producer in
  `poisoned_producers()`. This is a store-minted class-A live/replay/restart divergence and meets the
  packet's explicit BLOCK condition.
- **Affected local files:** `app/store/core.py:5643-5652`,
  `app/events/projectors.py:1218-1271`, `app/config.py:459-476`, and missing round-trip coverage at
  `tests/test_signal_rails_remediation.py:1093-1128`.
- **Recommended fix:** Implement one true length-prefixed decoder that consumes each declared number
  of characters before looking for the next separator. Pin
  `parse(mint(producer_id, sequence)) == sequence` over arbitrary valid UTF-8 producer IDs,
  including `|`, `:`, and Unicode, then repeat live/replay/restart parity on both stores.
- **Pass/fail evidence:** Direct round-trip checks passed for `:` and Unicode and failed for `|`.
  In a full release composition, memory and SQLite each released live at sequence 1 with no marker;
  replay and fresh restart marked the producer on both stores. No existing test failed.

This is the only newly counted finding. The sibling failures below demonstrate that prior findings
remain open; they are not counted again.

## Root-cause disposition of the seven prior findings

| Prior finding | Verdict | Round-2 result |
|---|---|---|
| P0-1 — Windows cap-literal pin | **FIXED** | `.as_posix()` makes the path comparison platform-stable. The named pin passes on this Windows host. |
| P0-2 — inert state-seed proof | **OPEN** | The simple flat-seed defect now turns both replacement pins red, but an incorrect state-conditional seed limited to epoch 1 leaves those pins and the complete five-file rails corpus green. |
| P0-3 — release-carrier domain | **OPEN** | The parser now binds the producer and checks `2**63-1`, but an unbounded sibling payload carrier still reaches SQLite's durable bind; the two release floors also accept different type domains. |
| P0-4 — poisoned-heal validation | **OPEN** | The shared validator rejects the directly tested malformed/non-next heals, but tolerant high-water bookkeeping trusts a forbidden release field before that validation and enables a later live/replay divergence. |
| P1-1 — release identity and exact-next | **FIXED AS SPECIFICALLY REPORTED; BROADER REGRESSION IS P0-5** | Owner binding, normal open-close identity, and zero-width exact-next checks are live. The mint/parser grammar is nevertheless not closed over valid producer IDs. |
| P1-2 — memory anchor global scan | **FIXED** | Memory uses `_execution_event_dedupe`; the no-scan pin is live and SQLite retains its keyed lookup. |
| P1-3 — unrelated recorder formatting | **FIXED** | `git diff b48235e..HEAD -- app/recorder` is empty. |

Because three prior P0 classes remain open, named item 1 fails even without P0-5.

## Prior blocking findings that remain open

### P0-2 remains open — the replacement seed pins cover only the first epoch

- **Cause:** Both replacement pins release a healthy epoch whose
  `quarantine_epoch_sequence == 1`. They distinguish removal of the subtraction but do not
  distinguish a subtraction incorrectly conditioned on the sequence being exactly 1.
- **Impact:** The bounded verifier is still mutation-incomplete. At epoch 2 and later, the incorrect
  seed raises on a healthy segment and silently enters the poison/classification fallback. The
  final returned rail is correct, so ordinary result assertions hide the broken verification path.
- **Affected local files:** `app/store/memory.py:389-489`,
  `app/store/sqlite.py:1581-1686`, and
  `tests/test_signal_rails_remediation.py:344-419,973-1021`.
- **Recommended fix:** Parameterize the first-try/no-fallback property across at least two
  consecutive epochs in both stores and retain a mutation that breaks only epoch 2+.
- **Pass/fail evidence:** Removing the subtraction made both named pins fail. A second, incorrect
  state-conditional version passed both named pins and all **154** tests in the five authorized
  rails files. A focused epoch-2 composition recorded the bounded-check error in both stores while
  the public release result remained sequence 2. File-copy restoration left an empty diff.

### P0-3 remains open — the durable carrier domain is not enforced at every ingress

- **Cause:** `project_producer_rails_tolerant()` records any positive Python `int` found in
  `epoch_sequence` for both `PRODUCER_QUARANTINED` and `PRODUCER_RELEASED` before strict payload
  validation and without applying `_SQLITE_MAX_SIGNED_INT`. The resulting
  `PoisonedProducerMarker.last_known_epoch_sequence` is copied into memory and is passed through
  `_upsert_producer_log_rail()` to SQLite with no sink-side range check. The release-floor
  implementations separately use different type rules: memory reads event values one by one,
  whereas SQLite applies `MAX(json_extract(...))` and then accepts only the aggregate if it is a
  Python `int`. SQLite also passes a nullable `dedupe_key` directly to the parser while memory
  normalizes it to an empty string.
- **Impact:** Memory accepts a carrier SQLite cannot bind during `initialize()`. Other malformed
  numeric representations can be retained, ignored, or selected differently by the two floors,
  causing one store to refuse a release while the other advances it. A NULL release key produces a
  controlled ignore in memory but an uncaught `AttributeError` in SQLite.
- **Affected local files:** `app/events/projectors.py:1526-1538,1606-1612`,
  `app/store/memory.py:320-373`, and
  `app/store/sqlite.py:1688-1748,1790-1818`.
- **Recommended fix:** Put a shared signed-integer-domain validator at the memory carrier and SQLite
  durable sink. In tolerant replay, derive opener sequence only from a structurally valid,
  bounded `PRODUCER_QUARANTINED` payload and release sequence only from the producer-bound key.
  Replace SQLite's JSON aggregate floor with the same decoded-event helper used by memory and
  normalize nullable keys identically.
- **Pass/fail evidence:** A first-out-of-domain opener carrier remained representable in memory but
  made SQLite `initialize()` raise `OverflowError`. A separate floor composition made memory refuse
  at the builder while SQLite released at sequence 1. With a NULL release key, memory released at
  sequence 1 while SQLite raised `AttributeError`. No existing test failed.

#### Exhaustive carrier-write map

`_upsert_producer_log_rail()` at `app/store/sqlite.py:1725-1753` is the only non-literal SQLite
sink; it binds `rail.quarantine_epoch_sequence` directly at line 1747.

| SQLite assignment/call | Source | Signed-domain status |
|---|---|---|
| `:1808` startup valid projection | Strict opener/release appliers | **Bounded** |
| `:1810-1818` startup poisoned marker | Tolerant raw `last_known_epoch_sequence` | **UNBOUNDED — blocking ingress** |
| `:1799-1805` rebuild reset | Literal `0` | **Bounded** |
| `:8238` ingest opener update | Builder-validated `epoch_sequence + 1` | **Bounded before sink** |
| `:8240` unchanged ingest rail | Existing validated row/carrier | **Bounded by source** |
| `:8375-8384` rate opener | Builder-validated `epoch_sequence + 1` | **Bounded before sink** |
| `:8483` interior repair | Strict fold from zero | **Bounded** |
| `:8524-8529` final release row | Every branch passes `producer_released_event()` first | **Bounded before sink** |
| `:1756-1773` rate-bucket insert | Literal `0` on insert; sequence unchanged on conflict | **Bounded** |

The memory carrier assignments mirror those paths:

| Memory assignment | Source | Signed-domain status |
|---|---|---|
| `app/store/memory.py:340-343` valid rebuild | Strict projection | **Bounded** |
| `:344-349` poisoned-marker rebuild | Tolerant raw `last_known_epoch_sequence` | **UNBOUNDED — cross-store divergence** |
| `:375-387` incremental opener | Builder-validated caller | **Bounded before assignment** |
| `:5937-5940` unchanged rail | Existing plan-validated rail | **Bounded by source** |
| `:6087` rate opener | Builder-validated caller | **Bounded before assignment** |
| `:6191-6193` interior repair | Strict fold from zero | **Bounded** |
| `:6232` final release | `producer_released_event()`-validated value | **Bounded before assignment** |
| `:745,771` atomic restore | Previously sourced copy | **No new domain** |

### P0-4 remains open — invalid release data enters high-water state before validation

- **Cause:** Tolerant replay updates `last_known` from raw `epoch_sequence` before
  `_validated_release_event_shape()` judges the event. `PRODUCER_RELEASED` has a closed payload and
  does not ratify that field, yet a forbidden in-range value becomes the marker's high-water value.
  The live release floors correctly ignore that forbidden payload field, so live recovery and replay
  no longer use the same predecessor sequence.
- **Impact:** On both stores, the live recovery clears `poisoned_producers()` and advances to a low
  sequence derived from the valid key floor, while replay and restart retain the marker because that
  sequence is not next after the contaminated high-water value.
- **Affected local files:** `app/events/projectors.py:1526-1586`,
  `app/store/memory.py:352-373,6104-6233`, and
  `app/store/sqlite.py:1688-1722,8414-8529`.
- **Recommended fix:** Do not update high-water state from an event until its event-type-specific
  structural source has been validated. `PRODUCER_QUARANTINED` may contribute only its bounded
  payload carrier; `PRODUCER_RELEASED` may contribute only its validated, producer-bound key.
  Reuse that same helper in both floors and in the poisoned-heal next-sequence check.
- **Pass/fail evidence:** With one malformed release contributing only a forbidden in-range carrier,
  both stores rebuilt a marker at the higher value. The next live recovery cleared the marker at
  sequence 2; `project_read_models()` and fresh restart remained marked on both stores. The probe
  exited 0 and the repository stayed clean.

## Eight named round-2 items

| Item | Verdict | Independent result |
|---|---|---|
| 1. Seven prior findings fixed at root cause | **FAIL** | P0-1, P1-2, and P1-3 are fixed. P0-2, P0-3, and P0-4 remain open; P1-1's specific checks are fixed but the same parser surface has the new P0-5 regression. |
| 2. Replacement seed pins and a surviving mutant | **FAIL** | The flat seed turns both named pins red. An incorrect epoch-1-only conditional seed passes those pins and all 154 focused tests, then takes the wrong path at epoch 2 on both stores. |
| 3. Parser round-trip and dual-store composition | **FAIL** | `:` and Unicode round-trip. `|` does not; both stores release live and then disagree with replay/restart. P0-5. |
| 4. Malformed/non-next poisoned heal | **PASS, narrowly** | The named pin is live: disabling actor validation turns it red. Fresh blank/whitespace actor, extra field, over-limit counter, naive timestamp, non-next sequence, wrong owner, and NULL-key variants all remained marked in the tolerant fold. The broader pre-validation high-water composition still fails under P0-4/item 5. |
| 5. Exact-next open-close/zero-width and store-minted agreement | **FAIL** | Reverting either exact identity check turns its named pin red, but store-minted releases still diverge under P0-5 and the P0-4 high-water composition. |
| 6. Dual-store recovery scenarios | **PASS for the named matrix** | Legacy unfoldable heal, legacy wedge heal, open-log drift state-1 release, and interior repair-and-refuse each agreed among live state, `project_read_models()`, and restart on memory and SQLite. The additional P0-4/P0-5 compositions show the matrix is not exhaustive. |
| 7. Windows cap-literal pin | **PASS** | `test_ratified_cap_literals_are_single_sourced` passes by name on this Windows host and in the full battery. |
| 8. Closed test-edit audit | **PASS** | `git diff b48235e..HEAD -- tests/` stays within the closed list and disclosed helper adaptations; no pre-existing strict assertion was silently removed or loosened. |

## Design-refinement rulings

- **Log-floor + 1:** **FAITHFUL as a rule, incomplete as implemented.** Deriving a zero-width release
  from log truth prevents key re-minting and is consistent on valid state. The two floors must first
  share one bounded type domain; today they do not.
- **Parse the release's own dedupe key:** **FAITHFUL as a rule, incomplete as implemented.** The
  payload remains closed and no field was added, but the parser must be a total inverse of the
  ratified mint over valid producer IDs.
- **Option-A zero/interior repair-and-refuse:** **FAITHFUL.** The four named recovery scenarios
  reproduce on both stores and replay. This ruling does not authorize the divergent malformed
  high-water path.

## Test-edit audit

The cumulative test diff contains eight files, **+2,761 / -64**:

- three new legacy fixture corpora and the new remediation module;
- `test_signal_ingest_properties.py` **+41/-1**;
- `test_signal_rails_core.py` **+9/-1**;
- `test_signal_rails_projector.py` **+87/-44**; and
- `test_signal_rails_store.py` **+44/-18**.

There are zero removed `pytest.raises` assertions. The seven removed `assert` lines all belong to the
two explicitly authorized stale-cache re-pins and are replaced by stronger fail-closed, marker, and
write-free assertions. The only removed test definition is the authorized cap-test rename/re-home;
the same values (`1001`, `101`, `10_001`) retain write-time failure assertions. The projector helpers
now attach the ratified release key so existing strict tests reach their intended assertion. The
no-rescan and rollback helpers move to the replacement live seams without weakening their properties.
`git diff --check b48235e..HEAD -- tests/` passes.

## Reproduction record

- Reviewed local and fetched remote tip:
  `68c71fe8a1c2edc9db914d09bd5dc508b3a753d2`; the tree was clean before this
  reviewer-owned addendum.
- Full Windows battery, unique OS-temp `--basetemp`: **4,727 passed, 11 skipped, 1 xfailed,
  0 failed, 0 errors**, exit 0. Coverage printed
  `Required test coverage of 93.0% reached`; exact branch coverage is **93.0770%**.
- `ruff check .`: PASS. `mypy app/`: PASS, 77 files. `lint-imports`: PASS, 6 contracts kept.
  Repository-wide `ruff format --check .` has exactly the ten disclosed base-debt files and no
  additional file.
- Scaling gate: **13 passed**.
- Conformance oracle: the packet's direct `python tests\r2_conformance_oracle.py` command fails to
  resolve `app` here and would not invoke pytest even if importable. The test file's own documented
  invocation, `python -m pytest -q tests\r2_conformance_oracle.py`, passes **61/61** with a unique
  OS-temp base. This is a runbook correction, not credited as proof from the direct command.
- Mutation evidence: flat-seed, parser owner/bound, shared actor validation, open-close identity,
  and zero-width exact-next mutations all turned their named pins red. The epoch-1-only seed mutation
  stayed green as described under P0-2.
- Static scope: no DDL/index, `app/server.py`, R6b surface, new event payload field, or vocabulary
  value was added. The cumulative recorder diff is empty.

## Evidence provenance note

The round-2 instruction says a Fable-5 pre-review found and remediated the parser-framing,
payload-bound, floor-domain, and NULL-key defects and recorded that work in
`work/active/SIGNAL-R6aR-STATE.md`. The freshly fetched remote branch ends at `68c71fe`; the state
file ends at slice 9 and contains neither that pre-review entry nor those four fixes. This
addendum reviews the pushed evidence actually present and gives no credit to unavailable work. The
discrepancy is supporting evidence, not a separately counted finding.

## REV-0044 addendum — R-1/R-2 gate status

**The R6a gate remains blocked. REV-0044 remains ACCEPT-WITH-CHANGES.**

- **R-1 remains open:** the named legacy fixtures and nominal recovery matrix pass, but an
  unbounded tolerant carrier still makes the same history open in memory and fail SQLite startup;
  other malformed histories create live/replay/restart disagreement.
- **R-2 remains open:** the ordinary debit and memory anchor fixes pass, but the required
  state-conditional-seed evidence is still mutation-incomplete and an incorrect epoch-2 path remains
  masked by fallback classification.

Keep D-2a OFF and R6b blocked. Corrections must arrive as a disclosed implementer-owned change plus a
new reviewer-owned artifact; do not amend this result in place.
