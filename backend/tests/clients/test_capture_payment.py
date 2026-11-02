from unittest.mock import patch

import httpx
import pytest

from app.clients.checkout_client import CheckoutClient


PAYMENT_ID = "pay_" + "a" * 26
BASE_URL = "https://test.api.sandbox.checkout.com"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "sk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_BASE_URL", BASE_URL)
    return CheckoutClient()


def test_capture_payment_sends_request_and_returns_accepted_response(client):
    # A merchant requests capture after authorization. Acceptance is not completion.
    url = f"{BASE_URL}/payments/{PAYMENT_ID}/captures"
    response = httpx.Response(
        202,
        json={"action_id": "act_" + "b" * 26},
        request=httpx.Request("POST", url),
    )

    with patch("app.clients.checkout_client.httpx.post", return_value=response) as post:
        result = client.capture_payment(PAYMENT_ID, 1000, "capture_order_001")

    post.assert_called_once_with(
        url,
        headers={
            "Authorization": "Bearer sk_sbox_fake",
            "Content-Type": "application/json",
        },
        json={"amount": 1000, "reference": "capture_order_001"},
        timeout=10.0,
    )
    assert result is response
    assert result.status_code == 202


@pytest.mark.parametrize("field,value,message", [
    ("payment_id", None, "payment_id is missing or invalid"),
    ("payment_id", 123, "payment_id is missing or invalid"),
    ("payment_id", "", "payment_id is missing or invalid"),
    ("payment_id", "pay_short", "payment_id is missing or invalid"),
    ("payment_id", "pay_" + "a" * 27, "payment_id is missing or invalid"),
    ("payment_id", PAYMENT_ID + "/captures", "payment_id is missing or invalid"),
    ("payment_id", " " + PAYMENT_ID, "payment_id is missing or invalid"),
    ("amount", 0, "amount must be a positive integer in minor units"),
    ("amount", -1, "amount must be a positive integer in minor units"),
    ("amount", True, "amount must be a positive integer in minor units"),
    ("amount", False, "amount must be a positive integer in minor units"),
    ("amount", 1000.0, "amount must be a positive integer in minor units"),
    ("amount", "1000", "amount must be a positive integer in minor units"),
    ("amount", None, "amount must be a positive integer in minor units"),
    ("reference", None, "reference must be a nonblank string of at most 80 characters"),
    ("reference", 123, "reference must be a nonblank string of at most 80 characters"),
    ("reference", "", "reference must be a nonblank string of at most 80 characters"),
    ("reference", "   ", "reference must be a nonblank string of at most 80 characters"),
    ("reference", "r" * 81, "reference must be a nonblank string of at most 80 characters"),
])
def test_invalid_capture_input_sends_no_request(client, field, value, message):
    # Reject malformed capture inputs before any financial request is sent.
    arguments = {"payment_id": PAYMENT_ID, "amount": 1000, "reference": "capture_order_001"}
    arguments[field] = value

    with patch("app.clients.checkout_client.httpx.post") as post:
        with pytest.raises(ValueError, match=message):
            client.capture_payment(**arguments)
        post.assert_not_called()


def test_capture_accepts_minimum_amount_and_reference_length_boundary(client):
    response = httpx.Response(202, request=httpx.Request("POST", BASE_URL))
    with patch("app.clients.checkout_client.httpx.post", return_value=response) as post:
        client.capture_payment(PAYMENT_ID, 1, "r" * 80)

    assert post.call_args.kwargs["json"] == {"amount": 1, "reference": "r" * 80}


@pytest.mark.parametrize("status", [401, 403, 404, 409, 422, 429, 500, 502, 503, 504])
def test_capture_propagates_http_error_without_retry(client, status):
    # Preserve the response for the caller; do not blindly repeat a capture.
    response = httpx.Response(status, request=httpx.Request("POST", BASE_URL))
    with patch("app.clients.checkout_client.httpx.post", return_value=response) as post:
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            client.capture_payment(PAYMENT_ID, 1000, "capture_order_001")
        post.assert_called_once()

    assert exc_info.value.response is response


@pytest.mark.parametrize("error_type", [httpx.ReadTimeout, httpx.ConnectError])
def test_capture_propagates_transport_error_without_retry(client, error_type):
    # A lost response may follow a processed capture. Keep the outcome uncertain.
    error = error_type("Simulated transport error")
    with patch("app.clients.checkout_client.httpx.post", side_effect=error) as post:
        with pytest.raises(error_type) as exc_info:
            client.capture_payment(PAYMENT_ID, 1000, "capture_order_001")
        post.assert_called_once()

    assert exc_info.value is error
