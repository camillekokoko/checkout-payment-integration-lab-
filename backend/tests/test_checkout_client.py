from unittest.mock import patch

import httpx
import pytest

from app.checkout_client import CheckoutClient


def test_create_token_rejects_blank_public_key(monkeypatch):
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "fake-secret-key")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://checkout.invalid")
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
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "fake-secret-key")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://checkout.invalid")
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
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "fake-secret-key")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://checkout.invalid")
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
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "fake-secret-key")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://checkout.invalid")
    monkeypatch.setenv("CHECKOUT_PUBLIC_KEY", "pk_sbox_fake")
    
    client = CheckoutClient()
    
    with patch("app.checkout_client.httpx.post") as mock_post:
        mock_post.return_value = httpx.Response(
            status_code=201,
            json={"token": "tok_test_fake"},
        ) 
        
        card = {
            "number": "fake-card-number",
            "expiry_month": 12,
            "expiry_year": 2030,
            "cvv": "fake-cvv",
        }
        
        response = client.create_token(card)
        
        mock_post.assert_called_once_with(
            "https://checkout.invalid/tokens",
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

def test_create_token_propagates_timeout(monkeypatch):
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "fake-secret-key")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://checkout.invalid")
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
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "fake-secret-key")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://checkout.invalid")

    client = CheckoutClient()

    with patch("app.checkout_client.httpx.post") as mock_post:
        mock_post.side_effect = httpx.ReadTimeout("Simulated timeout")

        with pytest.raises(httpx.ReadTimeout):
            client.create_payment(amount=1000, currency="AUD", token="tok_test_fake")

        mock_post.assert_called_once()


@pytest.mark.parametrize("amount", [0, -1, 10.5, 1000.0, "1000", None, True, False])
def test_create_payment_rejects_invalid_amount(monkeypatch, amount):
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "fake-secret-key")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://checkout.invalid")

    client = CheckoutClient()

    with patch("app.checkout_client.httpx.post") as mock_post:
        with pytest.raises(
            ValueError, match="amount must be a positive integer in minor units"
        ):
            client.create_payment(amount=amount, currency="AUD", token="tok_test_fake")

        mock_post.assert_not_called()
