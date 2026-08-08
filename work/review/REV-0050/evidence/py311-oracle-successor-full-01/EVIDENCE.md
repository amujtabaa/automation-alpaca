# WO-0148 Python 3.11 oracle successor - full gate evidence

This retained directory is the sole fresh post-review full-repository branch-
coverage gate for the tests-only Python 3.11 oracle successor. The run forces
`BROKER_ADAPTER=mock` and `MARKET_DATA_FEED=mock`; existing fixtures may execute
SQL/DDL only against disposable SQLite files below `pytest-temp/`.

Terminal result:

- 5,848 tests recorded in JUnit, with zero failures and zero errors;
- 11 skipped cases and one expected failure;
- JUnit suite time 2,000.131 seconds; process wall time 2,004.1 seconds;
- 19,985/21,081 statements and 7,181/8,126 branches covered;
- raw combined line/branch coverage `93.01194919026261%` against the unchanged
  literal 93% floor; and
- coverage JSON SHA-256
  `B5E55DA9579505B180DB96061AC300403FB5B5A79CABF47A51B7FEBA56FF53D2`;
  JUnit SHA-256
  `BB1FD4992A5C2ECAB2E70CC76F759B98F1031C1275F3B7D1271578EB44B508BE`.

No credential, Alpaca/broker network activity, persistent application
database, runtime wiring, workflow change, PR/merge, deletion, or cleanup
occurred. The disposable fixture files, coverage database, JUnit, and temp tree
remain retained below this directory.
