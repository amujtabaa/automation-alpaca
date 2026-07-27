"""Deterministic, JSON-safe tape records for observed market-data snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timezone
import json
import math
from typing import Any
from zoneinfo import ZoneInfo

from app.marketdata.service import MarketSnapshot


SCHEMA_VERSION = 1
MAX_OBSERVED_PRICE = 1_000_000.0
_NEW_YORK = ZoneInfo("America/New_York")


class SessionPhase(str):
    """Market-session taxonomy retained with every raw snapshot."""

    PREMARKET = "premarket"
    REGULAR = "regular"
    AFTER_HOURS = "after_hours"
    CLOSED = "closed"


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("tape timestamps must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _json_number(value: float | None) -> float | str | None:
    if value is None or math.isfinite(value):
        return value
    if math.isnan(value):
        return "NaN"
    return "Infinity" if value > 0 else "-Infinity"


def _python_number(value: float | str | None) -> float | None:
    if value is None or isinstance(value, float):
        return value
    special = {"NaN": math.nan, "Infinity": math.inf, "-Infinity": -math.inf}
    if value in special:
        return special[value]
    raise ValueError(f"unrecognized encoded tape number: {value!r}")


def _positive_finite(value: float | None) -> bool:
    return value is not None and math.isfinite(value) and value > 0.0


def session_phase(observed_at: datetime) -> str:
    """Classify an observed timestamp without consulting external calendars."""
    local = observed_at.astimezone(_NEW_YORK)
    if local.weekday() >= 5:
        return SessionPhase.CLOSED
    current = local.timetz().replace(tzinfo=None)
    if time(4, 0) <= current < time(9, 30):
        return SessionPhase.PREMARKET
    if time(9, 30) <= current < time(16, 0):
        return SessionPhase.REGULAR
    if time(16, 0) <= current < time(20, 0):
        return SessionPhase.AFTER_HOURS
    return SessionPhase.CLOSED


@dataclass(frozen=True)
class SnapshotValidity:
    """Explicit validity flags: bad input is retained rather than filtered away."""

    stale: bool
    last_price_finite: bool
    bid_positive: bool
    ask_in_range: bool
    volume_nonnegative: bool
    prev_close_positive: bool

    @classmethod
    def from_snapshot(cls, snapshot: MarketSnapshot) -> SnapshotValidity:
        return cls(
            stale=snapshot.stale,
            last_price_finite=(
                snapshot.last_price is not None and math.isfinite(snapshot.last_price)
            ),
            bid_positive=_positive_finite(snapshot.bid),
            ask_in_range=(
                _positive_finite(snapshot.ask)
                and snapshot.ask is not None
                and snapshot.ask <= MAX_OBSERVED_PRICE
            ),
            volume_nonnegative=(
                snapshot.volume is not None
                and math.isfinite(snapshot.volume)
                and snapshot.volume >= 0.0
            ),
            prev_close_positive=_positive_finite(snapshot.prev_close),
        )


@dataclass(frozen=True)
class TapeRecord:
    """One append-only observed snapshot, encoded canonically for replay."""

    observed_at: datetime
    session_phase: str
    snapshot: MarketSnapshot
    validity: SnapshotValidity

    @classmethod
    def capture(cls, snapshot: MarketSnapshot, *, observed_at: datetime) -> TapeRecord:
        return cls(
            observed_at=observed_at,
            session_phase=session_phase(observed_at),
            snapshot=snapshot,
            validity=SnapshotValidity.from_snapshot(snapshot),
        )

    def _payload(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "observed_at": _timestamp(self.observed_at),
            "session_phase": self.session_phase,
            "snapshot": {
                "symbol": self.snapshot.symbol,
                "last_price": _json_number(self.snapshot.last_price),
                "bid": _json_number(self.snapshot.bid),
                "ask": _json_number(self.snapshot.ask),
                "volume": _json_number(self.snapshot.volume),
                "prev_close": _json_number(self.snapshot.prev_close),
                "updated_at": _timestamp(self.snapshot.updated_at),
                "stale": self.snapshot.stale,
            },
            "validity": {
                "stale": self.validity.stale,
                "last_price_finite": self.validity.last_price_finite,
                "bid_positive": self.validity.bid_positive,
                "ask_in_range": self.validity.ask_in_range,
                "volume_nonnegative": self.validity.volume_nonnegative,
                "prev_close_positive": self.validity.prev_close_positive,
            },
        }

    def to_json_line(self) -> str:
        """Canonical line form, stable across replay and suitable for byte checks."""
        return json.dumps(
            self._payload(), allow_nan=False, separators=(",", ":"), sort_keys=True
        )

    @classmethod
    def from_json_line(cls, line: str) -> TapeRecord:
        payload = json.loads(line)
        if payload.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(f"unsupported tape schema version: {payload.get('schema_version')!r}")
        raw_snapshot = payload["snapshot"]
        snapshot = MarketSnapshot(
            symbol=raw_snapshot["symbol"],
            last_price=_python_number(raw_snapshot["last_price"]),
            bid=_python_number(raw_snapshot["bid"]),
            ask=_python_number(raw_snapshot["ask"]),
            volume=_python_number(raw_snapshot["volume"]),
            prev_close=_python_number(raw_snapshot["prev_close"]),
            updated_at=_parse_timestamp(raw_snapshot["updated_at"]),
            stale=raw_snapshot["stale"],
        )
        validity = SnapshotValidity(**payload["validity"])
        return cls(
            observed_at=_parse_timestamp(payload["observed_at"]),
            session_phase=payload["session_phase"],
            snapshot=snapshot,
            validity=validity,
        )
