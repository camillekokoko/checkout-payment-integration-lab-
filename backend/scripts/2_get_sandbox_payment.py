"""Read one Sandbox payment's status and balances. No writes or retries."""

import argparse
from pathlib import Path
import re
import sys

import httpx


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payment_id", help="Existing Sandbox payment ID (pay_...)")
    args = parser.parse_args(argv)
    if re.fullmatch(r"pay_[A-Za-z0-9_]{26}", args.payment_id) is None:
        print("Invalid payment ID. No request sent.")
        return 1

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.clients.checkout_client import CheckoutClient

    try:
        client = CheckoutClient()
    except ValueError:
        print("Invalid Sandbox configuration. No request sent.")
        return 1

    print("Read-only Sandbox lookup. No payment or capture will be created.")
    try:
        response = client.get_payment(args.payment_id)
        data = response.json()
        fields = ("total_authorized", "total_captured", "total_voided", "available_to_capture")
        if response.status_code != 200 or not isinstance(data, dict) or data.get("id") != args.payment_id:
            raise ValueError
        balances = data.get("balances")
        status, currency = data.get("status"), data.get("currency")
        if (
            not isinstance(status, str) or re.fullmatch(r"[A-Za-z ]{1,40}", status) is None
            or not isinstance(currency, str) or re.fullmatch(r"[A-Z]{3}", currency) is None
            or not isinstance(balances, dict)
            or any(type(balances.get(field)) is not int or balances[field] < 0 for field in fields)
        ):
            raise ValueError
        print("HTTP status:", response.status_code)
        print("Payment ID:", args.payment_id)
        print("Status:", status)
        print("Currency:", currency)
        for field in fields:
            print(field + ":", balances[field])
        return 0
    except httpx.HTTPStatusError as error:
        print("Lookup HTTP status:", error.response.status_code)
    except httpx.RequestError:
        print("Lookup connection error or timeout. Payment outcome is not established.")
    except (ValueError, TypeError):
        print("Unexpected lookup response format. Payment outcome is not established.")
    print("No automatic retry was attempted.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
