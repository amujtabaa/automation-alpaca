# WO-0149 superseded partial source/test delta — retained evidence

## Status and provenance

This directory is a transparent capture of the uncommitted WO-0149 partial application/test
implementation found in the main worktree on 2026-08-05 before cleanup under WO-0153. WO-0149 was
formally superseded by ratified ADR-020 R2 and ADR-021 R2. This material is historical evidence
only: it grants no implementation or activation authority for WO-0150, WO-0151, WO-0152, M1, or M2.

- Capture base commit: `192056d4e050517ad9b92bfb5f17bf2780e23a47`
- Capture completed (UTC): `2026-08-06T00:48:33.2526000Z` (the Git patch creation time; the two
  raw copies were captured at `2026-08-06T00:48:21Z` immediately beforehand)
- Provenance: main-worktree mixed delta, classified in WO-0153 as superseded partial WO-0149
  application/test material.
- Capture method: Git-native `git diff --binary HEAD -- <eight exact tracked paths>` plus raw,
  byte-for-byte copies of the two named untracked files.

## Artifact inventory

| Artifact path | Bytes | SHA-256 | Purpose |
| --- | ---: | --- | --- |
| `tracked-wo-0149-source-test.patch` | 183081 | `820149dc249d7f1b91d1af46427614f1329540a7aac69be4d74b58407c6a84f0` | Binary-safe patch from the capture base for all eight tracked paths below. |
| `untracked/app/execution_core/acquisition.py` | 40001 | `d7c8fac467313245dfbfefd49099ba14c81427cb7b748729450fc93522c94b33` | Exact raw representation of the untracked acquisition source file. |
| `untracked/tests/execution_core/test_acquisition.py` | 37307 | `b45e60091ba753b2ecd51c8da29f01fc2c8fb6cea097b6ef0bed2203540e0fa6` | Exact raw representation of the untracked acquisition test file. |

## Tracked-path capture inventory

The patch contains precisely these capture-base deltas. `Base blob` is the blob at
`192056d4e050517ad9b92bfb5f17bf2780e23a47`; `captured working bytes` and SHA-256 identify the
pre-restoration file content represented by the patch.

| Path | Base blob | Captured working bytes | Captured SHA-256 | Patch numstat |
| --- | --- | ---: | --- | --- |
| `app/execution_core/__init__.py` | `b54e3287b4eac728ae66de567400f34e9b8f89c8` | 8069 | `a14b7d20293cee124955505102203807f962fbeadd8488abd4db5e7ff69baecf` | `50 / 0` |
| `app/execution_core/authority.py` | `4b2aafe3e7a8e51b1683285d4850c2a93582cd62` | 84234 | `02aef5a852766db4041107026daefbf48e5f878ec1e012f6986f382a81caac5a` | `986 / 4` |
| `app/execution_core/identity.py` | `8029793d171edbedeb0a7affbf0ace6d0f42b3bf` | 9681 | `b5b0db048572b502b94f73fcd4b41be8a76e50ad2e75aaa09ca6774c94e411cd` | `35 / 0` |
| `app/execution_core/protection.py` | `b69e65434a8b8d5f74c460203a7db85a6eb267c8` | 94866 | `7f417177d28d6f876510b222b952c420b2ccabc7e89b59adc569184b249e54fd` | `6 / 0` |
| `app/execution_core/venue.py` | `ee30c4831980edbbf7afc74132130e463d9190f9` | 437903 | `36d51ff7619717c24f7a3d492042bdad1a62f0f15e58537e4b7848dc7ba9b099` | `1105 / 0` |
| `tests/execution_core/test_authority.py` | `2881533108dc65c6a75646cb6bbae0278b3ee26e` | 231487 | `25a08601d7ad4bcc647d069c7ed24117231b6f070961b0e40e600622e9baf82d` | `1296 / 257` |
| `tests/execution_core/test_authority_stateful.py` | `9d9ea9f0e04f0b13e83f56885f561adddd479fb6` | 102103 | `ea66eb86c510de24788ecf480e3c98eff1f3b8ae6c05941d8adff3bb2bdc9cfd` | `28 / 49` |
| `tests/execution_core/test_import_boundary.py` | `0da878a322b0aa357e4071e5a552d522ef0bc727` | 212623 | `6a9162ceaa801b94f847ce7f7b2f51a07b29323b100342b9c89d603447e87810` | `25 / 0` |

## Verification and restoration instructions

At capture time, `git apply --check --reverse tracked-wo-0149-source-test.patch` succeeded against
the mixed working tree. This proves the patch exactly reverses the complete tracked delta for the
eight listed paths; `git apply --numstat` reported no other path. The SHA-256 values of both raw
copies exactly equalled the original untracked files at capture time.

To reconstruct the historical partial state in a disposable, separately authorised checkout of the
capture base:

```text
git checkout --detach 192056d4e050517ad9b92bfb5f17bf2780e23a47
git apply --check tracked-wo-0149-source-test.patch
git apply tracked-wo-0149-source-test.patch
copy untracked/app/execution_core/acquisition.py app/execution_core/acquisition.py
copy untracked/tests/execution_core/test_acquisition.py tests/execution_core/test_acquisition.py
```

The patch is an immutable byte-for-byte capture, including original whitespace. Repository
formatting checks exclude this retained historical artifact and instead use `git apply --check
--binary` for validity; it is not a current source-formatting defect.

Then recompute the listed SHA-256 values. Restoration is evidence recovery only; it is not
authority to execute, validate, continue, or adopt the superseded implementation.
