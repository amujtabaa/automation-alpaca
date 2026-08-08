# WO-0152 E3 baseline format normalization

Status: **test-only post-confirmation normalization**

The frozen FR-08 detector was confirmed unchanged first: source SHA-256
`1a7e685f954dc8de4424ad926285d993e0e9958eae2ce1a2f60af5b03689eb22`,
confirmation artifact SHA-256
`757a6e564abce77193a3d03ab6bcf5ce519e6399062ec987109f384595ac078f`, and
all three controls passed with exit code 0.

After that required confirmation, the project formatter normalized only
`tests/execution_core/test_acquisition_stateful.py`. The source now hashes to
`a958cffd97f197adb768255c1480733cbb451f6abe79024d5026a5cf4a2fcb9f`.
The exact same three controls were rerun on the formatted source and again
completed with exit code 0. Ruff check and format verification pass.

This is the first permitted E3 source change after the frozen confirmation. It
does not revise the confirmation artifact or its evidence, change test
semantics, add production/runtime/database/SQL/DDL/broker/network authority,
or satisfy the paired E2/E3 93% exact-head closeout.
