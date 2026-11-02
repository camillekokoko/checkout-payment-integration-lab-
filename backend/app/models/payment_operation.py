from dataclasses import dataclass
from typing import Literal


ActionType = Literal["Capture", "Void", "Refund"]


@dataclass(frozen=True)
class PaymentOperationResult:
    action_type: ActionType
    payment_id: str
    amount: int
    reference: str
    status: Literal["accepted", "rejected", "unknown"]
    action_id: str | None = None
    error_kind: str | None = None


@dataclass(frozen=True)
class PaymentOperationConfirmation:
    action_type: ActionType
    payment_id: str
    action_id: str | None
    amount: int
    status: Literal["succeeded", "failed", "unknown"]
    reason: str | None = None
