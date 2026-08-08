# WO-0150 R1 documentation candidate manifest

Status: **FROZEN DOCUMENTATION-ONLY REVIEW SET**

Parent commit: `4de04ef16f34ab0c71068ca04c036a2f68138d04`

This manifest freezes the exact source set for the R1 RED preflight. It does
not include any application or test exploration, and it does not itself grant
implementation acceptance. The retained original REV-0057 artifacts are
historical evidence outside this replacement source set.

| Path | SHA-256 |
| --- | --- |
| `work/active/WO-0150-reset-kernel-e1-generation-lineage.md` | `b1822cb630395dea3b90de3a22a0901fc17294c945b95a8e96b8e10b0048f2f0` |
| `work/review/REV-0057/CORRECTION-02.md` | `df4da78659e9a6c6a5646a2331908f77ef65a5e54c943e7cbd2390e1643f3898` |
| `work/review/REV-0057/WO-0150-IMPLEMENTATION-BOUNDARY-FINDINGS-R1.md` | `582464fac80b38d092799bf5c0b1fc9c24f0a44bb38703c31e9310a619e4713e` |
| `work/review/REV-0057/WO-0150-RED-CONTRACT-R1.md` | `8165c4e05d4cf7bc21294601e19b8306275d29787b66d78c7175a85f4cf53b14` |
| `pkl/project/goals.md` | `8899f6ae21c51f6d5bd5a1c8ffd29c8425d605f9ce19a942206ac07a229c8e5c` |
| `pkl/architecture/architecture-map.md` | `afd8b7f13df1f043a9029bfedc8f99dd53143d5093a23e5c14bd21106b16dff2` |

Excluded by rule: every `app/**` and `tests/**` path, including the current
uncommitted exploratory E1 code/test delta. Those paths cannot be staged,
committed, or treated as R1 implementation evidence until this source set gains
an independent `ACCEPT` and the active work order records that result.
