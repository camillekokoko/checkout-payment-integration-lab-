from unittest.mock import Mock

import httpx
import pytest

from app.clients.checkout_client import CheckoutClient
from app.models.order import Order
from app.services.authorization_reconciliation import reconcile_authorization
from app.services.reconciliation_retry import LookupRetryPolicy, _retry_after


PAYMENT_ID = "pay_" + "a" * 26


@pytest.fixture
def flow(monkeypatch):
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "sk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://test.api.sandbox.checkout.com")
    now = [0.0]
    sleeps = []

    def sleep(delay):
        sleeps.append(delay)
        now[0] += delay

    monkeypatch.setattr("app.services.reconciliation_retry.time.monotonic", lambda: now[0])
    monkeypatch.setattr("app.services.reconciliation_retry.time.sleep", sleep)
    monkeypatch.setattr("app.services.reconciliation_retry.random.uniform", lambda a, b: 0.1)
    get = Mock()
    post = Mock(side_effect=AssertionError("GET retry must never POST"))
    monkeypatch.setattr(httpx, "get", get)
    monkeypatch.setattr(httpx, "post", post)

    def run(attempts=3, budget=20):
        return reconcile_authorization(
            CheckoutClient(), Order("order_001", 1000, "AUD"), payment_id=PAYMENT_ID,
            retry_policy=LookupRetryPolicy(attempts, budget),
        )

    yield run, get, sleeps, now
    post.assert_not_called()


def response(code=200, headers=None, **changes):
    return httpx.Response(code, headers=headers, json={
        "id": PAYMENT_ID, "reference": "order_001", "amount": 1000,
        "currency": "AUD", "status": "Authorized", **changes,
    }, request=httpx.Request("GET", "https://checkout.invalid"))


@pytest.mark.parametrize("failure", [httpx.ReadTimeout("private"), httpx.ConnectError("private"),
                                        response(429), response(502), response(503), response(504)])
def test_transient_failure_then_success(flow, failure):
    run, get, sleeps, _ = flow
    get.side_effect = [failure, response()]
    assert run().status == "authorized"
    assert get.call_count == 2
    assert sleeps == [1.1]


def test_attempts_exhausted_stay_unknown(flow):
    run, get, sleeps, _ = flow
    get.side_effect = httpx.ReadTimeout("private")
    result = run()
    assert result.status == "unknown"
    assert result.reason == "lookup_retries_exhausted"
    assert get.call_count == 3
    assert sleeps == [1.1, 2.1]
    assert "private" not in repr(result)


@pytest.mark.parametrize("code", [401, 403, 404, 409, 422, 500])
def test_other_http_errors_stop_immediately(flow, code):
    run, get, sleeps, _ = flow
    get.return_value = response(code)
    assert run().status == "unknown"
    get.assert_called_once()
    assert sleeps == []


@pytest.mark.parametrize("changes, status", [({"status": "Pending"}, "pending"),
    ({"amount": 1500}, "unknown"), ({"status": []}, "unknown")])
def test_received_evidence_is_not_polled(flow, changes, status):
    run, get, sleeps, _ = flow
    get.return_value = response(**changes)
    assert run().status == status
    get.assert_called_once()
    assert sleeps == []


def test_retry_after_is_minimum_delay(flow):
    run, get, sleeps, _ = flow
    get.side_effect = [response(429, {"Retry-After": "4"}), response()]
    assert run().status == "authorized"
    assert sleeps == [4.1]


def test_retry_after_beyond_budget_stops_without_early_retry(flow):
    run, get, sleeps, _ = flow
    get.return_value = response(429, {"Retry-After": "30"})
    assert run().reason == "lookup_retry_budget_exhausted"
    get.assert_called_once()
    assert sleeps == []


def test_elapsed_request_time_counts_against_budget(flow):
    run, get, sleeps, now = flow

    def slow_get(*args, **kwargs):
        now[0] += 19
        raise httpx.ReadTimeout("private")

    get.side_effect = slow_get
    assert run().reason == "lookup_retry_budget_exhausted"
    get.assert_called_once()
    assert sleeps == []


def test_each_attempt_timeout_uses_remaining_budget(flow):
    run, get, sleeps, _ = flow
    get.side_effect = [response(503), response()]
    assert run(budget=3).status == "authorized"
    assert get.call_args_list[0].kwargs["timeout"] == 3
    assert get.call_args_list[1].kwargs["timeout"] == pytest.approx(1.9)


@pytest.mark.parametrize("attempts,budget", [(0, 20), (6, 20), (True, 20), (2, 0),
    (2, float("nan")), (2, float("inf")), (2, 61)])
def test_invalid_policy_rejected(attempts, budget):
    with pytest.raises(ValueError):
        LookupRetryPolicy(attempts, budget)


def test_retry_after_date_and_invalid_header():
    assert _retry_after("Wed, 01 Jan 2099 00:00:00 GMT") > 0
    assert _retry_after("Wed, 01 Jan 2020 00:00:00 GMT") == 0
    assert _retry_after("invalid") == 0
    assert _retry_after("-2") == 0
