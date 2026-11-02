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


def test_actions_lookup_uses_secret_key_and_returns_response(client):
    response = httpx.Response(200, json=[], request=httpx.Request("GET", BASE_URL))
    with patch("app.clients.checkout_client.httpx.get", return_value=response) as get:
        result = client.get_payment_actions(PAYMENT_ID)
    get.assert_called_once_with(
        f"{BASE_URL}/payments/{PAYMENT_ID}/actions",
        headers={"Authorization": "Bearer sk_sbox_fake"}, timeout=10.0,
    )
    assert result is response


@pytest.mark.parametrize("payment_id", [None, 123, "", "pay_short", PAYMENT_ID + "/actions"])
def test_bad_payment_id_does_not_send_actions_lookup(client, payment_id):
    with patch("app.clients.checkout_client.httpx.get") as get:
        with pytest.raises(ValueError, match="payment_id"):
            client.get_payment_actions(payment_id)
        get.assert_not_called()


@pytest.mark.parametrize("status", [401, 403, 404, 429, 500, 503])
def test_actions_http_error_propagates_without_retry(client, status):
    response = httpx.Response(status, request=httpx.Request("GET", BASE_URL))
    with patch("app.clients.checkout_client.httpx.get", return_value=response) as get:
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            client.get_payment_actions(PAYMENT_ID)
        get.assert_called_once()
    assert exc_info.value.response is response


def test_actions_timeout_propagates_without_retry(client):
    with patch("app.clients.checkout_client.httpx.get", side_effect=httpx.ReadTimeout("timeout")) as get:
        with pytest.raises(httpx.ReadTimeout):
            client.get_payment_actions(PAYMENT_ID)
        get.assert_called_once()
