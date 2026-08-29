# REV-0116 author disposition

Date: 2026-08-29

Status: **ALL THREE P1 FINDINGS ACCEPTED — contract corrected; exact re-review pending**

The fresh preflight returned `ACCEPT-WITH-CHANGES`, P0=0/P1=3/P2=0. The reviewer-owned result is
preserved unchanged at raw SHA-256
`5cf497c636a66efee779f75935f80e8e65762a2b163a48ccd1745466cc7ac98c` and blob
`d1c42097ffccc7097adc4cac98529eb66d026070`.

## Accepted findings and root corrections

1. **Cold request/retry dead end — accepted.** `StartupRequest` now carries only immutable
   application/execution-profile/market-profile selection coordinates. After owner-lock
   acquisition, startup loads the current inert checkpoint and current repository proof, invokes
   owner-controlled private restore constructors, and reprojects byte-identically before creating
   a private `UnitOfWorkContext`. A non-serving result never leaks context. A retry always reloads
   the latest committed checkpoint, including a prior invalidation successor.
2. **Incomplete unresolved-effect set — accepted.** Reconciliation now consumes the complete
   authenticated current-unresolved union in the checkpoint selection proof: OPEN, qualifying
   INVALIDATED, and qualifying closed-late-owner effects. It does not use the narrower
   `load_open_venue_effects` result as completeness authority. Only exact claimed identities are
   queried, and the complete union is reloaded before service.
3. **Subscription loss at final edge — accepted.** Market-source evidence now has an exact
   currentness operation bound to acknowledgement, fence, source profile, stream generation, and
   sequence mode. Startup checks it immediately after baseline commit and immediately before
   `SERVING`; loss is non-serving.

The scope amendment adds only the owner modules and checkpoint codec needed for private
proof-bound restore constructors plus direct tests. It adds no public owner API, generic framework,
DDL, new durable-input domain, or runtime adapter implementation.

`request-r1.md` will ask the same fresh seat to verify only these three corrections and direct
regressions. Source remains held until that correction-only review returns zero open P0/P1.
