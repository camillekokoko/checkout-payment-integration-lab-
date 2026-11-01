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
- [ ] M3: Authorization-only, capture, void, and refunds (where supported)
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
  The client currently propagates errors without automatically retrying.

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
- [x] Accept only the exact currency string `AUD`; reject other currencies,
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

Latest verified offline test result: **136 passed** (client, model, service, and script tests). This does not verify live
Sandbox authentication or payment processing.

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
│   │   └── create_sandbox_payment.py  # Manual Sandbox learning flow
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
.venv/bin/python backend/scripts/create_sandbox_payment.py
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
