# REV-0074 R1 author disposition

`result-r1.md` is accepted as valid negative evidence and remains unchanged.

The R1 finding is corrected by freezing `InputSemanticKeyKind`, `InputSemanticKey`, exact
operation-to-key derivation, the immutable `durable_input_semantic_key` family, record/repository
methods, C3 write placement, and authority hydration treatment. Primary input IDs remain technical
dedupe authority; alternate keys are exact owner proof and are never collapsed to a generic result.

The correction covers the reproduced `QueryClaimId` and one-use `EmergencyGrantId` cases plus the
other history-shaped alternate indexes already present in venue and manual-flatten reducers. It
does not activate source implementation or SQLite. A new `request-r2.md` binds the amended head for
a fresh independent verdict in `result-r2.md`.
