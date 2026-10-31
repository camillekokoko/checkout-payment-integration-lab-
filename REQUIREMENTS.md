# Technical Requirements — Checkout.com Payment Integration Lab

## Scope

Build a sandbox-only end-to-end **merchant integration** using a Python FastAPI backend and React/TypeScript frontend, connected to Checkout.com. This is a portfolio project, not a production payment system.

### Actors
- **Customer:** places a test order and sees payment status.
- **Merchant operator:** views payments and performs permitted capture/refund actions.
- **Checkout.com:** processes API requests and delivers webhook events.

## Functional Requirements

### FR-001: Configuration and API Authentication
1. Load `CHECKOUT_SECRET_KEY` and `CHECKOUT_BASE_URL` from environment variables; fail fast if missing.
2. Use the appropriate Sandbox secret key for server-side Payments API calls.
3. Configure HTTP timeouts and distinguish HTTP 401, 403, 429, and transient 5xx errors.
4. Never expose secret credentials in frontend code, responses, or logs.

**Acceptance:** Missing configuration raises a clear error; unit tests validate authentication headers without printing credentials.

### FR-002: Payment Creation and Lookup
1. Accept merchant order ID, positive integer amount in minor units, and currency.
2. Use the documented Checkout.com payment/session/tokenization flow for the chosen checkout product.
3. Persist Checkout.com payment IDs and map provider status to local order/payment state.
4. Support retrieving the current payment state from the backend.

**Acceptance:** Mocked successful payment creates one local record; invalid amounts return a client error.

### FR-003: Authorization, Capture, Void, and Refund
1. Support authorization-only payments and subsequent capture where available.
2. Support full/partial capture and refund subject to provider capabilities.
3. Support voiding an uncaptured authorization where available.
4. Validate amounts, operation permissions, and payment state transitions.
5. Record each attempted financial operation.

**Acceptance:** Tests reject capture beyond authorized amount and unauthorized refund attempts.

### FR-004: Idempotency and Retry Handling
1. Use Checkout.com's documented `Cko-Idempotency-Key` header on supported write operations.
2. Reuse the same key when retrying the same logical operation after a timeout.
3. Apply bounded retries and exponential backoff/jitter to retryable failures.
4. Resolve ambiguous outcomes via payment lookup/actions or webhook reconciliation.
5. Persist operation identifiers to avoid duplicate processing after restarts.

**Acceptance:** Repeated requests and simulated timeouts do not duplicate local business operations.

### FR-005: Webhook Processing
1. Expose a FastAPI webhook endpoint.
2. Verify webhook authenticity using Checkout.com's documented mechanism before processing.
3. Persist event IDs and deduplicate repeated deliveries.
4. Handle retries and out-of-order events safely.
5. Update local state transactionally and return appropriate acknowledgments.

**Acceptance:** Invalid signatures are rejected; duplicate valid events do not apply changes twice.

### FR-006: PostgreSQL Persistence
1. Store orders, payments, provider IDs, capture/refund operations, and webhook events.
2. Enforce uniqueness on relevant operation/event identifiers.
3. Preserve timestamps and audit history without storing raw card data.

**Acceptance:** Duplicate event inserts are safely deduplicated; transaction history is queryable.

### FR-007: Customer Checkout UI (React + TypeScript)
1. Display a sample shopping cart and AUD total.
2. Integrate an official Checkout.com-supported client-side SDK/component (e.g., Flow or Frames, depending on integration choice).
3. Use a public key only if required by the chosen SDK; keep the secret key server-side.
4. Show pending, success, and failure states based on trusted backend/provider data.
5. Never collect or store raw card numbers/CVV in the merchant application.

**Acceptance:** A customer can complete a supported Sandbox test payment and view the order status.

### FR-008: Merchant Dashboard (React + TypeScript)
1. Authenticate merchant operators and enforce backend authorization.
2. Display transactions, amounts, currency, order/payment IDs, statuses, and timestamps.
3. Show payment actions and webhook event history.
4. Allow permitted capture, void, and refund operations with confirmations and validation.
5. Display errors and troubleshooting context without exposing secrets.

**Acceptance:** Unauthorized users cannot execute refund/capture via direct API calls; permitted actions appear in the audit trail.

### FR-009: Automated Testing
1. Use pytest for backend unit/integration tests with mocked provider calls.
2. Test configuration, HTTP errors, payment state transitions, idempotency, and webhooks.
3. Add frontend component and user-flow tests.
4. Keep real Sandbox integration tests opt-in and separate from offline CI.

**Acceptance:** Offline CI tests pass without live Checkout.com credentials.

### FR-010: CI/CD and Observability
1. Provide Docker Compose for backend, frontend, and PostgreSQL.
2. Run lint, tests, and builds through GitHub Actions.
3. Use structured logs, correlation IDs, and sensitive-data redaction.
4. Document webhook troubleshooting, reconciliation, and incident scenarios.

**Acceptance:** A fresh clone can run locally using documented commands; CI does not reveal secrets.

## Non-Functional Requirements

| Category | Requirement |
| --- | --- |
| Security | Least-privilege credentials, operator authorization, verified webhooks |
| Reliability | Idempotency, bounded retries, reconciliation |
| Data Integrity | Integer minor units, database constraints, transactional updates |
| Maintainability | Modular Python services, typed interfaces, clear configuration |
| Testability | Offline provider mocks; opt-in Sandbox tests |
| Observability | Structured logs, correlation IDs, operation/event visibility |
| Payment-data safety | Hosted/tokenized card entry; never store PAN/CVV |

## Definition of Done

A roadmap milestone is complete only after implementation, positive and negative tests, documentation updates, and a check that no credentials or sensitive payment data are committed.

## Out of Scope (Initial Version)

- Production payments and real customer/card data.
- Building a card vault or processing raw PAN/CVV.
- Complex disputes, multi-merchant onboarding, or settlement-file ingestion.

Provider SDK requirements, API permissions, endpoints, and webhook verification must be validated against the current [Checkout.com API reference](https://api-reference.checkout.com/) before implementation.
