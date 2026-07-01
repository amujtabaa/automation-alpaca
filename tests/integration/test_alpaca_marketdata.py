"""Env-gated integration tests for the real Alpaca market-data stream.

NOT part of the standard unit-test run: skipped unless paper credentials are
present, and makes real network calls (a REST snapshot fetch + a brief live
websocket connection) to Alpaca's market-data API. Run deliberately with:

    ALPACA_PAPER_API_KEY=... ALPACA_PAPER_API_SECRET=... pytest tests/integration/

Cannot be exercised in this build environment (no live credentials, and
premarket/after-hours feed *quality* is an explicitly deferred empirical
unknown — see docs/IMPLEMENTATION_PROMPT_PHASE_5.md's "Known Unknown"
section). This file exists so a developer *with* real credentials gets a real
smoke test rather than having to write one from scratch the first time they
need to verify the live connection actually works.

Import discipline matches test_alpaca_paper.py: ``alpaca-py`` is imported
lazily inside the test, not at module top, so collecting this file without the
SDK installed does not raise — the skipif fires first.
"""

from __future__ import annotations

import asyncio
import os

import pytest

_HAVE_CREDS = bool(
    os.getenv("ALPACA_PAPER_API_KEY") and os.getenv("ALPACA_PAPER_API_SECRET")
)

pytestmark = [
    pytest.mark.anyio,
    pytest.mark.skipif(
        not _HAVE_CREDS, reason="Alpaca paper credentials not configured"
    ),
]


def _stream():
    # Imported lazily so this module collects cleanly without alpaca-py present.
    from app.marketdata.alpaca_stream import AlpacaMarketDataStream

    return AlpacaMarketDataStream(
        api_key=os.environ["ALPACA_PAPER_API_KEY"],
        api_secret=os.environ["ALPACA_PAPER_API_SECRET"],
    )


async def test_subscribe_seeds_previous_close_via_rest():
    """The REST seed alone is verifiable regardless of market hours — unlike
    live trade/quote ticks, a symbol's previous daily close doesn't depend on
    the market being open right now."""

    stream = _stream()

    await stream.subscribe(["AAPL"])
    snapshot = await stream.get_snapshot("AAPL")

    assert snapshot is not None
    assert snapshot.prev_close is not None
    assert snapshot.prev_close > 0


async def test_run_connects_and_stops_cleanly():
    """A real, brief live connection: start run() as a background task, give
    it a few seconds to establish the websocket, then stop() and confirm the
    task completes without hanging or raising.

    Does NOT assert on live tick data arriving — outside market hours (or with
    a thin premarket/after-hours feed, the empirical unknown this project
    explicitly flags) no ticks may arrive in the test window at all, and that
    must not make this test flaky. It only asserts the connection lifecycle
    itself (connect, subscribe, stop) works against the real API.
    """

    stream = _stream()
    await stream.subscribe(["AAPL"])

    run_task = asyncio.create_task(stream.run())
    try:
        await asyncio.sleep(3.0)  # let the websocket connect
        assert run_task.done() is False  # still running, not crashed immediately
    finally:
        await stream.stop()
        try:
            await asyncio.wait_for(run_task, timeout=5.0)
        except asyncio.TimeoutError:
            run_task.cancel()
            raise AssertionError("run() did not stop within 5s of stop() being called")
