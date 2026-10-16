import tempfile
import unittest
from pathlib import Path

from order_engine.matcher import MatchingEngine
from order_engine.models import Order
from order_engine.storage import Storage


class MatchingEngineTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = str(Path(self.temp_dir.name) / "test.db")
        self.storage = Storage(self.db)
        self.engine = MatchingEngine(self.storage)

    def tearDown(self):
        self.storage.close()
        self.temp_dir.cleanup()

    def test_non_crossing_order_rests_in_book(self):
        result = self.engine.process(Order.create("BUY", 99, 5))
        self.assertEqual(result["status"], "OPEN")
        self.assertEqual(len(self.engine.buys), 1)
        self.assertEqual(self.engine.buys[0]["quantity"], 5)

    def test_crossing_orders_create_trade(self):
        self.engine.process(Order.create("SELL", 100, 4))
        result = self.engine.process(Order.create("BUY", 101, 3))
        self.assertEqual(result["status"], "FILLED")
        self.assertEqual(len(result["trades"]), 1)
        self.assertEqual(result["trades"][0]["quantity"], 3)
        self.assertEqual(self.storage.stats()["trades"], 1)
        self.assertEqual(self.engine.sells[0]["quantity"], 1)

    def test_partial_fill_rests_remainder(self):
        self.engine.process(Order.create("SELL", 100, 2))
        result = self.engine.process(Order.create("BUY", 100, 5))
        self.assertEqual(result["status"], "PARTIAL")
        self.assertEqual(result["remaining_quantity"], 3)
        self.assertEqual(self.engine.buys[0]["quantity"], 3)

    def test_recovery_restores_open_orders(self):
        order = Order.create("BUY", 99, 5)
        self.engine.process(order)
        self.storage.close()
        self.storage = Storage(self.db)
        self.engine = MatchingEngine(self.storage)
        self.assertEqual(len(self.engine.buys), 1)
        self.assertEqual(self.engine.buys[0]["order_id"], order.order_id)

    def test_duplicate_message_does_not_create_duplicate_trade(self):
        sell = Order.create("SELL", 100, 2)
        self.engine.process(sell)
        buy = Order.create("BUY", 100, 2)
        self.engine.process(buy)
        result = self.engine.process(buy)
        self.assertEqual(result["type"], "DUPLICATE")
        self.assertEqual(self.storage.stats()["trades"], 1)


if __name__ == "__main__":
    unittest.main()
