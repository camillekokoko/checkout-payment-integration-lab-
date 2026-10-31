# Checkout.com Payment Integration Lab

A Python-based merchant payment integration project using
Checkout.com's Payments API.

## Project Objectives

Build a production-inspired payment integration that demonstrates:

- REST API integration
- Secure API authentication
- Payment authorization, capture, and refunds
- Idempotency and retry handling
- Webhook processing
- Payment status tracking
- Automated API testing
- CI/CD and observability

## Tech Stack

- Python 3.12+
- FastAPI
- HTTPX
- PostgreSQL
- pytest
- Docker
- GitHub Actions

## Development Roadmap

- [ ] Day 1: API Client & Authentication
- [ ] Day 2: Create Payment API
- [ ] Day 3: Authorization, Capture & Refund
- [ ] Day 4: Idempotency & Safe Retries
- [ ] Day 5: Webhook Receiver & Signature Verification
- [ ] Day 6: PostgreSQL & Payment Status Tracking
- [ ] Day 7: Automated API Testing
- [ ] Day 8: Docker & GitHub Actions CI/CD
- [ ] Day 9: Error Handling & Structured Logging
- [ ] Day 10: Production Troubleshooting Simulation

## Architecture

Merchant Client
    |
    v
Python FastAPI Backend
    |
    v
Checkout.com Payments API
    |
    v
Webhook Notifications
    |
    v
PostgreSQL

## Security

- Never commit API credentials.
- Store secrets in environment variables.
- Verify incoming webhook signatures.
- Use Checkout.com Sandbox for integration testing.

## Project Status

🚧 In Development