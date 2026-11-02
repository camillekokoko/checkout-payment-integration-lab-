from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class CaptureResult:
    """An in-memory request outcome, never proof of completed capture."""

    payment_id: str
    amount: int
    reference: str
    status: Literal["accepted", "rejected", "unknown"]
    action_id: str | None = None
    error_kind: str | None = None


@dataclass(frozen=True)
class CaptureConfirmation:
    """Provider evidence for one capture action, not settlement confirmation."""

    payment_id: str
    action_id: str | None
    amount: int
    status: Literal["succeeded", "failed", "unknown"]
    reason: str | None = None
