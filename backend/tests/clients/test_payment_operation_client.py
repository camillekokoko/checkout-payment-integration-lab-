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


@pytest.mark.parametrize("method,endpoint,extra", [
    ("void_payment", "voids", {}), ("refund_payment", "refunds", {}),
    ("capture_payment", "captures", {"capture_type": "NonFinal"}),
    ("capture_payment", "captures", {"capture_type": "Final"}),
])
def test_operation_request_uses_correct_endpoint_and_payload(client, method, endpoint, extra):
    response = httpx.Response(202, request=httpx.Request("POST", BASE_URL))
    with patch("app.clients.checkout_client.httpx.post", return_value=response) as post:
        result = getattr(client, method)(PAYMENT_ID, 500, "operation_001", **extra)
    post.assert_called_once_with(
        f"{BASE_URL}/payments/{PAYMENT_ID}/{endpoint}",
        headers={"Authorization": "Bearer sk_sbox_fake", "Content-Type": "application/json"},
        json={"amount": 500, "reference": "operation_001", **extra}, timeout=10.0,
    )
    assert result is response


@pytest.mark.parametrize("capture_type", ["final", "invalid", True, 1, []])
def test_invalid_capture_type_sends_no_request(client, capture_type):
    with patch("app.clients.checkout_client.httpx.post") as post:
        with pytest.raises(ValueError, match="capture_type"):
            client.capture_payment(PAYMENT_ID, 500, "operation_001", capture_type=capture_type)
        post.assert_not_called()


@pytest.mark.parametrize("method", ["void_payment", "refund_payment"])
@pytest.mark.parametrize("amount", [0, -1, True, 1000.0])
def test_invalid_void_or_refund_amount_sends_no_request(client, method, amount):
    with patch("app.clients.checkout_client.httpx.post") as post:
        with pytest.raises(ValueError):
            getattr(client, method)(PAYMENT_ID, amount, "operation_001")
        post.assert_not_called()


@pytest.mark.parametrize("method", ["void_payment", "refund_payment"])
def test_operation_http_error_is_preserved_without_retry(client, method):
    response = httpx.Response(422, request=httpx.Request("POST", BASE_URL))
    with patch("app.clients.checkout_client.httpx.post", return_value=response) as post:
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            getattr(client, method)(PAYMENT_ID, 500, "operation_001")
        post.assert_called_once()
    assert exc_info.value.response is response
