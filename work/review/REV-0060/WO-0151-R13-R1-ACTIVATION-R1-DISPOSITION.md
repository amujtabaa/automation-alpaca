# WO-0151 R13-R1 records-only activation R1 disposition

Status: **PENDING FOCUSED INDEPENDENT ACCEPTANCE**

## Remediation

The first clean activation result SHA-256
`72fce061222edf684cdd2684aeebbf740c1432fbefc4df10dc6b3eb1354b2d89`
returned `ACCEPT-WITH-CHANGES`, P0=0/P1=1/P2=0. Its sole P1 was a
prospective scope escape: the prior disposition allowed conditional edits to
regression suites outside the exact five-path implementation boundary.

This R1 disposition replaces only that activation wording. The unchanged
ratified semantic authority remains:

- R13 contract SHA-256
  `240fc0e1fba4b509cb9a8d5449777b889d43648751abd8cdce54672f89d63c90`;
- clean R13-R1 semantic manifest SHA-256
  `c05cddbc4d6d7d7cede2b893d6a3b287791eb25adc3015f7181fda5629fc9222`;
- independent semantic result SHA-256
  `71b7ff74f62bdc64f7f25cff5f8b047a30d82ebad961c0e2cdeb48f16638d1a5`.

## Exact two-commit boundary

The first commit is documentation-only and uses exactly the publication set
frozen by the R1 manifest. It contains no `app/`, `tests/`, `.github/`, ADR
body, runtime, database, or operational path.

The second commit changes only the seven current records to reconcile the
exact first publication SHA and activate edits to exactly these five paths:

- `app/execution_core/venue.py`;
- `app/execution_core/authority.py`;
- `app/execution_core/acquisition.py`;
- `tests/execution_core/test_acquisition.py`;
- `tests/execution_core/test_import_boundary.py`.

`tests/execution_core/test_authority.py`,
`tests/execution_core/test_venue_recovery.py`, and
`tests/execution_core/test_protection.py` may be executed as regression
evidence but may not be edited under R13. Every other source/test path is also
read-only. Any discovered need to edit outside the exact five paths requires
a replacement exact scope, manifest, and fresh independent review before that
edit occurs.

No R13 source/test implementation begins until the first commit publishes
successfully and the second commit reconciles its exact SHA. WO-0152 remains
ACTIVE/PAUSED; the frozen B-first-fill detector remains unchanged and unstaged
until R13 implementation independently accepts.

The two original format-blocked R13 manifests and original activation packet
remain untracked, byte-stable historical evidence. They are not publication
inputs and must not be normalized, staged, or rewritten.

All existing safety and scope exclusions remain in force. Paired exact-head
Python 3.11/3.12 success at the unchanged 93% threshold remains mandatory.
