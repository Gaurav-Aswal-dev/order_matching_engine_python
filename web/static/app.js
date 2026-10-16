const $ = (id) => document.getElementById(id);
let selectedSide = "BUY";
let toastTimer;

function money(value) {
  if (value === null || value === undefined || value === "") return "—";
  return Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}
function showToast(message) {
  const el = $("toast");
  el.textContent = message;
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 3000);
}
async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.detail || `Request failed (${response.status})`);
  return payload;
}
function setConnection(healthy) {
  $("connection-label").textContent = healthy ? "Connected to API" : "API unavailable";
  $("connection-label").style.color = healthy ? "#65dfb3" : "#ff8298";
}
function renderBook(book) {
  const sells = [...book.sells].sort((a, b) => Number(a.price) - Number(b.price));
  const buys = [...book.buys].sort((a, b) => Number(b.price) - Number(a.price));
  const maxQty = Math.max(1, ...sells.map(o => Number(o.quantity)), ...buys.map(o => Number(o.quantity)));
  function rows(items, side) {
    if (!items.length) return `<div class="empty-state">No resting ${side.toLowerCase()} orders</div>`;
    return items.slice(0, 8).map(o => {
      const width = Math.max(5, Number(o.quantity) / maxQty * 100);
      return `<div class="book-row ${side.toLowerCase()}" style="--bar:${width}%">
        <span class="book-price">${money(o.price)}</span><span class="book-qty">${Number(o.quantity).toLocaleString("en-IN")}</span>
      </div>`;
    }).join("");
  }
  $("sell-book").innerHTML = rows(sells, "SELL");
  $("buy-book").innerHTML = rows(buys, "BUY");
  $("sell-count").textContent = sells.length;
  $("buy-count").textContent = buys.length;
  const bestBid = buys.length ? Number(buys[0].price) : null;
  const bestAsk = sells.length ? Number(sells[0].price) : null;
  $("best-bid").textContent = bestBid === null ? "—" : `₹${money(bestBid)}`;
  $("best-ask").textContent = bestAsk === null ? "—" : `₹${money(bestAsk)}`;
  $("spread").textContent = bestBid === null || bestAsk === null ? "—" : `₹${money(bestAsk - bestBid)}`;
}
function renderTrades(payload) {
  const trades = payload.trades || [];
  if (!trades.length) {
    $("trades-body").innerHTML = '<tr><td colspan="6" class="empty-table">No trades yet. Place crossing orders to see executions.</td></tr>';
    return;
  }
  $("trades-body").innerHTML = trades.slice(0, 10).map(t => `
    <tr>
      <td class="trade-id">#${t.trade_id}</td>
      <td>${String(t.buy_order_id).slice(0, 13)}…</td>
      <td>${String(t.sell_order_id).slice(0, 13)}…</td>
      <td class="trade-price">₹${money(t.price)}</td>
      <td class="trade-qty">${Number(t.quantity).toLocaleString("en-IN")}</td>
      <td><span class="status-chip">● EXECUTED</span></td>
    </tr>`).join("");
}
async function refreshDashboard() {
  try {
    const [health, book, trades, stats] = await Promise.all([
      api("/api/health"), api("/api/book"), api("/api/trades?limit=10"), api("/api/stats")
    ]);
    setConnection(health.status === "ok");
    renderBook(book);
    renderTrades(trades);
    $("stat-orders").textContent = Number(stats.orders).toLocaleString("en-IN");
    $("stat-open").textContent = Number(stats.open_orders).toLocaleString("en-IN");
    $("stat-trades").textContent = Number(stats.trades).toLocaleString("en-IN");
    $("stat-volume").textContent = Number(stats.traded_quantity).toLocaleString("en-IN");
    $("last-updated").textContent = `Updated ${new Date().toLocaleTimeString()}`;
  } catch (error) {
    setConnection(false);
    $("last-updated").textContent = "Unable to reach API";
  }
}
function chooseSide(side) {
  selectedSide = side;
  $("side-input").value = side;
  document.querySelectorAll(".side-button").forEach(button => {
    button.classList.toggle("selected", button.dataset.side === side);
  });
  $("submit-button").classList.toggle("buy-submit", side === "BUY");
  $("submit-button").classList.toggle("sell-submit", side === "SELL");
  $("submit-button").querySelector("span:first-child").textContent = `Submit ${side.toLowerCase()} order`;
  $("order-hint-text").textContent = side === "BUY"
    ? "A buy matches a resting sell at or below your limit price."
    : "A sell matches a resting buy at or above your limit price.";
}
document.querySelectorAll(".side-button").forEach(button => {
  button.addEventListener("click", () => chooseSide(button.dataset.side));
});
$("refresh-button").addEventListener("click", refreshDashboard);
$("order-form").addEventListener("submit", async event => {
  event.preventDefault();
  const button = $("submit-button");
  const feedback = $("order-feedback");
  const price = Number($("price-input").value);
  const quantity = Number($("quantity-input").value);
  if (!Number.isFinite(price) || price <= 0 || !Number.isInteger(quantity) || quantity <= 0) {
    feedback.className = "feedback error";
    feedback.textContent = "Enter a positive price and a whole-number quantity.";
    return;
  }
  button.disabled = true;
  feedback.className = "feedback";
  feedback.textContent = "Sending order to the matching engine…";
  try {
    const result = await api("/api/orders", {
      method: "POST",
      body: JSON.stringify({ side: selectedSide, price, quantity })
    });
    const tradeCount = (result.trades || []).length;
    feedback.className = "feedback success";
    feedback.textContent = `${result.status}: ${tradeCount} trade(s), ${result.remaining_quantity} unit(s) remaining.`;
    showToast(`${selectedSide} order accepted: ${result.status}`);
    await refreshDashboard();
  } catch (error) {
    feedback.className = "feedback error";
    feedback.textContent = error.message;
    showToast(`Order failed: ${error.message}`);
  } finally {
    button.disabled = false;
  }
});
chooseSide("BUY");
refreshDashboard();
setInterval(refreshDashboard, 3000);
