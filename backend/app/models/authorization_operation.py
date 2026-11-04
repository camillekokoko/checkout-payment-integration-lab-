from dataclasses import dataclass, field


@dataclass(frozen=True)
class AuthorizationOperation:
    """In-memory identity and input snapshot for one authorization operation.

    The service creates the key once and reuses this snapshot across attempts.
    Hiding the token from repr does not protect explicit logging or serialization.
    """

    idempotency_key: str
    order_id: str
    amount: int
    currency: str
    token: str = field(repr=False)
