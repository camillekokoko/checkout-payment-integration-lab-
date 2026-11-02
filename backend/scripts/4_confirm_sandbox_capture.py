"""Read a specific Sandbox capture action. Never submit a capture request."""
'''
python scripts/4_confirm_sandbox_capture.py \
  pay_nna4tjqbpqbidl22nvvomxj6zm \
  act_np3flqezyfledouggdc4mniukq \
  --amount 1000 \
  --reference capture_sandbox_2ca1c85f
'''
import argparse
from pathlib import Path
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("payment_id")
    parser.add_argument("action_id")
    parser.add_argument("--amount", required=True, type=int, help="Expected capture amount in minor units")
    parser.add_argument("--reference", required=True, help="Original capture reference")
    args = parser.parse_args(argv)

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.clients.checkout_client import CheckoutClient
    from app.models.capture import CaptureResult
    from app.services.capture_service import confirm_capture

    try:
        client = CheckoutClient()
    except ValueError:
        print("Invalid Sandbox configuration. No request sent.")
        return 1

    # Reconstruct the expected action from the caller's saved request identifiers.
    capture = CaptureResult(
        args.payment_id, args.amount, args.reference, "accepted", args.action_id
    )
    print("Read-only Sandbox capture confirmation. No capture POST will be sent.")
    try:
        result = confirm_capture(client, capture)
    except ValueError:
        print("Invalid payment ID, action ID, or amount. No request sent.")
        return 1

    print("Payment ID:", result.payment_id)
    print("Action ID:", result.action_id)
    print("Confirmation:", result.status)
    print("Reason:", result.reason)
    if result.status == "unknown":
        print("Outcome unconfirmed. Do not resubmit capture based on this result.")
        return 2
    if result.status == "failed":
        print("Provider reported this action failed. No automatic retry was attempted.")
        return 1
    print("Provider confirmed this capture action succeeded; settlement is separate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
