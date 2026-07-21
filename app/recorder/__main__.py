"""Run the recorder intentionally: ``python -m app.recorder``."""

from __future__ import annotations

import asyncio

from app.config import load_settings
from app.recorder.runner import run_tape_recorder


def main() -> None:
    asyncio.run(run_tape_recorder(load_settings()))


if __name__ == "__main__":
    main()
