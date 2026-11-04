"""Read-only authorization reconciliation after an uncertain payment request.

Run from backend/ with trusted original order values. No token or key required.
    python scripts/6_reconcile_authorization.py --order-id ORDER_REFERENCE --amount 1000 --currency AUD --payment-id PAYMENT_ID
Without a known payment ID, omit --payment-id for manual-investigation guidance.
Optional GET retries: --max-attempts 3 --retry-budget 20 (seconds).
Exit 0: recognized non-pending snapshot; 1: invalid input/config; 2: pending/unknown.
Exit 0 does not mean successful payment or permission for fulfillment/retry.
"""

import argparse
from pathlib import Path
import re
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--order-id", required=True, help="Trusted original order reference")
    parser.add_argument("--amount", required=True, type=int, help="Original amount in minor units")
    parser.add_argument("--currency", required=True, choices=("AUD",))
    parser.add_argument("--payment-id", help="Known payment ID associated with the original request")
    parser.add_argument("--max-attempts", type=int, choices=range(1, 6), default=1)
    parser.add_argument("--retry-budget", type=float, default=20.0, help="GET scheduling budget, up to 60 seconds")
    args = parser.parse_args(argv)

    if (
        not args.order_id.strip() or len(args.order_id) > 80 or args.amount <= 0
        or (args.payment_id is not None and re.fullmatch(r"pay_[A-Za-z0-9_]{26}", args.payment_id) is None)
    ):
        print("Invalid reconciliation input. No request sent.")
        return 1

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.clients.checkout_client import CheckoutClient
    from app.models.order import Order
    from app.services.authorization_reconciliation import reconcile_authorization
    from app.services.reconciliation_retry import LookupRetryPolicy

    try:
        policy = LookupRetryPolicy(args.max_attempts, args.retry_budget)
    except ValueError:
        print("Invalid retry policy. No request sent.")
        return 1

    client = None
    if args.payment_id is not None:
        try:
            client = CheckoutClient()
        except ValueError:
            print("Invalid Sandbox configuration. No request sent.")
            return 1
    result = reconcile_authorization(
        client, Order(args.order_id, args.amount, args.currency), payment_id=args.payment_id,
        retry_policy=policy,
    )
    print("Read-only reconciliation. No writes.")
    print("Maximum GET attempts:", policy.max_attempts)
    print("Observed status:", result.status)
    print("Payment ID:", result.payment_id or "unavailable")
    print("Reason:", result.reason)
    print("Next action:", result.action)
    return 2 if result.status in ("unknown", "pending") else 0


if __name__ == "__main__":
    raise SystemExit(main())
