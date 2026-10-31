# Technical Requirements

## FR-001: API Authentication

The application must:

1. Read the Checkout.com secret API key from environment variables.
2. Authenticate requests using the Authorization header.
3. Support Sandbox and Production configuration.
4. Handle HTTP 401 and 403 responses.
5. Never expose API credentials in logs.

## FR-002: Payment Creation

The application must:

1. Accept a payment amount and currency.
2. Send payment requests to Checkout.com's Payments API.
3. Support idempotency keys.
4. Return the payment ID and status.
5. Handle unsuccessful API responses.

## FR-003: Webhook Processing

The application must:

1. Expose a webhook endpoint.
2. Verify incoming webhook signatures.
3. Detect duplicate webhook events.
4. Update payment status.
5. Return appropriate HTTP responses.

## Non-Functional Requirements

- Secure credential management
- Automated unit and integration tests
- Structured logging
- Reliable retry handling
- CI/CD automation