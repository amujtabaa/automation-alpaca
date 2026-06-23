"""Approval Gate package — the pluggable candidate→order decision seam (D-004).

Beta exposes one mode (human-in-the-loop). The interface lives in
:mod:`app.approval.gate`; the human implementation in :mod:`app.approval.human`.
"""

from __future__ import annotations

from app.approval.gate import ApprovalGate, GateDecision
from app.approval.human import HumanApprovalGate

__all__ = ["ApprovalGate", "GateDecision", "HumanApprovalGate"]
