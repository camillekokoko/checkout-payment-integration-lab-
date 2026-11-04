from unittest.mock import Mock

import httpx
import pytest

from app.clients.checkout_client import CheckoutClient
from app.models.order import Order
from app.services.authorization_reconciliation import reconcile_authorization


PAYMENT_ID = "pay_" + "a" * 26


@pytest.fixture
def flow(monkeypatch):
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "sk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://test.api.sandbox.checkout.com")
    get = Mock(side_effect=AssertionError("Unexpected GET"))
    post = Mock(side_effect=AssertionError("Reconciliation must not POST"))
    monkeypatch.setattr(httpx, "get", get)
    monkeypatch.setattr(httpx, "post", post)
    yield CheckoutClient(), Order("order_001", 1000, "AUD"), get
    post.assert_not_called()


def response(http_status=200, **changes):
    data = dict(id=PAYMENT_ID, reference="order_001", amount=1000, currency="AUD", status="Authorized")
    return httpx.Response(http_status, json={**data, **changes}, request=httpx.Request("GET", "https://checkout.invalid"))


def test_missing_id_requires_manual_investigation_without_http(flow):
    client, operation, get = flow
    result = reconcile_authorization(client, operation)
    assert result.status == "unknown"
    assert result.reason == "missing_payment_id"
    assert "Do not replace" in result.action
    get.assert_not_called()
    assert "tok_private" not in repr(result)


@pytest.mark.parametrize("payment_id", ["", "pay_short", "../payments", 123])
def test_invalid_id_is_blocked_before_lookup(flow, payment_id):
    client, operation, get = flow
    with pytest.raises(ValueError):
        reconcile_authorization(client, operation, payment_id=payment_id)
    get.assert_not_called()


@pytest.mark.parametrize("provider, local", [
    ("Authorized", "authorized"), ("Pending", "pending"), ("Declined", "declined"),
    ("Captured", "captured"), ("Voided", "voided"), ("Refunded", "refunded"),
    ("Partially Captured", "partially_captured"), ("Partially Refunded", "partially_refunded"),
])
def test_known_payment_snapshot_is_observed_once(flow, provider, local):
    client, operation, get = flow
    get.side_effect = None
    get.return_value = response(status=provider)
    result = reconcile_authorization(client, operation, payment_id=PAYMENT_ID)
    assert result.status == local
    assert result.payment_id == PAYMENT_ID
    if local == "pending":
        assert "Wait" in result.action
    get.assert_called_once()


@pytest.mark.parametrize("status", [401, 403, 404, 409, 429, 503])
def test_lookup_http_failure_keeps_unknown_without_retry(flow, status):
    client, operation, get = flow
    get.side_effect = None
    get.return_value = response(status)
    result = reconcile_authorization(client, operation, payment_id=PAYMENT_ID)
    assert (result.status, result.reason) == ("unknown", "lookup_http_error")
    get.assert_called_once()


def test_lookup_timeout_keeps_unknown_and_hides_error_details(flow):
    client, operation, get = flow
    get.side_effect = httpx.ReadTimeout("private-detail")
    result = reconcile_authorization(client, operation, payment_id=PAYMENT_ID)
    assert result.status == "unknown"
    assert "private-detail" not in repr(result)
    get.assert_called_once()


@pytest.mark.parametrize("changes", [
    {"id": "pay_" + "b" * 26}, {"reference": "another_order"}, {"amount": 1500},
    {"amount": True}, {"currency": "USD"}, {"status": "FutureStatus"}, {"status": []},
])
def test_inconsistent_or_unrecognized_evidence_stays_unknown(flow, changes):
    client, operation, get = flow
    get.side_effect = None
    get.return_value = httpx.Response(
        200, json={**response().json(), **changes},
        request=httpx.Request("GET", "https://checkout.invalid"),
    )
    assert reconcile_authorization(client, operation, payment_id=PAYMENT_ID).status == "unknown"
    get.assert_called_once()


@pytest.mark.parametrize("body", [b"invalid-json", b"null", b"[]", b"{}"])
def test_malformed_lookup_stays_unknown(flow, body):
    client, operation, get = flow
    get.side_effect = None
    get.return_value = httpx.Response(200, content=body, request=httpx.Request("GET", "https://checkout.invalid"))
    assert reconcile_authorization(client, operation, payment_id=PAYMENT_ID).status == "unknown"
    get.assert_called_once()
