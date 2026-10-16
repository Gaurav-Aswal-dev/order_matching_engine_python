from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    price TEXT NOT NULL,
    original_quantity INTEGER NOT NULL CHECK (original_quantity > 0),
    remaining_quantity INTEGER NOT NULL CHECK (remaining_quantity >= 0),
    created_at REAL NOT NULL,
    source TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('OPEN', 'PARTIAL', 'FILLED', 'CANCELLED'))
);

CREATE INDEX IF NOT EXISTS idx_orders_open_side_price_time
ON orders(side, status, price, created_at);

CREATE TABLE IF NOT EXISTS trades (
    trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
    buy_order_id TEXT NOT NULL,
    sell_order_id TEXT NOT NULL,
    price TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    executed_at REAL NOT NULL,
    FOREIGN KEY (buy_order_id) REFERENCES orders(order_id),
    FOREIGN KEY (sell_order_id) REFERENCES orders(order_id)
);

CREATE TABLE IF NOT EXISTS processed_messages (
    order_id TEXT PRIMARY KEY,
    processed_at REAL NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(order_id)
);
"""


class Storage:
    def __init__(self, database_path: str = "order_engine.db", check_same_thread: bool = True):
        self.database_path = str(database_path)
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True) if Path(self.database_path).parent != Path(".") else None
        self.connection = sqlite3.connect(self.database_path, timeout=30, check_same_thread=check_same_thread)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA journal_mode = WAL")
        self.connection.execute("PRAGMA synchronous = FULL")
        self.connection.executescript(SCHEMA)
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def load_open_orders(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            """SELECT order_id, side, price, remaining_quantity AS quantity,
                      created_at, source
               FROM orders
               WHERE status IN ('OPEN', 'PARTIAL') AND remaining_quantity > 0
               ORDER BY created_at ASC, order_id ASC"""
        ).fetchall()
        return [dict(row) for row in rows]

    def was_processed(self, order_id: str) -> bool:
        return self.connection.execute(
            "SELECT 1 FROM processed_messages WHERE order_id = ?", (order_id,)
        ).fetchone() is not None

    def save_order_and_trades(self, incoming: dict, trades: list[dict], remaining: int, status: str) -> None:
        """Atomically persist the incoming order, book changes, trades, and deduplication marker."""
        con = self.connection
        try:
            con.execute("BEGIN IMMEDIATE")
            con.execute(
                """INSERT INTO orders
                   (order_id, side, price, original_quantity, remaining_quantity,
                    created_at, source, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(order_id) DO UPDATE SET
                     remaining_quantity=excluded.remaining_quantity,
                     status=excluded.status""",
                (incoming["order_id"], incoming["side"], incoming["price"],
                 incoming["original_quantity"], remaining, incoming["created_at"],
                 incoming["source"], status),
            )

            for update in incoming.get("book_updates", []):
                con.execute(
                    "UPDATE orders SET remaining_quantity=?, status=? WHERE order_id=?",
                    (update["remaining_quantity"], update["status"], update["order_id"]),
                )

            for trade in trades:
                con.execute(
                    """INSERT INTO trades
                       (buy_order_id, sell_order_id, price, quantity, executed_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (trade["buy_order_id"], trade["sell_order_id"], trade["price"],
                     trade["quantity"], trade["executed_at"]),
                )

            con.execute(
                "INSERT OR IGNORE INTO processed_messages(order_id, processed_at) VALUES (?, strftime('%s','now'))",
                (incoming["order_id"],),
            )
            con.commit()
        except Exception:
            con.rollback()
            raise

    def insert_order_only(self, order: dict) -> None:
        """Persist a valid order that could not be matched; retained for compatibility."""
        self.save_order_and_trades(
            {
                **order,
                "original_quantity": order["quantity"],
                "book_updates": [],
            },
            [], order["quantity"], "OPEN"
        )

    def list_orders(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM orders ORDER BY created_at, order_id"
        ).fetchall()
        return [dict(row) for row in rows]

    def list_trades(self) -> list[dict[str, Any]]:
        rows = self.connection.execute(
            "SELECT * FROM trades ORDER BY trade_id"
        ).fetchall()
        return [dict(row) for row in rows]

    def stats(self) -> dict[str, int]:
        return {
            "orders": self.connection.execute("SELECT COUNT(*) FROM orders").fetchone()[0],
            "open_orders": self.connection.execute(
                "SELECT COUNT(*) FROM orders WHERE status IN ('OPEN','PARTIAL')"
            ).fetchone()[0],
            "trades": self.connection.execute("SELECT COUNT(*) FROM trades").fetchone()[0],
        }
