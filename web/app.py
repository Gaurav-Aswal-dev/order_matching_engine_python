from __future__ import annotations

import os
import sys
from pathlib import Path
from threading import RLock
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Allow running from the project root: uvicorn web.app:app --reload
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from order_engine.matcher import MatchingEngine
from order_engine.models import Order
from order_engine.storage import Storage

APP_DIR = Path(__file__).resolve().parent
DB_PATH = os.environ.get("ORDER_ENGINE_DB", str(PROJECT_ROOT / "web_demo.db"))

app = FastAPI(
    title="Order Matching Engine",
    description="Educational order book demo with Python, IPC project core, SQLite persistence, and a web dashboard.",
    version="1.0.0",
)
app.mount("/static", StaticFiles(directory=str(APP_DIR / "static")), name="static")

# The API's in-process engine is a separate web-demo mode. The CLI demo continues to show
# the producer and matcher as independent multiprocessing processes.
_storage = Storage(DB_PATH, check_same_thread=False)
_engine = MatchingEngine(_storage)
_lock = RLock()


class OrderRequest(BaseModel):
    side: Literal["BUY", "SELL"]
    price: float = Field(gt=0, le=1_000_000_000)
    quantity: int = Field(gt=0, le=1_000_000)


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(APP_DIR / "static" / "index.html")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "order-matching-engine"}


@app.get("/api/book")
def get_book():
    with _lock:
        return _engine.snapshot()


@app.get("/api/trades")
def get_trades(limit: int = 50):
    if not 1 <= limit <= 500:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 500")
    with _lock:
        trades = _storage.list_trades()
    return {"trades": list(reversed(trades[-limit:]))}


@app.get("/api/stats")
def get_stats():
    with _lock:
        stats = _storage.stats()
        trades = _storage.list_trades()
    stats["traded_quantity"] = sum(int(t["quantity"]) for t in trades)
    stats["database"] = Path(DB_PATH).name
    return stats


@app.post("/api/orders")
def submit_order(request: OrderRequest):
    try:
        order = Order.create(request.side, request.price, request.quantity, source="web-ui")
        with _lock:
            result = _engine.process(order)
        return {
            **result,
            "side": order.side,
            "price": order.price,
            "quantity": order.quantity,
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        # Avoid returning internal traceback/details to the browser.
        raise HTTPException(status_code=500, detail="Order could not be processed. Check server logs.") from exc


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("web.app:app", host="127.0.0.1", port=8000, reload=False)
