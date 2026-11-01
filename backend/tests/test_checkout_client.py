from unittest.mock import patch

import httpx
import pytest

from app.checkout_client import CheckoutClient


@pytest.mark.parametrize("currency", ["USD", "HKD", "aud", "Aud", " AUD ", "", None, 36])
def test_create_payment_rejects_unsupported_currency(monkeypatch, currency):
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "sk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://test.api.sandbox.checkout.com")

    client = CheckoutClient()

    with patch("app.checkout_client.httpx.post") as mock_post:
        with pytest.raises(ValueError, match="currency must be AUD"):
            client.create_payment(amount=1000, currency=currency, token="tok_test_fake", order_id="order_1001")

        mock_post.assert_not_called()


def test_create_payment_sends_aud_amount_in_minor_units(monkeypatch):
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "sk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://test.api.sandbox.checkout.com")

    client = CheckoutClient()
    provider_response = httpx.Response(
        201,
        json={"id": "pay_test_fake"},
        request=httpx.Request("POST", "https://test.api.sandbox.checkout.com/payments"),
    )

    with patch("app.checkout_client.httpx.post", return_value=provider_response) as mock_post:
        response = client.create_payment(amount=1000, currency="AUD", token="tok_test_fake", order_id="order_1001")

        mock_post.assert_called_once()
        payload = mock_post.call_args.kwargs["json"]
        assert payload["currency"] == "AUD"
        assert payload["amount"] == 1000
        assert response is provider_response


@pytest.mark.parametrize("order_id", [None, 1001, True, [], "", "   ", "\t\n", "x" * 81])
def test_create_payment_rejects_invalid_order_id(monkeypatch, order_id):
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "sk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://test.api.sandbox.checkout.com")

    client = CheckoutClient()

    with patch("app.checkout_client.httpx.post") as mock_post:
        with pytest.raises(
            ValueError, match="order_id must be a nonblank string of at most 80 characters"
        ):
            client.create_payment(
                amount=1000, currency="AUD", token="tok_test_fake", order_id=order_id
            )

        mock_post.assert_not_called()


@pytest.mark.parametrize("order_id", ["order_1001", "x", "x" * 80, " order_1001 "])
def test_create_payment_sends_order_id_as_reference(monkeypatch, order_id):
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "sk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://test.api.sandbox.checkout.com")

    client = CheckoutClient()
    provider_response = httpx.Response(
        201,
        json={"id": "pay_test_fake"},
        request=httpx.Request("POST", "https://test.api.sandbox.checkout.com/payments"),
    )

    with patch("app.checkout_client.httpx.post", return_value=provider_response) as mock_post:
        client.create_payment(
            amount=1000, currency="AUD", token="tok_test_fake", order_id=order_id
        )

        mock_post.assert_called_once()
        assert mock_post.call_args.kwargs["json"]["reference"] == order_id


def test_client_rejects_missing_secret_key(monkeypatch):
    monkeypatch.delenv("CHECKOUT_SECRET_KEY", raising=False)
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://test.api.sandbox.checkout.com")

    with pytest.raises(ValueError, match="CHECKOUT_SECRET_KEY is missing"):
        CheckoutClient()


@pytest.mark.parametrize("secret_key", ["sk_fake", "invalid_key", "   ", "pk_sbox_fake"])
def test_client_rejects_non_sandbox_secret_key(monkeypatch, secret_key):
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", secret_key)
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://test.api.sandbox.checkout.com")

    with pytest.raises(ValueError, match="CHECKOUT_SECRET_KEY must be a Sandbox key"):
        CheckoutClient()


@pytest.mark.parametrize("base_url", [
    "https://test.api.checkout.com",
    "http://test.api.sandbox.checkout.com",
    "https://test.api.sandbox.checkout.com.example.org",
    "https://api.sandbox.checkout.com",
    "https://extra.test.api.sandbox.checkout.com",
    "https://user:password@test.api.sandbox.checkout.com",
    "https://test.api.sandbox.checkout.com:443",
    "https://test.api.sandbox.checkout.com:invalid",
    "https://test.api.sandbox.checkout.com/payments",
    "https://test.api.sandbox.checkout.com?mode=test",
    "https://test.api.sandbox.checkout.com#section",
    "https://[invalid",
    "   ",
])
def test_client_rejects_invalid_base_url(monkeypatch, base_url):
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "sk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_BASE_URL", base_url)

    with pytest.raises(ValueError, match="CHECKOUT_BASE_URL must be a Sandbox HTTPS base URL"):
        CheckoutClient()


@pytest.mark.parametrize("suffix", ["", "/"])
def test_client_accepts_sandbox_base_url(monkeypatch, suffix):
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "sk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://test.api.sandbox.checkout.com" + suffix)

    client = CheckoutClient()

    assert client.base_url == "https://test.api.sandbox.checkout.com"


def test_create_payment_uses_secret_key(monkeypatch):
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "sk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_PUBLIC_KEY", "pk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://test.api.sandbox.checkout.com")

    client = CheckoutClient()

    # Payment creation must use the server-side secret key, not the public key.
    with patch("app.checkout_client.httpx.post") as mock_post:
        mock_post.return_value = httpx.Response(
            201,
            json={"id": "pay_test_fake"},
            request=httpx.Request("POST", "https://test.api.sandbox.checkout.com/payments"),
        )

        response = client.create_payment(amount=1000, currency="AUD", token="tok_test_fake", order_id="order_1001")

        assert response is mock_post.return_value
        mock_post.assert_called_once()
        assert mock_post.call_args.kwargs["headers"]["Authorization"] == (
            "Bearer sk_sbox_fake"
        )


@pytest.mark.parametrize("status_code", [401, 403, 429, 500, 502, 503, 504])
def test_create_payment_propagates_http_error(monkeypatch, status_code):
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "sk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://test.api.sandbox.checkout.com")

    client = CheckoutClient()
    provider_response = httpx.Response(
        status_code,
        request=httpx.Request("POST", "https://test.api.sandbox.checkout.com/payments"),
    )

    # Preserve the error response so the caller can inspect its status.
    # Do not retry here: a server error does not prove payment processing failed.
    with patch("app.checkout_client.httpx.post", return_value=provider_response) as mock_post:
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            client.create_payment(amount=1000, currency="AUD", token="tok_test_fake", order_id="order_1001")

        assert exc_info.value.response is provider_response
        assert exc_info.value.response.status_code == status_code
        mock_post.assert_called_once()


def test_get_payment_uses_secret_key_and_returns_response(monkeypatch):
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "sk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_PUBLIC_KEY", "pk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://test.api.sandbox.checkout.com")

    client = CheckoutClient()
    url = "https://test.api.sandbox.checkout.com/payments/pay_test_fake"
    provider_response = httpx.Response(
        200,
        json={"id": "pay_test_fake"},
        request=httpx.Request("GET", url),
    )

    with patch("app.checkout_client.httpx.get", return_value=provider_response) as mock_get:
        response = client.get_payment("pay_test_fake")

        assert response is provider_response
        mock_get.assert_called_once_with(
            url,
            headers={"Authorization": "Bearer sk_sbox_fake"},
            timeout=10.0,
        )


@pytest.mark.parametrize("status_code", [401, 403, 404, 429, 500, 502, 503, 504])
def test_get_payment_propagates_http_error(monkeypatch, status_code):
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "sk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://test.api.sandbox.checkout.com")

    client = CheckoutClient()
    provider_response = httpx.Response(
        status_code,
        request=httpx.Request("GET", "https://test.api.sandbox.checkout.com/payments/pay_test_fake"),
    )

    # A failed lookup must not be interpreted as a failed payment.
    with patch("app.checkout_client.httpx.get", return_value=provider_response) as mock_get:
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            client.get_payment("pay_test_fake")

        assert exc_info.value.response is provider_response
        assert exc_info.value.response.status_code == status_code
        mock_get.assert_called_once()


def test_client_rejects_missing_base_url(monkeypatch):
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "sk_sbox_fake")
    monkeypatch.delenv("CHECKOUT_BASE_URL", raising=False)

    with pytest.raises(ValueError, match="CHECKOUT_BASE_URL is missing"):
        CheckoutClient()


def test_create_token_rejects_blank_public_key(monkeypatch):
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "sk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://test.api.sandbox.checkout.com")
    monkeypatch.setenv("CHECKOUT_PUBLIC_KEY", "   ")
    
    client = CheckoutClient()

    with patch("app.checkout_client.httpx.post") as mock_post:
        with pytest.raises(
            ValueError,
            match="CHECKOUT_PUBLIC_KEY is missing or invalid",
        ):
            client.create_token({})

        mock_post.assert_not_called()
        
def test_create_token_rejects_invalid_public_key(monkeypatch):
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "sk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://test.api.sandbox.checkout.com")
    monkeypatch.setenv("CHECKOUT_PUBLIC_KEY", "invalid_key")
    
    client = CheckoutClient()
    
    with patch("app.checkout_client.httpx.post") as mock_post:
        with pytest.raises(
            ValueError,
            match="CHECKOUT_PUBLIC_KEY is missing or invalid",
        ):
            client.create_token({})
    
        mock_post.assert_not_called()
            
            
def test_create_token_rejects_missing_public_key(monkeypatch):
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "sk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://test.api.sandbox.checkout.com")
    monkeypatch.delenv("CHECKOUT_PUBLIC_KEY", raising=False) #return None
    
    client = CheckoutClient()
        
    with patch("app.checkout_client.httpx.post") as mock_post:
        with pytest.raises(
            ValueError,
            match="CHECKOUT_PUBLIC_KEY is missing or invalid",
        ):
            client.create_token({})
        
        mock_post.assert_not_called()
        
def test_create_token_returns_response(monkeypatch):
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "sk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://test.api.sandbox.checkout.com")
    monkeypatch.setenv("CHECKOUT_PUBLIC_KEY", "pk_sbox_fake")
    
    client = CheckoutClient()
    
    with patch("app.checkout_client.httpx.post") as mock_post:
        mock_post.return_value = httpx.Response(
            status_code=201,
            json={"token": "tok_test_fake"},
            request=httpx.Request("POST", "https://test.api.sandbox.checkout.com/tokens"),
        ) 
        
        card = {
            "number": "fake-card-number",
            "expiry_month": 12,
            "expiry_year": 2030,
            "cvv": "fake-cvv",
        }
        
        response = client.create_token(card)
        
        mock_post.assert_called_once_with(
            "https://test.api.sandbox.checkout.com/tokens",
            headers={
                "Authorization": "Bearer pk_sbox_fake",
                "Content-Type": "application/json",
            },
            json={
                "type": "card",
                "number": "fake-card-number",
                "expiry_month": 12,
                "expiry_year": 2030,
                "cvv": "fake-cvv",
            },
            timeout=10.0,
        )   
        assert response is mock_post.return_value #is checks if same object, == equals checks if same value

@pytest.mark.parametrize("status_code", [401, 403, 422, 429, 500, 502, 503, 504])
def test_create_token_propagates_http_error(monkeypatch, status_code):
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "sk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://test.api.sandbox.checkout.com")
    monkeypatch.setenv("CHECKOUT_PUBLIC_KEY", "pk_sbox_fake")

    client = CheckoutClient()
    card = {
        "number": "fake-card-number",
        "expiry_month": 12,
        "expiry_year": 2030,
        "cvv": "fake-cvv",
    }
    provider_response = httpx.Response(
        status_code,
        request=httpx.Request("POST", "https://test.api.sandbox.checkout.com/tokens"),
    )

    # Preserve HTTP errors for the caller without automatically retrying.
    with patch("app.checkout_client.httpx.post", return_value=provider_response) as mock_post:
        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            client.create_token(card)

        assert exc_info.value.response is provider_response
        assert exc_info.value.response.status_code == status_code
        mock_post.assert_called_once()


def test_create_token_propagates_timeout(monkeypatch):
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "sk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://test.api.sandbox.checkout.com")
    monkeypatch.setenv("CHECKOUT_PUBLIC_KEY", "pk_sbox_fake")  
        
    client = CheckoutClient()
    
    card = {
        "number": "fake-card-number",
        "expiry_month": 12,
        "expiry_year": 2030,
        "cvv": "fake-cvv",
    }
    
    with patch("app.checkout_client.httpx.post") as mock_post:
        mock_post.side_effect = httpx.ReadTimeout("Simulated timeout")

        with pytest.raises(httpx.ReadTimeout):
            client.create_token(card)

        mock_post.assert_called_once()


# Business case: A customer submits an AUD 10.00 payment, but the backend
# times out while waiting for the response. The provider may have processed
# the payment, so a timeout does not mean failure; retrying could duplicate it.
# This test verifies that the client propagates the timeout and makes one call.
# The application should keep the outcome uncertain and withhold fulfillment
# until payment lookup (if a payment ID is available) or a verified webhook
# confirms the outcome. State management and reconciliation are outside this test.
def test_create_payment_propagates_timeout(monkeypatch):
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "sk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://test.api.sandbox.checkout.com")

    client = CheckoutClient()

    with patch("app.checkout_client.httpx.post") as mock_post:
        mock_post.side_effect = httpx.ReadTimeout("Simulated timeout")

        with pytest.raises(httpx.ReadTimeout):
            client.create_payment(amount=1000, currency="AUD", token="tok_test_fake", order_id="order_1001")

        mock_post.assert_called_once()


@pytest.mark.parametrize("amount", [0, -1, 10.5, 1000.0, "1000", None, True, False])
def test_create_payment_rejects_invalid_amount(monkeypatch, amount):
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "sk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://test.api.sandbox.checkout.com")

    client = CheckoutClient()

    with patch("app.checkout_client.httpx.post") as mock_post:
        with pytest.raises(
            ValueError, match="amount must be a positive integer in minor units"
        ):
            client.create_payment(amount=amount, currency="AUD", token="tok_test_fake", order_id="order_1001")

        mock_post.assert_not_called()
