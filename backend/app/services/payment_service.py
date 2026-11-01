from dataclasses import dataclass

import httpx

from app.models.payment import Payment


def payment_from_response(order_id: str, data: dict) -> Payment:
    if not isinstance(data, dict):
        raise ValueError("Payment response must be an object")
    for field in ("id", "status"):
        if not isinstance(data[field], str) or not data[field].strip():
            raise ValueError(f"Payment response {field} must be a nonblank string")
    return Payment(
        order_id=order_id,
        payment_id=data["id"],
        status=map_payment_status(data["status"]),
    )


def map_payment_status(provider_status: str) -> str:
    # This maps a snapshot, not a state transition or an order fulfilment decision.
    return {
        "Pending": "pending",
        "Authorized": "authorized",
        "Declined": "declined",
    }.get(provider_status, "unknown")


@dataclass(frozen=True)
class PaymentErrorDecision:
    kind: str
    action: str
    outcome_unknown: bool


def classify_payment_error(
    error: httpx.HTTPStatusError | httpx.RequestError,
) -> PaymentErrorDecision:
    """Return operator guidance without retrying or declaring a payment declined.

    outcome_unknown describes this request's result, not earlier payment attempts.
    Decisions contain no provider bodies, credentials, or request URLs.
    """
    if isinstance(error, httpx.RequestError):
        return PaymentErrorDecision(
            "connection_error", "Reconcile the payment before any new attempt.", True
        )
    status = error.response.status_code
    if status == 401:
        return PaymentErrorDecision(
            "authentication_error", "Check server-side Sandbox credentials.", False
        )
    if status == 403:
        return PaymentErrorDecision(
            "permission_error", "Check API key scopes and account permissions.", False
        )
    if status == 422:
        return PaymentErrorDecision(
            "invalid_request", "Correct the request configuration or payload.", False
        )
    if status == 429:
        return PaymentErrorDecision(
            "rate_limited", "Stop requests; apply the M4 retry and reconciliation policy.", True
        )
    return PaymentErrorDecision(
        "uncertain_outcome", "Reconcile the payment before any new attempt.", True
    )
