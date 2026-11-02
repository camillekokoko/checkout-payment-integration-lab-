"""Manual learning flow: test-card token -> AUD 10 authorization -> lookup.

Loads local .env configuration through CheckoutClient; existing environment values win.
No real card input, capture request, or automatic retries.
Test card source: https://api-reference.checkout.com/tag/tokens
"""

from datetime import datetime, timezone
from pathlib import Path
import re
import sys
from uuid import uuid4

import httpx


def report_response(response):
    print("HTTP status:", response.status_code)
    request_id = response.headers.get("cko-request-id", "")
    if re.fullmatch(r"[A-Za-z0-9_-]{1,100}", request_id):
        print("Request ID:", request_id)


def report_error_details(response):
    # Only print symbolic error identifiers, never arbitrary response content.
    try:
        data = response.json()
    except ValueError:
        return
    if not isinstance(data, dict):
        return

    error_type = data.get("error_type")
    if isinstance(error_type, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,99}", error_type):
        print("Error type:", error_type)

    error_codes = data.get("error_codes")
    if isinstance(error_codes, list):
        for code in error_codes[:20]:
            if isinstance(code, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,99}", code):
                print("Error code:", code)


def main():
    # CheckoutClient loads .env at import without overriding existing environment values.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.clients.checkout_client import CheckoutClient
    from app.models.order import Order
    from app.services.payment_service import (
        authorize_order_payment, classify_payment_error, payment_from_response,
    )

    print("Sandbox only: one AUD 10.00 payment request with capture=False.")
    print("Uses a fixed provider test card. No real card data is accepted.")
    
    try:
        client = CheckoutClient()
        client.validate_token_config()
        client.validate_payment_config()
    except ValueError:
        print("Invalid Sandbox URL, key format, or processing channel ID. No request sent.")
        return 1

    order_id = "sandbox_order_" + uuid4().hex
    print("Order reference:", order_id, flush=True)
    print("Keep this reference for Dashboard reconciliation if the payment outcome is uncertain.")
    stage = "token creation"

    try:
        # Fixed provider example card; future expiry is for Sandbox testing only.
        token_response = client.create_token({
            "number": "4543474002249996",
            "expiry_month": 12,
            "expiry_year": datetime.now(timezone.utc).year + 2,
            "cvv": "956",
        })
        print("Token creation:")
        report_response(token_response)
        payment_token = token_response.json()["token"]
        if not isinstance(payment_token, str) or not payment_token.startswith("tok_"):
            raise ValueError

        stage = "payment creation"
        payment_response = authorize_order_payment(
            client, Order(id=order_id, amount=1000, currency="AUD"), payment_token
        )
        print("Payment creation:")
        report_response(payment_response)
        payment_data = payment_response.json()
        payment_id = payment_data["id"]
        if not isinstance(payment_id, str) or re.fullmatch(r"pay_[A-Za-z0-9_]{26}", payment_id) is None:
            raise ValueError
        print("Payment ID:", payment_id, flush=True)
        payment = payment_from_response(order_id, payment_data)
        print("Provider status:", safe_status(payment_data))
        print("Local status:", payment.status)

        stage = "payment lookup"
        lookup_response = client.get_payment(payment.payment_id)
        print("Payment lookup:")
        report_response(lookup_response)
        print("Provider status:", safe_status(lookup_response.json()))
        print("Flow completed. No capture request was sent; inspect the payment in Sandbox Dashboard.")
        return 0
    except httpx.HTTPStatusError as error:
        print("HTTP error during", stage)
        report_response(error.response)
        report_error_details(error.response)
        decision = classify_payment_error(error)
        print("Error category:", decision.kind)
        print("Next action:", decision.action)
    except httpx.RequestError as error:
        print("Connection error or timeout during", stage)
        decision = classify_payment_error(error)
        print("Error category:", decision.kind)
        print("Next action:", decision.action)
    except (ValueError, KeyError, TypeError):
        print("Unexpected response format during", stage)

    if stage == "token creation":
        print("Payment creation was not attempted.")
    else:
        print("Do not rerun blindly: inspect Dashboard using the order reference/payment ID first.")
        print("A request error does not establish whether the payment was processed.")
    print("No automatic retry was attempted.")
    return 1


def safe_status(data):
    if not isinstance(data, dict):
        return "unavailable"
    status = data.get("status")
    if isinstance(status, str) and re.fullmatch(r"[A-Za-z ]{1,50}", status):
        return status
    return "unavailable"


if __name__ == "__main__":
    raise SystemExit(main())
