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
        
        
    def get_payment(self, payment_id: str):
        url = f"{self.base_url}/payments/{payment_id}"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        response = httpx.get(url, headers=headers, timeout=10.0)
        
        response.raise_for_status()
        return response
    
    def create_payment(self, amount: int, currency: str, token: str):
        if type(amount) is not int or amount <= 0:
            raise ValueError("amount must be a positive integer in minor units")

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
            "capture": False
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
        public_key = os.getenv("CHECKOUT_PUBLIC_KEY")

        if not public_key or not public_key.startswith("pk_sbox_"):
            raise ValueError("CHECKOUT_PUBLIC_KEY is missing or invalid")

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

