# API Inventory — Checkout.com Sandbox

All paths are relative to the configured account-specific Sandbox base URL:
`https://{prefix}.api.sandbox.checkout.com`. Keys are supplied as Bearer headers.
This list describes the repository's current integration, not every provider API.

| Method and path | Client method | Purpose | Key | Verification in this project |
| --- | --- | --- | --- | --- |
| `POST /tokens` | `create_token(card)` | Exchange a provider test card for a token | Public | Mock tests and earlier user-run live Sandbox `201` |
| `POST /payments` | `create_payment(..., capture=..., idempotency_key=None)` | Create a token-based payment; authorization services choose AUD and `capture=False`; optionally forward a retained key | Secret | Earlier user-run live `201`, Authorized; M4 key forwarding, consistency guard and conflict/replay behavior: mocks only |
| `GET /payments/{id}` | `get_payment(payment_id, timeout=10.0)` | Read payment status/balances; reconcile against trusted original order values | Secret | Earlier user-run live `200`, Authorized; M4 reconciliation and bounded GET retries: mocks only |
| `POST /payments/{id}/captures` | `capture_payment(payment_id, amount, reference)` | Submit a capture action | Secret | Mock tests and user-run live Sandbox acceptance; action subsequently confirmed succeeded |
| `GET /payments/{id}/actions` | `get_payment_actions(payment_id)` | Read action history and reconcile a specific capture | Secret | Mock tests and user-run live Sandbox confirmation: succeeded (2026-11-02) |
| `POST /payments/{id}/voids` | `void_payment(payment_id, amount, reference)` | Release remaining uncaptured authorization | Secret | Mocks and user-run live Void action confirmation: succeeded |
| `POST /payments/{id}/refunds` | `refund_payment(payment_id, amount, reference)` | Return captured funds within refund availability | Secret | Mocks and user-run live Partial Refund `400` and remaining Refund `600` action confirmations: succeeded, Reason None |

The capture endpoint also supports explicit `NonFinal` and `Final` choices. The
partial-capture request and its specific action are user-verified live as
succeeded. Final-remaining Capture `500` was also confirmed `succeeded`,
`Reason: None` (2026-11-02), as was remaining Refund `600`. The earlier first full
capture was also confirmed live. These are exact-action confirmations, not
independent verification of fresh payment balances or settlement.

API definitions: [Tokens reference](https://api-reference.checkout.com/tag/tokens)
and [Payments reference](https://api-reference.checkout.com/tag/payments).
Direct `card` tokenization is a testing exercise. The planned website uses Flow
Payment Sessions; raw PAN/CVV must not reach the merchant backend.

## Current business workflows

- **Authorize an order:** script → `authorize_order_payment()` → payment client.
- **Submit a retained authorization operation (M4):** caller retains the snapshot
  from `create_authorization_operation()` → `submit_authorization_operation()` →
  Client validates/forwards the key and checks request consistency → one payment POST.
- **Reconcile an uncertain authorization (M4):** `reconcile_authorization()` →
  known payment ID lookup → match ID/reference/amount/currency → observed status
  and operator guidance. No ID means unknown/manual investigation without HTTP.
- **Request full capture:** `capture_authorized_payment()` → payment lookup →
  eligibility checks → one capture POST → request result.
- **Confirm capture:** `confirm_capture()` → actions GET → exact ID/type/amount
  match → boolean approval → confirmation snapshot.

Manual commands in `backend/scripts/`: `1_create_sandbox_payment.py`,
`2_get_sandbox_payment.py`, `3_capture_sandbox_payment.py`, and
`4_confirm_sandbox_capture.py`, plus `5_payment_operations.py` for partial capture,
void, refund and generic confirmation. `6_reconcile_authorization.py` provides
read-only reconciliation with optional bounded GET retries. See the README for arguments. Capture confirmation
is read-only; the capture command must not be rerun just to check its result.

`pay_...` identifies a payment; `act_...` identifies an individual action.
The payment response's capture `action_id` is matched against an action's `id`.
Never assume that the latest action is the capture being investigated.

`202` is request acceptance, not confirmation of completed capture or settlement.
An unlisted action or a failed lookup leaves the capture unconfirmed. No flow
automatically retries write requests or treats missing evidence as failure.

## M4 verification and remaining work

As of 2026-11-04, the offline client/model/service/script suite has **556 passing
tests**. M4 behaviors below are mock-verified, not live provider verification.
These workflows reuse existing payment endpoints; they do not add provider APIs.

- The service creates one UUID4 per new authorization operation. The Client
  accepts an optional `Cko-Idempotency-Key`; canonical UUID4 validation is a local
  policy. Legacy `authorize_order_payment()` and the creation CLI still omit it.
- A retained in-memory tracker binds the key to an HMAC fingerprint of method,
  URL and full payload before POST. Changed requests are rejected locally,
  including after timeouts or HTTP errors. Records contain keys and digests,
  not raw tokens. Clients must explicitly share a tracker to share bindings.
- HTTP `409` is classified as an uncertain request conflict, with guidance to
  stop writes and reconcile. Replayed `202` tests preserve the original payment
  ID and interpret body status rather than assuming successful payment.
- Reconciliation needs trusted order values and a payment ID associated with the
  original request, not a token or key. Matching fields alone cannot prove the
  provider's idempotency-key association. Failed lookups (including 404), malformed
  responses and mismatches remain unknown. Pending is returned without polling.
- Only reconciliation GETs support opt-in retries: timeout/network errors and
  HTTP 429/502/503/504. Default is one attempt; the policy allows up to five total
  attempts, exponential backoff/jitter, Retry-After seconds/date handling and a
  monotonic scheduling budget up to 60 seconds. It reduces per-phase timeouts but
  cannot forcibly cancel an active synchronous request or enforce a hard total
  wall-time limit. Exhaustion remains unknown. Other lookup HTTP errors stop.

The current official guide confirms default 72-hour key retention in Sandbox and
production, with configurable production settings. Effective account scope/source
eligibility and detailed financial POST retry rules still need verification; see
the [POST retry decision table](m4-post-retry-policy.md). Automatic POST retries and key support for capture/void/refund
are not implemented. Tracker consistency does not authorize retries, deduplicate
new keys, prevent concurrent writes or survive tracker/process replacement.
Records have no automatic eviction; durable storage remains M6.

See the [README M4 progress](../README.md#m4-in-progress--idempotency-safe-retries-and-timeout-reconciliation)
for the current checklist and CLI examples. The
[M4 learning guide](m4-key-learnings.md) and cheat sheet cover operation identity,
tracker consistency, reconciliation service/CLI and bounded GET retries.

## Planned, not implemented

- `POST /payment-sessions`: create the session for the planned Flow website.

These endpoints are not counted as used or live-tested APIs. Provider permissions
and current requirements must be checked when each flow is implemented.
