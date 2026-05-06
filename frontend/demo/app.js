// FlowScope Demo Trading Frontend Application

const API_BASE_URL = "http://localhost:8000/api";
let equityChart = null;
let equityData = [];
let pollInterval = null;

// Initialize on page load
document.addEventListener("DOMContentLoaded", () => {
  initializeChart();
  refreshStatus();
  addLogEntry("Demo trading dashboard initialized", "info");
});

// Initialize Chart.js equity curve
function initializeChart() {
  const ctx = document.getElementById("equityChart").getContext("2d");
  equityChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        {
          label: "Equity ($)",
          data: [],
          borderColor: "#4285f4",
          backgroundColor: "rgba(66, 133, 244, 0.1)",
          borderWidth: 2,
          fill: true,
          tension: 0.4,
          pointRadius: 3,
          pointHoverRadius: 5,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: {
          display: true,
          position: "top",
          labels: {
            color: "#e8eaed",
          },
        },
      },
      scales: {
        x: {
          grid: {
            color: "#3c4043",
          },
          ticks: {
            color: "#9aa0a6",
          },
        },
        y: {
          grid: {
            color: "#3c4043",
          },
          ticks: {
            color: "#9aa0a6",
            callback: (value) => `$${value.toFixed(2)}`,
          },
        },
      },
    },
  });
}

// Start demo session
async function startDemo() {
  try {
    const btnStart = document.getElementById("btnStart");
    btnStart.disabled = true;
    btnStart.innerHTML = "⏳ Starting...";

    const response = await fetch(`${API_BASE_URL}/demo/start`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        initial_balance: 10000.0,
        description: "Demo trading session",
      }),
    });

    const result = await response.json();

    if (result.success) {
      addLogEntry(`Demo session started: ${result.data.session_id}`, "success");
      updateUIState("running");
      startPolling();
    } else {
      throw new Error(result.detail || "Failed to start demo");
    }
  } catch (error) {
    addLogEntry(`Error starting demo: ${error.message}`, "error");
    alert(`Failed to start demo: ${error.message}`);
  } finally {
    const btnStart = document.getElementById("btnStart");
    btnStart.disabled = false;
    btnStart.innerHTML = "▶ Start Demo";
  }
}

// Stop demo session
async function stopDemo() {
  try {
    const btnStop = document.getElementById("btnStop");
    btnStop.disabled = true;
    btnStop.innerHTML = "⏳ Stopping...";

    const response = await fetch(`${API_BASE_URL}/demo/stop`, {
      method: "POST",
    });

    const result = await response.json();

    if (result.success) {
      addLogEntry(
        `Demo session stopped. Total trades: ${result.data.total_trades}`,
        "warning",
      );
      updateUIState("stopped");
      stopPolling();
    } else {
      throw new Error(result.detail || "Failed to stop demo");
    }
  } catch (error) {
    addLogEntry(`Error stopping demo: ${error.message}`, "error");
    alert(`Failed to stop demo: ${error.message}`);
  } finally {
    const btnStop = document.getElementById("btnStop");
    btnStop.disabled = false;
    btnStop.innerHTML = "⏹ Stop Demo";
  }
}

// Refresh status
async function refreshStatus() {
  try {
    const response = await fetch(`${API_BASE_URL}/demo/status`);
    const result = await response.json();

    if (result.success && result.running) {
      updateUIState("running");
      updateStatistics(result.data);
      updatePositions(result.data.positions);
      updateTrades(result.data.recent_trades);
      updateEquityChart(result.data);
      startPolling();
    } else {
      updateUIState("stopped");
    }
  } catch (error) {
    console.error("Error refreshing status:", error);
    updateUIState("disconnected");
  }
}

// Update UI state
function updateUIState(state) {
  const statusIndicator = document.getElementById("statusIndicator");
  const statusText = document.getElementById("statusText");
  const btnStart = document.getElementById("btnStart");
  const btnStop = document.getElementById("btnStop");

  statusIndicator.className = "status-indicator";

  if (state === "running") {
    statusIndicator.classList.add("connected", "running");
    statusText.textContent = "Running";
    btnStart.disabled = true;
    btnStop.disabled = false;
  } else if (state === "stopped") {
    statusIndicator.classList.add("connected");
    statusText.textContent = "Connected";
    btnStart.disabled = false;
    btnStop.disabled = true;
  } else {
    statusText.textContent = "Disconnected";
    btnStart.disabled = false;
    btnStop.disabled = true;
  }
}

// Update statistics display
function updateStatistics(data) {
  document.getElementById("statBalance").textContent =
    `$${(data.current_balance || 0).toFixed(2)}`;

  const pnlElement = document.getElementById("statPnL");
  const pnl = data.total_unrealized_pnl || 0;
  pnlElement.textContent = `$${pnl.toFixed(2)}`;
  pnlElement.className = `stat-value ${pnl >= 0 ? "positive" : "negative"}`;

  const stats = data.statistics || {};
  document.getElementById("statTrades").textContent = stats.total_trades || 0;
  document.getElementById("statWinrate").textContent =
    `${(stats.winrate || 0).toFixed(1)}%`;
}

// Update positions table
function updatePositions(positions) {
  const tbody = document.getElementById("positionsBody");

  if (!positions || positions.length === 0) {
    tbody.innerHTML =
      '<tr><td colspan="7" class="empty-message">No active positions</td></tr>';
    return;
  }

  tbody.innerHTML = positions
    .map(
      (pos) => `
        <tr>
            <td><strong>${pos.symbol}</strong></td>
            <td>
                <span style="color: ${pos.side === "LONG" ? "#0f9d58" : "#db4437"}">
                    ${pos.side}
                </span>
            </td>
            <td>${pos.size.toFixed(4)}</td>
            <td>$${pos.entry_price.toFixed(2)}</td>
            <td>$${pos.mark_price.toFixed(2)}</td>
            <td style="color: ${pos.unrealized_pnl >= 0 ? "#0f9d58" : "#db4437"}">
                $${pos.unrealized_pnl.toFixed(2)}
            </td>
            <td>
                <button class="btn btn-danger btn-small" 
                        onclick="closePosition('${pos.symbol}')">
                    Close
                </button>
            </td>
        </tr>
    `,
    )
    .join("");
}

// Update trades table
function updateTrades(trades) {
  const tbody = document.getElementById("tradesBody");

  if (!trades || trades.length === 0) {
    tbody.innerHTML =
      '<tr><td colspan="8" class="empty-message">No trades yet</td></tr>';
    return;
  }

  tbody.innerHTML = trades
    .map(
      (trade) => `
        <tr>
            <td>${formatTimestamp(trade.timestamp)}</td>
            <td><strong>${trade.symbol}</strong></td>
            <td>${trade.signal_type}</td>
            <td>
                <span style="color: ${trade.bias === "Bullish" ? "#0f9d58" : "#db4437"}">
                    ${trade.bias}
                </span>
            </td>
            <td>${trade.setup_type}</td>
            <td>$${(trade.entry_price || 0).toFixed(2)}</td>
            <td style="color: ${trade.pnl >= 0 ? "#0f9d58" : "#db4437"}">
                $${(trade.pnl || 0).toFixed(2)}
            </td>
            <td>
                <span style="color: ${trade.status === "CLOSED" ? "#0f9d58" : "#f4b400"}">
                    ${trade.status}
                </span>
            </td>
        </tr>
    `,
    )
    .join("");
}

// Update equity chart
function updateEquityChart(data) {
  const now = new Date();
  equityData.push({
    timestamp: now,
    balance: data.current_balance || 0,
  });

  // Keep last 50 data points
  if (equityData.length > 50) {
    equityData.shift();
  }

  equityChart.data.labels = equityData.map((d) =>
    d.timestamp.toLocaleTimeString(),
  );
  equityChart.data.datasets[0].data = equityData.map((d) => d.balance);
  equityChart.update();
}

// Close position
async function closePosition(symbol) {
  if (!confirm(`Close position for ${symbol}?`)) {
    return;
  }

  try {
    const response = await fetch(`${API_BASE_URL}/demo/close`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        symbol: symbol,
        reason: "Manual Close",
      }),
    });

    const result = await response.json();

    if (result.success) {
      addLogEntry(
        `Position closed: ${symbol}, PnL: $${(result.data.pnl || 0).toFixed(2)}`,
        "info",
      );
      refreshStatus();
    } else {
      throw new Error(result.detail || "Failed to close position");
    }
  } catch (error) {
    addLogEntry(`Error closing position: ${error.message}`, "error");
    alert(`Failed to close position: ${error.message}`);
  }
}

// Add log entry
function addLogEntry(message, type = "info") {
  const logContainer = document.getElementById("signalLog");
  const timestamp = new Date().toLocaleTimeString();

  const entry = document.createElement("div");
  entry.className = `log-entry ${type}`;
  entry.innerHTML = `<span class="log-timestamp">[${timestamp}]</span>${message}`;

  logContainer.insertBefore(entry, logContainer.firstChild);

  // Keep last 50 entries
  while (logContainer.children.length > 50) {
    logContainer.removeChild(logContainer.lastChild);
  }
}

// Format timestamp
function formatTimestamp(timestamp) {
  if (!timestamp) return "-";
  const date = new Date(timestamp);
  return date.toLocaleString();
}

// Start polling for updates
function startPolling() {
  if (pollInterval) {
    clearInterval(pollInterval);
  }
  pollInterval = setInterval(refreshStatus, 5000); // Poll every 5 seconds
}

// Stop polling
function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
}

// Auto-refresh on page visibility change
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") {
    refreshStatus();
  }
});
