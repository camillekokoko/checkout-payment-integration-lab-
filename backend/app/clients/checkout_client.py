from locale import currency
import os
import re
import token
from urllib.parse import urlsplit
import httpx
from dotenv import load_dotenv

load_dotenv()

class CheckoutClient:
    def __init__(self):
        self.api_key = os.getenv("CHECKOUT_SECRET_KEY")
        self.base_url = os.getenv("CHECKOUT_BASE_URL")
        self.processing_channel_id = os.getenv("CHECKOUT_PROCESSING_CHANNEL_ID")
        
        if not self.api_key:
            raise ValueError("CHECKOUT_SECRET_KEY is missing")  
        if not self.api_key.startswith("sk_sbox_"):
            raise ValueError("CHECKOUT_SECRET_KEY must be a Sandbox key")
        if not self.base_url:
            raise ValueError("CHECKOUT_BASE_URL is missing")   
        try:
            parsed_url = urlsplit(self.base_url)
            valid_url = (
                parsed_url.scheme == "https"
                and re.fullmatch(
                    r"[a-z0-9-]+\.api\.sandbox\.checkout\.com",
                    parsed_url.hostname or "",
                ) is not None
                and parsed_url.username is None
                and parsed_url.password is None
                and parsed_url.port is None
                and parsed_url.netloc.lower() == parsed_url.hostname
                and parsed_url.path in ("", "/")
                and not parsed_url.query
                and not parsed_url.fragment
            )
        except ValueError:
            valid_url = False

        if not valid_url:
            raise ValueError("CHECKOUT_BASE_URL must be a Sandbox HTTPS base URL")

        self.base_url = self.base_url.rstrip("/")
        
        
    def validate_token_config(self):
        public_key = os.getenv("CHECKOUT_PUBLIC_KEY")
        if not public_key or not public_key.startswith("pk_sbox_"):
            raise ValueError("CHECKOUT_PUBLIC_KEY is missing or invalid")
        return public_key

    def validate_payment_config(self):
        if not self.processing_channel_id or re.fullmatch(
            r"pc_[A-Za-z0-9_]{26}", self.processing_channel_id
        ) is None:
            raise ValueError("CHECKOUT_PROCESSING_CHANNEL_ID is missing or invalid")

    def get_payment(self, payment_id: str):
        url = f"{self.base_url}/payments/{payment_id}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        response = httpx.get(url, headers=headers, timeout=10.0)
        
        response.raise_for_status()
        return response
    
    def get_payment_actions(self, payment_id: str):
        """GET /payments/{id}/actions for read-only operation reconciliation."""
        if not isinstance(payment_id, str) or re.fullmatch(r"pay_[A-Za-z0-9_]{26}", payment_id) is None:
            raise ValueError("payment_id is missing or invalid")
        response = httpx.get(
            f"{self.base_url}/payments/{payment_id}/actions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=10.0,
        )
        response.raise_for_status()
        return response

    def create_payment(
        self, amount: int, currency: str, token: str, order_id: str, *, capture: bool
    ):
        """Send a payment request; the caller chooses the capture strategy."""
        if type(amount) is not int or amount <= 0:
            raise ValueError("amount must be a positive integer in minor units")

        if not isinstance(currency, str) or re.fullmatch(r"[A-Z]{3}", currency) is None:
            raise ValueError("currency must be a three-letter uppercase code")
        if type(capture) is not bool:
            raise ValueError("capture must be a boolean")
        
        if type(order_id) is not str or not order_id.strip() or len(order_id) > 80:
            raise ValueError("order_id must be a nonblank string of at most 80 characters")

        self.validate_payment_config()
        
        url = f"{self.base_url.rstrip('/')}/payments"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "source": {
                "type": "token",
                "token": token
            },
            "amount": amount,
            "currency": currency,
            "capture": capture,
            "reference": order_id,
            "processing_channel_id": self.processing_channel_id,
        }

        response = httpx.post(
            url,
            headers=headers,
            json=payload,
            timeout=10.0
        )
        response.raise_for_status()
        return response
    
    def create_token(self, card: dict):
        public_key = self.validate_token_config()

        url = f"{self.base_url.rstrip('/')}/tokens"

        headers = {
            "Authorization": f"Bearer {public_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "type": "card",
            "number": card["number"],
            "expiry_month": card["expiry_month"],
            "expiry_year": card["expiry_year"],
            "cvv": card["cvv"]
        }

        response = httpx.post(
            url,
            headers=headers,
            json=payload,
            timeout=10.0
        )
        
        response.raise_for_status()
        return response

    def capture_payment(self, payment_id: str, amount: int, reference: str):
        """POST /payments/{id}/captures; 202 accepts a request, not completed capture.

        Eligibility and remaining balance checks belong to the capture service.
        Errors propagate without automatic retries.
        """
        if not isinstance(payment_id, str) or re.fullmatch(
            r"pay_[A-Za-z0-9_]{26}", payment_id
        ) is None:
            raise ValueError("payment_id is missing or invalid")

        if type(amount) is not int or amount <= 0:
            raise ValueError("amount must be a positive integer in minor units")

        if type(reference) is not str or not reference.strip() or len(reference) > 80:
            raise ValueError("reference must be a nonblank string of at most 80 characters")

        url = f"{self.base_url.rstrip('/')}/payments/{payment_id}/captures"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "amount": amount,
            "reference": reference
        }

        response = httpx.post(
            url,
            headers=headers,
            json=payload,
            timeout=10.0
        )

        response.raise_for_status()
        return response
