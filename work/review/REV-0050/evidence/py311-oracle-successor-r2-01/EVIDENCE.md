# WO-0148 Python 3.11 oracle successor - R2 evidence

The first R2 invocation did not reach test setup because this Windows host
denied enumeration of its default user-level pytest temp directory. A second
invocation named a workspace-local `--basetemp`, but its new parent evidence
directory did not yet exist, so pytest again failed before setup. Neither
environment-only attempt produced an application assertion, SQLite result, or
acceptance evidence.

The authoritative rerun uses the retained workspace-local `pytest-temp/`
subdirectory below this file with `BROKER_ADAPTER=mock` and
`MARKET_DATA_FEED=mock`.

Terminal result: **61/61 passed** in 6.7 seconds. Existing fixtures used only
disposable files below the retained `pytest-temp/` tree. No credential,
Alpaca/broker/network activity, persistent application database, runtime
wiring, or workflow change was used.
