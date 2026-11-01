import httpx
import pytest

from app.models.payment import Payment
from app.services.payment_service import (
    classify_payment_error,
    map_payment_status,
    payment_from_response,
)


def test_payment_from_response_links_order_to_provider_result():
    # Keep the merchant order ID separate from the provider payment ID.
    data = {"id": "pay_test_001", "status": "Authorized"}

    payment = payment_from_response("order_001", data)

    assert payment == Payment(
        order_id="order_001",
        payment_id="pay_test_001",
        status="authorized",
    )


@pytest.mark.parametrize("provider_status,local_status", [
    ("Authorized", "authorized"), ("Pending", "pending"), ("Declined", "declined"),
])
def test_map_payment_status(provider_status, local_status):
    # Authorization is recorded separately from capture.
    assert map_payment_status(provider_status) == local_status


@pytest.mark.parametrize("provider_status", ["Captured", "FutureStatus", "", "authorized"])
def test_unmapped_status_remains_unknown(provider_status):
    # Unimplemented mappings must not imply payment failure or success.
    assert map_payment_status(provider_status) == "unknown"


def test_payment_from_response_preserves_unknown_outcome():
    payment = payment_from_response(
        "order_001", {"id": "pay_test_001", "status": "FutureStatus"}
    )

    assert payment.status == "unknown"


@pytest.mark.parametrize("missing_field", ["id", "status"])
def test_payment_from_response_rejects_missing_required_field(missing_field):
    # Incomplete responses must not silently become local payment records.
    # This conversion error does not establish that the payment failed.
    data = {"id": "pay_test_001", "status": "Authorized"}
    del data[missing_field]

    with pytest.raises(KeyError) as exc_info:
        payment_from_response("order_001", data)

    assert exc_info.value.args == (missing_field,)


@pytest.mark.parametrize("field", ["id", "status"])
@pytest.mark.parametrize("value", [None, "", "   ", 123, [], {}])
def test_payment_from_response_rejects_invalid_required_value(field, value):
    data = {"id": "pay_test_001", "status": "Authorized", field: value}
    with pytest.raises(ValueError, match=field):
        payment_from_response("order_001", data)


@pytest.mark.parametrize("data", [None, [], "invalid"])
def test_payment_from_response_rejects_non_object(data):
    with pytest.raises(ValueError, match="object"):
        payment_from_response("order_001", data)


@pytest.mark.parametrize("status,kind,unknown", [
    (401, "authentication_error", False),
    (403, "permission_error", False),
    (422, "invalid_request", False),
    (429, "rate_limited", True),
    (408, "uncertain_outcome", True),
    (500, "uncertain_outcome", True),
    (502, "uncertain_outcome", True),
    (503, "uncertain_outcome", True),
    (504, "uncertain_outcome", True),
])
def test_http_error_decision_does_not_mark_payment_declined(status, kind, unknown):
    # Provider authentication errors describe our API access, not a card decline.
    request = httpx.Request("POST", "https://checkout.invalid/payments")
    response = httpx.Response(status, request=request, json={"secret": "private-body"})
    error = httpx.HTTPStatusError("private-error-detail", request=request, response=response)

    decision = classify_payment_error(error)

    assert decision.kind == kind
    assert decision.outcome_unknown is unknown
    assert "private" not in repr(decision)


@pytest.mark.parametrize("error_type", [httpx.ReadTimeout, httpx.ConnectTimeout, httpx.ConnectError])
def test_transport_error_requires_reconciliation(error_type):
    # Conservatively preserve uncertainty, even when delivery cannot be established.
    decision = classify_payment_error(error_type("private-error-detail"))
    assert decision.kind == "connection_error"
    assert decision.outcome_unknown is True
    assert "Reconcile" in decision.action
    assert "private" not in repr(decision)
