from copy import deepcopy
from unittest.mock import Mock

import httpx
import pytest

from app.clients.checkout_client import CheckoutClient
from app.services.capture_service import capture_authorized_payment


PAYMENT_ID = "pay_" + "a" * 26
ACTION_ID = "act_" + "b" * 26
REFERENCE = "capture_order_001"
BASE_URL = "https://test.api.sandbox.checkout.com"


def response(method, status, data):
    return httpx.Response(
        status, json=data, request=httpx.Request(method, BASE_URL + "/payments/" + PAYMENT_ID)
    )


@pytest.fixture
def authorized_payment():
    return {
        "id": PAYMENT_ID, "status": "Authorized", "currency": "AUD",
        # Deliberately differs: the service must use balances, not this field.
        "amount": 2000,
        "balances": {
            "total_authorized": 1000, "total_captured": 0,
            "total_voided": 0, "available_to_capture": 1000,
        },
    }


@pytest.fixture
def flow(monkeypatch, authorized_payment):
    monkeypatch.setenv("PYTHON_DOTENV_DISABLED", "1")
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "sk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_BASE_URL", BASE_URL)
    get = Mock(return_value=response("GET", 200, authorized_payment))
    post = Mock(return_value=response("POST", 202, {"action_id": ACTION_ID}))
    monkeypatch.setattr(httpx, "get", get)
    monkeypatch.setattr(httpx, "post", post)
    return CheckoutClient(), get, post


def test_merchant_requests_full_capture_after_fresh_lookup(flow):
    client, get, post = flow
    calls = Mock()
    calls.attach_mock(get, "lookup")
    calls.attach_mock(post, "capture")

    result = capture_authorized_payment(client, PAYMENT_ID, 1000, REFERENCE)

    assert [call[0] for call in calls.mock_calls] == ["lookup", "capture"]
    get.assert_called_once_with(
        f"{BASE_URL}/payments/{PAYMENT_ID}",
        headers={"Authorization": "Bearer sk_sbox_fake"}, timeout=10.0,
    )
    post.assert_called_once_with(
        f"{BASE_URL}/payments/{PAYMENT_ID}/captures",
        headers={"Authorization": "Bearer sk_sbox_fake", "Content-Type": "application/json"},
        json={"amount": 1000, "reference": REFERENCE}, timeout=10.0,
    )
    assert result.payment_id == PAYMENT_ID
    assert result.amount == 1000
    assert result.reference == REFERENCE
    assert result.status == "accepted"  # Never "captured": asynchronous request.
    assert result.action_id == ACTION_ID
    assert result.error_kind is None


@pytest.mark.parametrize("amount", [500, 1001])
def test_partial_or_excessive_capture_is_blocked(flow, amount):
    client, get, post = flow
    with pytest.raises(ValueError):
        capture_authorized_payment(client, PAYMENT_ID, amount, REFERENCE)
    get.assert_called_once()
    post.assert_not_called()


@pytest.mark.parametrize("field,value", [
    ("payment_id", "pay_short"), ("payment_id", PAYMENT_ID + "/captures"),
    ("amount", True), ("amount", 0), ("amount", 1000.0), ("amount", 10000000000),
    ("reference", " "), ("reference", "r" * 81),
])
def test_bad_input_stops_before_lookup(flow, field, value):
    client, get, post = flow
    arguments = {"payment_id": PAYMENT_ID, "amount": 1000, "reference": REFERENCE}
    arguments[field] = value
    with pytest.raises(ValueError):
        capture_authorized_payment(client, **arguments)
    get.assert_not_called()
    post.assert_not_called()


@pytest.mark.parametrize("field,value", [
    ("status", "Pending"), ("status", "Declined"), ("status", "Captured"),
    ("status", "Partially Captured"), ("status", "Voided"), ("status", "FutureStatus"),
    ("currency", "USD"), ("id", "pay_" + "c" * 26),
])
def test_ineligible_or_mismatched_payment_sends_no_capture(flow, authorized_payment, field, value):
    client, get, post = flow
    authorized_payment[field] = value
    get.return_value = response("GET", 200, authorized_payment)
    with pytest.raises(ValueError):
        capture_authorized_payment(client, PAYMENT_ID, 1000, REFERENCE)
    post.assert_not_called()


@pytest.mark.parametrize("field,value", [
    ("available_to_capture", 0), ("available_to_capture", 500),
    ("available_to_capture", 1500), ("available_to_capture", None),
    ("available_to_capture", True), ("available_to_capture", "1000"),
    ("available_to_capture", -1), ("available_to_capture", 1000.0),
    ("total_captured", 500), ("total_voided", 500),
    ("total_authorized", 2000), ("total_captured", None),
])
def test_inconsistent_or_previously_used_balance_sends_no_capture(flow, authorized_payment, field, value):
    client, get, post = flow
    authorized_payment["balances"][field] = value
    get.return_value = response("GET", 200, authorized_payment)
    with pytest.raises(ValueError):
        capture_authorized_payment(client, PAYMENT_ID, 1000, REFERENCE)
    post.assert_not_called()


@pytest.mark.parametrize("missing_field", ["id", "status", "currency", "balances"])
def test_missing_lookup_field_sends_no_capture(flow, authorized_payment, missing_field):
    client, get, post = flow
    data = deepcopy(authorized_payment)
    del data[missing_field]
    get.return_value = response("GET", 200, data)
    with pytest.raises(ValueError):
        capture_authorized_payment(client, PAYMENT_ID, 1000, REFERENCE)
    post.assert_not_called()


def test_malformed_lookup_json_sends_no_capture(flow):
    client, get, post = flow
    get.return_value = httpx.Response(200, content=b"invalid-json", request=httpx.Request("GET", BASE_URL))
    with pytest.raises(ValueError, match="Invalid payment lookup"):
        capture_authorized_payment(client, PAYMENT_ID, 1000, REFERENCE)
    post.assert_not_called()


@pytest.mark.parametrize("status", [401, 403, 404, 503])
def test_lookup_http_error_stops_without_retry_or_capture(flow, status):
    client, get, post = flow
    get.return_value = response("GET", status, {})
    with pytest.raises(httpx.HTTPStatusError):
        capture_authorized_payment(client, PAYMENT_ID, 1000, REFERENCE)
    get.assert_called_once()
    post.assert_not_called()


def test_lookup_timeout_does_not_submit_capture(flow):
    client, get, post = flow
    get.side_effect = httpx.ReadTimeout("Simulated lookup timeout")
    with pytest.raises(httpx.ReadTimeout):
        capture_authorized_payment(client, PAYMENT_ID, 1000, REFERENCE)
    get.assert_called_once()
    post.assert_not_called()


@pytest.mark.parametrize("status,expected,kind", [
    (401, "rejected", "authentication_error"), (403, "rejected", "permission_error"),
    (422, "rejected", "invalid_request"), (409, "unknown", "uncertain_outcome"),
    (429, "unknown", "rate_limited"), (500, "unknown", "uncertain_outcome"),
    (502, "unknown", "uncertain_outcome"), (503, "unknown", "uncertain_outcome"),
    (504, "unknown", "uncertain_outcome"),
])
def test_capture_http_error_becomes_request_outcome_without_retry(flow, status, expected, kind):
    client, _, post = flow
    post.return_value = response("POST", status, {"private": "never expose this"})
    result = capture_authorized_payment(client, PAYMENT_ID, 1000, REFERENCE)
    assert result.status == expected
    assert result.error_kind == kind
    assert result.action_id is None
    assert "private" not in repr(result)
    post.assert_called_once()


@pytest.mark.parametrize("error_type", [httpx.ReadTimeout, httpx.ConnectError])
def test_capture_transport_error_keeps_outcome_unknown(flow, error_type):
    client, _, post = flow
    post.side_effect = error_type("private transport detail")
    result = capture_authorized_payment(client, PAYMENT_ID, 1000, REFERENCE)
    assert result.status == "unknown"
    assert result.error_kind == "connection_error"
    assert "private" not in repr(result)
    post.assert_called_once()


@pytest.mark.parametrize("status,body", [
    (202, {}), (202, []), (202, {"action_id": None}),
    (202, {"action_id": "act_short"}), (200, {"action_id": ACTION_ID}),
])
def test_unexpected_capture_acknowledgement_is_unknown_not_retried(flow, status, body):
    client, _, post = flow
    post.return_value = response("POST", status, body)
    result = capture_authorized_payment(client, PAYMENT_ID, 1000, REFERENCE)
    assert result.status == "unknown"
    assert result.error_kind == "invalid_capture_response"
    post.assert_called_once()


def test_malformed_capture_json_is_unknown_not_retried(flow):
    client, _, post = flow
    post.return_value = httpx.Response(202, content=b"invalid-json", request=httpx.Request("POST", BASE_URL))
    result = capture_authorized_payment(client, PAYMENT_ID, 1000, REFERENCE)
    assert result.status == "unknown"
    post.assert_called_once()
