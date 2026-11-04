# Project Tracker — Checkout.com Payment Integration Lab

**Last updated: 2026-11-04 · Australia/Melbourne**

Current milestone: **M4 — In progress**. Last verified offline suite: **575 passed**.
Latest completed batch: fail-closed authorization POST retry preflight (`d2523d6`).
The gate is a standalone helper, is not connected to submission, and never grants
POST retry permission. Automatic financial POST retries remain disabled.

This is a manually maintained work calendar and learning tracker. Dates below
record evidenced work, not deadlines. Future sessions are unscheduled.

## November 2026 work calendar

| Mon | Tue | Wed | Thu | Fri | Sat | Sun |
| --- | --- | --- | --- | --- | --- | --- |
| — | — | — | — | — | — | 1 |
| **2 · M3 complete; M4 plan** | 3 | **4 · M4 implementation + learning** | 5 | 6 | 7 | 8 |
| 9 | 10 | 11 | 12 | 13 | 14 | 15 |
| 16 | 17 | 18 | 19 | 20 | 21 | 22 |
| 23 | 24 | 25 | 26 | 27 | 28 | 29 |
| 30 | — | — | — | — | — | — |

Unannotated days have no work recorded in this tracker; they do not imply missed
work or a scheduled session. M1/M2 completion dates have not been reconstructed.

## Milestone board

| Milestone | Status | Completion evidence / next outcome |
| --- | --- | --- |
| M1 · Configuration and HTTPX client | Complete within documented scope | [Learning notes](m1-key-learnings.md) and README checklist |
| M2 · Payment creation and lookup | Complete within documented scope | [Completion notes](m2-completion.md) and README checklist |
| M3 · Capture, void and refund | Complete within documented scope | [Lifecycle guide](m3-payment-lifecycle.md), offline tests and user-run action confirmations |
| M4 · Idempotency, retry and reconciliation | **In progress** | Known-ID reconciliation and GET retries implemented; financial POST eligibility/integration remains |
| M5 · Verified, deduplicated webhooks | Planned | Signature verification, repeated/out-of-order events and safe processing |
| M6 · PostgreSQL persistence | Planned | Durable order/payment/operation/event records and restart consistency |
| M7 · Customer checkout | Planned | React checkout and Flow Payment Sessions |
| M8 · Payment result and order status | Planned | Customer-facing result/status flows |
| M9 · Merchant dashboard | Planned | Authenticated merchant controls |
| M10 · Event timeline | Planned | Webhook timeline and troubleshooting |
| M11 · Backend/frontend testing milestone | Planned; backend tests already ongoing | Broader testing milestone does not postpone tests for current batches |
| M12 · Docker and CI | Planned | Docker Compose and GitHub Actions |
| M13 · Observability | Planned | Structured logging, correlation IDs and secret redaction |
| M14 · Incident simulations and demo | Planned | Failure scenarios and final portfolio walkthrough |

## Session journal

| Date | Complete business scenario / batch | Evidence | State at end |
| --- | --- | --- | --- |
| 2026-11-02 | Finish Sandbox capture/void/refund confirmation evidence, including final Capture 500 and remaining Refund 600 | `2c9714c`; [M3 guide](m3-payment-lifecycle.md) | M3 scoped complete; 440 offline tests recorded |
| 2026-11-02 | Plan M4 work and completion criteria | `2d17c28` | M4 planned |
| 2026-11-04 | Retain one authorization identity across attempts; forward idempotency header; classify conflict/replay evidence | `3f4d449`, `d5f2f77` | Immutable operation and service/Client flow implemented; 466 tests recorded |
| 2026-11-04 | Reject changed requests under a retained key before HTTP | `160fb9a` | HMAC tracker and tests; 474 tests recorded |
| 2026-11-04 | Follow up unknown authorization using known payment ID; no-ID manual guidance | `b27868b` | Read-only service/CLI; 523 tests recorded |
| 2026-11-04 | Recover transient reconciliation GET failures within limits | `56c3ea9` | Opt-in GET retries; 556 tests recorded |
| 2026-11-04 | Document provider evidence, decision table and current learning flows | `2406dfc` | Research/documentation checkpoint; M4 remains in progress |
| 2026-11-04 | Assess retained context, timing, expiry and attempts before considering POST retry | `d2523d6` | Standalone fail-closed gate; 575 tests recorded; not wired into submission |

Test totals describe the recorded offline checkpoint, not live provider guarantees.
Commit IDs are historical evidence; a documentation commit does not imply a fresh
test run. No session durations or completion percentages are estimated.

## Next session — one bounded scenario

**Scenario:** an authorization response is lost; determine whether to reconcile,
wait or require manual review without submitting another payment.

- [ ] Walk through `AuthorizationRetryEvidence` and `assess_authorization_retry()`.
- [ ] Confirm understanding: waiting or matching fingerprints does not authorize a POST.
- [ ] Resolve how trustworthy first-send time, request fingerprint and account
  context will be retained before submission and supplied to the gate.
- [ ] Review unresolved provider token/error/scope rules in the
  [POST policy record](m4-post-retry-policy.md).
- [ ] Agree the next implementation batch and its failure-case tests after review.
- [ ] Synchronize learning docs/README/API inventory with gate progress and its
  integration limits; keep M4 in progress until completion criteria are met.

No date or deadline has been assigned. Do not start a different milestone merely
because the current helper tests pass.

## M4 work remaining

- [ ] Confirm account/source/error eligibility and effective scope/retention for
  financial POST retries; documented provider defaults alone do not resolve all rules.
- [ ] Connect trustworthy operation evidence and the decision gate to the agreed
  caller workflow, without falsely treating it as retry permission.
- [ ] Implement a justified bounded POST retry policy only after eligibility is resolved.
- [ ] Integrate retained-operation identity into the payment-creation CLI; legacy
  `authorize_order_payment()` and that CLI still omit the key.
- [ ] Define any additional capture/void/refund key scope with separate scenarios.
- [ ] Review completion evidence and limitations before marking M4 complete.

M5 webhooks and M6 durable persistence remain separate milestones. Manual no-ID
investigation is current behavior; automated recovery is not implemented.

## End-of-session update routine

1. Add a dated journal row with the completed business scenario and evidence.
2. Record the exact tests run/result, or state that no tests were rerun.
3. Check off only finished work; record unresolved questions separately.
4. Set one next-session scenario, with a date only if explicitly scheduled.
5. Commit/push only when requested. This file does not schedule reminders or
   automatically update from GitHub.
