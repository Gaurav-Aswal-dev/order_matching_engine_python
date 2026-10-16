/*
 * C++17 miniature price-time-priority matcher.
 * This is a native algorithm demonstration separate from the Python/SQLite app.
 *
 * Build:
 *   g++ -std=c++17 -Wall -Wextra -O2 matching_demo.cpp -o matching_demo
 * Run:
 *   ./matching_demo
 */
#include <algorithm>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

struct Order {
    std::string id;
    bool is_buy;
    int price;
    int quantity;
    long long sequence;
};

struct Trade {
    std::string buy_id;
    std::string sell_id;
    int price;
    int quantity;
};

class MatchingBook {
public:
    void add(Order incoming) {
        int remaining = incoming.quantity;

        if (incoming.is_buy) {
            std::sort(sells.begin(), sells.end(), [](const Order& a, const Order& b) {
                if (a.price != b.price) return a.price < b.price;
                return a.sequence < b.sequence;
            });
            while (remaining > 0 && !sells.empty() && incoming.price >= sells.front().price) {
                Order& resting = sells.front();
                const int qty = std::min(remaining, resting.quantity);
                trades.push_back({incoming.id, resting.id, resting.price, qty});
                remaining -= qty;
                resting.quantity -= qty;
                if (resting.quantity == 0) sells.erase(sells.begin());
            }
            if (remaining > 0) {
                incoming.quantity = remaining;
                buys.push_back(incoming);
            }
        } else {
            std::sort(buys.begin(), buys.end(), [](const Order& a, const Order& b) {
                if (a.price != b.price) return a.price > b.price;
                return a.sequence < b.sequence;
            });
            while (remaining > 0 && !buys.empty() && incoming.price <= buys.front().price) {
                Order& resting = buys.front();
                const int qty = std::min(remaining, resting.quantity);
                trades.push_back({resting.id, incoming.id, resting.price, qty});
                remaining -= qty;
                resting.quantity -= qty;
                if (resting.quantity == 0) buys.erase(buys.begin());
            }
            if (remaining > 0) {
                incoming.quantity = remaining;
                sells.push_back(incoming);
            }
        }
    }

    void print() const {
        std::cout << "\nTrades:\n";
        if (trades.empty()) std::cout << "  (none)\n";
        for (const auto& t : trades) {
            std::cout << "  " << t.quantity << " unit(s) @ " << t.price
                      << " | BUY " << t.buy_id << " / SELL " << t.sell_id << '\n';
        }
        std::cout << "\nOpen buys (best first):\n";
        auto sorted_buys = buys;
        std::sort(sorted_buys.begin(), sorted_buys.end(), [](const Order& a, const Order& b) {
            if (a.price != b.price) return a.price > b.price;
            return a.sequence < b.sequence;
        });
        if (sorted_buys.empty()) std::cout << "  (empty)\n";
        for (const auto& o : sorted_buys)
            std::cout << "  BUY  " << o.price << " x " << o.quantity << " [" << o.id << "]\n";

        std::cout << "Open sells (best first):\n";
        auto sorted_sells = sells;
        std::sort(sorted_sells.begin(), sorted_sells.end(), [](const Order& a, const Order& b) {
            if (a.price != b.price) return a.price < b.price;
            return a.sequence < b.sequence;
        });
        if (sorted_sells.empty()) std::cout << "  (empty)\n";
        for (const auto& o : sorted_sells)
            std::cout << "  SELL " << o.price << " x " << o.quantity << " [" << o.id << "]\n";
    }

private:
    std::vector<Order> buys;
    std::vector<Order> sells;
    std::vector<Trade> trades;
};

int main() {
    MatchingBook book;
    std::cout << "C++ matching algorithm demo (price-time priority)\n";
    book.add({"S1", false, 100, 5, 1});
    book.add({"S2", false, 101, 4, 2});
    book.add({"B1", true, 99, 3, 3});
    book.add({"B2", true, 100, 2, 4});
    book.add({"B3", true, 102, 5, 5});
    book.print();
    return 0;
}
