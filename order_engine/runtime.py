from __future__ import annotations

import multiprocessing as mp
import os
import json
import queue as queue_module
import time
from typing import Any

from .matcher import MatchingEngine
from .models import Order
from .producer import producer_worker
from .storage import Storage


def matcher_worker(inbox, database_path: str, result_queue=None, ready_event=None, crash_after: int | None = None):
    """Child process: load durable state, consume IPC messages, match and persist."""
    storage = Storage(database_path)
    try:
        engine = MatchingEngine(storage)
        if ready_event:
            ready_event.set()
        processed = 0
        while True:
            message = inbox.get()
            if message.get("type") == "STOP":
                break
            try:
                order = Order.from_message(message)
                result = engine.process(order)
                processed += 1
                if result_queue is not None:
                    result_queue.put(result)
                if crash_after is not None and processed >= crash_after:
                    os._exit(17)  # Deliberately simulate a hard process crash for the demo.
            except Exception as exc:
                if result_queue is not None:
                    result_queue.put({"type": "ERROR", "error": str(exc), "message": message})
    finally:
        storage.close()


def run_demo(database_path: str = "order_engine.db", count: int = 20, delay: float = 0.05,
             crash_after: int | None = None) -> None:
    """Run producer and matcher as separate processes connected by a multiprocessing.Queue."""
    ctx = mp.get_context("spawn")
    inbox = ctx.Queue()
    results = ctx.Queue()
    ready = ctx.Event()

    matcher = ctx.Process(
        target=matcher_worker,
        args=(inbox, database_path, results, ready, crash_after),
        name="MatcherProcess",
    )
    producer = ctx.Process(
        target=producer_worker,
        args=(inbox, count, 42, delay),
        name="ProducerProcess",
    )
    matcher.start()
    if not ready.wait(timeout=10):
        matcher.terminate()
        raise RuntimeError("Matcher did not become ready")
    producer.start()

    producer.join()
    matcher.join(timeout=10)
    if matcher.is_alive():
        matcher.terminate()
        matcher.join()

    print(f"Producer exit code: {producer.exitcode}")
    print(f"Matcher exit code: {matcher.exitcode}")
    received = 0
    while True:
        try:
            result = results.get_nowait()
        except queue_module.Empty:
            break
        received += 1
        if result.get("type") == "RESULT":
            print(f"{result['status']:7} order={result['order_id']} remaining={result['remaining_quantity']} trades={len(result['trades'])}")
        elif result.get("type") == "ERROR":
            print(f"ERROR: {result['error']}")
    print(f"Results received: {received}")
    inbox.close()
    results.close()


def run_matcher_only(database_path: str = "order_engine.db") -> None:
    """Interactive single-process helper for sending manual orders through the same engine."""
    storage = Storage(database_path)
    try:
        engine = MatchingEngine(storage)
        print("Matcher ready. Enter: BUY price quantity | SELL price quantity | quit")
        while True:
            raw = input("> ").strip()
            if raw.lower() in {"quit", "exit"}:
                break
            parts = raw.split()
            if len(parts) != 3:
                print("Use: BUY price quantity")
                continue
            try:
                order = Order.create(parts[0], parts[1], int(parts[2]), source="interactive")
                print(engine.process(order))
            except Exception as exc:
                print(f"Invalid order: {exc}")
    finally:
        storage.close()


def run_showcase(database_path: str = "showcase.db") -> None:
    """Run a deterministic presentation scenario showing resting orders, crossing, and partial fills."""
    ctx = mp.get_context("spawn")
    inbox = ctx.Queue()
    results = ctx.Queue()
    ready = ctx.Event()
    matcher = ctx.Process(
        target=matcher_worker,
        args=(inbox, database_path, results, ready, None),
        name="MatcherProcess",
    )
    matcher.start()
    if not ready.wait(timeout=10):
        matcher.terminate()
        matcher.join()
        raise RuntimeError("Matcher did not become ready")

    # Each order is intentionally chosen to make the matching behavior easy to explain live.
    scenario = [
        ("showcase-sell-1", "SELL", "100", 5, "Resting sell: five units at 100"),
        ("showcase-sell-2", "SELL", "101", 4, "Second sell: four units at 101"),
        ("showcase-buy-1", "BUY", "99", 3, "Buy at 99 cannot cross either sell, so it rests"),
        ("showcase-buy-2", "BUY", "100", 2, "Buy at 100 matches two units at the resting sell price"),
        ("showcase-buy-3", "BUY", "102", 5, "Buy at 102 consumes the remaining best sells"),
    ]
    start_time = time.time()
    for index, (order_id, side, price, quantity, _explanation) in enumerate(scenario):
        inbox.put({
            "type": "ORDER",
            "order_id": order_id,
            "side": side,
            "price": price,
            "quantity": quantity,
            "created_at": start_time + index * 0.001,
            "source": "deterministic-showcase",
        })
    inbox.put({"type": "STOP"})
    matcher.join(timeout=15)
    if matcher.is_alive():
        matcher.terminate()
        matcher.join()
        raise RuntimeError("Matcher did not stop in time")

    print("\\n=== ORDER MATCHING ENGINE: LIVE SHOWCASE ===")
    print("Rule: price-time priority; the resting order sets the trade price.\\n")
    for index, (order_id, side, price, quantity, explanation) in enumerate(scenario, 1):
        print(f"{index}. {side:4} {price:>3} x {quantity}  | {explanation}")
        try:
            result = results.get(timeout=2)
        except queue_module.Empty:
            print("   No result received. Check matcher logs/database.")
            continue
        if result.get("type") == "RESULT":
            print(f"   => {result['status']}; remaining quantity: {result['remaining_quantity']}")
            for trade in result["trades"]:
                print(f"      TRADE: {trade['quantity']} unit(s) @ {trade['price']} "
                      f"(buy={trade['buy_order_id']}, sell={trade['sell_order_id']})")
        else:
            print(f"   => {result}")
    inbox.close()
    results.close()

    storage = Storage(database_path)
    try:
        engine = MatchingEngine(storage)
        book = engine.snapshot()
        print("\\n=== FINAL OPEN ORDER BOOK ===")
        print("BUY orders (best price first):")
        if book["buys"]:
            for order in book["buys"]:
                print(f"  BUY  {order['price']:>3} x {order['quantity']}  id={order['order_id']}")
        else:
            print("  (empty)")
        print("SELL orders (best price first):")
        if book["sells"]:
            for order in book["sells"]:
                print(f"  SELL {order['price']:>3} x {order['quantity']}  id={order['order_id']}")
        else:
            print("  (empty)")
        print("\\n=== DATABASE SUMMARY ===")
        print(json.dumps(storage.stats(), indent=2))
        print("\\nRun `python -m order_engine --db showcase.db inspect` to inspect persisted rows.")
    finally:
        storage.close()
