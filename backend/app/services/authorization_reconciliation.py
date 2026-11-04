from dataclasses import dataclass
import re
from typing import TYPE_CHECKING

from app.models.order import Order
from app.services.payment_service import map_payment_status
from app.services.reconciliation_retry import LookupRetryPolicy, LookupStopped, lookup_payment

if TYPE_CHECKING:
    from app.clients.checkout_client import CheckoutClient


@dataclass(frozen=True)
class AuthorizationReconciliation:
    """A read-only payment snapshot, never permission for another write."""

    status: str
    payment_id: str | None
    reason: str
    action: str


def reconcile_authorization(
    client: "CheckoutClient | None", order: Order, *, payment_id: str | None = None,
    retry_policy: LookupRetryPolicy | None = None,
) -> AuthorizationReconciliation:
    """Read a known payment after uncertainty; optional retries apply only to GET.

    No token or idempotency key is needed for a read. The caller supplies trusted
    order data and a payment ID associated with the original operation, not an
    arbitrary matching payment. Reference/amount/currency checks catch mismatches,
    but cannot prove the provider's idempotency-key association. No-ID recovery
    remains manual; a reference is not a unique payment identity.
    """
    def unresolved(reason: str) -> AuthorizationReconciliation:
        return AuthorizationReconciliation(
            "unknown", payment_id, reason,
            "Stop writes; investigate the original operation. Do not replace its key.",
        )

    if not isinstance(order.id, str) or not order.id.strip() or len(order.id) > 80:
        raise ValueError("order_id must be a nonblank string of at most 80 characters")
    if type(order.amount) is not int or order.amount <= 0:
        raise ValueError("amount must be a positive integer in minor units")
    if order.currency != "AUD":
        raise ValueError("currency must be AUD")
    if payment_id is None:
        return unresolved("missing_payment_id")
    if not isinstance(payment_id, str) or re.fullmatch(r"pay_[A-Za-z0-9_]{26}", payment_id) is None:
        raise ValueError("payment_id must be a valid Sandbox payment identifier")
    if client is None:
        raise ValueError("client is required for a payment lookup")
    try:
        response = lookup_payment(client, payment_id, retry_policy or LookupRetryPolicy())
    except LookupStopped as error:
        # Even a 404 is a failed lookup, not evidence the original POST failed.
        return unresolved(str(error))
    if response.status_code != 200:
        return unresolved("unexpected_lookup_status")
    try:
        data = response.json()
    except ValueError:
        return unresolved("invalid_lookup_response")
    if not isinstance(data, dict):
        return unresolved("invalid_lookup_response")
    if (
        data.get("id") != payment_id
        or data.get("reference") != order.id
        or type(data.get("amount")) is not int
        or data["amount"] != order.amount
        or data.get("currency") != order.currency
    ):
        return unresolved("payment_mismatch")
    provider_status = data.get("status")
    if not isinstance(provider_status, str):
        return unresolved("invalid_lookup_response")
    status = map_payment_status(provider_status)
    if status == "unknown":
        return unresolved("unrecognized_payment_status")
    if status == "pending":
        return AuthorizationReconciliation(
            status, payment_id, "payment_pending",
            "Wait for further evidence; do not submit another authorization.",
        )
    return AuthorizationReconciliation(
        status, payment_id, "payment_snapshot_observed",
        "Use the observed payment lifecycle for the next business decision; "
        "do not repeat the original authorization. This does not prove settlement.",
    )
