# C++ companion demonstration

The main application is Python. All OS concepts, including process creation and IPC, remain implemented in Python using `multiprocessing` and `multiprocessing.Queue`.

The C++ program is a separate, optional demonstration of the matching algorithm only. It is not called by the Python app and does not share its database.

## C++: matching algorithm

`cpp/matching_demo.cpp` demonstrates price-time priority, matching, partial fills, and the remaining order book.

### Windows with MinGW-w64 installed

```powershell
cd native\cpp
g++ -std=c++17 -Wall -Wextra -O2 matching_demo.cpp -o matching_demo.exe
.\matching_demo.exe
```

### Linux / WSL / macOS

```bash
cd native/cpp
g++ -std=c++17 -Wall -Wextra -O2 matching_demo.cpp -o matching_demo
./matching_demo
```

## Architecture boundary

- **Python**: process creation, IPC, order matching, SQLite persistence, recovery, CLI, and tests.
- **C++**: optional standalone matching-algorithm demonstration only.
- No C source code is included. No OS/IPC functionality is implemented in C or C++.
