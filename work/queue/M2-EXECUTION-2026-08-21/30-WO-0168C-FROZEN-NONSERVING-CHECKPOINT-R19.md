# WO-0168c frozen non-serving checkpoint contract — R19 literal commitment containers

Status: **FINAL PREFLIGHT CANDIDATE — DOCUMENTATION ONLY; NO DDL OR DATABASE AUTHORITY**

Date: 2026-08-23

R19 incorporates R18 and changes exactly two commitment preimages after one R18 reviewer returned
`ACCEPT` and the other identified two non-literal containers. All other R18/R17 and recursively
incorporated authority remains exact.

The ROOT lineage `source_record_binding` is exactly:

```text
K("execution-core/m2-acquisition/dormant-root-source/v1",
  ["m2.acquisition.DormantRootSourceBinding/v1",
   H(route_selected_record_binding),H(root_selected_record_binding)])
```

The row is one canonical JSON three-member array. Both `H` values are lowercase 64-character hex
encodings of the exact 32-byte selected-record bindings. No concatenation or multi-argument `K`
form is admitted.

The acquisition `bounded_registry_commitment` is exactly:

```text
K("execution-core/m2-acquisition/dormant-registry/v2",
  ["m2.acquisition.DormantRegistry/v2",DormantGenerationRows,
   DormantGenerationCurrentRows,DormantMarketStreamRows,DormantMarketCursorRows])
```

The preimage row is one canonical JSON five-member array in that exact order. R18's literal empty
and representative nonempty known answers pin both rows, every tag, and both field orders; an
untagged array, concatenation, swapped wrapper/binding, raw bytes, omitted member, or alternate
container fails independently.

R19 changes no SQL, DDL byte, source surface, public export, transaction rule, runtime composition,
serving type, or serving authority. Fresh REV-0077 exact-head review must return `ACCEPT` with
`P0=0/P1=0` before source implementation resumes. No SQLite or database execution is authorized.
