# WO-0151 exact-head coverage attempt 02 disposition

## Boundary

This record preserves, but does not accept, the second local test-only attempt
to raise the unchanged repository coverage ratchet inside E2. It is a
diagnostic disposition, not a functional acceptance result, a replacement for
the 93% gate, or an authorization to change production code.

## Exact candidate before removal

- Branch: `codex/arch-reset-2026-07-r1`.
- Parent HEAD: `a2b84abc1914517cf591f27fb88f0b20b2a47ef7`.
- Only tracked worktree delta: 340 additions in
  `tests/execution_core/test_acquisition.py`.
- Verified SHA-256 of that file before removal:
  `eb5b3bcf004939f9d934e26f9aa45cf3c6f40e18f42427c6332324465c3a7eb8`.

The two focused controls passed. They were deliberately limited to
owner-minted permit and exit-permit relational-coordinate variants; no
production path was changed and no database, SQL/DDL, broker, runtime, or
network path was used.

## Measured result and root disposition

The pure execution-core coverage measurement changed from `89.510921%` to
`89.668145%`: 14 newly covered lines and 14 newly covered branches, or 28 of
17,809 measured pure obligations. The remaining pure gap to 93% was 594
points. This is not a realistic proportional use of E2's private-seam tests:
continuing linearly would duplicate proof at the wrong layer and turn a
coverage ratchet into an open-ended test treadmill.

The user therefore authorized this exact delta's removal after this record was
created. The correct root-level route is the separate, behavior-first E3
generated/stateful/replay/restart/boundedness proof layer, while retaining the
unchanged 93% gate for paired E2/E3 exact-head closeout.

## Disposition

`DECLINED - TEST-ONLY E2 COVERAGE TREADMILL`.

The experiment is retained only by this bounded diagnostic record and the Git
history-free working-copy evidence above. It is not staged, committed, pushed,
or used as a WO-0151 or M1 acceptance basis.

