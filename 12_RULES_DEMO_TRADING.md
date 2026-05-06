# 📜 12 RULES — DEMO TRADING STATE MANAGEMENT

**Core Principle:** SESSION → ACCOUNT → POSITION → EXECUTION

**Satu Kalimat:** Kalau session belum jalan, sistem harus "buta total" terhadap Binance

---

## 🔥 RULE 1 — SESSION AS SINGLE SOURCE OF TRUTH

**Session status adalah SATU-SATUNYA gate untuk semua operasi.**

```typescript
// ✅ CORRECT
IF session.running == false:
    → Do NOT fetch positions
    → Do NOT fetch balance
    → Do NOT render trading data

// ❌ WRONG
IF positions exist:
    → Assume session is running
```

**Implementation:**

```typescript
// Backend: backend/api/demo_trading.py
if not _demo_engine or not _demo_engine.running:
    raise HTTPException(400, "No active demo session")

// Frontend: frontend/app/demo-trading/page.tsx
const isSessionRunning = statusResponse?.success && statusResponse?.running;
```

---

## 🔍 RULE 2 — STATUS FIRST (WAJIB)

**ALWAYS fetch `/demo/status` DULUAN sebelum operasi apapun.**

**Required Fields:**

- `running` (boolean) — Gate keeper
- `current_balance` (float) — Validation
- `available_balance` (float) — Risk control

**Implementation:**

```typescript
// Frontend: Fetch status FIRST
const { data: statusResponse } = useQuery({
  queryKey: ["demo", "status"],
  queryFn: () => api.getDemoStatus(),
  refetchInterval: 5000,
});

const status = statusResponse?.data;
const isSessionRunning = statusResponse?.success && statusResponse?.running;
```

---

## 🔌 RULE 3 — CONDITIONAL DATA FETCH

**Hanya fetch data Binance JIKA session running.**

```typescript
// ✅ CORRECT
IF session.running == true:
    Fetch:
    - GET /fapi/v2/account   → balance
    - GET /fapi/v2/positionRisk → positions

ELSE:
    Skip ALL Binance-related fetch
```

**Implementation:**

```typescript
// Frontend: enabled flag
const { data: positions } = useQuery({
  queryKey: ["demo", "positions"],
  queryFn: () => api.getDemoPositions(),
  enabled: isSessionRunning, // 🔥 CRITICAL
});

const { data: trades } = useQuery({
  queryKey: ["demo", "trades"],
  queryFn: () => api.getDemoTrades(),
  enabled: isSessionRunning, // 🔥 CRITICAL
});
```

---

## 🧩 RULE 4 — ACCOUNT + POSITION MODEL

**Pisahkan ACCOUNT state (balance) dari POSITION state (execution).**

```python
# Backend: backend/services/binance_demo/binance_client.py

account = {
    "wallet_balance": float,      # Total equity
    "available_balance": float,   # Available for new orders
    "total_unrealized_pnl": float,  # Floating PnL
    "margin_balance": float,      # Margin used
    "initial_margin": float,      # Initial margin required
    "maint_margin": float,        # Maintenance margin
}

positions = [
    {
        "symbol": str,
        "side": "LONG" | "SHORT",
        "size": float,
        "entry_price": float,
        "mark_price": float,
        "unrealized_pnl": float,
        "leverage": int,
    }
]
```

**Fetch Atomic:**

```python
async def get_full_state(self):
    account = await self.get_account_state()
    positions = await self.get_open_positions()
    return {"account": account, "positions": positions}
```

---

## ⚙️ RULE 5 — EXECUTION FLOW

**Ketika signal arrives, ikuti flow ini:**

```python
# Backend: backend/services/binance_demo/demo_execution_engine.py

1. Check session.running
   IF false → REJECT immediately

2. Fetch latest account + positions
   full_state = await client.get_full_state()

3. Validate balance:
   IF available_balance <= 0 → REJECT

4. Check position:
   IF exists:
       → manage (hold / close / reverse)
   ELSE:
       → open new position

5. Validate margin:
   IF available_balance < required_margin → REJECT

6. Execute order
```

**Implementation:**

```python
async def execute_signal(self, ...):
    if not self.running:
        return {"success": False, "error": "Session not running"}

    # STEP 1: Fetch full state
    full_state = await self.client.get_full_state()
    account = full_state["account"]
    positions = full_state["positions"]

    # STEP 2: Validate balance
    if account["available_balance"] <= 0:
        return {"success": False, "error": "No available balance"}

    # STEP 3: Check existing position
    if position_exists(symbol, positions):
        return {"success": False, "error": "Position already exists"}

    # STEP 4: Margin validation
    required_margin = quantity * entry_price / leverage
    if account["available_balance"] < required_margin:
        return {"success": False, "error": "Insufficient margin"}

    # STEP 5: Execute
    order = await self.client.place_order(...)
```

---

## 🚨 RULE 6 — MARGIN VALIDATION (WAJIB BENAR)

**SEBELUM order, VALIDATE margin tersedia.**

```python
required_margin = (quantity * mark_price) / leverage

IF available_balance < required_margin:
    → REJECT order
    → Log: "Insufficient margin"
```

**Implementation:**

```python
# Calculate required margin
required_margin = quantity * entry_price  # Assuming 1x leverage

# Validate
if available_balance < required_margin:
    error_msg = (f"REJECTED: available_balance ({available_balance:.2f}) < "
                 f"required_margin ({required_margin:.2f})")
    logger.error(f"[EXECUTE] {error_msg}")
    return {"success": False, "error": error_msg}
```

---

## 🚫 RULE 7 — NO FALLBACK RULE

**JANGAN PERNAH gunakan fallback/hardcoded values.**

```typescript
// ❌ WRONG
const balance = status.current_balance ?? 10000; // NEVER!
let equity = 10000; // NEVER!

// ✅ CORRECT
const balance = status.current_balance ?? 0; // or null
let equity = 0; // Calculate from actual trades
```

**Forbidden:**

- `?? 10000` — Fake balance
- `|| 10000` — Fake balance
- Hardcoded starting balance

**Required:**

- Use `0` or `null` if data unavailable
- Show error message if balance fetch fails
- UI harus jelas: "Failed to fetch balance"

**Implementation:**

```typescript
// Frontend: Stats calculation
const stats =
  hasActiveSession && status
    ? {
        balance: status.current_balance ?? 0, // ✅ OK
        // NOT: status.current_balance ?? 10000  ❌
      }
    : {
        balance: 0, // Idle state
      };

// Frontend: Equity chart
let equity = 0; // ✅ Start from 0
// NOT: let equity = 10000;  ❌
```

---

## 🧪 RULE 8 — DEBUG OUTPUT

**LOG semua decision penting untuk debugging.**

```python
# Backend: Log execution flow
logger.info(f"[EXECUTE] Fetching full state for: {symbol} {bias}")
logger.info(f"[EXECUTE] Account: wallet={wallet:.2f}, available={avail:.2f}")
logger.info(f"[EXECUTE] Found {len(positions)} open positions")

# Validation logs
if available_balance <= 0:
    logger.error(f"[EXECUTE] REJECTED: available_balance={available_balance:.2f}")

if available_balance < required_margin:
    logger.error(f"[EXECUTE] REJECTED: insufficient margin")

logger.info(f"[EXECUTE] Order validation passed: qty={qty}, margin={margin:.2f}")
```

**Required Logs:**

- `session.running` status
- `wallet_balance`, `available_balance`
- `positions count`
- `execution decision` (accept/reject)
- `margin validation` result

---

## 🧠 RULE 9 — FRONTEND RULES

**UI HARUS mengikuti session state.**

```typescript
// ✅ CORRECT
IF session.running == false:
    → show "No Active Session"
    → show Start button
    → hide all trading data

IF session.running == true:
    → show balance (REAL from Binance)
    → show positions (REAL from Binance)
    → show stats (REAL calculations)
```

**Implementation:**

```tsx
// Idle state (session not running)
{
  !hasActiveSession && (
    <div className="no-session">
      <h3>No Active Demo Session</h3>
      <p>Click "▶ Start Demo" to begin trading</p>
      <button>▶ Start Demo</button>
    </div>
  );
}

// Trading dashboard (session running)
{
  hasActiveSession && (
    <>
      <StatCard balance={status.current_balance} />
      <PositionList positions={positions} />
      <EquityChart trades={trades} />
    </>
  );
}
```

---

## 🔄 RULE 10 — CACHE & STATE RESET

**On session STOP, RESET semua state.**

```typescript
// Frontend: Clear ALL demo queries
queryClient.removeQueries({ queryKey: ["demo"] });

// Actions:
- Clear positions cache
- Clear balance cache
- Clear trades cache
- Reset UI to idle state
```

**Implementation:**

```typescript
// Stop mutation
const stopMutation = useMutation({
  mutationFn: () => api.stopDemo(),
  onSuccess: () => {
    setIsRunning(false);
    // RULE 10: Clear ALL demo queries
    queryClient.removeQueries({ queryKey: ["demo"] });
  },
});

// Force stop mutation
const forceStopMutation = useMutation({
  mutationFn: () => api.forceStopDemo(),
  onSuccess: () => {
    setIsRunning(false);
    // RULE 10: Clear ALL demo queries
    queryClient.removeQueries({ queryKey: ["demo"] });
  },
});
```

---

## 🔁 RULE 11 — SESSION RECOVERY

**IF start fails dengan "already running", call `/demo/force-stop`.**

```typescript
// Frontend: Handle error 400
if (error?.response?.status === 400) {
  const shouldForceStop = window.confirm(
    "Session already running. Force stop now?",
  );
  if (shouldForceStop) {
    forceStopMutation.mutate();
  }
}
```

**Backend: Force-stop endpoint**

```python
@router.post("/force-stop")
async def force_stop_demo_session():
    global _demo_engine

    if _demo_engine and _demo_engine.running:
        await _demo_engine.stop_session()  # Graceful first

    _demo_engine = None  # Clear instance
    return {"success": True, "message": "Session cleared"}
```

---

## 🚫 RULE 12 — FORBIDDEN BEHAVIOR

**Sistem TIDAK BOLEH:**

1. ❌ Fetch positions when session inactive
2. ❌ Assume positions = session active
3. ❌ Use position data as balance source
4. ❌ Fallback to fake balance ($10,000)
5. ❌ Execute orders without session check
6. ❌ Show trading data before session starts

**Core Principle:**

```
SESSION → ACCOUNT → POSITION → EXECUTION

NOT:

POSITION → ASSUME EVERYTHING
```

---

## 🎯 IMPLEMENTATION CHECKLIST

### Backend (`backend/api/demo_trading.py`)

- [ ] `/demo/status` returns `running`, `current_balance`, `available_balance`
- [ ] `/demo/execute` checks `session.running` first
- [ ] `/demo/start` validates `initial_balance` (min: 100, max: 1,000,000)
- [ ] `/demo/stop` clears engine instance
- [ ] `/demo/force-stop` endpoint exists
- [ ] Debug logging di semua endpoint

### Backend (`backend/services/binance_demo/`)

- [ ] `get_account_state()` fetches from `/fapi/v2/account`
- [ ] `get_open_positions()` fetches from `/fapi/v2/positionRisk`
- [ ] `get_full_state()` atomic fetch (account + positions)
- [ ] `execute_signal()` validates: balance > 0, margin check
- [ ] Debug logging di `execute_signal()`

### Frontend (`frontend/app/demo-trading/page.tsx`)

- [ ] Fetch status FIRST (gate keeper)
- [ ] `isSessionRunning` computed from `status.success && status.running`
- [ ] All queries have `enabled: isSessionRunning`
- [ ] Stats conditional on `hasActiveSession`
- [ ] Idle state vs Trading dashboard rendering
- [ ] No fallback values (`?? 10000`)

### Frontend (`frontend/app/demo-trading/components/`)

- [ ] `ControlPanel.tsx` has Start/Stop/Force Stop buttons
- [ ] `EquityChart.tsx` no hardcoded $10,000
- [ ] `StatCard.tsx` shows zeros when idle
- [ ] `PositionList.tsx` empty when session not running

---

## 🧪 TEST SCENARIOS

### Scenario 1: Page Load (Session Not Running)

```
1. Open http://localhost:3000/demo-trading
2. Expected:
   ✅ "No Active Demo Session" message
   ✅ No balance shown ($0.00)
   ✅ No positions shown
   ✅ Only "▶ Start Demo" button visible
   ✅ NO API calls to /demo/positions in Network tab
```

### Scenario 2: After Start Session

```
1. Click "▶ Start Demo"
2. Expected:
   ✅ Dashboard appears
   ✅ Balance: REAL from Binance Testnet (not $10,000)
   ✅ Positions: REAL from Binance Testnet
   ✅ Stats: REAL calculations
   ✅ API calls to /demo/positions happening
```

### Scenario 3: After Stop Session

```
1. Click "⏹ Stop Demo"
2. Expected:
   ✅ Dashboard disappears
   ✅ "No Active Session" message appears
   ✅ All data cleared (zeros)
   ✅ Cache cleared (no stale data)
```

### Scenario 4: Force Stop (Stuck Session)

```
1. Start session, then simulate crash
2. Try to start again → Error 400 "already running"
3. Click "⚠️ Force Stop"
4. Expected:
   ✅ Session cleared
   ✅ Can start new session
   ✅ Cache cleared
```

### Scenario 5: Balance Validation

```
1. Start session with $10,000
2. Execute signal → Should succeed
3. Simulate balance = 0
4. Execute signal → Should reject with "No available balance"
```

### Scenario 6: Margin Validation

```
1. Start session with $1,000
2. Try to execute large order (required margin > $1,000)
3. Expected: Reject with "Insufficient margin"
```

---

## 📝 KEY PRINCIPLES

### 1. Session is King

```
Session running = Gate keeper for EVERYTHING
No session = No data, no execution, no UI
```

### 2. Dual-Source Architecture

```
Account State (Balance) = Validation + Risk Control
Position State (Execution) = Trading State
BOTH must be fetched atomically
```

### 3. No Assumptions

```
Don't assume positions = session active
Don't assume balance = $10,000
Don't assume anything without checking session.running
```

### 4. Clear State

```
On stop: Clear ALL caches
On start: Fresh fetch from Binance
On error: Show error, don't fallback
```

### 5. Debug First

```
Log EVERY decision
Log EVERY validation
Log EVERY rejection
```

---

## 🔥 SATU KALIMAT BIAR NANCEP

**"Kalau session belum jalan, sistem harus BUTA TOTAL terhadap Binance — tidak fetch, tidak render, tidak asumsi."**

---

## 📚 RELATED DOCUMENTATION

- `DEMO_TRADING_ARCHITECTURE.md` — Full architecture overview
- `backend/services/binance_demo/README.md` — Binance client implementation
- `frontend/app/demo-trading/README.md` — Frontend implementation

---

**Version:** 1.0  
**Last Updated:** 2026-05-04  
**Status:** ✅ IMPLEMENTED
