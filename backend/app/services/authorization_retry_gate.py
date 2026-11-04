"""Fail-closed preflight for uncertain authorization POSTs; performs no I/O.

This gate is not wired into submission and never grants retry permission while
provider source/error/scope eligibility remains unresolved. Evidence must come
from trusted retained application records, not browser input.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Literal


@dataclass(frozen=True)
class AuthorizationRetryEvidence:
    """Opaque digests/context identifiers must not contain raw tokens or secrets.

    first_submitted_at is the earliest send time and must never be reset on retry.
    retention is the effective, verified account window, not an assumed default.
    """

    original_key: str = field(repr=False)
    request_fingerprint: bytes = field(repr=False)
    account_context: str = field(repr=False)
    first_submitted_at: datetime
    last_submitted_at: datetime
    attempts: int
    outcome: str
    payment_id: str | None = None
    retention: timedelta | None = None
    retry_after: timedelta = timedelta(0)


@dataclass(frozen=True)
class AuthorizationRetryDecision:
    action: Literal["reconcile", "wait", "manual_review"]
    reason: str
    wait_seconds: float = 0.0


def assess_authorization_retry(
    evidence: AuthorizationRetryEvidence, *, current_key: str,
    current_fingerprint: bytes, current_account_context: str,
    now: datetime, max_attempts: int = 3,
    safety_margin: timedelta = timedelta(seconds=10),
) -> AuthorizationRetryDecision:
    """Reject unsafe/missing evidence and identify the next read/wait/review step.

    Waiting out the returned delay is not permission to POST. Reassess retained
    evidence later, then resolve provider eligibility before implementing retries.
    A ten-second expiry margin is a local preflight choice, not a request deadline.
    """
    def review(reason):
        return AuthorizationRetryDecision("manual_review", reason)

    if type(max_attempts) is not int or not 1 <= max_attempts <= 5:
        raise ValueError("max_attempts must be an integer from 1 to 5")
    if not isinstance(safety_margin, timedelta) or safety_margin < timedelta(0):
        raise ValueError("safety_margin must be a nonnegative timedelta")
    if evidence.payment_id is not None:
        return AuthorizationRetryDecision("reconcile", "known_payment_id")
    if (
        not isinstance(evidence.original_key, str) or not evidence.original_key
        or not isinstance(evidence.request_fingerprint, bytes) or not evidence.request_fingerprint
        or not isinstance(evidence.account_context, str) or not evidence.account_context
    ):
        return review("missing_original_context")
    if current_key != evidence.original_key:
        return review("key_changed")
    if current_fingerprint != evidence.request_fingerprint:
        return review("request_changed")
    if current_account_context != evidence.account_context:
        return review("account_context_changed")
    dates = (now, evidence.first_submitted_at, evidence.last_submitted_at)
    if any(not isinstance(t, datetime) or t.tzinfo is None or t.utcoffset() is None for t in dates):
        return review("invalid_submission_time")
    if not evidence.first_submitted_at <= evidence.last_submitted_at <= now:
        return review("inconsistent_submission_time")
    if type(evidence.attempts) is not int or evidence.attempts < 1:
        return review("invalid_attempt_count")
    if evidence.attempts >= max_attempts:
        return review("attempts_exhausted")
    if not isinstance(evidence.retention, timedelta) or evidence.retention <= timedelta(0):
        return review("unverified_retention")
    if not isinstance(evidence.retry_after, timedelta) or evidence.retry_after < timedelta(0):
        return review("invalid_retry_delay")
    remaining = evidence.retention - (now - evidence.first_submitted_at)
    if remaining <= safety_margin:
        return review("retention_expired_or_too_close")
    if evidence.outcome not in ("transport_unknown", "processing_conflict"):
        return review("outcome_not_eligible")
    minimum_wait = max(timedelta(seconds=30), evidence.retry_after)
    wait = max(timedelta(0), minimum_wait - (now - evidence.last_submitted_at))
    if wait + safety_margin >= remaining:
        return review("wait_exceeds_retention")
    if wait > timedelta(0):
        return AuthorizationRetryDecision("wait", "minimum_wait_not_elapsed", wait.total_seconds())
    # Passing local consistency/time checks cannot invent missing provider rules.
    return review("provider_eligibility_unverified")
