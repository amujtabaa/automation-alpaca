# WO-0123 market-data tape format

`python -m app.recorder` is an intentionally separate, read-only operational process. It uses
only `MarketDataService` (the existing market-data port), never receives a `BrokerAdapter` or
`StateStore`, and therefore cannot submit, cancel, or replace orders or change position/fill/
envelope truth.

## Operation

The recorder is off by default. To start a deliberate paper-market-data collection session, set:

```text
ENABLE_TAPE_RECORDER=true
TAPE_RECORDER_SYMBOLS=AAPL,MSFT
MARKET_DATA_FEED=auto
```

Then run `python -m app.recorder`. With paper credentials present, `MARKET_DATA_FEED=auto` uses
the existing paper market-data stream; without them it remains the fake feed and does not make a
network call. No recorder setting enables a trading path.

Optional settings are `TAPE_RECORDER_PATH` (default `./data/tapes/tape.ndjson`),
`TAPE_RECORDER_INTERVAL_SECONDS` (default `1`), `TAPE_RECORDER_MAX_BYTES` (default `52428800`),
and `TAPE_RECORDER_MAX_SEGMENTS` (default `7`). The active file rotates before it exceeds its byte
limit; at the defaults the retained corpus is bounded to roughly 350 MiB plus one in-flight line.
Older rotated segments are discarded. Tape files live under ignored `data/`, outside execution
truth, and are disposable collection artifacts.

## NDJSON schema v1

Each canonical UTF-8 line contains:

- `schema_version`, `observed_at`, and `session_phase` (`premarket`, `regular`, `after_hours`, or
  `closed`);
- a raw market snapshot: symbol, last price, bid, ask, volume, previous close, source update time,
  and source staleness;
- explicit validity flags for staleness, finite last price, positive bid/previous close,
  in-range ask (at most 1,000,000), and nonnegative volume.

Every current snapshot is written on every capture pass. Invalid, stale, negative, out-of-range,
or non-finite observations are retained with their flags rather than filtered. Non-finite values
use the JSON-safe strings `NaN`, `Infinity`, and `-Infinity`; replay restores the original Python
float value. Sorted, compact JSON makes a read/replay/re-encode sequence byte-identical, so later
replay work can reproduce exactly the snapshot sequence the engine would have observed.

The tape is the corpus hook for later regime labels: each raw observation has its symbol and
session phase, and the full observed print/snapshot stream can later be bucketed as a spike,
grinder, trend-pullback, fakeout pump, or halt-resume gap. WO-0123 deliberately does not score a
policy or model fills.
