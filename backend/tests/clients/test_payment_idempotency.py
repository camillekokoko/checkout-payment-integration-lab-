from unittest.mock import patch

import httpx
import pytest

from app.clients.checkout_client import CheckoutClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "sk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://test.api.sandbox.checkout.com")
    monkeypatch.setenv("CHECKOUT_PROCESSING_CHANNEL_ID", "pc_" + "a" * 26)
    return CheckoutClient()


@pytest.mark.parametrize("key", [
    "", " ", 123, True, [], "not-a-uuid", "a\r\nInjected: value",
    "12345678-1234-1234-9234-123456789abc",  # UUID1 is outside our local policy.
])
def test_invalid_key_stops_before_http(client, key):
    with patch("app.clients.checkout_client.httpx.post") as post:
        with pytest.raises(ValueError, match="canonical UUID4"):
            client.create_payment(
                1000, "AUD", "tok_fake", "order_001", capture=False, idempotency_key=key,
            )
        post.assert_not_called()


def test_legacy_call_does_not_generate_a_key(client):
    response = httpx.Response(201, request=httpx.Request("POST", "https://checkout.invalid"))
    with patch("app.clients.checkout_client.httpx.post", return_value=response) as post:
        client.create_payment(1000, "AUD", "tok_fake", "order_001", capture=False)
    assert "Cko-Idempotency-Key" not in post.call_args.kwargs["headers"]
