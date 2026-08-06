# WO-0150 R1 replacement documentation candidate manifest

Status: **FROZEN DOCUMENTATION-ONLY REVIEW SET**

Parent commit: `4de04ef16f34ab0c71068ca04c036a2f68138d04`

This replacement freeze supersedes only the earlier unaccepted R1 documentation
candidate manifest SHA-256
`0f2ecc9f09c0487516599385910102c1de754a2971ea5f70228780a55de414b6`.
That manifest and its request remain retained negative/predecessor evidence.
This replacement adds the authoritative append-only records and the corrections
needed to make R1's gate, actual-source boundary control, and direct venue
provenance requirements unambiguous.

| Path | SHA-256 |
| --- | --- |
| `work/active/WO-0150-reset-kernel-e1-generation-lineage.md` | `2a2fc00bf28a2a68503ef31b5a4fc1df85b654129ad06dbad4e6e954bcc31e8e` |
| `work/review/REV-0057/CORRECTION-02.md` | `df4da78659e9a6c6a5646a2331908f77ef65a5e54c943e7cbd2390e1643f3898` |
| `work/review/REV-0057/CORRECTION-03.md` | `a7a7652e90f0ee06c52429e341f3488f710f4e512bf909c77f6ad7f9e7dc5c4b` |
| `work/review/REV-0057/WO-0150-IMPLEMENTATION-BOUNDARY-FINDINGS-R1.md` | `582464fac80b38d092799bf5c0b1fc9c24f0a44bb38703c31e9310a619e4713e` |
| `work/review/REV-0057/WO-0150-RED-CONTRACT-R1.md` | `a0636443228b04a94bf34b7dfba66b450541955342c3f51f762a59843b842def` |
| `pkl/project/goals.md` | `79a034d13e05b1bafdcc4a8bd2b67dd904ecbad5eb38ed1d89bcc82e7c31a07a` |
| `pkl/architecture/architecture-map.md` | `717d4c0ea4a7ad119c91ad9d9f568c228a7dd95efd8bc9f27fd73e60b6011d0c` |
| `pkl/log.md` | `6af0d1f88e665ddd196dca8e856a26cc212e808ae8704740b21e7939aba16a4d` |
| `work/ledger.jsonl` | `da5fa3749f88e6e1e2fb3788a91366edc8401925f815914facd877952a8e58c5` |

Excluded by rule: every `app/**` and `tests/**` path, including the current
uncommitted exploratory E1 code/test delta. Those paths cannot be staged,
committed, or treated as R1 implementation evidence until this exact source set
receives an independent `ACCEPT` with P0=0/P1=0 and the active work order
records that result.
