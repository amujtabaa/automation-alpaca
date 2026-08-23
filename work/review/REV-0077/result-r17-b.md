# REV-0077 R17-B independent preflight review

Reviewed exact commit `85ddd1a3c438d73e3991436a562ae81ff31263cf`, tree
`b8da99dc2ccbea04c03cd8c344606ebcd40c9347`, and R17 SHA-256
`fae546a497033c772b9f8a7ab0a3b496963f54aa7d200f5dd44dd741b435d503`.

### [P1] Dormant wire integrity hashes are reused as source-owner provenance

- Location: `work/queue/M2-EXECUTION-2026-08-21/28-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R17.md:61`
- Requirement: WO-0168c's root rule states that integrity bytes are not authority (`work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md:72`). The R16-B finding required an exact domain-separated dormant owner commitment rather than silently substituting the dormant row's self-hash into R6's acquisition owner slot (`work/review/REV-0077/result-r16-b.md:15-23`). R6 defines that slot as the acquisition member of the owner-preimage row (`work/queue/M2-EXECUTION-2026-08-21/17-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R6.md:43-59`).
- Evidence: `static-reasoning` — R17 defines `dormant_commitment` as the acquisition row's final self-integrity member and then places that identical digest in the acquisition source-owner slot (lines 65-70). It repeats the alias for dormant protection: the row's final self-hash occupies the protection source-owner slot (lines 78-87). Calling the acquisition value a “source-projection commitment” does not create a distinct preimage or domain; the only formulas are `execution-core/m2-acquisition/dormant/v2` and `execution-core/m2-protection/dormant/v1`, both already used for wire self-integrity. The listed wrong-slot controls can reject an arbitrary wrong value but cannot fail a mutant that intentionally aliases the valid self-hash into the provenance slot, because aliasing is the frozen expected behavior.
- Impact: R17 does not root-resolve the R16 absent-owner-preimage defect and leaves implementation to treat payload integrity as the evidence that authenticated its own absent-owner provenance. This weakens the acyclic integrity/authority separation at the exact projected-envelope boundary.
- Resolution: Freeze distinct domain-separated acquisition and protection source-projection commitments, derived from the exact repository-authentic selected-record preimages, while retaining separate wire-integrity commitments. Specify both owner-row substitutions and add controls that independently swap, omit, cross-scope, and alias each wire self-hash into its source-projection slot.

### [P1] The dormant collection rows have no exact payload wire grammar

- Location: `work/queue/M2-EXECUTION-2026-08-21/28-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R17.md:44`
- Requirement: The documentation-only preflight must freeze exact non-serving wire types, arrays, tags, ordering, finite limits, and commitments before source authority is released (`work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md:84`). R17 must be implementable from the recursively incorporated authority without inventing a serialization.
- Evidence: `static-reasoning` — R17 adds five payload members—`UnresolvedGenerationRows`, `UnresolvedGenerationCurrentRows`, `UnresolvedMarketStreamRows`, `UnresolvedMarketCursorRows`, and `LineageRows`—then says their grammars are the retained “R1/R5” forms (lines 44-57). Those sources do not define one such wire grammar. R1's acquisition payload uses reducer-owner `Generation` and `MarketStreamRoute` rows with semantic commitments and no generation-current or cursor rows (`09-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R1.md:197-236`). R5 instead defines storage-record binding tags and flattened SQL vectors for selection-proof commitments, including `generation-current/v1`, `stream/v1`, and `cursor/v1`; it does not define canonical payload array encodings for those records (`15-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R5.md:140-166`). The current repository records materially differ from R1's owner rows—for example, `AcquisitionGenerationRecord` carries status, predecessor ID, and text hashes, while R1 `Generation` carries `PositionScope`, binding commitments, serving class, and a final semantic commitment (`app/execution_core/persistence/records.py:135-152`; R1 lines 209-216). R17 also freezes no wrapper tags, exact field order/storage encoding, or per-collection cap for the new current/stream/cursor payload arrays.
- Impact: Two conforming implementers can encode different bytes, or one can silently reuse selection-proof record bindings as payload rows even though those are digests rather than the required canonical wire values. Known answers, decoder strictness, dormant commitments, and cross-source controls cannot be failure-capable against an encoding the preflight never uniquely specifies.
- Resolution: Freeze the exact tag, member order, scalar encoding, optional representation, canonical ordering key, and finite cap for every dormant collection and row. State explicitly whether each row is a repository storage projection or an owner semantic projection, and define the exact conversion/equality relation where both exist.

Verdict: ACCEPT-WITH-CHANGES
P0: 0
P1: 2
P2: 0
Unverified: No SQLite, database, DDL, schema-install, runtime-composition, or serving-path test was run. R17 is documentation-only; findings derive statically from the exact candidate, recursively incorporated contracts, and current source/repository selection types.
