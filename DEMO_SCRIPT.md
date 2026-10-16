# Saturday Demonstration Plan (5–7 minutes)

## Before class
1. Open the extracted project folder in VS Code.
2. Open a terminal in that folder.
3. Run `python -m unittest discover -s tests -v` and confirm all tests pass.
4. Use a fresh database filename for the live run: `showcase.db`.

## Live demonstration

### 1. Explain the problem (30 seconds)
A stock exchange receives buy and sell orders. If a buy price meets or exceeds a resting sell price, a trade can happen. Otherwise the order waits in the order book.

### 2. Show the architecture (45 seconds)
- `producer.py` generates order messages.
- `runtime.py` starts independent processes.
- `multiprocessing.Queue` carries messages between them.
- `matcher.py` applies price-time priority.
- `storage.py` stores order state and trades in SQLite.

### 3. Run the deterministic scenario (2 minutes)
```bash
python -m order_engine --db showcase.db showcase
```

Explain these behaviors:
- SELL 100 x 5 and SELL 101 x 4 rest in the book.
- BUY 99 x 3 does not cross either sell, so it rests.
- BUY 100 x 2 trades with the best sell at 100, leaving 3 sell units.
- BUY 102 x 5 consumes the remaining 3 units at 100 and 2 units at 101.
- The unfilled BUY 99 x 3 and SELL 101 x 2 remain in the final book.

### 4. Show persistence (45 seconds)
```bash
python -m order_engine --db showcase.db inspect
```
Point out that the orders and trade records are in SQLite, not only in process memory.

### 5. Show recovery (45 seconds)
```bash
python -m order_engine --db showcase.db book
```
Explain that the matcher reloads OPEN/PARTIAL orders when it starts. A trade history alone is insufficient to reconstruct every unfilled order.

### 6. Show tests (30 seconds)
```bash
python -m unittest discover -s tests -v
```

## Strong viva answers

**Why separate processes?** To demonstrate OS process creation and inter-process communication. Independent processes do not share ordinary Python memory.

**Why use a Queue?** It transfers serialized messages safely between processes and provides blocking reads. It is simple IPC, not a durable broker.

**Why SQLite?** It provides transactions and durable storage without requiring a separate database server.

**What is price-time priority?** Better prices win first. At the same price, earlier orders win.

**Why execute at the resting order's price?** This prototype uses the resting order's price as its explicit matching rule.

**What happens after a crash?** Committed order/trade state remains in SQLite; on restart, open and partially filled orders are loaded into the book.

**What is the biggest limitation?** The IPC queue itself is not durable. An order sent but not committed before a hard crash can be lost. A production design needs durable input/replay and acknowledgements.

## Avoid these demo traps
- Do not reuse a database from earlier random demos if you want the expected small scenario.
- Run commands from the project root, the folder containing `order_engine` and `tests`.
- Do not claim this is production-grade or exactly-once delivery.
- If a command fails, use the README and show the tested matching logic rather than improvising database edits.
## Optional C++ bonus (algorithm only)

The operating-system concepts remain in the Python application. If time allows, show the standalone C++ matcher:

Windows with MinGW-w64:
```powershell
cd native\cpp
g++ -std=c++17 -Wall -Wextra -O2 matching_demo.cpp -o matching_demo.exe
.\matching_demo.exe
```

Linux / WSL / macOS:
```bash
cd native/cpp
g++ -std=c++17 -Wall -Wextra -O2 matching_demo.cpp -o matching_demo
./matching_demo
```

Describe it accurately: C++ demonstrates the matching algorithm; Python handles processes, IPC, persistence, and recovery.
## Optional web dashboard (HTML/CSS/JavaScript)

From the project root:
```powershell
python -m pip install -r requirements-web.txt
python -m uvicorn web.app:app --host 127.0.0.1 --port 8000
```
Open `http://127.0.0.1:8000`.

Suggested 60-second interaction:
1. Place a `SELL` order at price `100`, quantity `5`.
2. Place a `BUY` order at price `99`, quantity `3`; show that it rests in the book.
3. Place a `BUY` order at price `100`, quantity `2`; show the trade log update.
4. Point to the order/trade counters and the remaining book.

The web dashboard is a separate server mode using the same Python matching and SQLite classes. The CLI producer/matcher IPC demonstration is a distinct mode.
