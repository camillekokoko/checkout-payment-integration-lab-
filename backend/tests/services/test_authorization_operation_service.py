from unittest.mock import Mock, patch
from uuid import UUID

import httpx
import pytest

from app.clients.checkout_client import CheckoutClient
from app.models.order import Order
from app.services.payment_service import (
    classify_payment_error, create_authorization_operation, payment_from_response,
    submit_authorization_operation,
)


def test_new_operations_have_distinct_uuid4_keys():
    order = Order("order_001", 1000, "AUD")
    first = create_authorization_operation(order, "tok_fake")
    second = create_authorization_operation(order, "tok_fake")

    assert UUID(first.idempotency_key).version == 4
    assert first.idempotency_key != second.idempotency_key
    assert (first.order_id, first.amount, first.currency, first.token) == (
        "order_001", 1000, "AUD", "tok_fake",
    )


@pytest.mark.parametrize("order, token", [
    (Order("order_001", 1000, "USD"), "tok_fake"),
    (Order("order_001", True, "AUD"), "tok_fake"),
    (Order("order_001", 0, "AUD"), "tok_fake"),
    (Order("", 1000, "AUD"), "tok_fake"),
    (Order("x" * 81, 1000, "AUD"), "tok_fake"),
    (Order("order_001", 1000, "AUD"), " "),
])
def test_invalid_operation_inputs_are_rejected(order, token):
    with pytest.raises(ValueError):
        create_authorization_operation(order, token)


def test_timeout_preserves_operation_for_a_separately_decided_attempt():
    # The service preserves identity independently of the transport implementation.
    operation = create_authorization_operation(Order("order_001", 1000, "AUD"), "tok_fake")
    response = httpx.Response(201)
    client = Mock()
    client.create_payment.side_effect = [httpx.ReadTimeout("Simulated timeout"), response]

    with pytest.raises(httpx.ReadTimeout):
        submit_authorization_operation(client, operation)
    client.create_payment.assert_called_once()

    assert submit_authorization_operation(client, operation) is response
    assert client.create_payment.call_count == 2
    for attempt in client.create_payment.call_args_list:
        assert attempt.kwargs == {
            "amount": 1000, "currency": "AUD", "token": "tok_fake",
            "order_id": "order_001", "capture": False,
            "idempotency_key": operation.idempotency_key,
        }


def test_real_client_reuses_key_and_payload_after_lost_response(monkeypatch):
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "sk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://test.api.sandbox.checkout.com")
    monkeypatch.setenv("CHECKOUT_PROCESSING_CHANNEL_ID", "pc_" + "a" * 26)
    client = CheckoutClient()
    operation = create_authorization_operation(Order("order_001", 1000, "AUD"), "tok_fake")
    provider_payments = {}
    requests = []

    def provider(url, *, headers, json, timeout):
        key = headers["Cko-Idempotency-Key"]
        requests.append((url, dict(headers), dict(json), timeout))
        if key not in provider_payments:
            provider_payments[key] = {"id": f"pay_fake_{len(provider_payments) + 1}", "status": "Authorized"}
            # Provider processed the first request, but its response was lost.
            if len(requests) == 1:
                raise httpx.ReadTimeout("Simulated lost response")
        return httpx.Response(
            202, json=provider_payments[key], request=httpx.Request("POST", url),
        )

    with patch("app.clients.checkout_client.httpx.post", side_effect=provider):
        with pytest.raises(httpx.ReadTimeout):
            submit_authorization_operation(client, operation)
        assert len(requests) == 1  # No automatic retry.
        response = submit_authorization_operation(client, operation)
        assert response.json()["id"] == "pay_fake_1"
        assert requests[0] == requests[1]
        assert requests[0][1]["Cko-Idempotency-Key"] == operation.idempotency_key
        assert requests[0][2]["capture"] is False
        assert len(provider_payments) == 1

        # Starting another operation is distinct even with identical order inputs.
        new_operation = create_authorization_operation(Order("order_001", 1000, "AUD"), "tok_fake")
        submit_authorization_operation(client, new_operation)
        assert requests[2][1]["Cko-Idempotency-Key"] != operation.idempotency_key
        assert len(provider_payments) == 2


@pytest.fixture
def sandbox_client(monkeypatch):
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "sk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://test.api.sandbox.checkout.com")
    monkeypatch.setenv("CHECKOUT_PROCESSING_CHANNEL_ID", "pc_" + "a" * 26)
    return CheckoutClient()


def test_timeout_then_conflict_keeps_unknown_and_stops_writes(sandbox_client):
    operation = create_authorization_operation(Order("order_001", 1000, "AUD"), "tok_fake")
    conflict = httpx.Response(
        409, request=httpx.Request("POST", "https://checkout.invalid/payments"),
    )
    with patch("app.clients.checkout_client.httpx.post", side_effect=[
        httpx.ReadTimeout("Simulated lost response"), conflict,
    ]) as post:
        with pytest.raises(httpx.ReadTimeout) as timeout:
            submit_authorization_operation(sandbox_client, operation)
        assert classify_payment_error(timeout.value).outcome_unknown is True
        assert post.call_count == 1

        # A separate caller decision simulates a duplicate request; no retry loop.
        with pytest.raises(httpx.HTTPStatusError) as error:
            submit_authorization_operation(sandbox_client, operation)
        decision = classify_payment_error(error.value)
        assert decision.kind == "request_conflict"
        assert decision.outcome_unknown is True
        assert "Stop writes" in decision.action
        assert "do not replace" in decision.action
        assert post.call_count == 2
        assert post.call_args_list[0] == post.call_args_list[1]


@pytest.mark.parametrize("provider_status, local_status", [
    ("Authorized", "authorized"), ("Pending", "pending"),
    ("Declined", "declined"), ("FutureStatus", "unknown"),
])
def test_replayed_202_uses_original_id_and_body_status(sandbox_client, provider_status, local_status):
    operation = create_authorization_operation(Order("order_001", 1000, "AUD"), "tok_fake")
    replay = httpx.Response(
        202, json={"id": "pay_original", "status": provider_status},
        request=httpx.Request("POST", "https://checkout.invalid/payments"),
    )
    with patch("app.clients.checkout_client.httpx.post", side_effect=[
        httpx.ReadTimeout("Simulated lost response"), replay,
    ]) as post:
        with pytest.raises(httpx.ReadTimeout):
            submit_authorization_operation(sandbox_client, operation)
        response = submit_authorization_operation(sandbox_client, operation)
        payment = payment_from_response(operation.order_id, response.json())
        assert payment.payment_id == "pay_original"
        assert payment.status == local_status
        assert post.call_count == 2
        assert post.call_args_list[0] == post.call_args_list[1]
