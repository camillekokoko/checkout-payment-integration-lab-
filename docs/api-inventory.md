# API Inventory — Checkout.com Sandbox

All paths are relative to the configured account-specific Sandbox base URL:
`https://{prefix}.api.sandbox.checkout.com`. Keys are supplied as Bearer headers.
This list describes the repository's current integration, not every provider API.

| Method and path | Client method | Purpose | Key | Verification in this project |
| --- | --- | --- | --- | --- |
| `POST /tokens` | `create_token(card)` | Exchange a provider test card for a token | Public | Mock tests and earlier user-run live Sandbox `201` |
| `POST /payments` | `create_payment(..., capture=...)` | Create a token-based payment; our service chooses AUD and `capture=False` | Secret | Mock tests and earlier user-run live Sandbox `201`, Authorized |
| `GET /payments/{id}` | `get_payment(payment_id)` | Read payment status and capture balances | Secret | Mock tests and earlier user-run live Sandbox `200`, Authorized |
| `POST /payments/{id}/captures` | `capture_payment(payment_id, amount, reference)` | Submit a capture action | Secret | Mock tests and user-run live Sandbox acceptance; action subsequently confirmed succeeded |
| `GET /payments/{id}/actions` | `get_payment_actions(payment_id)` | Read action history and reconcile a specific capture | Secret | Mock tests and user-run live Sandbox confirmation: succeeded (2026-11-02) |
| `POST /payments/{id}/voids` | `void_payment(payment_id, amount, reference)` | Release remaining uncaptured authorization | Secret | Mocks and user-run live request accepted; Void confirmation pending |
| `POST /payments/{id}/refunds` | `refund_payment(payment_id, amount, reference)` | Return captured funds within refund availability | Secret | Mocks and user-run live request accepted; Refund confirmation pending |

The capture endpoint also supports explicit `NonFinal` and `Final` choices. The
partial-capture request now has user-run live acceptance evidence, with its
specific action confirmation pending. Final-remaining capture is mock-verified
only; the earlier first full capture is the live-confirmed scenario.

API definitions: [Tokens reference](https://api-reference.checkout.com/tag/tokens)
and [Payments reference](https://api-reference.checkout.com/tag/payments).
Direct `card` tokenization is a testing exercise. The planned website uses Flow
Payment Sessions; raw PAN/CVV must not reach the merchant backend.

## Current business workflows

- **Authorize an order:** script → `authorize_order_payment()` → payment client.
- **Request full capture:** `capture_authorized_payment()` → payment lookup →
  eligibility checks → one capture POST → request result.
- **Confirm capture:** `confirm_capture()` → actions GET → exact ID/type/amount
  match → boolean approval → confirmation snapshot.

Manual commands in `backend/scripts/`: `1_create_sandbox_payment.py`,
`2_get_sandbox_payment.py`, `3_capture_sandbox_payment.py`, and
`4_confirm_sandbox_capture.py`, plus `5_payment_operations.py` for partial capture,
void, refund and generic confirmation. See the README for arguments. Capture confirmation
is read-only; the capture command must not be rerun just to check its result.

`pay_...` identifies a payment; `act_...` identifies an individual action.
The payment response's capture `action_id` is matched against an action's `id`.
Never assume that the latest action is the capture being investigated.

`202` is request acceptance, not confirmation of completed capture or settlement.
An unlisted action or a failed lookup leaves the capture unconfirmed. No flow
automatically retries write requests or treats missing evidence as failure.

## Planned, not implemented

- `POST /payment-sessions`: create the session for the planned Flow website.

These endpoints are not counted as used or live-tested APIs. Provider permissions
and current requirements must be checked when each flow is implemented.
