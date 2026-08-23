# REV-0077 R15-B independent preflight review

Reviewed exact commit `14de501f576b52e128863c9c079f1ba43f13ace4`, tree
`a896e5ba1468183083af0a659788b0f60797eb18`, and R15 SHA-256
`826b733e7b9d7c82dce93e4b712f27ff92c8f6b89590d0ff450994ff42d1626d`.

### [P1] Whole-map authority cardinality rejects authentic unselected retained authorizations

- Location: `work/queue/M2-EXECUTION-2026-08-21/26-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R15.md:66`
- Requirement: R15 lines 26-31 restrict projection to proof-selected effect IDs and require unrelated terminal history to be untouched, while lines 66-67 require reached-key cardinality against every authority current map. The incorporated authority classification in `work/queue/M2-EXECUTION-2026-08-21/07-WO-0168H-FROZEN-OWNER-STATE-WIRE-CONTRACT.md:519-525` classifies `_effect_authority_by_id` as payload semantic state, not an omitted history map.
- Evidence: `static-reasoning` — repository selection admits only `OPEN`/`INVALIDATED` effects plus `CLOSED` effects with a late-admitted owner (`app/execution_core/persistence/repository.py:4072-4089`). Authority transitions only insert into `_effect_authority_by_id` (`app/execution_core/authority.py:7866-7891`, with the same append-only pattern at the other creation paths); closing a normally dispatched or never-dispatched effect does not remove its authorization. Therefore an authentic state can contain one selected live effect and one ordinary closed ownerless historical authorization. R15 permits lookup of only the selected effect ID, so reached count is one while the authentic map size is two. Enforcing line 67 refuses the state; ignoring line 67 violates the frozen cardinality rule.
- Impact: checkpoint availability still depends on unrelated lifetime authority history. A valid account eventually becomes unprojectable even though the selected current venue/acquisition subset is in cap, contradicting R15's noise-invariance and selected-work guarantees.
- Resolution: define the exact expected key set separately for each authority map. In particular, make `_effect_authority_by_id` a permitted authenticated superset whose checkpoint subset is keyed by proof-selected effects (or add an authorized bounded discovery source), rather than comparing the selected count to whole-map size. Add an authentic control with an unselected closed ownerless authorization plus an in-cap selected effect; it must produce the same bytes as the selected state without that unrelated history and must kill a whole-map-cardinality mutant.

### [P1] Adding the rank maps changes the existing protection-book commitment unless R15 freezes an exclusion

- Location: `work/queue/M2-EXECUTION-2026-08-21/26-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R15.md:20`
- Requirement: R15 lines 20-24 say the two new ordinal indexes are derived accelerators that do not alter any serving commitment or authority decision; lines 104-107 release `venue.py` only for those indexes and their invariants and claim no serving-authority change.
- Evidence: `static-reasoning` — `VenueRecoveryBook` is a dataclass, and `_protection_book_commitment` iterates every `dataclasses.fields(book)` member and commits its name and value unless the name is in one explicit three-field exclusion set (`app/execution_core/venue.py:7990-8022`). The two R15 field names are not frozen as exclusions, and the R15 controls at lines 98-102 do not require that exclusion or an unchanged-commitment known answer. Implementing the two fields as specified therefore automatically adds both map roots to the protection-book preimage, changing `_protection_commitment` for every book, including empty books, despite line 24.
- Impact: the preflight currently releases a source change that can silently invalidate existing venue/protection commitments and every authority/proof binding derived from them. That is a serving safety-commitment change, not a lookup-only implementation detail.
- Resolution: freeze both exact field names in `_protection_book_commitment`'s derived-field exclusion set before releasing implementation, and add failure-capable controls that pin the pre-R15 protection commitment across empty and nonempty books while separately proving selected-rank lookup/invariant failures. The control must fail if either exclusion is removed or if either rank map is consulted by a serving authority decision.

Verdict: ACCEPT-WITH-CHANGES
P0: 0
P1: 2
P2: 0
Unverified: No SQLite, DDL, database, runtime, or executable test activity was performed. The findings are static derivations from the exact candidate, recursive contract, repository selection SQL text, and current reducer/commitment code.
