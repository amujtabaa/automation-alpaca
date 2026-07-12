"""The pure sell-side policy package (ADR-010 §1/D-4, WO-0018).

Everything here is a pure function of ``(envelope, snapshot tape, injected
clock value, prior envelope events)`` — no IO, no global state, no clock
reads. The engine seam (WO-0019) re-validates every plan against the same
:func:`app.sellside.policy.validate_action` at write time (D-3: bounds
checked twice; disagreement is a defect signal, not merely a breach).

Numeric constants in this package are MECHANISM parameters (windows,
quantiles, multiples) distilled from ``pkl/architecture/sellside-research-
notes.md``; which values actually pay is an empirical question for the W4
replay harness — tune there, not here.
"""

from app.sellside.policy import decide, validate_action  # noqa: F401
from app.sellside.regime import Regime  # noqa: F401
from app.sellside.types import (  # noqa: F401
    ActionKind,
    BreachSignal,
    ExhaustedSignal,
    ExpiredSignal,
    NoAction,
    NoActionReason,
    PlannedAction,
    StaleDataSignal,
)
