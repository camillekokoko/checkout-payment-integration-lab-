from unittest.mock import Mock

import httpx
import pytest

from app.clients.checkout_client import CheckoutClient
from app.models.capture import CaptureResult
from app.services.capture_service import capture_authorized_payment, confirm_capture


PAYMENT_ID = "pay_" + "a" * 26
ACTION_ID = "act_" + "b" * 26


def response(status, body):
    return httpx.Response(status, json=body, request=httpx.Request("GET", "https://checkout.invalid"))


@pytest.fixture
def accepted():
    return CaptureResult(PAYMENT_ID, 1000, "capture_order_001", "accepted", ACTION_ID)


@pytest.fixture
def action():
    return {"id": ACTION_ID, "type": "Capture", "amount": 1000, "approved": True}


@pytest.fixture
def flow(monkeypatch, action):
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "sk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://test.api.sandbox.checkout.com")
    get = Mock(return_value=response(200, [action]))
    post = Mock(side_effect=AssertionError("Confirmation must never POST"))
    monkeypatch.setattr(httpx, "get", get)
    monkeypatch.setattr(httpx, "post", post)
    return CheckoutClient(), get, post


@pytest.mark.parametrize("approved,expected", [(True, "succeeded"), (False, "failed")])
def test_confirmation_uses_exact_action_not_latest_action(flow, accepted, action, approved, expected):
    client, get, post = flow
    action["approved"] = approved
    unrelated = {"id": "act_" + "c" * 26, "type": "Capture", "amount": 1000, "approved": not approved}
    get.return_value = response(200, [unrelated, action])

    result = confirm_capture(client, accepted)

    assert result.status == expected
    assert result.action_id == ACTION_ID
    assert result.payment_id == PAYMENT_ID
    assert result.amount == 1000
    assert result.reason is None
    assert accepted.status == "accepted"  # Original snapshot is unchanged.
    get.assert_called_once()
    post.assert_not_called()


@pytest.mark.parametrize("body,reason", [
    ([], "action_not_found"),
    ([{"id": "act_" + "c" * 26}], "action_not_found"),
    ({}, "invalid_actions_response"),
    ([None], "invalid_actions_response"),
    ([{"id": ACTION_ID}, {"id": ACTION_ID}], "duplicate_action_id"),
])
def test_missing_or_ambiguous_evidence_stays_unknown(flow, accepted, body, reason):
    client, get, post = flow
    get.return_value = response(200, body)
    result = confirm_capture(client, accepted)
    assert result.status == "unknown"
    assert result.reason == reason
    get.assert_called_once()
    post.assert_not_called()


@pytest.mark.parametrize("field,value,reason", [
    ("type", "Authorization", "action_mismatch"),
    ("type", "Refund", "action_mismatch"),
    ("amount", 500, "action_mismatch"),
    ("amount", "1000", "action_mismatch"),
    ("amount", 1000.0, "action_mismatch"),
    ("approved", None, "approval_unconfirmed"),
    ("approved", 1, "approval_unconfirmed"),
    ("approved", "false", "approval_unconfirmed"),
])
def test_confirmation_requires_matching_capture_and_boolean_approval(flow, accepted, action, field, value, reason):
    client, get, post = flow
    action[field] = value
    get.return_value = response(200, [action])
    result = confirm_capture(client, accepted)
    assert result.status == "unknown"
    assert result.reason == reason
    post.assert_not_called()


@pytest.mark.parametrize("status", [401, 403, 404, 429, 503])
def test_read_failure_does_not_mean_capture_failed(flow, accepted, status):
    client, get, post = flow
    get.return_value = response(status, {})
    result = confirm_capture(client, accepted)
    assert result.status == "unknown"
    assert result.reason == "lookup_failed"
    get.assert_called_once()
    post.assert_not_called()


def test_lookup_timeout_keeps_outcome_unknown(flow, accepted):
    client, get, post = flow
    get.side_effect = httpx.ReadTimeout("private detail")
    result = confirm_capture(client, accepted)
    assert result.status == "unknown"
    assert "private" not in repr(result)
    get.assert_called_once()
    post.assert_not_called()


def test_malformed_json_is_unknown(flow, accepted):
    client, get, post = flow
    get.return_value = httpx.Response(200, content=b"invalid", request=httpx.Request("GET", "https://checkout.invalid"))
    assert confirm_capture(client, accepted).status == "unknown"
    post.assert_not_called()


def test_missing_action_id_does_not_guess_another_capture(flow):
    client, get, post = flow
    capture = CaptureResult(PAYMENT_ID, 1000, "capture_order_001", "unknown")
    result = confirm_capture(client, capture)
    assert result.status == "unknown"
    assert result.reason == "missing_action_id"
    get.assert_not_called()
    post.assert_not_called()


@pytest.mark.parametrize("payment_id,action_id,amount", [
    ("pay_short", ACTION_ID, 1000), (PAYMENT_ID, "act_short", 1000),
    (PAYMENT_ID, ACTION_ID, True), (PAYMENT_ID, ACTION_ID, 0),
])
def test_invalid_confirmation_input_stops_before_http(flow, payment_id, action_id, amount):
    client, get, post = flow
    capture = CaptureResult(payment_id, amount, "capture_order_001", "accepted", action_id)
    with pytest.raises(ValueError):
        confirm_capture(client, capture)
    get.assert_not_called()
    post.assert_not_called()


def test_authorization_to_capture_to_confirmation_business_flow(flow, action):
    client, get, post = flow
    get.side_effect = [response(200, {
        "id": PAYMENT_ID, "status": "Authorized", "currency": "AUD",
        "balances": {"total_authorized": 1000, "total_captured": 0,
                     "total_voided": 0, "available_to_capture": 1000},
    }), response(200, [action])]
    post.side_effect = None
    post.return_value = response(202, {"action_id": ACTION_ID})

    capture = capture_authorized_payment(client, PAYMENT_ID, 1000, "capture_order_001")
    confirmation = confirm_capture(client, capture)

    assert capture.status == "accepted"
    assert confirmation.status == "succeeded"
    assert get.call_count == 2
    post.assert_called_once()
