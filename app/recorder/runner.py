"""Operational runner for the isolated, flag-gated tape recorder."""

from __future__ import annotations

import asyncio
from contextlib import suppress
import logging
from pathlib import Path

from app.config import Settings
from app.marketdata.factory import create_market_data_service
from app.models import utcnow
from app.recorder.service import TapeRecorder
from app.recorder.store import TapeStore


_log = logging.getLogger(__name__)


async def run_tape_recorder(settings: Settings) -> None:
    """Run an intentional recorder session without starting the trading app."""
    if not settings.enable_tape_recorder:
        _log.info("Tape recorder disabled; no market-data or broker calls were made.")
        return

    market_data = create_market_data_service(settings)
    await market_data.subscribe(list(settings.tape_recorder_symbols))
    recorder = TapeRecorder(
        market_data=market_data,
        store=TapeStore(
            Path(settings.tape_recorder_path),
            max_bytes=settings.tape_recorder_max_bytes,
            max_segments=settings.tape_recorder_max_segments,
        ),
        enabled=True,
        clock=utcnow,
    )
    feed_task = asyncio.create_task(market_data.run())
    try:
        await recorder.capture_forever(settings.tape_recorder_interval_seconds)
    finally:
        await market_data.stop()
        feed_task.cancel()
        with suppress(asyncio.CancelledError):
            await feed_task
