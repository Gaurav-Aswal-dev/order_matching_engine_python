from __future__ import annotations

from decimal import Decimal
import time
from typing import Any

from .models import Order, as_price
from .storage import Storage


class MatchingEngine:
    """Price-time-priority matching engine. SQLite is the durable source of truth."""

    def __init__(self, storage: Storage):
        self.storage = storage
        self.buys: list[dict[str, Any]] = []
        self.sells: list[dict[str, Any]] = []
        self._recover()

    def _recover(self) -> None:
        """Rebuild the live book from persisted open/partially-filled orders."""
        self.buys.clear()
        self.sells.clear()
        for row in self.storage.load_open_orders():
            order = {
                "order_id": row["order_id"],
                "side": row["side"],
                "price": as_price(row["price"]),
                "quantity": int(row["quantity"]),
                "created_at": float(row["created_at"]),
                "source": row["source"],
            }
            (self.buys if order["side"] == "BUY" else self.sells).append(order)
        self._sort_books()

    def _sort_books(self) -> None:
        # Best buy first; best sell first. FIFO for equal prices.
        self.buys.sort(key=lambda o: (-Decimal(o["price"]), o["created_at"], o["order_id"]))
        self.sells.sort(key=lambda o: (Decimal(o["price"]), o["created_at"], o["order_id"]))

    def snapshot(self) -> dict:
        return {"buys": [dict(o) for o in self.buys], "sells": [dict(o) for o in self.sells]}

    def process(self, order: Order) -> dict:
        if self.storage.was_processed(order.order_id):
            return {"type": "DUPLICATE", "order_id": order.order_id}

        incoming = {
            "order_id": order.order_id,
            "side": order.side,
            "price": order.price,
            "original_quantity": order.quantity,
            "created_at": order.created_at,
            "source": order.source,
        }
        remaining = order.quantity
        trades: list[dict] = []
        book_updates: list[dict] = []
        opposite = self.sells if order.side == "BUY" else self.buys

        while remaining > 0 and opposite:
            resting = opposite[0]
            crosses = (
                Decimal(order.price) >= Decimal(resting["price"])
                if order.side == "BUY"
                else Decimal(order.price) <= Decimal(resting["price"])
            )
            if not crosses:
                break

            traded_qty = min(remaining, int(resting["quantity"]))
            # The resting order sets the execution price.
            trade_price = resting["price"]
            trades.append({
                "buy_order_id": order.order_id if order.side == "BUY" else resting["order_id"],
                "sell_order_id": order.order_id if order.side == "SELL" else resting["order_id"],
                "price": trade_price,
                "quantity": traded_qty,
                "executed_at": time.time(),
            })
            remaining -= traded_qty
            resting["quantity"] -= traded_qty
            resting["status_after_update"] = "FILLED" if resting["quantity"] == 0 else "PARTIAL"
            book_updates.append({
                "order_id": resting["order_id"],
                "remaining_quantity": resting["quantity"],
                "status": resting["status_after_update"],
            })
            if resting["quantity"] == 0:
                opposite.pop(0)

        status = "FILLED" if remaining == 0 else ("PARTIAL" if trades else "OPEN")
        incoming["book_updates"] = book_updates

        # Persist all related mutations in one transaction before publishing in-memory result.
        self.storage.save_order_and_trades(incoming, trades, remaining, status)

        if remaining > 0:
            resting_order = {
                "order_id": order.order_id,
                "side": order.side,
                "price": order.price,
                "quantity": remaining,
                "created_at": order.created_at,
                "source": order.source,
            }
            (self.buys if order.side == "BUY" else self.sells).append(resting_order)
            self._sort_books()

        return {
            "type": "RESULT",
            "order_id": order.order_id,
            "status": status,
            "remaining_quantity": remaining,
            "trades": trades,
        }
