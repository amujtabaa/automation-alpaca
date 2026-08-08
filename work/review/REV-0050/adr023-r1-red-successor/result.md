# ADR-023 R1 RED metadata-seal successor review

Review target: `9fe4c37f4114aee2ac5ca2f499b784cabc657cc6` over exact sole parent
`7e0b869c852b66a6744b447429f4bf0eca756b5b`

No P0, P1, or P2 findings.

Evidence (`reproduced-live` and exact committed-tree inspection):

- The target is checked out at `HEAD`, has the requested sole parent, and changes exactly the five
  recorded paths. The tracked worktree is clean, `git diff --check` passes, the active-WO scope
  checker reports `SCOPE CHECK PASSED`, and there is no `app/**` delta.
- The metadata helper now accepts an explicit ordered constructor-field inventory, validates every
  field's exact `init` flag, requires `__match_args__` to contain exactly the constructor fields,
  and constructs its independent reference dataclass with identical per-field `init` metadata.
  Inventory order, duplicates, omitted names, and additional names cannot pass the exact inventory
  check.
- The one exception is centralized as all `MarketOccurrence` fields except `occurrence_id` and is
  applied to every real-occurrence metadata/lifecycle path: public entrypoint argument sealing,
  public value-shape sealing, and the recursive passive-value graph. Every other dataclass retains
  the default all-fields-constructor-initialized requirement.
- The new synthetic control passes and executes both required negative cases: omitting the derived
  identity exception fails, and excluding an additional constructor field fails. The surrounding
  passive helper selection passes 17/17; the five focused R1 controls pass 5/5.
- Fresh collection reports 506 successor RED tests and 745 predecessor tests. The successor JUnit
  rehashes to `FCE5BA7AC5A0DFDDE405D1E97DD780089A60C9D2E8BAD5FDA4D9968B89EF4A84`
  and contains 506 cases / 410 intentional structural failures / 96 passes / 0 errors / 0 skips.
  Compared with the prior 505-case artifact, its only added case is the new passing metadata-seal
  control and no retained case changes status. The unchanged predecessor JUnit rehashes to
  `D35BB7940EC211CBB33B4E75F8C7677CEB795490830AD723CA80BC8735D3DC99`
  and contains 745/745 passes with no failures, errors, or skips.
- Ruff lint and format-check pass for the changed Python file, and it parses with the Python 3.11
  grammar target.

Verdict: ACCEPT
P0: 0
P1: 0
P2: 0
Unverified: The 506-case RED execution and 745-case predecessor execution were not repeated because
their exact artifacts, hashes, metadata, fresh collections, sampled controls, and status comparison
were consistent. Actual Python 3.11 execution was not performed locally; the required Python 3.11
grammar parse passed. No production behavior is accepted, and this verdict authorizes only the
already approved WO-0148 production-implementation gate.
