from unittest.mock import Mock

import httpx
import pytest

from app.clients.checkout_client import CheckoutClient
from app.models.payment_operation import PaymentOperationResult
from app.services.payment_operation_service import (
    capture_payment_amount, confirm_payment_operation, refund_captured_payment,
    void_authorized_payment,
)


PAYMENT_ID = "pay_" + "a" * 26
ACTION_ID = "act_" + "b" * 26
BASE_URL = "https://test.api.sandbox.checkout.com"
FUNCTIONS = {"Capture": capture_payment_amount, "Void": void_authorized_payment, "Refund": refund_captured_payment}
AMOUNTS = {"Capture": 500, "Void": 1000, "Refund": 400}


def response(status, data):
    return httpx.Response(status, json=data, request=httpx.Request("GET", BASE_URL))


def snapshot(kind):
    return {
        "id": PAYMENT_ID, "currency": "AUD", "source": {"type": "card", "scheme": "Visa"},
        "status": "Captured" if kind == "Refund" else "Authorized",
        "balances": {
            "total_authorized": 1000, "total_voided": 0,
            "total_captured": 1000 if kind == "Refund" else 0,
            "available_to_capture": 0 if kind == "Refund" else 1000,
            "available_to_void": 1000, "total_refunded": 0,
            "available_to_refund": 1000 if kind == "Refund" else 0,
        },
    }


@pytest.fixture
def flow(monkeypatch):
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "sk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_BASE_URL", BASE_URL)
    get = Mock(side_effect=AssertionError("Unexpected GET"))
    post = Mock(return_value=response(202, {"action_id": ACTION_ID}))
    monkeypatch.setattr(httpx, "get", get)
    monkeypatch.setattr(httpx, "post", post)
    return CheckoutClient(), get, post


@pytest.mark.parametrize("kind,endpoint", [("Capture", "captures"), ("Void", "voids"), ("Refund", "refunds")])
def test_eligible_operation_looks_up_then_submits_once(flow, kind, endpoint):
    client, get, post = flow
    get.side_effect = None
    get.return_value = response(200, snapshot(kind))
    calls = Mock()
    calls.attach_mock(get, "get")
    calls.attach_mock(post, "post")
    result = FUNCTIONS[kind](client, PAYMENT_ID, AMOUNTS[kind], "operation_001")
    assert [call[0] for call in calls.mock_calls] == ["get", "post"]
    assert result.action_type == kind
    assert result.status == "accepted"
    assert result.action_id == ACTION_ID
    assert post.call_args.args == (f"{BASE_URL}/payments/{PAYMENT_ID}/{endpoint}",)
    assert post.call_args.kwargs["json"]["amount"] == AMOUNTS[kind]
    if kind == "Capture":
        assert post.call_args.kwargs["json"]["capture_type"] == "NonFinal"


def test_partial_capture_then_final_remaining_capture(flow):
    client, get, post = flow
    data = snapshot("Capture")
    data["status"] = "Partially Captured"
    data["balances"].update(total_captured=500, available_to_capture=500)
    get.side_effect = None
    get.return_value = response(200, data)
    result = capture_payment_amount(client, PAYMENT_ID, 500, "final_remaining", final=True)
    assert result.status == "accepted"
    assert post.call_args.kwargs["json"]["capture_type"] == "Final"


@pytest.mark.parametrize("amount", [400, 1000])
def test_partial_and_full_refund_within_captured_balance(flow, amount):
    client, get, post = flow
    get.side_effect = None
    get.return_value = response(200, snapshot("Refund"))
    result = refund_captured_payment(client, PAYMENT_ID, amount, "refund_001")
    assert result.status == "accepted"
    post.assert_called_once()


def test_second_refund_uses_remaining_refundable_balance(flow):
    client, get, post = flow
    data = snapshot("Refund")
    data["status"] = "Partially Refunded"
    data["balances"].update(total_refunded=400, available_to_refund=600)
    get.side_effect = None
    get.return_value = response(200, data)
    assert refund_captured_payment(client, PAYMENT_ID, 600, "refund_remaining").status == "accepted"
    post.assert_called_once()


@pytest.mark.parametrize("kind,amount", [("Capture", 1001), ("Capture", 1000), ("Void", 500), ("Refund", 1001)])
def test_invalid_operation_amount_relative_to_balance_blocks_post(flow, kind, amount):
    client, get, post = flow
    get.side_effect = None
    get.return_value = response(200, snapshot(kind))
    with pytest.raises(ValueError):
        FUNCTIONS[kind](client, PAYMENT_ID, amount, "operation_001")
    post.assert_not_called()


def test_final_partial_capture_cannot_silently_void_remainder(flow):
    client, get, post = flow
    get.side_effect = None
    get.return_value = response(200, snapshot("Capture"))
    with pytest.raises(ValueError, match="Final capture"):
        capture_payment_amount(client, PAYMENT_ID, 500, "final_wrong", final=True)
    post.assert_not_called()


@pytest.mark.parametrize("kind,status", [
    ("Capture", "Captured"), ("Capture", "Voided"), ("Capture", "Pending"),
    ("Void", "Captured"), ("Void", "Partially Captured"), ("Void", "Voided"),
    ("Refund", "Authorized"), ("Refund", "Refunded"), ("Refund", "Declined"),
])
def test_wrong_payment_state_blocks_operation(flow, kind, status):
    client, get, post = flow
    data = snapshot(kind)
    data["status"] = status
    get.side_effect = None
    get.return_value = response(200, data)
    with pytest.raises(ValueError):
        FUNCTIONS[kind](client, PAYMENT_ID, AMOUNTS[kind], "operation_001")
    post.assert_not_called()


@pytest.mark.parametrize("kind,field,value", [
    ("Capture", "available_to_capture", None), ("Capture", "total_captured", True),
    ("Capture", "total_authorized", 2000), ("Capture", "available_to_capture", 0),
    ("Void", "total_captured", 100), ("Void", "available_to_void", 0),
    ("Void", "available_to_void", 500), ("Void", "available_to_void", "1000"),
    ("Refund", "available_to_refund", 0), ("Refund", "available_to_refund", 2000),
    ("Refund", "total_refunded", 2000), ("Refund", "available_to_refund", True),
])
def test_missing_or_inconsistent_balances_block_post(flow, kind, field, value):
    client, get, post = flow
    data = snapshot(kind)
    data["balances"][field] = value
    get.side_effect = None
    get.return_value = response(200, data)
    with pytest.raises(ValueError):
        FUNCTIONS[kind](client, PAYMENT_ID, AMOUNTS[kind], "operation_001")
    post.assert_not_called()


@pytest.mark.parametrize("kind", FUNCTIONS)
@pytest.mark.parametrize("bad_field", ["id", "currency", "source", "balances"])
def test_mismatched_or_incomplete_snapshot_blocks_post(flow, kind, bad_field):
    client, get, post = flow
    data = snapshot(kind)
    del data[bad_field]
    get.side_effect = None
    get.return_value = response(200, data)
    with pytest.raises(ValueError):
        FUNCTIONS[kind](client, PAYMENT_ID, AMOUNTS[kind], "operation_001")
    post.assert_not_called()


@pytest.mark.parametrize("kind", FUNCTIONS)
@pytest.mark.parametrize("amount", [0, True, 1000.0])
def test_bad_input_blocks_even_lookup(flow, kind, amount):
    client, get, post = flow
    with pytest.raises(ValueError):
        FUNCTIONS[kind](client, PAYMENT_ID, amount, "operation_001")
    get.assert_not_called()
    post.assert_not_called()


@pytest.mark.parametrize("kind", FUNCTIONS)
def test_amex_reference_limit_is_checked_before_write(flow, kind):
    client, get, post = flow
    data = snapshot(kind)
    data["source"]["scheme"] = "Amex"
    get.side_effect = None
    get.return_value = response(200, data)
    with pytest.raises(ValueError, match="Amex"):
        FUNCTIONS[kind](client, PAYMENT_ID, AMOUNTS[kind], "r" * 31)
    post.assert_not_called()


@pytest.mark.parametrize("kind", FUNCTIONS)
@pytest.mark.parametrize("status,expected", [(401, "rejected"), (403, "rejected"), (422, "rejected"), (429, "unknown"), (503, "unknown")])
def test_operation_http_error_is_not_retried(flow, kind, status, expected):
    client, get, post = flow
    get.side_effect = None
    get.return_value = response(200, snapshot(kind))
    post.return_value = response(status, {"private": "never-print"})
    result = FUNCTIONS[kind](client, PAYMENT_ID, AMOUNTS[kind], "operation_001")
    assert result.status == expected
    assert "private" not in repr(result)
    post.assert_called_once()


@pytest.mark.parametrize("kind", FUNCTIONS)
def test_write_timeout_preserves_unknown_and_never_retries(flow, kind):
    client, get, post = flow
    get.side_effect = None
    get.return_value = response(200, snapshot(kind))
    post.side_effect = httpx.ReadTimeout("private-detail")
    result = FUNCTIONS[kind](client, PAYMENT_ID, AMOUNTS[kind], "operation_001")
    assert result.status == "unknown"
    assert result.error_kind == "connection_error"
    assert "private" not in repr(result)
    post.assert_called_once()


@pytest.mark.parametrize("kind", FUNCTIONS)
def test_lookup_failure_never_submits_an_operation(flow, kind):
    client, get, post = flow
    get.side_effect = httpx.ReadTimeout("lookup timeout")
    with pytest.raises(httpx.ReadTimeout):
        FUNCTIONS[kind](client, PAYMENT_ID, AMOUNTS[kind], "operation_001")
    get.assert_called_once()
    post.assert_not_called()


@pytest.mark.parametrize("kind", FUNCTIONS)
@pytest.mark.parametrize("body", [{}, [], {"action_id": "act_short"}])
def test_malformed_acknowledgment_is_unknown(flow, kind, body):
    client, get, post = flow
    get.side_effect = None
    get.return_value = response(200, snapshot(kind))
    post.return_value = response(202, body)
    assert FUNCTIONS[kind](client, PAYMENT_ID, AMOUNTS[kind], "operation_001").status == "unknown"
    post.assert_called_once()


@pytest.mark.parametrize("kind", ["Void", "Refund"])
@pytest.mark.parametrize("approved,expected", [(True, "succeeded"), (False, "failed"), (None, "unknown")])
def test_void_and_refund_confirmation_matches_exact_action(flow, kind, approved, expected):
    client, get, post = flow
    operation = PaymentOperationResult(kind, PAYMENT_ID, 500, "operation_001", "accepted", ACTION_ID)
    get.side_effect = None
    get.return_value = response(200, [
        {"id": "act_" + "c" * 26, "type": kind, "amount": 500, "approved": False},
        {"id": ACTION_ID, "type": kind, "amount": 500, "approved": approved},
    ])
    assert confirm_payment_operation(client, operation).status == expected
    get.assert_called_once()
    post.assert_not_called()


@pytest.mark.parametrize("kind", ["Void", "Refund"])
def test_wrong_action_type_cannot_confirm_a_different_operation(flow, kind):
    client, get, post = flow
    operation = PaymentOperationResult(kind, PAYMENT_ID, 500, "operation_001", "accepted", ACTION_ID)
    get.side_effect = None
    get.return_value = response(200, [{"id": ACTION_ID, "type": "Capture", "amount": 500, "approved": True}])
    assert confirm_payment_operation(client, operation).status == "unknown"
    post.assert_not_called()


@pytest.mark.parametrize("kind", FUNCTIONS)
def test_request_to_confirmation_business_scenario(flow, kind):
    client, get, post = flow
    get.side_effect = [response(200, snapshot(kind)), response(200, [{
        "id": ACTION_ID, "type": kind, "amount": AMOUNTS[kind], "approved": True,
    }])]
    operation = FUNCTIONS[kind](client, PAYMENT_ID, AMOUNTS[kind], "operation_001")
    confirmation = confirm_payment_operation(client, operation)
    assert operation.status == "accepted"
    assert confirmation.status == "succeeded"
    assert confirmation.action_type == kind
    assert get.call_count == 2
    post.assert_called_once()


def test_non_boolean_final_option_is_blocked_before_http(flow):
    client, get, post = flow
    with pytest.raises(ValueError, match="final"):
        capture_payment_amount(client, PAYMENT_ID, 500, "operation_001", final="false")
    get.assert_not_called()
    post.assert_not_called()
