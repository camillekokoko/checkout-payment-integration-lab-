from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from app.services.authorization_retry_gate import AuthorizationRetryEvidence, assess_authorization_retry


NOW = datetime(2026, 11, 4, 12, tzinfo=timezone.utc)


def evidence(**changes):
    value = AuthorizationRetryEvidence(
        original_key="retained-key", request_fingerprint=b"opaque-digest",
        account_context="opaque-account-context", first_submitted_at=NOW - timedelta(seconds=40),
        last_submitted_at=NOW - timedelta(seconds=40), attempts=1,
        outcome="transport_unknown", retention=timedelta(hours=72),
    )
    return replace(value, **changes)


def assess(value, **changes):
    return assess_authorization_retry(value, **{
        "current_key": "retained-key", "current_fingerprint": b"opaque-digest",
        "current_account_context": "opaque-account-context", "now": NOW, **changes,
    })


def test_matching_context_never_grants_unsupported_post_permission():
    result = assess(evidence())
    assert (result.action, result.reason) == ("manual_review", "provider_eligibility_unverified")


def test_known_payment_id_prefers_reconciliation_even_without_retention():
    result = assess(evidence(payment_id="pay_known", retention=None))
    assert result.action == "reconcile"


@pytest.mark.parametrize("changes, reason", [
    ({"current_key": "new-key"}, "key_changed"),
    ({"current_fingerprint": b"changed"}, "request_changed"),
    ({"current_account_context": "other-account"}, "account_context_changed"),
])
def test_changed_request_context_is_rejected(changes, reason):
    assert assess(evidence(), **changes).reason == reason


@pytest.mark.parametrize("changes, reason", [
    ({"original_key": ""}, "missing_original_context"),
    ({"retention": None}, "unverified_retention"),
    ({"attempts": 3}, "attempts_exhausted"),
    ({"attempts": True}, "invalid_attempt_count"),
    ({"outcome": "http_422"}, "outcome_not_eligible"),
    ({"outcome": "http_503"}, "outcome_not_eligible"),
    ({"first_submitted_at": NOW.replace(tzinfo=None)}, "invalid_submission_time"),
    ({"last_submitted_at": NOW + timedelta(seconds=1)}, "inconsistent_submission_time"),
    ({"retention": timedelta(seconds=45)}, "retention_expired_or_too_close"),
    ({"retry_after": timedelta(seconds=-1)}, "invalid_retry_delay"),
    ({"retry_after": timedelta(hours=73)}, "wait_exceeds_retention"),
])
def test_missing_unsafe_or_expired_evidence_stays_manual(changes, reason):
    result = assess(evidence(**changes))
    assert result.action == "manual_review"
    assert result.reason == reason


def test_processing_conflict_must_wait_without_resetting_first_send_time():
    value = evidence(last_submitted_at=NOW - timedelta(seconds=5), outcome="processing_conflict")
    result = assess(value)
    assert result.action == "wait"
    assert result.wait_seconds == 25
    assert assess(value, now=NOW + timedelta(seconds=25)).reason == "provider_eligibility_unverified"


def test_latest_attempt_does_not_extend_original_retention():
    value = evidence(first_submitted_at=NOW - timedelta(hours=73), last_submitted_at=NOW - timedelta(seconds=5))
    assert assess(value).reason == "retention_expired_or_too_close"


def test_evidence_repr_omits_retained_identity_and_digests():
    output = repr(evidence())
    assert "retained-key" not in output
    assert "opaque-digest" not in output
    assert "opaque-account-context" not in output
