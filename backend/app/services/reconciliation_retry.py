"""Bounded GET attempts for reconciliation only; never accepts a write callback."""

from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import math
import random
import time

import httpx


@dataclass(frozen=True)
class LookupRetryPolicy:
    max_attempts: int = 1
    budget_seconds: float = 20.0

    def __post_init__(self):
        if type(self.max_attempts) is not int or not 1 <= self.max_attempts <= 5:
            raise ValueError("max_attempts must be an integer from 1 to 5")
        if (
            type(self.budget_seconds) not in (int, float)
            or not math.isfinite(self.budget_seconds)
            or not 0 < self.budget_seconds <= 60
        ):
            raise ValueError("budget_seconds must be finite and within (0, 60]")


class LookupStopped(Exception):
    """Only a safe symbolic reason is carried back to the caller."""


def _retry_after(value: str | None) -> float:
    if value is None:
        return 0.0
    if value.isascii() and value.isdigit():
        # Avoid parsing arbitrarily large integers from an untrusted header.
        return float(value) if len(value) < 10 else math.inf
    try:
        date = parsedate_to_datetime(value)
        if date.tzinfo is None:
            return 0.0
        return max(0.0, (date - datetime.now(timezone.utc)).total_seconds())
    except (ValueError, TypeError, OverflowError):
        return 0.0


def lookup_payment(client, payment_id: str, policy: LookupRetryPolicy) -> httpx.Response:
    """Use a monotonic scheduling budget and reduce per-phase HTTP timeouts.

    HTTPX timeout values limit individual network phases, not total wall time.
    An active synchronous GET cannot be forcibly cancelled by this budget.
    No new attempt starts after the budget expires. A valid pending response is
    returned immediately: retrying failed transport is not status polling.
    """
    deadline = time.monotonic() + policy.budget_seconds
    for attempt in range(1, policy.max_attempts + 1):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise LookupStopped("lookup_retry_budget_exhausted")
        retry_after = 0.0
        try:
            response = client.get_payment(payment_id, timeout=min(10.0, remaining))
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as error:
            if error.response.status_code not in (429, 502, 503, 504):
                raise LookupStopped("lookup_http_error") from None
            reason = "lookup_http_error"
            retry_after = _retry_after(error.response.headers.get("Retry-After"))
        except (httpx.TimeoutException, httpx.NetworkError):
            reason = "lookup_transport_error"
        except httpx.RequestError:
            # Redirect/protocol errors are not assumed transient.
            raise LookupStopped("lookup_transport_error") from None

        if attempt == policy.max_attempts:
            raise LookupStopped(reason if policy.max_attempts == 1 else "lookup_retries_exhausted")
        # Local policy: 1, 2, 4... seconds plus up to 250ms jitter.
        delay = max(2 ** (attempt - 1), retry_after) + random.uniform(0.0, 0.25)
        if delay >= deadline - time.monotonic():
            raise LookupStopped("lookup_retry_budget_exhausted")
        time.sleep(delay)
    raise AssertionError("Validated policy always permits at least one attempt")
