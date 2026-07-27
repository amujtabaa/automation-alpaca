"""Bounded, append-only NDJSON storage for WO-0123 market-data tapes."""

from __future__ import annotations

from pathlib import Path

from app.recorder.models import TapeRecord


class TapeStore:
    """A separate rotating store; it never touches execution or event-log truth."""

    def __init__(self, path: Path, *, max_bytes: int, max_segments: int) -> None:
        if max_bytes < 1:
            raise ValueError("max_bytes must be at least one")
        if max_segments < 1:
            raise ValueError("max_segments must be at least one")
        self.path = path
        self.max_bytes = max_bytes
        self.max_segments = max_segments

    def _archive_path(self, segment: int) -> Path:
        return self.path.with_name(f"{self.path.stem}.{segment}{self.path.suffix}")

    def _rotate(self) -> None:
        for segment in range(self.max_segments - 1, 0, -1):
            source = self.path if segment == 1 else self._archive_path(segment - 1)
            destination = self._archive_path(segment)
            if source.exists():
                destination.unlink(missing_ok=True)
                source.replace(destination)

    def append_line(self, line: str) -> None:
        """Append one canonical line, rotating before the active segment grows."""
        if not line.endswith("\n"):
            line = f"{line}\n"
        encoded = line.encode("utf-8")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        write_mode = "a"
        if self.path.exists() and self.path.stat().st_size + len(encoded) > self.max_bytes:
            if self.max_segments == 1:
                write_mode = "w"
            else:
                self._rotate()
        with self.path.open(write_mode, encoding="utf-8", newline="\n") as tape:
            tape.write(line)

    def append(self, record: TapeRecord) -> None:
        self.append_line(record.to_json_line())

    def replay(self) -> list[TapeRecord]:
        """Read retained tape segments from oldest to newest without mutation."""
        records: list[TapeRecord] = []
        paths = [self._archive_path(index) for index in range(self.max_segments - 1, 0, -1)]
        paths.append(self.path)
        for path in paths:
            if not path.exists():
                continue
            for line in path.read_text(encoding="utf-8").splitlines():
                if line:
                    records.append(TapeRecord.from_json_line(line))
        return records
