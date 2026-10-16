# Order Matching Engine with IPC (Python)

A runnable educational implementation of the project described in the supplied brief. It uses two independent processes, `multiprocessing.Queue` for IPC, price-time-priority matching, and SQLite as the durable source of truth.

## Features implemented

- **Producer process** generates buy/sell orders and sends them one at a time.
- **Matcher process** receives and validates order messages over an IPC queue.
- **Matching rules**: a buy crosses a sell when buy price >= resting sell price; a sell crosses a buy when sell price <= resting buy price.
- **Price-time priority**: highest-priced buy and lowest-priced sell have priority; older orders win ties.
- **Partial fills**: matched quantity is traded and any remainder stays in the book.
- **SQLite persistence**: orders and trades are committed transactionally; WAL mode and `synchronous=FULL` are enabled.
- **Recovery**: on startup, open and partially-filled orders are loaded from SQLite. Completed trades remain queryable.
- **Duplicate-message protection**: a processed order ID is recorded transactionally.
- **Crash demonstration**: deliberately terminate the matcher after N processed orders, then restart it to observe recovered book state.
- **Tests** cover matching, partial fills, recovery, and duplicate delivery.

## Requirements

- Python 3.10+
- No third-party packages. Only the Python standard library is used.

## Run it

Open a terminal in this folder.

### 1. Run the producer and matcher processes

```bash
python -m order_engine --db demo.db demo --count 20
```

The demo starts separate `ProducerProcess` and `MatcherProcess` children. The producer sends orders through a `multiprocessing.Queue`.

### 2. Run the deterministic presentation showcase

Use a fresh database so the expected output stays easy to explain:

```bash
python -m order_engine --db showcase.db showcase
```

This runs a fixed scenario that demonstrates resting orders, a non-crossing order, matching at the resting price, and one incoming order filling against multiple resting orders.

### 3. Inspect saved orders and trades

```bash
python -m order_engine --db demo.db inspect
```

### 4. Inspect the recovered live order book

```bash
python -m order_engine --db demo.db book
```

### 5. Enter orders manually

```bash
python -m order_engine --db manual.db interactive
```

Example input:

```text
SELL 100 5
BUY 99 3
BUY 101 2
quit
```

### 6. Simulate a matcher crash

```bash
python -m order_engine --db crash-demo.db demo --count 20 --crash-after 5
```

The matcher exits abruptly after processing the configured number of orders. Inspect what was committed:

```bash
python -m order_engine --db crash-demo.db inspect
python -m order_engine --db crash-demo.db book
```

Then restart normally using the same database:

```bash
python -m order_engine --db crash-demo.db demo --count 5
```

The matcher reconstructs the outstanding book from persisted open/partial orders. The demo producer uses new order IDs each run, so it does not replay the exact unacknowledged messages from the previous run.

### 7. Run tests

From the project folder:

```bash
python -m unittest discover -s tests -v
```

## Optional C and C++ demonstrations

The Python application is the main runnable system, and all OS concepts (process creation and IPC) stay in Python using `multiprocessing` and `multiprocessing.Queue`. The `native/` folder contains only `native/cpp/matching_demo.cpp`, a standalone C++ price-time-priority matching demo. It can be compiled on Windows if a C++ compiler is installed. It is a companion algorithm demonstration, not a module integrated into the Python runtime. No C source files are included.

## File layout

```text
order_matching_engine_python/
├── order_engine/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── matcher.py
│   ├── models.py
│   ├── producer.py
│   ├── runtime.py
│   └── storage.py
├── tests/
│   └── test_engine.py
└── README.md
```

## Matching example

If a resting `SELL 100 x 5` exists and a new `BUY 102 x 3` arrives, 3 units trade at 100 (the resting order's price). The sell order remains in the book with quantity 2.

## Important design notes and limitations

This is a learning project, not a production exchange.

1. The demo has one matcher process and one producer process. A single matcher serializes book updates, avoiding concurrent matching races.
2. SQLite is the source of truth. Open order quantities and each trade are committed in one transaction.
3. The book is reconstructed from open and partially-filled orders, not from trades alone. Completed trades cannot reveal every still-open order.
4. `multiprocessing.Queue` is a simple IPC channel, not a durable message broker. A hard crash can lose messages that were queued but not committed. A production version would need acknowledgements, replayable input logs, or a durable broker and a carefully designed idempotency protocol.
5. The crash demo is intentionally rough: it demonstrates persistence and recovery, but does not guarantee exactly-once processing for every order sent immediately before a crash.
6. Prices are stored as decimal strings to avoid binary floating-point comparisons.
7. This prototype does not implement authentication, market symbols, cancel/replace requests, exchange sessions, regulatory controls, or high-throughput performance engineering.

## Concept map

- **OS**: process creation, IPC, blocking queue reads, abnormal termination, restart.
- **DBMS**: transactions, constraints, durability settings, persisted state, recovery.
- **Algorithms**: price-time priority, crossing-price check, partial fills.


## Web dashboard (HTML/CSS/JavaScript)

The `web/` folder adds a browser dashboard backed by FastAPI. The UI is plain HTML, CSS, and JavaScript; the backend calls the existing Python matching engine and SQLite storage.

### Start on Windows

From the project root (the folder containing `order_engine`, `web`, and `tests`):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-web.txt
python -m uvicorn web.app:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000` in your browser. Stop the server with Ctrl+C.

### API endpoints

- `GET /api/health` - health check
- `GET /api/book` - current open order book
- `GET /api/trades?limit=10` - latest trade records
- `GET /api/stats` - order/trade counts and traded quantity
- `POST /api/orders` - submit a simulated order, JSON such as `{"side":"BUY","price":101,"quantity":3}`

FastAPI's interactive API docs are at `http://127.0.0.1:8000/docs`.

### Important architecture note

The web server runs a matching-engine instance in its own server process. The separate producer/matcher IPC demo remains available through the CLI (`python -m order_engine --db demo.db demo`). The web dashboard uses the same matching and storage classes but is not itself wired through the multiprocessing producer queue. Keep that distinction clear in your presentation. This is a local educational demo, not a real trading service; do not expose it to the public internet.
