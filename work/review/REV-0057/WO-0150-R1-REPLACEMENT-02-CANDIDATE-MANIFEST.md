# WO-0150 R1 replacement 02 documentation candidate manifest

Status: **FROZEN DOCUMENTATION-ONLY REVIEW SET**

Parent commit: `4de04ef16f34ab0c71068ca04c036a2f68138d04`

This freeze supersedes only the unaccepted R1 replacement candidate manifest
SHA-256 `2718ee823a094378245504c6e74f40069b57fe912958d0722e2674947daddf9f`.
That candidate, its request, and its findings remain retained negative evidence.
This corrected source set incorporates the independent wire/export/current-book
projection adjudication without changing an accepted ADR or activating E2.

| Path | SHA-256 |
| --- | --- |
| `work/active/WO-0150-reset-kernel-e1-generation-lineage.md` | `d3b3e9235250a81901dffbfcb69d2255d3717c06b35bdb650e3515cae43a1919` |
| `work/review/REV-0057/CORRECTION-02.md` | `df4da78659e9a6c6a5646a2331908f77ef65a5e54c943e7cbd2390e1643f3898` |
| `work/review/REV-0057/CORRECTION-03.md` | `a7a7652e90f0ee06c52429e341f3488f710f4e512bf909c77f6ad7f9e7dc5c4b` |
| `work/review/REV-0057/CORRECTION-04.md` | `30a742065de6233ba9826e0c9106282f81f37196c0324a3aa23b5d368d49f92d` |
| `work/review/REV-0057/WO-0150-IMPLEMENTATION-BOUNDARY-FINDINGS-R1.md` | `582464fac80b38d092799bf5c0b1fc9c24f0a44bb38703c31e9310a619e4713e` |
| `work/review/REV-0057/WO-0150-RED-CONTRACT-R1.md` | `e66271ae95d1f9f4174ea8cadd7b104f45183b580bd78fde34afdc7364fa4e5a` |
| `pkl/project/goals.md` | `235ce200ab8376970012b7f741b31b7a54a91fd4516934a6f281bf80ba4164d2` |
| `pkl/architecture/architecture-map.md` | `6e06b471a2a9d265ad7e31d89eb5781fb06fc9f7808b19da3786d8453d4147e4` |
| `pkl/log.md` | `78e43a9e8b9af1a351b8b3c5c373ac78a76188b06b91af26ffc33090722313db` |
| `work/ledger.jsonl` | `66d337f1d2cb2cb5f14ddbc5d8824a5cd43843d49472a9872a39802b0e798b0b` |

Excluded by rule: every `app/**` and `tests/**` path, including the current
uncommitted exploratory E1 code/test delta. Those paths cannot be staged,
committed, or treated as R1 implementation evidence until this exact source set
receives an independent `ACCEPT` with P0=0/P1=0 and the active work order
records that result.
