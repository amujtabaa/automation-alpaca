# REV-0077 R18-A independent preflight review

Reviewed exact commit `27d97717a362842ed90e3bc045421990fc3a43d5`, tree
`87d42f08ef723fa67ce189ca56d2dd1e4e5e8f36`, and R18 SHA-256
`3341d83257e5e98f8645173ce6b2b890726711357236a5045e35dcc0f31a05cc`.

### [P1] Two dormant commitment preimages remain non-canonical

- Location: `work/queue/M2-EXECUTION-2026-08-21/29-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R18.md:89`, `:101`
- Requirement: WO-0168c requires exact byte-implementable, acyclic wire and commitment preimages. The recursively retained grammar defines `K(domain,row)` as exactly `_commit_parts(domain, canonical_json_utf8(row))`; collection commitments cover an explicit complete count-bearing wrapper (`work/queue/M2-EXECUTION-2026-08-21/09-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R1.md:68-70`; `work/queue/M2-EXECUTION-2026-08-21/07-WO-0168H-FROZEN-OWNER-STATE-WIRE-CONTRACT.md:200-205`). The R17 finding required exact registry/lineage preimages, not only exact child rows.
- Evidence: `static-reasoning` — R18 correctly gives every dormant wrapper and child row an exact shape and correctly separates both source-projection slots from the wire self-hashes. However, the ROOT lineage source binding is defined as `K(domain,route-binding,root-binding)`, which has three arguments and supplies raw binding bytes where `K` accepts one canonical JSON row. R18 also defines `bounded_registry_commitment` over “canonical four ... wrappers” without freezing the single JSON row passed to `K`: no outer tag, array brackets/member count, or other exact container is specified. Concatenating four wrappers, hashing a four-member array, and hashing a tagged five-member row are different bytes and all fit that prose. Literal known answers cannot remove the implementation choice because the normative preimage itself is not unique.
- Impact: R18 does not completely resolve the R17 byte-grammar class. Independent implementations can produce different dormant ROOT source bindings and bounded-registry commitments while following the stated child-row grammar, so the candidate is not yet byte-implementable from recursive authority without inventing encoding.
- Resolution: Express each as one exact `K(domain,row)` value: freeze a tagged canonical row (with an exact bytes representation such as `H(...)` or the inherited exact byte scalar) for the route/root binding pair, and freeze one explicit tagged or untagged JSON array containing the four registry wrappers in exact order. Pin those exact rows in the stated known answers and mutants.

Verdict: ACCEPT-WITH-CHANGES
P0: 0
P1: 1
P2: 0
Unverified: No SQLite, database, DDL, schema-install, runtime-composition, serving-path, or executable test was run. Review was static against the exact R18 candidate, both R17 results, current record/selection-binding source, and recursively incorporated wire authority.
