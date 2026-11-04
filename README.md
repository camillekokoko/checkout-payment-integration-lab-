# Checkout.com Payment Integration Lab

A production-inspired **end-to-end merchant payment integration demo** using Checkout.com Sandbox, a Python FastAPI backend, and a React/TypeScript frontend.

> Learning / portfolio project; not affiliated with Checkout.com. Sandbox test payments only.

## Features to build

**Customer Checkout:** Sample cart, checkout using an official Checkout.com-supported client-side payment component, payment result, and order status.

**Merchant Dashboard:** Authenticated transaction list, payment details, authorization/capture/refund actions, webhook event timeline, and troubleshooting views.

## Tech Stack

| Layer | Technology |
| --- | --- |
| Frontend | React, TypeScript |
| Backend | Python 3.12+, FastAPI |
| Checkout.com API Client | HTTPX |
| Database | PostgreSQL |
| Backend Testing | pytest |
| Frontend Testing | Vitest, React Testing Library (planned) |
| CI/CD | Docker, GitHub Actions |

## Architecture

```text
Customer Checkout (React)          Merchant Dashboard (React)
        |                                     |
        | Checkout.com client SDK             | Merchant API
        | (public key if required)            |
        +------------------+------------------+
                           |
                   FastAPI Merchant Backend
                      |             |
                      |             +--> PostgreSQL
                      |                  (orders, payments, events)
                      |
                      +--> Checkout.com Payments API
                           (secret key, server-side)

Checkout.com Webhooks --> FastAPI Webhook Handler --> PostgreSQL
                            (verify + deduplicate)
```

The exact Checkout.com client SDK and session/tokenization flow depend on the chosen product (e.g. Flow or Frames). Never collect or store raw card details in our backend.

## Development Roadmap

### Phase 1: Python Backend & Provider Integration
- [x] M1: Sandbox configuration, credentials validation, and HTTPX client
- [x] M2: Sandbox payment creation/lookup, validation, in-memory records, and error decisions
- [x] M3: Sandbox authorization-only, capture, void, and refund services (scoped)
- [ ] M4: Idempotency, safe retries, and timeout reconciliation
- [ ] M5: Webhook signature verification, deduplication, and event processing
- [ ] M6: PostgreSQL order/payment/operation/event persistence

### Phase 2: Customer & Merchant UI
- [ ] M7: React customer checkout using Checkout.com-supported SDK
- [ ] M8: Payment result and order status pages
- [ ] M9: Authenticated merchant dashboard with capture/refund controls
- [ ] M10: Webhook event timeline and troubleshooting view

### Phase 3: Testing, CI/CD & Observability
- [ ] M11: pytest backend tests and frontend component tests
- [ ] M12: Docker Compose and GitHub Actions CI
- [ ] M13: Structured logging, correlation IDs, and secret redaction
- [ ] M14: Payment incident simulations and final demo documentation

Milestones are checked off only when code, tests, and documentation are complete.

### M1 Complete — Configuration and HTTPX Client

Learning notes: [M1 Key Learnings](docs/m1-key-learnings.md).

M1 covers local configuration validation, authentication header construction,
explicit timeouts, and propagation of HTTP errors to the caller. Credential
validation here means local format checks, not verification of live Sandbox keys.

- [x] Load the secret key and base URL from environment variables.
- [x] Raise a clear error when either required setting is missing.
- [x] Make HTTPX requests with an explicit timeout.
- [x] Test token public-key validation, token request construction, and response forwarding with mocks.
- [x] Test timeout propagation without automatic retries for token and payment creation.
- [x] Test that a missing secret key raises a clear error.
- [x] Test that a missing base URL raises a clear error.
- [x] Test that payment creation uses the secret key in its authentication header.
- [x] Test the authentication header and successful response forwarding for payment lookup.
- [x] Test that payment creation raises HTTPStatusError for 401, 403, 429,
  500, 502, 503, and 504, preserving the response without automatic retries.
- [x] Test that payment lookup propagates HTTP errors (401, 403, 404, 429,
  500, 502, 503, and 504), preserving the response without automatic retries.
- [x] Test that token creation propagates HTTP errors (401, 403, 422, 429,
  500, 502, 503, and 504), preserving the response without automatic retries.
- [x] Review Bearer key formats and the unique Sandbox base URL against official documentation.
- [x] Reject secret keys without the Sandbox `sk_sbox_` prefix (format guard only).
- [x] Validate the Sandbox HTTPS hostname and reject credentials, explicit ports,
  extra paths, queries, and fragments. Accept and normalize a trailing slash.

### Follow-up Work — M4, M6, and M7

- [x] M2: Choose Flow Payment Sessions for the website; implementation belongs
  to M7. The Python card-token method remains a learning exercise.
- [x] M2: Add application-level operator decisions for authentication and permission errors.
- [ ] M6: Persist merchant order/payment associations in PostgreSQL.
- [ ] M4: Handle rate limits, safe retries, and uncertain payment outcomes.
  Reconciliation GETs now support opt-in bounded retries; financial POSTs still
  propagate errors without automatic retries.

> **Tokenization — learning use only:** Token creation requires a Public Key,
> and direct requests with `type: "card"` are for testing only. The Python
> `create_token(card)` method is a learning exercise. The intended merchant
> checkout must use a supported client-side payment component to handle card
> details; the merchant backend must not receive raw PAN/CVV.
> See the official [Tokens reference](https://api-reference.checkout.com/tag/tokens).

Documentation review (2026-11-01): the official
[authentication reference](https://api-reference.checkout.com/) specifies Bearer
secret keys for supported server-side endpoints and Bearer public keys for
client-side authentication. Sandbox requests use an account-specific
`https://{prefix}.api.sandbox.checkout.com` base URL. The
[Tokens reference](https://api-reference.checkout.com/tag/tokens) requires a public
key for token creation and limits direct `card` token requests to testing.
The existing header formats match these formats, but this is not live credential
verification. The merchant checkout must use a supported client-side component;
the backend must not receive raw card details.

### M2 Complete — AUD Sandbox Payment Creation and Lookup

Scope and walkthrough: [M2 Completion](docs/m2-completion.md). M2 covers the
Python learning flow and in-memory records. Durable persistence belongs to M6;
the Flow website integration belongs to M7. This does not complete all of FR-002.

Visual reference: [M2 Cheat Sheet (JPG)](docs/assets/m2-cheat-sheet.jpg).

- [x] Implement payment creation and lookup client methods.
- [x] Validate positive integer amounts in minor units, rejecting booleans.
- [x] Apply the merchant's AUD-only policy in the payment service; reject other currencies,
  lowercase input, whitespace, and invalid types before sending an HTTP request.
- [x] Test that AUD 10.00 is sent as amount `1000` and currency `AUD`.
- [x] Validate `CHECKOUT_PROCESSING_CHANNEL_ID` before payment creation and send
  it in the payment payload. This resolved the initial Sandbox
  `422 processing_channel_id_required` error.
- [x] Verify one live Sandbox flow: token creation `201`, AUD 10.00 payment
  creation `201` with status `Authorized`, and payment lookup `200` returning
  `Authorized`. No capture request was sent.
- [x] Accept a required merchant `order_id` and send it as the payment `reference`.
- [x] Validate order IDs as nonblank strings of at most 80 characters; preserve
  accepted IDs unchanged, including any surrounding whitespace.
- [x] Convert payment responses into in-memory `Payment` records linked to an
  order and reject missing, blank, or incorrectly typed required response fields.
- [x] Map `Pending`, `Authorized`, and `Declined` to local statuses. Unrecognized
  statuses remain `unknown`; capture/refund state handling belongs to M3.
- [x] Classify authentication, permission, validation, rate-limit, and uncertain
  errors in the manual script, with operator guidance and no automatic retries.
- [x] Test the script offline, including successful lookup, HTTP errors, timeout,
  and an incomplete payment response without creating another payment.
- [x] Select Flow Payment Sessions for the planned client-side checkout.

The script's records are not persisted. Safe retries/idempotency (M4), webhooks
(M5), PostgreSQL (M6), and Flow UI/session endpoints (M7) remain unfinished.

Latest verified offline test result: **556 passed** (2026-11-04; client, model, service, and script tests). This does not verify live
Sandbox authentication or payment processing.

Layer responsibilities: `authorize_order_payment(client, order, token)` applies
the merchant's AUD-only, authorization-only policy. `CheckoutClient.create_payment()`
validates request formats and requires an explicit keyword-only `capture` boolean;
it forwards the currency and capture choice instead of deciding merchant policy.
The manual Sandbox script invokes the service and still sends `capture=False`.

### M3 Complete — Sandbox Capture, Void, and Refund Services

M3 completion covers the internal AUD Sandbox services, CLI flows, mocks and
representative live action confirmations. Authenticated merchant API access,
idempotency, durable operation storage and verified webhooks remain later work.
Final-remaining capture `500` and remaining refund `600` also have user-run live
exact-action confirmations: `succeeded`, `Reason: None` (2026-11-02).

- [x] Add the capture client method with payment ID, positive integer amount,
  and reference validation before sending a request.
- [x] Test capture URL, Secret Key header, payload, timeout, and forwarding of a
  mocked `202 Accepted` response. Acceptance is not capture completion.
- [x] Test invalid inputs send no request and HTTP/transport errors propagate
  without automatic retries (33 capture tests).
- [x] Add a first-full-capture service: fresh lookup, matching payment ID, AUD,
  Authorized status, and integer balance checks before POST. Reject previous
  captures/voids, partial requests, and amounts above the available balance.
- [x] Return request outcomes as accepted, rejected, or unknown; a valid `202`
  acknowledgement records an action ID without marking the payment captured.
- [x] Test the complete capture service with mocked HTTP (58 service cases),
  including lookup failures, malformed responses, and no automatic retries.
- [x] Add a read-only capture confirmation service using the exact action ID,
  Capture type, amount, and boolean approval; missing evidence remains unknown.
- [x] Test confirmation and the combined capture/confirmation scenario without
  another capture POST. No automatic polling, retries, or persistence added.
- [x] User-run live Sandbox capture request returned accepted with an action ID.
- [x] User-run live Sandbox action lookup confirmed the specific AUD 10.00
  capture succeeded (`Confirmation: succeeded`, `Reason: None`, 2026-11-02).
  This verifies the capture action, not settlement.
- [x] Implement partial capture with explicit NonFinal, and final capture of the
  entire remaining balance; validate provider capture availability before POST.
- [x] Implement full void of remaining uncaptured authorization, and full/partial
  refunds within current refundable availability, with matching action confirmation.
- [x] Add mocked client/service/CLI tests and payment snapshot mappings for capture,
  void, and refund states. Operator authentication and persistence remain future work.
- [x] User-run live Sandbox void `1000` and refund `400` requests returned accepted
  with action IDs (2026-11-02); acceptance is not final confirmation.
- [x] Live Void `1000` and Refund `400` exact-action lookups both reported
  `Confirmation: succeeded`, `Reason: None` (2026-11-02).
- [x] User console log supplied live partial capture `500` acceptance and its action ID.
- [x] Live partial Capture `500` exact-action lookup reported
  `Confirmation: succeeded`, `Reason: None` (2026-11-02).
- [x] Live final-remaining Capture `500` (`shipment_final`) and remaining Refund
  `600` (`return_final`) exact-action lookups both reported
  `Confirmation: succeeded`, `Reason: None` (2026-11-02).

Business scenarios, walkthroughs, commands and Dashboard evidence:
[M3 Payment Lifecycle](docs/m3-payment-lifecycle.md).
Visual reference: [M3 Cheat Sheet](docs/assets/m3-cheat-sheet.jpg).
Provider endpoints and live/mock verification: [API Inventory](docs/api-inventory.md).
Lookup plus capture is not atomic and does not prevent concurrent or repeated
requests; idempotency and durable operation tracking remain follow-up work.

### M4 In Progress — Idempotency, Safe Retries, and Timeout Reconciliation

**Status: in progress (2026-11-04).** The authorization operation identity,
idempotency header support, conflict/replay handling, read-only reconciliation
service/CLI and opt-in bounded reconciliation GET retries are implemented and
mock-tested. Default provider retention and concurrency behavior are now documented;
financial POST retry implementation and remaining eligibility/scope checks are unfinished.
Business scenario: a merchant submits a payment request
and receives a timeout. Determine what happened and whether another attempt is
safe without creating a duplicate payment or financial operation.

Work in complete scenario batches, using implementation → tests → walkthrough
before moving to the next scenario.

1. **Retry the same logical operation safely.**
   - [x] Add immutable `AuthorizationOperation` with key, order ID, amount,
     currency and token; exclude the token from `repr` (not from serialization).
   - [x] Add `create_authorization_operation()` to generate a UUID4 once, and
     `submit_authorization_operation()` to forward the retained snapshot with
     `capture=False`, without automatic retries.
   - [x] Add optional `idempotency_key` support to `CheckoutClient.create_payment()`:
     validate canonical UUID4 format as a local policy and send `Cko-Idempotency-Key`.
   - [ ] Verify Checkout.com's idempotency support, scope, retention and limitations
     for each relevant endpoint before enabling retries. Payment header support
     and default 72-hour Sandbox/production retention are confirmed. Account-specific
     scope/settings, source eligibility and detailed POST error rules remain open.
   - [x] Preserve the same key and operation inputs across explicit submission
     attempts; generate a distinct key when creating a new operation.
   - [x] Detect conflicting requests for the same key within a retained in-memory
     tracker, using a fingerprint of method, URL and the complete payload. Retain
     bindings after errors and reject changes before HTTP.
2. **Reconcile an uncertain outcome.**
   - [x] Keep timeout/ambiguous error decisions uncertain; classify HTTP `409` as
     `request_conflict` with `outcome_unknown=True` and guidance to stop writes,
     reconcile the original operation and avoid replacing its key. The status
     alone does not establish the exact conflict cause.
   - [x] Test replayed `202` responses preserve the original payment ID and map
     the response body's status rather than treating HTTP acceptance as success.
   - [x] Add read-only payment reconciliation for a known payment ID; validate
     ID, original reference, integer amount and currency before adopting its status.
     Exact-action confirmation remains available through the M3 commands.
   - [x] Keep no-ID outcomes unresolved and provide manual-investigation guidance
     without a request; automated no-ID recovery is not implemented.
   - [x] Return observed status and operator guidance: wait for Pending, investigate
     unknown/mismatched evidence, and use known snapshots for the next business
     decision. No result automatically authorizes another write or fulfillment.
3. **Apply a bounded retry policy.**
   - [x] Separate reconciliation GET retry rules from financial POSTs; default to
     one GET attempt, with opt-in retries for timeout/network errors and HTTP
     429/502/503/504. Other HTTP errors and received payment evidence stop retries.
   - [x] Add exponential backoff, jitter, Retry-After seconds/date handling, up to
     five total attempts and a monotonic scheduling budget of up to 60 seconds.
     Reduce per-phase request timeouts to the remaining budget. The budget does
     not forcibly cancel an active synchronous request or guarantee a hard wall-time limit.
   - [x] Research and document default provider retention, caching, concurrency
     and minimum wait in a POST retry decision table; automatic POST retries remain disabled.
   - [ ] Resolve financial POST source/error eligibility, account-specific scope/settings
     and rate-limit/transient-error rules before enabling write retries.
   - [ ] Retry a POST only with evidence that it is safe, preserving the original
     idempotency key and payload.
4. **Verify and document the operator workflow.**
   - [x] Mock a provider completing an operation while its response is lost;
     verify the same key and HTTP payload on a separately initiated submission.
   - [x] Test timeout followed by `409`, replayed `202` statuses, distinct keys
     for new operations, and invalid keys blocked before HTTP.
   - [x] Test changed amounts, tokens, references, currency, capture choice,
     processing channels and URLs, plus tracker sharing across Clients.
   - [x] Test request conflicts, transient GET failures, Retry-After, no-ID handling,
     mismatched evidence, exhausted attempts/budgets and zero POSTs. Retry tests
     use fake time and do not actually sleep or contact the provider.
   - [x] Add `6_reconcile_authorization.py` with explicit snapshot, reason, next
     action and exit codes; require no token or idempotency key for reconciliation.
   - [x] Refresh the learning walkthrough and cheat sheet with reconciliation
     service/CLI, exit-code semantics and bounded GET retry behavior and limits.

Current flow: caller retains the snapshot returned by
`create_authorization_operation(order, token)`, then passes it to
`submit_authorization_operation(client, operation)`. Submission errors propagate
for the caller to classify; no retry loop, waiting or lookup is triggered.
Tests simulate later attempts and provider replay behavior, not permission to
retry live requests without a verified policy.

For follow-up reads, `reconcile_authorization(client, order, payment_id=...)`
accepts trusted original Order values rather than the token-bearing operation.
The caller must supply the ID associated with the original request: matching
reference/amount/currency alone cannot prove an idempotency-key association.
The service returns a snapshot without persisting it. Lookup failure, including
404, does not establish that the original payment failed.

The existing `authorize_order_payment()` and manual payment-creation CLI still use
the legacy path without an idempotency key. Capture, void and refund have not yet
received this key support. An immutable snapshot does not detect separately
constructed conflicting operations, deduplicate a new key for the same order,
or freeze client configuration such as the processing channel. The Client's tracker
now detects inconsistent requests for retained keys, including channel changes.
Each Client has a tracker by default; sharing one across Clients must be explicit.
Bindings are not automatically evicted and do not survive a new tracker or process
restart. Account scope, durable operation tracking and effective account-specific
retention checks remain follow-up work.

Provider research and current local decisions:
[M4 Authorization POST Retry Policy](docs/m4-post-retry-policy.md).

Current walkthrough: [M4 Key Learnings](docs/m4-key-learnings.md).
Visual reference: [M4 Cheat Sheet](docs/assets/m4-cheat-sheet.jpg).

Completion requires the agreed scenarios and failure cases to pass offline tests,
with retry/reconciliation decisions explained in a walkthrough. PostgreSQL
persistence remains M6 and verified webhooks remain M5. Document the limitations
of in-memory operation tracking across process restarts; M4 alone does not
establish durable crash recovery or concurrency safety.

## Planned Repository Structure

```text
checkout-payment-integration-lab/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── clients/
│   │   ├── services/
│   │   ├── webhooks/
│   │   └── models/
│   ├── scripts/
│   │   ├── 1_create_sandbox_payment.py
│   │   ├── 2_get_sandbox_payment.py
│   │   ├── 3_capture_sandbox_payment.py
│   │   ├── 4_confirm_sandbox_capture.py
│   │   ├── 5_payment_operations.py
│   │   └── 6_reconcile_authorization.py
│   └── tests/
│       ├── clients/
│       ├── models/
│       ├── services/
│       └── scripts/
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── Checkout.tsx
│       │   └── Dashboard.tsx
│       └── components/
├── docs/
├── README.md
├── REQUIREMENTS.md
├── .env.example
└── docker-compose.yml
```

**Note:** This is the target structure; some components are not implemented yet.
The current client is in `backend/app/clients/checkout_client.py`.
Manual execution belongs in `backend/scripts/`; reusable application code belongs
in `backend/app/`, and offline unit tests are grouped under `backend/tests/`.

## Local Setup (Current Milestone)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install httpx python-dotenv pytest
```

Configure a local `.env` file (never commit it):

```dotenv
CHECKOUT_SECRET_KEY=sk_sbox_REPLACE_ME
CHECKOUT_BASE_URL=https://YOUR_PREFIX.api.sandbox.checkout.com
CHECKOUT_PROCESSING_CHANNEL_ID=pc_REPLACE_WITH_YOUR_SANDBOX_CHANNEL_ID
```

These are placeholders. Use the account-specific Sandbox base URL and credentials. Frontend/Docker setup instructions will be added once implemented.

### Manual Sandbox Payment (Opt-in)

From the project root:

```bash
.venv/bin/python backend/scripts/1_create_sandbox_payment.py
```

This is a live Sandbox learning exercise, not an offline test. The script first
reads `CHECKOUT_BASE_URL`, `CHECKOUT_SECRET_KEY`, `CHECKOUT_PUBLIC_KEY`, and
`CHECKOUT_PROCESSING_CHANNEL_ID` from the
process environment, with local `.env` loading provided by `CheckoutClient`.
Existing environment values take precedence. Missing or invalid settings stop
the script before any API request; there are no interactive configuration prompts.
The script uses a fixed provider example test card to create a token,
requests one AUD 10.00 payment with `capture=False`, then looks up the returned
payment ID. It prints selected status fields and identifiers, not credentials,
tokens, or complete response bodies. It does not automatically retry. If payment
creation or lookup fails, inspect the Dashboard using the printed order reference
or payment ID before running it again. Account configuration may require additional
fields; a successful authorization is not guaranteed.

The script has been checked offline with mocked responses. A user-run live
Sandbox exercise also verified token creation (`201`), payment authorization
(`201`, `Authorized`), and lookup (`200`, `Authorized`). This verifies that flow
for the tested configuration; it does not verify capture, settlement, webhooks,
or reconciliation.

### Read-only Sandbox Payment Lookup (Opt-in)

From the project root, replace the ID below with an existing Sandbox payment ID:

```bash
.venv/bin/python backend/scripts/2_get_sandbox_payment.py pay_REPLACE_WITH_PAYMENT_ID
```

This script sends one GET and prints only the payment ID, status, currency and
selected balances. It does not create payments, submit captures, or retry.
Missing or invalid balances are reported as an unexpected response, not zero.

### Authorization Reconciliation After an Uncertain Outcome (Opt-in)

From `backend/`, with the virtual environment activated, supply trusted original
order values and the known payment ID. Each command is kept on one line:

```bash
python scripts/6_reconcile_authorization.py --order-id ORIGINAL_ORDER_REFERENCE --amount 1000 --currency AUD --payment-id pay_REPLACE_WITH_PAYMENT_ID
```

This performs one GET by default. To opt into up to three total GET attempts with
a 20-second scheduling budget:

```bash
python scripts/6_reconcile_authorization.py --order-id ORIGINAL_ORDER_REFERENCE --amount 1000 --currency AUD --payment-id pay_REPLACE_WITH_PAYMENT_ID --max-attempts 3 --retry-budget 20
```

Omit `--payment-id` if none is available: the command reports unknown and manual
investigation guidance without HTTP or requiring credentials. No token or
idempotency key argument is needed. With an ID, Sandbox credentials are required.

The CLI reports observed status, payment ID, reason and next action. Exit `0`
means a recognized non-Pending snapshot (including Declined), not payment success;
`1` means invalid input/configuration and `2` means Pending/unknown. Argument-parser
errors also exit `2` before HTTP. Pending is not polled. Retries only recover
eligible GET failures; no path creates, captures, voids or refunds a payment.
The scheduling budget stops new attempts, not an already active synchronous GET.

### Manual Sandbox Capture and Confirmation (Opt-in)

From `backend/`, with the virtual environment activated, submit a first full
capture only for an eligible authorization. Replace the example IDs and reference:

```bash
python scripts/3_capture_sandbox_payment.py pay_REPLACE_WITH_PAYMENT_ID \
  --amount 1000 --reference capture_order_001
```

This command performs a fresh GET and, if eligible, one capture POST. Keep its
action ID. Do not rerun it to check results; use the read-only command instead:

```bash
python scripts/4_confirm_sandbox_capture.py pay_REPLACE_WITH_PAYMENT_ID act_REPLACE_WITH_ACTION_ID \
  --amount 1000 --reference capture_order_001
```

Confirmation reads actions once. It never submits a capture or retries. Capture
exit codes: `0` accepted, `1` blocked/rejected/error, `2` uncertain. Confirmation
exit codes: `0` succeeded, `1` failed/invalid input/configuration, `2` unknown.
Neither command persists results or establishes settlement.

Partial capture, void, refund and generic action confirmation commands are grouped
under `scripts/5_payment_operations.py`; see [M3 Payment Lifecycle](docs/m3-payment-lifecycle.md).
User-run live lookups confirmed full capture, partial capture, void and partial
refund actions succeeded. Final-remaining Capture `500` and remaining Refund
`600` were also confirmed `succeeded`, `Reason: None` (2026-11-02). These are
action confirmations; fresh payment balances and settlement are not independently
verified by this evidence.

### Offline Unit Tests

From the project root, with the virtual environment activated:

```bash
cd backend
PYTHON_DOTENV_DISABLED=1 python -m pytest tests/clients tests/models tests/services tests/scripts -q
```

These tests use fake configuration and mocked HTTP calls. The environment flag
disables `.env` loading during this run. Run the specified test directories:
`backend/tests/test_connection.py` and `backend/tests/test_token_config.py` are
legacy manual scripts and are not part of this offline test suite. They still
need to be moved out of pytest discovery; the connection script also needs its
client import updated before manual use.

## Security

- Keep secret API keys exclusively on the backend; never embed them in frontend bundles or Git.
- Use an official Checkout.com-supported client-side payment component; a public key is only needed if required by that integration.
- Authenticate dashboard operators and authorize sensitive capture/refund operations on the backend.
- Verify webhook authenticity, deduplicate event IDs, and handle out-of-order events.
- Do not store raw PAN/CVV or log credentials and sensitive payment details.
- Reconcile ambiguous payment outcomes instead of assuming timeouts mean failure.

## Requirements

See [REQUIREMENTS.md](REQUIREMENTS.md) for functional requirements and acceptance criteria.

## Status

🚧 In development — Python Sandbox API client in progress.

## References

- [Checkout.com API reference](https://api-reference.checkout.com/)
- [Checkout.com documentation](https://www.checkout.com/docs)
