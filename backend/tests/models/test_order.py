from app.models.order import Order


def test_create_order():
    order = Order(
        id="order_001",
        amount=1000,
        currency="AUD",
    )

    assert (order.id, order.amount, order.currency) == ("order_001", 1000, "AUD")
