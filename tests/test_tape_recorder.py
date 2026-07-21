"""WO-0123 pins for the read-only, replayable market-data tape recorder."""

from __future__ import annotations

from datetime import datetime, timezone
import math
from pathlib import Path

import pytest

from app.config import (
    ENABLE_TAPE_RECORDER_ENV,
    TAPE_RECORDER_PATH_ENV,
    TAPE_RECORDER_SYMBOLS_ENV,
    load_settings,
)
from app.marketdata.fake import FakeMarketDataFeed
from app.recorder import SessionPhase, TapeRecorder, TapeStore


_CLOCK = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)  # 08:00 New York


class _OrderFlowSpyMarketData(FakeMarketDataFeed):
    """A market-data port that would expose any forbidden recorder call."""

    def __init__(self) -> None:
        super().__init__()
        self.list_snapshots_calls = 0
        self.order_flow_calls: list[str] = []

    async def list_snapshots(self):
        self.list_snapshots_calls += 1
        return await super().list_snapshots()

    async def submit_order(self, *args, **kwargs):
        self.order_flow_calls.append("submit")

    async def cancel_order(self, *args, **kwargs):
        self.order_flow_calls.append("cancel")

    async def replace_order(self, *args, **kwargs):
        self.order_flow_calls.append("replace")


def _recorder(tmp_path: Path, feed: _OrderFlowSpyMarketData, *, enabled: bool = True):
    return TapeRecorder(
        market_data=feed,
        store=TapeStore(tmp_path / "tape.ndjson", max_bytes=1_000_000, max_segments=2),
        enabled=enabled,
        clock=lambda: _CLOCK,
    )


@pytest.mark.anyio
async def test_recorder_path_makes_zero_order_flow_adapter_calls(tmp_path):
    feed = _OrderFlowSpyMarketData()
    feed.set_snapshot(
        "AAPL",
        last_price=100.0,
        bid=99.9,
        ask=100.1,
        volume=25.0,
        prev_close=98.0,
        updated_at=_CLOCK,
    )

    records = await _recorder(tmp_path, feed).capture_once()

    assert len(records) == 1
    assert feed.list_snapshots_calls == 1
    assert feed.order_flow_calls == []


@pytest.mark.anyio
async def test_flag_off_is_fully_inert(tmp_path):
    feed = _OrderFlowSpyMarketData()

    records = await _recorder(tmp_path, feed, enabled=False).capture_once()

    assert records == []
    assert feed.list_snapshots_calls == 0
    assert feed.order_flow_calls == []
    assert not (tmp_path / "tape.ndjson").exists()


@pytest.mark.anyio
async def test_replay_reconstructs_byte_identical_snapshot_sequence(tmp_path):
    feed = _OrderFlowSpyMarketData()
    feed.set_snapshot(
        "AAPL",
        last_price=100.0,
        bid=99.9,
        ask=100.1,
        volume=25.5,
        prev_close=98.0,
        updated_at=_CLOCK,
    )
    store = TapeStore(tmp_path / "tape.ndjson", max_bytes=1_000_000, max_segments=2)
    recorder = TapeRecorder(market_data=feed, store=store, enabled=True, clock=lambda: _CLOCK)

    captured = await recorder.capture_once()
    original_lines = (tmp_path / "tape.ndjson").read_text(encoding="utf-8").splitlines()
    replayed_lines = [record.to_json_line() for record in store.replay()]

    assert [record.to_json_line() for record in captured] == original_lines
    assert replayed_lines == original_lines
    assert captured[0].session_phase is SessionPhase.PREMARKET


@pytest.mark.anyio
async def test_invalid_market_data_is_preserved_with_validity_flags(tmp_path):
    feed = _OrderFlowSpyMarketData()
    feed.set_snapshot(
        "BAD",
        last_price=math.nan,
        bid=-1.0,
        ask=2_000_000.0,
        volume=-5.0,
        prev_close=0.0,
        stale=True,
        updated_at=_CLOCK,
    )
    store = TapeStore(tmp_path / "tape.ndjson", max_bytes=1_000_000, max_segments=2)

    [record] = await TapeRecorder(
        market_data=feed, store=store, enabled=True, clock=lambda: _CLOCK
    ).capture_once()
    [replayed] = store.replay()

    assert record.validity.stale is True
    assert record.validity.last_price_finite is False
    assert record.validity.bid_positive is False
    assert record.validity.ask_in_range is False
    assert record.validity.volume_nonnegative is False
    assert record.validity.prev_close_positive is False
    assert math.isnan(replayed.snapshot.last_price)
    assert replayed.snapshot.bid == -1.0


def test_store_replaces_active_segment_when_only_one_is_retained(tmp_path):
    first_line = '{"sequence":1}\n'
    second_line = '{"sequence":2}\n'
    store = TapeStore(
        tmp_path / "tape.ndjson",
        max_bytes=len(first_line.encode("utf-8")),
        max_segments=1,
    )

    store.append_line(first_line)
    store.append_line(second_line)

    assert (tmp_path / "tape.ndjson").read_text(encoding="utf-8") == second_line
    assert (tmp_path / "tape.ndjson").stat().st_size <= store.max_bytes
    assert list(tmp_path.glob("tape.*.ndjson")) == []


def test_store_rotates_and_replaces_oldest_when_two_segments_are_retained(tmp_path):
    store = TapeStore(tmp_path / "tape.ndjson", max_bytes=1, max_segments=2)
    first_line = '{"sequence":1}\n'
    second_line = '{"sequence":2}\n'
    third_line = '{"sequence":3}\n'

    store.append_line(first_line)
    store.append_line(second_line)
    store.append_line(third_line)

    assert (tmp_path / "tape.ndjson").read_text(encoding="utf-8") == third_line
    assert (tmp_path / "tape.1.ndjson").read_text(encoding="utf-8") == second_line


def test_recorder_settings_are_off_by_default_and_parse_operational_values(monkeypatch):
    for env in (ENABLE_TAPE_RECORDER_ENV, TAPE_RECORDER_PATH_ENV, TAPE_RECORDER_SYMBOLS_ENV):
        monkeypatch.delenv(env, raising=False)

    defaults = load_settings()

    assert defaults.enable_tape_recorder is False
    assert defaults.tape_recorder_symbols == ()

    monkeypatch.setenv(ENABLE_TAPE_RECORDER_ENV, "true")
    monkeypatch.setenv(TAPE_RECORDER_PATH_ENV, "./data/tapes/pm.ndjson")
    monkeypatch.setenv(TAPE_RECORDER_SYMBOLS_ENV, "aapl, msft, AAPL")

    configured = load_settings()

    assert configured.enable_tape_recorder is True
    assert configured.tape_recorder_path == "./data/tapes/pm.ndjson"
    assert configured.tape_recorder_symbols == ("AAPL", "MSFT")
