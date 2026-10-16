from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal
import time
import uuid

Side = Literal["BUY", "SELL"]


def as_price(value: object) -> str:
    """Validate a positive price and return a normalized decimal string."""
    try:
        price = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f"Invalid price: {value!r}") from None
    if not price.is_finite() or price <= 0:
        raise ValueError("Price must be a finite number greater than zero")
    # Avoid scientific notation in persisted/displayed prices.
    return format(price.normalize(), "f")


@dataclass(frozen=True)
class Order:
    order_id: str
    side: Side
    price: str
    quantity: int
    created_at: float
    source: str = "producer"

    @classmethod
    def create(cls, side: str, price: object, quantity: int, source: str = "producer") -> "Order":
        normalized_side = side.upper()
        if normalized_side not in ("BUY", "SELL"):
            raise ValueError("side must be BUY or SELL")
        if isinstance(quantity, bool) or not isinstance(quantity, int) or quantity <= 0:
            raise ValueError("quantity must be a positive integer")
        return cls(
            order_id=str(uuid.uuid4()),
            side=normalized_side,  # type: ignore[arg-type]
            price=as_price(price),
            quantity=quantity,
            created_at=time.time(),
            source=source,
        )

    def to_message(self) -> dict:
        return {
            "type": "ORDER",
            "order_id": self.order_id,
            "side": self.side,
            "price": self.price,
            "quantity": self.quantity,
            "created_at": self.created_at,
            "source": self.source,
        }

    @classmethod
    def from_message(cls, message: dict) -> "Order":
        if message.get("type") != "ORDER":
            raise ValueError("Not an ORDER message")
        side = str(message["side"]).upper()
        if side not in ("BUY", "SELL"):
            raise ValueError("side must be BUY or SELL")
        qty = message["quantity"]
        if isinstance(qty, bool) or not isinstance(qty, int) or qty <= 0:
            raise ValueError("quantity must be a positive integer")
        return cls(
            order_id=str(message["order_id"]),
            side=side,  # type: ignore[arg-type]
            price=as_price(message["price"]),
            quantity=qty,
            created_at=float(message["created_at"]),
            source=str(message.get("source", "producer")),
        )
