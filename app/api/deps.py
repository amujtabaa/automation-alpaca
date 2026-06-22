"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Request

from app.store.base import StateStore


def get_store(request: Request) -> StateStore:
    """The single process-wide StateStore, created at startup (see main.py)."""

    return request.app.state.store
