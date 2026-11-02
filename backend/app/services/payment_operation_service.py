import re
from typing import TYPE_CHECKING, Callable

import httpx

from app.models.payment_operation import (
    ActionType, PaymentOperationConfirmation, PaymentOperationResult,
)
from app.services.payment_service import classify_payment_error

if TYPE_CHECKING:
    from app.clients.checkout_client import CheckoutClient


def capture_payment_amount(
    client: "CheckoutClient", payment_id: str, amount: int, reference: str, *, final: bool = False
) -> PaymentOperationResult:
    """Capture part of an AUD card authorization, or close its remaining balance.

    NonFinal deliberately leaves the remainder open. Final must consume all
    remaining availability in this merchant policy, avoiding an implicit void.
    """
    _validate_input(payment_id, amount, reference)
    if type(final) is not bool:
        raise ValueError("final must be a boolean")
    data = _lookup_card_payment(client, payment_id, reference)
    if data.get("status") not in ("Authorized", "Partially Captured"):
        raise ValueError("Payment is not eligible for capture")
    balances = _balances(data, "total_authorized", "total_captured", "total_voided", "available_to_capture")
    available = balances["available_to_capture"]
    if balances["total_authorized"] != balances["total_captured"] + balances["total_voided"] + available:
        raise ValueError("Capture balances are inconsistent or awaiting reconciliation")
    if available <= 0 or amount > available:
        raise ValueError("Capture amount exceeds availability")
    if final and amount != available:
        raise ValueError("Final capture must consume the remaining available balance")
    if not final and amount >= available:
        raise ValueError("NonFinal capture must be smaller than availability; use final for the remainder")
    return _submit("Capture", payment_id, amount, reference, lambda: client.capture_payment(
        payment_id, amount, reference, capture_type="Final" if final else "NonFinal"
    ))


def void_authorized_payment(
    client: "CheckoutClient", payment_id: str, amount: int, reference: str
) -> PaymentOperationResult:
    """Release all remaining authorization before any capture; this is not a refund."""
    _validate_input(payment_id, amount, reference)
    data = _lookup_card_payment(client, payment_id, reference)
    if data.get("status") != "Authorized":
        raise ValueError("Only an Authorized payment can use this void flow")
    balances = _balances(data, "total_authorized", "total_captured", "total_voided", "available_to_void")
    if balances["total_captured"] != 0:
        raise ValueError("Captured funds cannot use this void flow")
    available = balances["available_to_void"]
    if available <= 0 or available != balances["total_authorized"] - balances["total_voided"]:
        raise ValueError("Void balances are unavailable or inconsistent")
    if amount != available:
        raise ValueError("This flow voids the full remaining authorization")
    return _submit("Void", payment_id, amount, reference, lambda: client.void_payment(payment_id, amount, reference))


def refund_captured_payment(
    client: "CheckoutClient", payment_id: str, amount: int, reference: str
) -> PaymentOperationResult:
    """Refund captured AUD card funds, in full or in part, within provider availability."""
    _validate_input(payment_id, amount, reference)
    data = _lookup_card_payment(client, payment_id, reference)
    if data.get("status") not in ("Captured", "Partially Captured", "Partially Refunded"):
        raise ValueError("Payment is not eligible for refund")
    balances = _balances(data, "total_captured", "total_refunded", "available_to_refund")
    available = balances["available_to_refund"]
    unrefunded = balances["total_captured"] - balances["total_refunded"]
    if available <= 0 or available > unrefunded or amount > available:
        raise ValueError("Refund amount exceeds availability or balances are inconsistent")
    return _submit("Refund", payment_id, amount, reference, lambda: client.refund_payment(payment_id, amount, reference))


def confirm_payment_operation(
    client: "CheckoutClient", operation: PaymentOperationResult
) -> PaymentOperationConfirmation:
    """Read one action snapshot; no polling, writes, or inference from another action."""
    _validate_identifiers(operation.payment_id, operation.amount)
    if operation.action_type not in ("Capture", "Void", "Refund"):
        raise ValueError("Unsupported action type")

    def unknown(reason: str) -> PaymentOperationConfirmation:
        return PaymentOperationConfirmation(
            operation.action_type, operation.payment_id, operation.action_id,
            operation.amount, "unknown", reason,
        )

    if operation.action_id is None:
        return unknown("missing_action_id")
    if not isinstance(operation.action_id, str) or re.fullmatch(r"act_[A-Za-z0-9_]{26}", operation.action_id) is None:
        raise ValueError("action_id is invalid")
    try:
        response = client.get_payment_actions(operation.payment_id)
    except (httpx.HTTPStatusError, httpx.RequestError):
        return unknown("lookup_failed")
    if response.status_code != 200:
        return unknown("invalid_actions_response")
    try:
        actions = response.json()
    except ValueError:
        return unknown("invalid_actions_response")
    if not isinstance(actions, list) or any(not isinstance(action, dict) for action in actions):
        return unknown("invalid_actions_response")
    matches = [action for action in actions if action.get("id") == operation.action_id]
    if not matches:
        return unknown("action_not_found")
    if len(matches) != 1:
        return unknown("duplicate_action_id")
    action = matches[0]
    if action.get("type") != operation.action_type or type(action.get("amount")) is not int or action["amount"] != operation.amount:
        return unknown("action_mismatch")
    if type(action.get("approved")) is not bool:
        return unknown("approval_unconfirmed")
    return PaymentOperationConfirmation(
        operation.action_type, operation.payment_id, operation.action_id,
        operation.amount, "succeeded" if action["approved"] else "failed",
    )


def _validate_identifiers(payment_id: str, amount: int) -> None:
    if not isinstance(payment_id, str) or re.fullmatch(r"pay_[A-Za-z0-9_]{26}", payment_id) is None:
        raise ValueError("payment_id is missing or invalid")
    if type(amount) is not int or not 0 < amount <= 9999999999:
        raise ValueError("amount must be a positive integer of at most 9999999999 minor units")


def _validate_input(payment_id: str, amount: int, reference: str) -> None:
    _validate_identifiers(payment_id, amount)
    if not isinstance(reference, str) or not reference.strip() or len(reference) > 80:
        raise ValueError("reference must be a nonblank string of at most 80 characters")


def _lookup_card_payment(client: "CheckoutClient", payment_id: str, reference: str) -> dict:
    # Fail before POST on missing or inconsistent evidence. Never guess a balance.
    response = client.get_payment(payment_id)
    if response.status_code != 200:
        raise ValueError("Unexpected payment lookup response")
    data = response.json()
    if not isinstance(data, dict) or data.get("id") != payment_id or data.get("currency") != "AUD":
        raise ValueError("Payment lookup must match an AUD payment")
    source = data.get("source")
    if not isinstance(source, dict) or source.get("type") != "card":
        raise ValueError("These operation flows support card payments only")
    if source.get("scheme") in ("Amex", "AMEX", "American Express") and len(reference) > 30:
        raise ValueError("Amex operation reference must be at most 30 characters")
    return data


def _balances(data: dict, *fields: str) -> dict:
    balances = data.get("balances")
    if not isinstance(balances, dict) or any(type(balances.get(field)) is not int or balances[field] < 0 for field in fields):
        raise ValueError("Required balances must be nonnegative integers")
    return balances


def _submit(
    action_type: ActionType, payment_id: str, amount: int, reference: str,
    send: Callable[[], httpx.Response],
) -> PaymentOperationResult:
    # This shared path is justified by identical acknowledgment/error semantics.
    try:
        response = send()
    except (httpx.HTTPStatusError, httpx.RequestError) as error:
        decision = classify_payment_error(error)
        return PaymentOperationResult(
            action_type, payment_id, amount, reference,
            "unknown" if decision.outcome_unknown else "rejected", error_kind=decision.kind,
        )
    if response.status_code == 202:
        try:
            body = response.json()
        except ValueError:
            body = None
        action_id = body.get("action_id") if isinstance(body, dict) else None
        if isinstance(action_id, str) and re.fullmatch(r"act_[A-Za-z0-9_]{26}", action_id):
            return PaymentOperationResult(action_type, payment_id, amount, reference, "accepted", action_id)
    # Even 200 "already ..." is not proof that this specific request created an action.
    return PaymentOperationResult(action_type, payment_id, amount, reference, "unknown", error_kind="invalid_operation_response")
