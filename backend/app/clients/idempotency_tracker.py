import hashlib
import hmac
import json
import secrets
from threading import Lock


class IdempotencyConflictError(ValueError):
    """A retained key was reused with different request data."""


class InMemoryIdempotencyTracker:
    """Bind keys to requests for this tracker's lifetime, including after errors.

    This is a consistency guard, not a retry policy or an in-flight request lock.
    Records are not durable or shared across processes. Do not replace the tracker
    to bypass a conflict; reconcile the original operation instead.
    """

    def __init__(self):
        self._fingerprints: dict[str, bytes] = {}
        self._secret = secrets.token_bytes(32)
        self._lock = Lock()

    def bind(self, key: str, *, method: str, url: str, payload: dict) -> None:
        canonical = json.dumps(
            {"method": method, "url": url, "payload": payload},
            sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
        # A per-tracker HMAC avoids retaining raw tokens or a plain token digest.
        fingerprint = hmac.digest(self._secret, canonical, hashlib.sha256)
        with self._lock:
            previous = self._fingerprints.get(key)
            if previous is not None and not hmac.compare_digest(previous, fingerprint):
                raise IdempotencyConflictError(
                    "Idempotency key conflicts with the original request. "
                    "No request sent; reconcile the original operation."
                )
            self._fingerprints[key] = fingerprint
