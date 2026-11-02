"""Submit one first-full-capture request for an existing AUD Sandbox payment."""

import argparse
from pathlib import Path
import sys

import httpx


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payment_id")
    parser.add_argument("--amount", required=True, type=int, help="Amount in minor units")
    parser.add_argument("--reference", required=True, help="Reference for this capture request")
    args = parser.parse_args(argv)

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.clients.checkout_client import CheckoutClient
    from app.services.capture_service import capture_authorized_payment

    try:
        client = CheckoutClient()
    except ValueError:
        print("Invalid Sandbox configuration. No request sent.")
        return 1

    print("Sandbox only: fresh lookup, then at most one full-capture POST.")
    try:
        result = capture_authorized_payment(client, args.payment_id, args.amount, args.reference)
    except ValueError:
        print("Invalid capture input, ineligible payment, or invalid lookup response.")
        print("No capture was submitted.")
        return 1
    except httpx.HTTPStatusError as error:
        print("Payment lookup HTTP status:", error.response.status_code)
        print("No capture was submitted. No automatic retry was attempted.")
        return 1
    except httpx.RequestError:
        print("Payment lookup connection error or timeout. No capture was submitted.")
        print("No automatic retry was attempted.")
        return 1

    print("Payment ID:", result.payment_id)
    print("Amount:", result.amount)
    print("Request status:", result.status)
    print("Action ID:", result.action_id)
    print("Error category:", result.error_kind)
    print("No automatic retry was attempted.")
    if result.status == "accepted":
        print("Keep the action ID. Use 4_confirm_sandbox_capture.py to check the outcome.")
        print("Acceptance does not confirm completed capture.")
        return 0
    if result.status == "unknown":
        print("Outcome uncertain. Reconcile before another capture attempt.")
        return 2
    print("Request rejected. Inspect configuration before deciding the next action.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
