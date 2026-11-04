from dataclasses import replace
from unittest.mock import patch

import httpx
import pytest

from app.clients.checkout_client import CheckoutClient
from app.clients.idempotency_tracker import IdempotencyConflictError, InMemoryIdempotencyTracker
from app.models.order import Order
from app.services.payment_service import create_authorization_operation, submit_authorization_operation


@pytest.fixture
def sandbox_config(monkeypatch):
    monkeypatch.setenv("CHECKOUT_SECRET_KEY", "sk_sbox_fake")
    monkeypatch.setenv("CHECKOUT_BASE_URL", "https://test.api.sandbox.checkout.com")
    monkeypatch.setenv("CHECKOUT_PROCESSING_CHANNEL_ID", "pc_" + "a" * 26)


@pytest.mark.parametrize("change", ["amount", "token", "order_id", "channel", "url"])
def test_changed_request_after_timeout_is_blocked_and_original_is_retained(sandbox_config, change):
    client = CheckoutClient()
    operation = create_authorization_operation(Order("order_001", 1000, "AUD"), "tok_private")
    original_channel = client.processing_channel_id
    original_url = client.base_url
    response = httpx.Response(202, request=httpx.Request("POST", "https://checkout.invalid"))
    with patch("app.clients.checkout_client.httpx.post", side_effect=[
        httpx.ReadTimeout("Simulated lost response"), response,
    ]) as post:
        with pytest.raises(httpx.ReadTimeout):
            submit_authorization_operation(client, operation)

        changed = operation
        if change in ("amount", "token", "order_id"):
            value = {"amount": 1500, "token": "tok_changed_private", "order_id": "order_002"}[change]
            changed = replace(operation, **{change: value})
        elif change == "channel":
            client.processing_channel_id = "pc_" + "b" * 26
        else:
            client.base_url = "https://other.api.sandbox.checkout.com"

        with pytest.raises(IdempotencyConflictError) as conflict:
            submit_authorization_operation(client, changed)
        assert post.call_count == 1  # The conflicting attempt never reaches HTTP.
        assert "private" not in str(conflict.value)
        assert operation.idempotency_key not in str(conflict.value)

        client.processing_channel_id = original_channel
        client.base_url = original_url
        assert submit_authorization_operation(client, operation) is response
        assert post.call_count == 2
        assert post.call_args_list[0] == post.call_args_list[1]


def test_shared_tracker_preserves_binding_across_clients_and_http_errors(sandbox_config):
    tracker = InMemoryIdempotencyTracker()
    first = CheckoutClient(idempotency_tracker=tracker)
    second = CheckoutClient(idempotency_tracker=tracker)
    operation = create_authorization_operation(Order("order_001", 1000, "AUD"), "tok_private")
    response = httpx.Response(409, request=httpx.Request("POST", "https://checkout.invalid"))
    with patch("app.clients.checkout_client.httpx.post", return_value=response) as post:
        with pytest.raises(httpx.HTTPStatusError):
            submit_authorization_operation(first, operation)
        with pytest.raises(IdempotencyConflictError):
            submit_authorization_operation(second, replace(operation, amount=1500))
        assert post.call_count == 1


@pytest.mark.parametrize("change", [{"currency": "USD"}, {"capture": True}])
def test_direct_client_calls_also_check_all_payload_fields(sandbox_config, change):
    client = CheckoutClient()
    operation = create_authorization_operation(Order("order_001", 1000, "AUD"), "tok_private")
    data = dict(amount=1000, currency="AUD", token="tok_private", order_id="order_001",
                capture=False, idempotency_key=operation.idempotency_key)
    response = httpx.Response(201, request=httpx.Request("POST", "https://checkout.invalid"))
    with patch("app.clients.checkout_client.httpx.post", return_value=response) as post:
        client.create_payment(**data)
        with pytest.raises(IdempotencyConflictError):
            client.create_payment(**{**data, **change})
        assert post.call_count == 1
