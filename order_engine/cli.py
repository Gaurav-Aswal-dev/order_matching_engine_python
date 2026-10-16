from __future__ import annotations

import argparse
import json
from multiprocessing import freeze_support

from .runtime import run_demo, run_matcher_only, run_showcase
from .storage import Storage


def main() -> None:
    parser = argparse.ArgumentParser(description="Educational Order Matching Engine with IPC")
    parser.add_argument("--db", default="order_engine.db", help="SQLite database path")
    sub = parser.add_subparsers(dest="command", required=True)

    demo = sub.add_parser("demo", help="run producer and matcher processes")
    demo.add_argument("--count", type=int, default=20)
    demo.add_argument("--delay", type=float, default=0.05)
    demo.add_argument("--crash-after", type=int, default=None,
                      help="simulate matcher crash after processing N orders")

    sub.add_parser("showcase", help="run a deterministic, presentation-friendly scenario")
    sub.add_parser("interactive", help="enter manual orders into a local matcher")
    sub.add_parser("inspect", help="print persisted orders, trades, and counts")
    sub.add_parser("book", help="print recovered open order book")

    args = parser.parse_args()
    if args.command == "demo":
        if args.count < 0 or args.delay < 0:
            parser.error("--count and --delay must be non-negative")
        run_demo(args.db, args.count, args.delay, args.crash_after)
    elif args.command == "showcase":
        run_showcase(args.db)
    elif args.command == "interactive":
        run_matcher_only(args.db)
    elif args.command in {"inspect", "book"}:
        storage = Storage(args.db)
        try:
            if args.command == "inspect":
                print(json.dumps({
                    "stats": storage.stats(),
                    "orders": storage.list_orders(),
                    "trades": storage.list_trades(),
                }, indent=2))
            else:
                from .matcher import MatchingEngine
                engine = MatchingEngine(storage)
                print(json.dumps(engine.snapshot(), indent=2))
        finally:
            storage.close()


if __name__ == "__main__":
    freeze_support()
    main()
