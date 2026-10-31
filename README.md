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
- [ ] M1: Sandbox configuration, credentials validation, and HTTPX client
- [ ] M2: Create and retrieve payments; validate amount/currency
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
│   └── tests/
├── frontend/
│   └── src/
│       ├── pages/
│       │   ├── Checkout.tsx
│       │   └── Dashboard.tsx
│       └── components/
├── docs/
│   ├── architecture.md
│   └── troubleshooting.md
├── README.md
├── REQUIREMENTS.md
├── .env.example
└── docker-compose.yml
```

**Note:** This is the target structure. Existing `app/` code can stay where it is until a tested refactor into `backend/`.

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
```

These are placeholders. Use the account-specific Sandbox base URL and credentials. Frontend/Docker setup instructions will be added once implemented.

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
