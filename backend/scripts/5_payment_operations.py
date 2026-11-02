"""Manual AUD Sandbox operations: three independent merchant business cases.

Run from backend/ with the virtual environment activated. Replace PAYMENT_ID
and ACTION_ID below with the relevant Sandbox identifiers. Amounts are minor
units: 1000 = AUD 10.00. Do not run all cases blindly against the same payment.

CASE 1 - Split shipment: partial capture
An AUD 10.00 order is authorized, but only AUD 5.00 of goods ship today.
Collect 500 using NonFinal and leave the rest open. After confirming the first
action and checking fresh balances, collect the remaining 500 using --final.
    python scripts/5_payment_operations.py partial-capture PAYMENT_ID --amount 500 --reference shipment_001
    python scripts/5_payment_operations.py partial-capture PAYMENT_ID --amount 500 --reference shipment_final --final
The second command is a separate business decision, not an automatic next step.

CASE 2 - Customer cancels before dispatch: void
An AUD 10.00 authorization has no captures. Release the full remaining 1000
hold instead of collecting money. A captured payment cannot use this void flow.
    python scripts/5_payment_operations.py void PAYMENT_ID --amount 1000 --reference canceled_order_001

CASE 3 - Customer returns an item after payment: partial refund
An AUD 10.00 payment was captured. Return AUD 4.00 (400), within the current
refundable balance. After confirmed success, 600 remains unrefunded if there
were no other refunds. Void and refund serve different payment lifecycle stages.
    python scripts/5_payment_operations.py refund PAYMENT_ID --amount 400 --reference return_001

AFTER EACH ACCEPTED REQUEST - Read-only confirmation
Keep the returned action ID. Use Capture, Void, or Refund to match the action
type, original amount, and reference. This command never sends an operation POST.
    python scripts/5_payment_operations.py confirm PAYMENT_ID --action-id ACTION_ID --action-type Refund --amount 400 --reference return_001
Accepted is not completed. Unknown/missing evidence is not failure. Do not
repeat a write merely to check its result; there are no automatic retries.
"""

import argparse
from pathlib import Path
import sys

import httpx


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("partial-capture", "void", "refund", "confirm"):
        command = commands.add_parser(name)
        command.add_argument("payment_id")
        command.add_argument("--amount", required=True, type=int, help="Minor units")
        command.add_argument("--reference", required=True)
        if name == "partial-capture":
            command.add_argument("--final", action="store_true", help="Capture the entire remaining balance")
        if name == "confirm":
            command.add_argument("--action-id", required=True)
            command.add_argument("--action-type", choices=("Capture", "Void", "Refund"), required=True)
    args = parser.parse_args(argv)

    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.clients.checkout_client import CheckoutClient
    from app.models.payment_operation import PaymentOperationResult
    from app.services.payment_operation_service import (
        capture_payment_amount, confirm_payment_operation,
        refund_captured_payment, void_authorized_payment,
    )
    try:
        client = CheckoutClient()
    except ValueError:
        print("Invalid Sandbox configuration. No request sent.")
        return 1

    is_confirmation = args.command == "confirm"
    print("Read-only action confirmation." if is_confirmation else "Sandbox only: lookup then at most one operation POST.")
    try:
        if is_confirmation:
            expected = PaymentOperationResult(
                args.action_type, args.payment_id, args.amount, args.reference, "accepted", args.action_id
            )
            result = confirm_payment_operation(client, expected)
        elif args.command == "partial-capture":
            result = capture_payment_amount(client, args.payment_id, args.amount, args.reference, final=args.final)
        elif args.command == "void":
            result = void_authorized_payment(client, args.payment_id, args.amount, args.reference)
        else:
            result = refund_captured_payment(client, args.payment_id, args.amount, args.reference)
    except ValueError:
        print("Invalid input, ineligible payment, or invalid lookup response. No operation POST sent.")
        return 1
    except httpx.HTTPStatusError as error:
        print("Payment lookup HTTP status:", error.response.status_code)
        print("No operation POST sent. No automatic retry.")
        return 1
    except httpx.RequestError:
        print("Payment lookup failed. No operation POST sent. No automatic retry.")
        return 1

    print("Action type:", result.action_type)
    print("Payment ID:", result.payment_id)
    print("Action ID:", result.action_id)
    print("Confirmation:" if is_confirmation else "Request status:", result.status)
    print("Reason:" if is_confirmation else "Error category:", result.reason if is_confirmation else result.error_kind)
    if result.status == "unknown":
        print("Outcome uncertain. Reconcile; do not repeat the write command.")
        return 2
    if result.status in ("failed", "rejected"):
        print("No automatic retry. Inspect the result before deciding the next action.")
        return 1
    if not is_confirmation:
        print("Keep the action ID and use the confirm command. Accepted is not completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
