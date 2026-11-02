import re
from typing import TYPE_CHECKING

import httpx

from app.models.capture import CaptureConfirmation, CaptureResult
from app.services.payment_service import classify_payment_error

if TYPE_CHECKING:
    from app.clients.checkout_client import CheckoutClient


def capture_authorized_payment(
    client: "CheckoutClient", payment_id: str, amount: int, reference: str
) -> CaptureResult:
    """Look up an AUD payment and request its first, full capture once.

    Lookup errors and eligibility failures stop before POST. Once POST is
    attempted, transport errors and ambiguous responses produce an unknown
    outcome. No retry, persistence, polling, or merchant authorization is added.
    Lookup is only a snapshot: it cannot prevent concurrent capture requests.
    """
    # Validate before GET too: malformed IDs must never be interpolated into URLs.
    if not isinstance(payment_id, str) or re.fullmatch(r"pay_[A-Za-z0-9_]{26}", payment_id) is None:
        raise ValueError("payment_id is missing or invalid")
    if type(amount) is not int or not 0 < amount <= 9999999999:
        raise ValueError("amount must be a positive integer of at most 9999999999 minor units")
    if not isinstance(reference, str) or not reference.strip() or len(reference) > 80:
        raise ValueError("reference must be a nonblank string of at most 80 characters")

    # GET /payments/{id}: use provider balances, not the original order amount.
    lookup = client.get_payment(payment_id)
    if lookup.status_code != 200:
        raise ValueError("Unexpected payment lookup response; no capture submitted")
    try:
        data = lookup.json()
    except ValueError:
        raise ValueError("Invalid payment lookup response; no capture submitted") from None
    _validate_full_capture(data, payment_id, amount)

    try:
        response = client.capture_payment(payment_id, amount, reference)
    except (httpx.HTTPStatusError, httpx.RequestError) as error:
        decision = classify_payment_error(error)
        return CaptureResult(
            payment_id, amount, reference,
            "unknown" if decision.outcome_unknown else "rejected",
            error_kind=decision.kind,
        )

    # 202 accepts an asynchronous action; it does not confirm funds were captured.
    if response.status_code == 202:
        try:
            body = response.json()
        except ValueError:
            body = None
        action_id = body.get("action_id") if isinstance(body, dict) else None
        if isinstance(action_id, str) and re.fullmatch(r"act_[A-Za-z0-9_]{26}", action_id):
            return CaptureResult(payment_id, amount, reference, "accepted", action_id=action_id)

    # A malformed acknowledgement may still follow an accepted capture. Do not retry.
    return CaptureResult(
        payment_id, amount, reference, "unknown", error_kind="invalid_capture_response"
    )


def confirm_capture(client: "CheckoutClient", capture: CaptureResult) -> CaptureConfirmation:
    """Read actions once and match the exact capture; never issue another POST.

    Missing evidence is unknown, not a failed capture. Without an action ID,
    leave reconciliation to a caller with additional provider evidence.
    """
    if not isinstance(capture.payment_id, str) or re.fullmatch(
        r"pay_[A-Za-z0-9_]{26}", capture.payment_id
    ) is None:
        raise ValueError("payment_id is missing or invalid")
    if type(capture.amount) is not int or not 0 < capture.amount <= 9999999999:
        raise ValueError("capture amount is missing or invalid")

    def unknown(reason: str) -> CaptureConfirmation:
        return CaptureConfirmation(
            capture.payment_id, capture.action_id, capture.amount, "unknown", reason
        )

    if capture.action_id is None:
        return unknown("missing_action_id")
    if not isinstance(capture.action_id, str) or re.fullmatch(
        r"act_[A-Za-z0-9_]{26}", capture.action_id
    ) is None:
        raise ValueError("action_id is invalid")
    try:
        response = client.get_payment_actions(capture.payment_id)
    except (httpx.HTTPStatusError, httpx.RequestError):
        # A failed read says nothing about whether the prior capture succeeded.
        return unknown("lookup_failed")
    if response.status_code != 200:
        return unknown("invalid_actions_response")
    try:
        actions = response.json()
    except ValueError:
        return unknown("invalid_actions_response")
    if not isinstance(actions, list) or any(not isinstance(action, dict) for action in actions):
        return unknown("invalid_actions_response")
    matches = [action for action in actions if action.get("id") == capture.action_id]
    if not matches:
        return unknown("action_not_found")
    if len(matches) != 1:
        return unknown("duplicate_action_id")
    action = matches[0]
    if (
        action.get("type") != "Capture"
        or type(action.get("amount")) is not int
        or action["amount"] != capture.amount
    ):
        return unknown("action_mismatch")
    if type(action.get("approved")) is not bool:
        return unknown("approval_unconfirmed")
    return CaptureConfirmation(
        capture.payment_id, capture.action_id, capture.amount,
        "succeeded" if action["approved"] else "failed",
    )


def _validate_full_capture(data: object, payment_id: str, amount: int) -> None:
    if not isinstance(data, dict) or data.get("id") != payment_id:
        raise ValueError("Payment lookup ID mismatch or invalid response")
    if data.get("status") != "Authorized":
        raise ValueError("Payment must be Authorized for this capture flow")
    if data.get("currency") != "AUD":
        raise ValueError("Payment currency must be AUD")
    balances = data.get("balances")
    if not isinstance(balances, dict):
        raise ValueError("Payment balances are missing or invalid")
    for field in ("total_authorized", "total_captured", "total_voided", "available_to_capture"):
        value = balances.get(field)
        if type(value) is not int or value < 0:
            raise ValueError("Payment balances must contain nonnegative integers")
    if balances["total_captured"] != 0 or balances["total_voided"] != 0:
        raise ValueError("This flow requires no previous capture or void")
    available = balances["available_to_capture"]
    if available <= 0 or amount > available:
        raise ValueError("Capture amount exceeds the remaining capturable amount")
    if amount != available or amount != balances["total_authorized"]:
        raise ValueError("This flow supports only the first full capture")
