"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Request

from app.approval.gate import ApprovalGate
from app.store.base import StateStore


def get_store(request: Request) -> StateStore:
    """The single process-wide StateStore, created at startup (see main.py)."""

    return request.app.state.store


def get_approval_gate(request: Request) -> ApprovalGate:
    """The process-wide Approval Gate, constructed at startup (see main.py)."""

    return request.app.state.approval_gate
