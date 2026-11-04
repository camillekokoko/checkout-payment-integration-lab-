from dataclasses import FrozenInstanceError

import pytest

from app.models.authorization_operation import AuthorizationOperation


def test_token_is_available_for_submission_but_hidden_from_repr():
    operation = AuthorizationOperation(
        idempotency_key="operation_key", order_id="order_001",
        amount=1000, currency="AUD", token="tok_fake_sensitive",
    )

    assert operation.token == "tok_fake_sensitive"
    assert "tok_fake_sensitive" not in repr(operation)


def test_operation_cannot_be_changed_between_attempts():
    operation = AuthorizationOperation(
        idempotency_key="operation_key", order_id="order_001",
        amount=1000, currency="AUD", token="tok_fake_sensitive",
    )

    for name, value in (("amount", 1500), ("idempotency_key", "replacement_key")):
        with pytest.raises(FrozenInstanceError):
            setattr(operation, name, value)
