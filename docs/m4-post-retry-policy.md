# M4 — Authorization POST Retry Decision Table

**Research checkpoint: 2026-11-04. Scope: token-based AUD authorization through
`POST /payments`, with `capture=False`.** This is a policy/design record, not an
implemented automatic POST retry loop. Existing POST submission still sends once.

## Verified provider evidence

The current [official Idempotency guide](https://www.checkout.com/docs/developer-resources/api/idempotency)
(page metadata: updated August 19, 2026) documents:

- `/payments` and the listed payment action endpoints support `Cko-Idempotency-Key`.
- Default retention is 72 hours in both Sandbox and production. Production
  settings can be changed through the account manager/support; after expiry,
  requests are processed normally.
- Results are cached for `2xx`. A successful original request can be replayed
  using the same key. `4xx`/`5xx` results are not saved; resubmission reattempts
  processing rather than necessarily replaying the error.
- Concurrent same-key requests receive `409` while one is processed. The guide
  recommends waiting at least 30 seconds before reattempting.
- UUID4 is recommended. We enforce canonical UUID4 as a local policy.

Official [409 versus 429 guidance](https://support.checkout.com/hc/en-us/articles/24570669653010-Why-did-I-receive-a-409-HTTP-response-to-my-idempotent-API-request-instead-of-429)
distinguishes concurrent-request conflicts from rate limits. The
[duplicate-response support article](https://support.checkout.com/hc/en-us/articles/26763450855186-Duplicate-payment-request-responses)
describes `202` for completed-request replay, whereas the main guide describes
replaying the original successful status/body. Accept and validate supported
successful responses without assuming one universal replay status.

The old ReadMe-hosted guide contains different expiry/concurrency rules. It is
not the policy source for this account-specific integration.

## Evidence still missing

- An explicit `/payments` guarantee for same key with a changed payload, including
  response behavior. Our local tracker rejects that combination independently.
- Key namespace boundaries across credentials/accounts/endpoints and whether any
  customized production setting applies. Do not assume keys protect across scopes.
- Which provider error codes make a financial POST appropriate to reattempt;
  support for idempotency is not a blanket instruction to retry every error.
- Token reuse/expiry behavior for this source after each uncertain/error outcome.

No live payment API call was made to obtain this research. Reading documentation
does not verify the behavior of a particular Sandbox account.

## Local decision table: what to do now

Every row below leaves automatic financial POST retries disabled in the current
code. The table records operator/design decisions, not new runtime enforcement.

| Original request evidence | Local decision | Evidence needed before any later POST |
| --- | --- | --- |
| Valid successful response and known status | Record payment ID and body status; use its lifecycle. Do not resend merely to confirm. | A distinct business operation requires its own authorization/eligibility decision. |
| Timeout/network error, original payment ID available | Keep unknown, run read-only `6_` reconciliation. | Reconcile first; a failed lookup is not proof the POST failed. |
| Timeout/network error, no payment ID | Keep unknown; investigate using retained merchant records/Dashboard. | Retained original identity/request, account context, valid retention and token eligibility; otherwise manual resolution. |
| `409` | Preserve original operation; wait for evidence or perform read-only reconciliation. Do not rotate its key. | Before a separately approved reattempt, respect at least the documented 30-second wait and any longer applicable delay. |
| `429` | Stop request pressure; retain original context and inspect rate-limit evidence. | Endpoint-specific retry eligibility and timing. A Retry-After value supplies delay, not authorization to write. |
| `500/502/503/504` or ambiguous acknowledgement | Keep uncertain; reconcile where possible. Do not apply the GET retry loop. | Determine whether a new processing attempt is appropriate; no saved error result is not proof no financial effect occurred. |
| `401/403` | Stop; investigate credentials/permissions. | Fix access and assess the original operation before an explicit new decision. Never retry unchanged automatically. |
| `422` | Stop; investigate validation/configuration. | Review corrected inputs and their operation identity; do not silently mutate a retained request under its old key. |
| Key missing, original payload unavailable, or tracker lost | Stop automatic resubmission. | Recover trustworthy original records; do not invent a replacement key for an unresolved operation. |
| Same key, changed amount/token/channel/URL/payload | Local tracker rejects before HTTP while its binding exists. | Investigate the conflict and original outcome. Changing the key is not a conflict-resolution strategy. |
| Retention expired or effective window cannot be established | Stop POST retry; read-only/manual reconciliation. | Provider-backed resolution and a separate business decision. Same key is not permanent protection. |

An observed Declined can resolve the lookup snapshot, but a fresh customer payment
is a new business decision, not an automatic retry of an unknown request.
Pending remains pending; there is no automatic authorization resubmission.

## Proposed gate for a future bounded POST implementation

The following requirements are **not implemented yet**:

1. Retain one operation identity, original request fingerprint, relevant account
   context and the earliest submission time before the first POST.
2. Establish the effective provider retention for that environment/account. Use
   the earliest local send time as a conservative age bound, not the most recent
   retry time. Do not extend the window after a retry or process restart.
3. Admit only explicitly approved error/outcome categories and token conditions.
   Prefer reconciliation when an associated payment ID is available.
4. Require the original key, unchanged request and appropriate account scope.
   A tracker match alone does not satisfy the gate.
5. Enforce a small attempt limit and scheduling budget. Calculate delays using
   the provider minimum wait, applicable Retry-After and local backoff/jitter.
   If the delay/attempt cannot fit safely before the deadline, stop; do not shorten
   the provider delay. Do not reuse the GET defaults or assume phase timeouts
   enforce a hard wall-time deadline.
6. Return explicit unresolved/manual guidance on exhaustion, missing evidence or
   expired retention. Never rotate the key automatically.

Persistence/restart recovery and coordination across workers remain M6 follow-up;
an in-memory prototype must clearly state these limits and must not claim durable
duplicate-payment prevention.

## Acceptance tests before enabling any POST retries

- Lost successful response, retained operation, validated replay: same key/request,
  original payment ID, and body status respected.
- Processing conflict: no early attempt before the provider minimum wait.
- A server delay beyond budget/retention stops without an additional POST.
- Expired/unknown retention, lost payload/tracker, scope mismatch or changed request
  blocks a later attempt locally.
- `401/403/422`, ambiguous errors and unsupported source/error conditions cannot
  fall through to an automatic retry.
- Attempts/budget exhaustion stays unresolved and never creates a replacement key.
- Fake clocks and a stateful mocked provider verify behavior without real charges
  or waits. These tests do not establish the provider's live guarantees.

Next implementation decision: resolve the missing `/payments` source/error/scope
rules, then implement the smallest justified POST retry gate. M4 remains in progress.
