from dataclasses import FrozenInstanceError

import pytest

from app.models.payment import Payment


def test_payment_links_order_to_provider_payment():
    # Keep the merchant order reference alongside the provider payment result.
    payment = Payment(
        order_id="order_001",
        payment_id="pay_test_001",
        status="Authorized",
    )

    assert payment.order_id == "order_001"
    assert payment.payment_id == "pay_test_001"
    assert payment.status == "Authorized"


def test_payment_cannot_be_reassigned_to_another_order():
    # Prevent accidental changes to the order associated with this record.
    payment = Payment("order_001", "pay_test_001", "Authorized")

    with pytest.raises(FrozenInstanceError):
        payment.order_id = "order_002"

    assert payment.order_id == "order_001"
