# REV-0118 WO-0170 corrected soak-driver smoke result R5

Status: `PASSED` as a driver smoke; mandatory 24-hour soak remains `NOT_RUN`.

## Bound identities

- Canonical source: `3b3b1462bc8a52e6dd4308121e87545bd11f6a70`
- Canonical tree: `800b0f7a56eda308d445810dc998107597f7c539`
- Proof branch: `codex/m2-wo0170-soak-smoke-sqlite-r1`
- Unlock commit: `87dbf2ece6f4b1fcf97dc55ca94a873b4be83cb7`
- Unlock tree: `d607bef24bd773b90e7de4c0454afe3c9afee63e`
- Proof-branch diff: the sole tracked change from the canonical source was the exact authorization
  flag transition from literal boolean `False` to literal boolean `True`.
- `SCHEMA_DDL`: unchanged at 190,705 UTF-8 bytes and SHA-256
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`.
- Corrected soak driver SHA-256:
  `9deff7a6be5035e6a7dcbec06482506a6acebf1a655502fa912100d201d0fdd6`.

## Result

The exact one-cycle command exited 0. Its seven-node schedule collected and passed 180 cases in
7.29 seconds, including pure write-fault/commit-ambiguity controls and fresh-file SQLite ambiguity,
startup fault, WAL restore, two-LIVE, and closure-lineage cases. The driver recorded one passing
cycle and correctly emitted:

- `status`: `NOT_RUN`
- `all_cycles_passed`: `true`
- configured duration: 1 second
- elapsed duration: 7.75 seconds
- required duration: 86,400 seconds

Evidence hashes:

- `summary.json`: `4bab561d4da030a76de86b783541318dcd7a1aaefb67734d2f4ade5d3d4845f8`
- `cycles.jsonl`: `6428e01e86f382e667a44915fc08718b4c359ca7e0f11dd21148486d34898c59`
- `cycle-000001.log`: `f21186537bf78d25361908aacc0f10bf1c67e65b5bdf19b6b35227ad161b802a`

This validates driver wiring only. It does not convert the mandatory uninterrupted 24-hour soak
into PASS. The flag-true branch and generated databases remain quarantined and are not
predecessors.

## Prohibited-activity confirmation

No configured or in-memory database, DDL-byte change, migration, runtime composition, credential,
broker/network activity, order, promotion, master merge, history rewrite, or M3 implementation
occurred.
