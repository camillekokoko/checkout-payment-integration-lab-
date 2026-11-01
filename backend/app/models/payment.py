from dataclasses import dataclass

@dataclass(frozen=True)
class Payment:
    order_id: str
    payment_id: str
    status: str  # Local status, e.g. "authorized"; not a settlement confirmation.
