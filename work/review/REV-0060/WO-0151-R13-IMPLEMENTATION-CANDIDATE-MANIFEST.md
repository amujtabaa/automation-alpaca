# WO-0151 R13 implementation candidate manifest

Status: **format-normalized replacement candidate -- focused exact-delta recheck pending**

Review base: `2208119083632ce26e58f966f6d7c3f3775f4aa7`
Branch: `codex/arch-reset-2026-07-r1`

This candidate implements only the ratified R13 atomic completed-successor
protection-cursor rollover and directly coupled late-retired-fact compatibility
semantics. The frozen WO-0152 detector is downstream evidence, not a candidate
path.

The predecessor manifest SHA-256
`b8fa0ab942ca32ec1a4aabb3c3f8d352ff33980437e72b456f26b5695ad11b8c`
and evidence SHA-256
`e837e776b335821086990130f8a1aeae0c2da4a72a6c8ad38ccd4bc515028b03`
were independently accepted in result
`2fead31818a1d826a3211a4dd2fa707656646d7a72cfb8a90f84c3b4f139b8fe`.
This replacement removes only their two Markdown hard-break spaces, re-pins
the directly necessary current records, and preserves every source/test byte.

## Authority pins

| Record | SHA-256 / exact evidence | Meaning |
|---|---|---|
| Unchanged R13 RED contract | `240fc0e1fba4b509cb9a8d5449777b889d43648751abd8cdce54672f89d63c90` | ratified implementation contract |
| Clean R13-R1 semantic manifest | `c05cddbc4d6d7d7cede2b893d6a3b287791eb25adc3015f7181fda5629fc9222` | ratified clean semantic freeze |
| R13-R1 semantic result | `71b7ff74f62bdc64f7f25cff5f8b047a30d82ebad961c0e2cdeb48f16638d1a5` | independent `ACCEPT`, P0=0/P1=0/P2=0 |
| R13-R1 activation R1 result | `82627d88422374f0230e8f00926b397b06104b32042a993ea21f453fc9403c59` | exact-five-path records-only `ACCEPT`, P0=0/P1=0/P2=0 |
| Documentation activation publication | `36e69167af234f0f3c048a049e97130219fc954d` | clean records-only publication |
| Activation-SHA reconciliation / review base | `2208119083632ce26e58f966f6d7c3f3775f4aa7` | exact source/test authority base |

## Exact candidate paths

| Path | SHA-256 | Role |
|---|---|---|
| `app/execution_core/venue.py` | `b10e0a5e8c55dbbedbfdb7156a5a6f8d9bef83867212f12299575aa67bf7dedb` | private sealed zero-economic rollover source, direct compatibility predicate, and unchanged ordinary-source fence |
| `app/execution_core/authority.py` | `6e028f3c80c0d27af5b5cb4a5ec6336a0bdff9c876d11ce670c6369c840e118a` | atomic rollover plus B-currentness publication, receipt/source binding, serving fence, and exact waiting-resolution route |
| `app/execution_core/acquisition.py` | `09cd9bb33fff2dcdcfadb68da837ea9afa108aac2fe75fface73b5121f07e0e0` | exact completed-versus-aborted receipt validation and ordinary-versus-cross-mandate protection dispatch |
| `tests/execution_core/test_acquisition.py` | `ae86b23b8cbdc26f7c47930956a8b8b364bb76bae34c6f081ae5dc16968a8512` | RED, B-first-fill, invalid-source, atomic-refusal, late-fact, and scoped mutation controls |
| `tests/execution_core/test_import_boundary.py` | `1ffda4dd5655401c95ec1eee20e25e0e424929ea7dfdd007b37ac49881b7e0d0` | failure-capable exact private owner/import/call and no-history boundary |
| `work/review/REV-0060/WO-0151-R13-IMPLEMENTATION-EVIDENCE.md` | `6ba0661c1b8713b1941d83eb0dbc4799a74f6883cb4a04e2099358da36d17c36` | format-normalized fresh local gate evidence and sequencing disclosure |

Only the six immutable source/test/evidence rows above are exact candidate
paths. Current work-order, PKL, ledger, and ratification records are downstream
publication state; they are validated by scope/governance checks but are not
self-referential inputs to this immutable implementation freeze. Any byte
change to an exact candidate path invalidates this manifest and requires a
replacement candidate plus fresh independent acceptance.

## Required independent disproof

Re-derive rather than assume all of the following:

1. Completed rooted flat A-to-B produces one and only one authentic,
   zero-quantity rollover whose source binding and receipt commitment both bind
   the exact successor registration; rolled venue and B currentness publish in
   one immutable authority result.
2. Aborted/unrooted A-to-B-to-C produces no rollover and retains the existing
   unbound-cursor route.
3. Wrong scope, same/rebound mandate, nonflat/inconsistent execution, live or
   unknown/cancellable ownership, malformed ordinary mandate change, wrong
   source registration, and duplicate receipt transition all fail closed.
4. The central serving predicate uses one direct scope lookup: no-currentness
   refresh remains structurally usable, but old A venue plus B currentness is
   non-serving and cannot produce successor admission.
5. B's first canonical fill uses the unchanged strict ordinary protection
   projector and yields fresh B `FLOOR_ONLY`; late retired-A facts both before
   and after that fill retain A lineage, preserve B as sole live generation,
   and force B-compatible `HARD_BAIL` without normal capacity.
6. Open/unknown B ownership after its first fill remains waiting for resolution
   rather than fabricating cancellation authority; safely stand-downable or
   cancellable B work retains the existing atomic preemption route.
7. The implementation adds no public export/API, venue-to-authority import,
   generic rollover command, history scan, controller history, runtime,
   persistence, database, or network path.
8. The tests are failure-capable and the first detector execution's sequencing
   disclosure is accurate; only the final clean full-suite rerun is success
   evidence.

## Fresh local evidence

- intended RED: two failures and one retained aborted-route pass;
- allowed-path suite: exit 0;
- full pure execution-core suite: 1,382 collected, exit 0 after final fix;
- frozen detector B-first-fill and late-A-after-B case: exit 0 without byte
  change;
- Ruff check/format, Mypy, diff, disposition, ledger, and PKL gates: exit 0.

No database-capable fixture, SQL/DDL, broker/network activity, runtime wiring,
or external CI was used for candidate acceptance.

## Frozen and retained exclusions

| Path | SHA-256 / treatment |
|---|---|
| `tests/execution_core/test_acquisition_stateful.py` | `c89dc011c359d104d9a2ae851f0a649926e04ac596acf6da444eecbea1774186`; unchanged frozen downstream detector, excluded and unstaged |
| `work/review/REV-0059/WO-0152-FR-08-B-FIRST-FILL-DETECTOR-FREEZE.md` | `d83257b7de12dfa440fae5adc3005cf41165b86b83a2c6f7c96295f8712cc9fb`; retained detector freeze |
| `work/review/REV-0058/WO-0151-R12-R1-ACTIVATION-DELTA-MANIFEST.md` | retained raw historical artifact; excluded and unstaged |
| `work/review/REV-0058/WO-0151-R12-R1-ACTIVATION-DELTA-R1-MANIFEST.md` | retained raw historical artifact; excluded and unstaged |
| `work/review/REV-0058/WO-0151-R12-R1-IMPLEMENTATION-CANDIDATE-MANIFEST.md` | retained raw historical artifact; excluded and unstaged |
| `work/review/REV-0058/WO-0151-RED-CANDIDATE-R12-R1-MANIFEST.md` | retained raw historical artifact; excluded and unstaged |
| Original format-blocked R13 semantic/activation manifests and request/result packet | retained byte-stable historical evidence; excluded and unstaged |

WO-0151 remains `REVIEW`; WO-0152 remains `ACTIVE` but paused. The unchanged
paired 93% exact-head Python 3.11/3.12 gate remains mandatory and unsatisfied.
No master merge, PR, cleanup, deletion, force-push, or rebase is authorized.
