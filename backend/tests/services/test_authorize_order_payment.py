from unittest.mock import patch

import httpx
import pytest

from app.clients.checkout_client import CheckoutClient
from app.models.order import Order
from app.services.payment_service import authorize_order_payment


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "sk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://test.api.sandbox.checkout.com")
    monkeypatch.setenv("CHECKOUT_PROCESSING_CHANNEL_ID", "pc_" + "a" * 26)
    return CheckoutClient()


def test_order_authorization_applies_merchant_policy(client):
    # The service supplies trusted order values and selects authorization only.
    order = Order("order_001", 1000, "AUD")
    response = httpx.Response(201, request=httpx.Request("POST", "https://checkout.invalid"))
    with patch("app.clients.checkout_client.httpx.post", return_value=response) as post:
        result = authorize_order_payment(client, order, "tok_fake")

    post.assert_called_once()
    payload = post.call_args.kwargs["json"]
    assert payload["amount"] == 1000
    assert payload["currency"] == "AUD"
    assert payload["reference"] == "order_001"
    assert payload["source"] == {"type": "token", "token": "tok_fake"}
    assert payload["capture"] is False
    assert result is response


@pytest.mark.parametrize("currency", ["USD", "HKD", "aud", "Aud", " AUD ", "", None, 36])
def test_merchant_rejects_non_aud_order_before_http(client, currency):
    with patch("app.clients.checkout_client.httpx.post") as post:
        with pytest.raises(ValueError, match="currency must be AUD"):
            authorize_order_payment(client, Order("order_001", 1000, currency), "tok_fake")
        post.assert_not_called()


@pytest.mark.parametrize("status", [401, 403, 422, 503])
def test_authorization_service_preserves_http_error_without_retry(client, status):
    response = httpx.Response(status, request=httpx.Request("POST", "https://checkout.invalid"))
    with patch("app.clients.checkout_client.httpx.post", return_value=response) as post:
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            authorize_order_payment(client, Order("order_001", 1000, "AUD"), "tok_fake")
        post.assert_called_once()
    assert exc_info.value.response is response


def test_authorization_timeout_does_not_retry(client):
    error = httpx.ReadTimeout("Simulated timeout")
    with patch("app.clients.checkout_client.httpx.post", side_effect=error) as post:
        with pytest.raises(httpx.ReadTimeout) as exc_info:
            authorize_order_payment(client, Order("order_001", 1000, "AUD"), "tok_fake")
        post.assert_called_once()
    assert exc_info.value is error
