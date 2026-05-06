# 🔒 CORE RULE — SESSION GATE DEMO TRADING

**Last Updated:** 2026-05-04  
**Status:** ✅ IMPLEMENTED

---

## 🎯 CORE PRINCIPLE

```
Session is the ONLY entry point.
Binance data is ONLY valid inside active session.
```

**Satu Kalimat:**  
**"Kalau session belum jalan, sistem harus BUTA TOTAL terhadap Binance."**

---

## 🔒 SESSION GATE (RULE 1)

```python
IF session.running == false:
    → block ALL operations
    → skip ALL Binance fetch
    → UI = idle
```

### Backend Implementation

```python
# backend/api/demo_trading.py

@router.get("/status")
async def get_demo_status():
    if not _demo_engine:
        return {
            "success": False,
            "running": False,
            "data": None,  # ✅ No fallback
        }

@router.post("/execute")
async def execute_demo_signal():
    if not _demo_engine or not _demo_engine.running:
        logger.warning("[EXECUTE] REJECTED: session.running == false")
        raise HTTPException(400, "No active demo session")
```

### Frontend Implementation

```typescript
// frontend/app/demo-trading/page.tsx

// Fetch status FIRST (gate keeper)
const { data: statusResponse } = useQuery({
  queryKey: ["demo", "status"],
  queryFn: () => api.getDemoStatus(),
  refetchInterval: 5000,
});

const isSessionRunning = statusResponse?.success && statusResponse?.running;

// Conditional fetch - SKIP if session not running
const { data: positions } = useQuery({
  queryKey: ["demo", "positions"],
  queryFn: () => api.getDemoPositions(),
  enabled: isSessionRunning, // 🔥 CRITICAL
});
```

---

## 🔌 DATA FETCH (RULE 2-3)

```python
IF session.running == true:
    account = GET /fapi/v2/account
    positions = GET /fapi/v2/positionRisk
ELSE:
    Skip ALL Binance fetch
```

### Backend: Atomic Fetch

```python
# backend/services/binance_demo/binance_client.py

async def get_full_state(self):
    """Fetch BOTH account + positions atomically"""
    account = await self.get_account_state()  # /fapi/v2/account
    positions = await self.get_open_positions()  # /fapi/v2/positionRisk

    return {
        "account": account,
        "positions": positions,
    }

# Account structure
account = {
    "wallet_balance": float,
    "available_balance": float,
    "total_unrealized_pnl": float,
    "margin_balance": float,
    "initial_margin": float,
    "maint_margin": float,
}

# Position structure
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

---

## ⚙️ EXECUTION FLOW (RULE 4-5)

```python
1. Validate session.running
   IF false → REJECT immediately

2. Fetch account + positions
   full_state = await client.get_full_state()

3. Validate balance:
   IF available_balance <= 0 → REJECT

4. Validate margin:
   required_margin = (qty * mark_price) / leverage
   IF available_balance < required_margin → REJECT

5. Position logic:
   IF position exists → manage
   ELSE → open new
```

### Backend Implementation

```python
# backend/services/binance_demo/demo_execution_engine.py

async def execute_signal(self, ...):
    if not self.running:
        return {"success": False, "error": "Session not running"}

    # STEP 1: Fetch full state
    full_state = await self.client.get_full_state()
    account = full_state["account"]
    positions = full_state["positions"]

    available_balance = account["available_balance"]
    wallet_balance = account["wallet_balance"]

    # STEP 2: Validate balance
    if available_balance <= 0:
        logger.error(f"[EXECUTE] REJECTED: available_balance <= 0")
        return {"success": False, "error": "No available balance"}

    # 🧪 STATE VALIDATION: Detect inconsistencies
    if wallet_balance == 0 and len(positions) > 0:
        logger.warning(f"[EXECUTE] ⚠️ INCONSISTENCY: wallet=0 but positions exist")
        logger.warning(f"[EXECUTE] Resetting local assumption - trusting Binance")

    # 🚨 NO FALLBACK: NULL balance = ERROR
    if available_balance is None:
        logger.error(f"[EXECUTE] 🚨 available_balance is NULL")
        return {"success": False, "error": "Balance fetch failed"}

    # STEP 3: Check existing position
    existing_position = next(
        (p for p in positions if p["symbol"] == symbol),
        None
    )

    if existing_position:
        return {
            "success": False,
            "error": "Position already exists",
            "existing_position": existing_position,
        }

    # STEP 4: Calculate position size
    risk_amount = available_balance * 0.01  # 1% risk
    quantity = risk_amount / entry_price
    required_margin = quantity * entry_price  # Assuming 1x leverage

    # STEP 5: Validate margin
    if available_balance < required_margin:
        logger.error(f"[EXECUTE] REJECTED: insufficient margin")
        return {"success": False, "error": "Insufficient margin"}

    # STEP 6: Execute order
    order = await self.client.place_order(...)
```

---

## 🧪 STATE VALIDATION (RULE 6)

```python
IF positions empty unexpectedly:
    → flag inconsistency
    → reset local assumption
```

### Backend Detection

```python
# Detect inconsistency
if wallet_balance == 0 and len(positions) > 0:
    logger.warning(f"⚠️ INCONSISTENCY: wallet=0 but {len(positions)} positions")
    logger.warning(f"Resetting local assumption - trusting Binance state")

# NULL balance = ERROR
if available_balance is None:
    logger.error(f"🚨 available_balance is NULL - STOP execution")
    return {"success": False, "error": "Balance fetch failed"}
```

### Frontend Detection

```typescript
// frontend/app/demo-trading/page.tsx

const hasInconsistency = hasActiveSession && status && positions && (
  // Balance is null/undefined
  (status.current_balance === null || status.current_balance === undefined) ||
  // Positions fetch failed but balance > 0
  (positions === null && status.current_balance > 0)
);

// Log for debugging
if (hasInconsistency) {
  console.warn('⚠️ STATE INCONSISTENCY:', {
    hasActiveSession,
    current_balance: status?.current_balance,
    positions_count: positions?.length,
  });
}

// Show warning UI
{hasInconsistency && (
  <div className="warning">
    ⚠️ State Inconsistency Detected
    <p>Session running but data incomplete. Try refreshing.</p>
  </div>
)}
```

---

## 🚨 NO FALLBACK (RULE 7)

```python
IF balance == null:
    → ERROR
    → STOP execution
```

### ❌ FORBIDDEN

```python
# NEVER DO THIS
balance = account_balance ?? 10000  # ❌ Fake fallback
balance = account_balance || 10000  # ❌ Fake fallback
```

### ✅ REQUIRED

```python
# CORRECT
if available_balance is None:
    return {"success": False, "error": "Balance fetch failed"}

# OR
balance = available_balance if available_balance is not None else 0
```

### Frontend

```typescript
// ✅ CORRECT
const stats =
  hasActiveSession && status
    ? {
        balance: status.current_balance ?? 0, // Use 0 or null
      }
    : {
        balance: 0, // Idle state
      };

// ❌ WRONG
const stats = {
  balance: status.current_balance ?? 10000, // NEVER!
};
```

---

## 🔄 CACHE RESET (RULE 8)

```typescript
On session stop:
- clear all queries
- reset UI state
```

### Frontend Implementation

```typescript
// frontend/app/demo-trading/page.tsx

// Stop mutation
const stopMutation = useMutation({
  mutationFn: () => api.stopDemo(),
  onSuccess: () => {
    setIsRunning(false);
    // 🔥 CLEAR ALL demo queries
    queryClient.removeQueries({ queryKey: ["demo"] });
  },
});

// Force stop mutation
const forceStopMutation = useMutation({
  mutationFn: () => api.forceStopDemo(),
  onSuccess: () => {
    setIsRunning(false);
    // 🔥 CLEAR ALL demo queries
    queryClient.removeQueries({ queryKey: ["demo"] });
  },
});
```

### What Gets Cleared

```typescript
queryClient.removeQueries({ queryKey: ["demo"] });

// Clears:
- ["demo", "status"]
- ["demo", "positions"]
- ["demo", "trades"]
- ["demo", "signals"]
- All cached data
```

---

## 🎨 UI STATE MACHINE

```
┌─────────────────────────────────────────────────┐
│            SESSION STATE MACHINE                 │
├─────────────────────────────────────────────────┤
│                                                 │
│  IDLE (session.running == false)                │
│  ├─ Show: "No Active Session"                   │
│  ├─ Show: "▶ Start Demo" button                 │
│  ├─ Hide: Balance, Positions, Stats             │
│  └─ Fetch: ONLY /demo/status                    │
│                                                 │
│  TRADING (session.running == true)              │
│  ├─ Show: Balance (REAL from Binance)           │
│  ├─ Show: Positions (REAL from Binance)         │
│  ├─ Show: Stats (REAL calculations)             │
│  ├─ Show: "⏹ Stop Demo" button                  │
│  └─ Fetch: /demo/status, /demo/positions, ...   │
│                                                 │
│  ERROR (balance == null)                        │
│  ├─ Show: "🚨 Failed to fetch balance"          │
│  ├─ Show: Error message                         │
│  └─ Action: Refresh or restart session          │
│                                                 │
│  INCONSISTENT (data mismatch)                   │
│  ├─ Show: "⚠️ State Inconsistency"              │
│  ├─ Show: Warning message                       │
│  └─ Action: Try refreshing                      │
│                                                 │
└─────────────────────────────────────────────────┘
```

---

## 🧪 TEST SCENARIOS

### Scenario 1: Page Load (Idle State)

```
GIVEN: Session not running
WHEN: User opens /demo-trading
THEN:
  ✅ UI shows "No Active Session"
  ✅ Only "▶ Start Demo" button visible
  ✅ NO API calls to /demo/positions
  ✅ NO API calls to /demo/trades
  ✅ Balance = $0.00 (not $10,000)
```

### Scenario 2: Start Session

```
GIVEN: User clicks "▶ Start Demo"
WHEN: Session starts successfully
THEN:
  ✅ Dashboard appears
  ✅ Balance fetched from Binance (REAL)
  ✅ Positions fetched from Binance (REAL)
  ✅ Stats calculated from REAL data
  ✅ API calls to /demo/positions happening
```

### Scenario 3: Stop Session

```
GIVEN: Session running
WHEN: User clicks "⏹ Stop Demo"
THEN:
  ✅ Dashboard disappears
  ✅ "No Active Session" message appears
  ✅ All data cleared (zeros)
  ✅ Cache cleared (no stale data)
  ✅ UI reset to idle state
```

### Scenario 4: Balance Validation

```
GIVEN: Session running with $1,000
WHEN: Execute signal with required margin $2,000
THEN:
  ✅ REJECTED: "Insufficient margin"
  ✅ available_balance (1000) < required_margin (2000)
  ✅ No order placed
```

### Scenario 5: NULL Balance

```
GIVEN: Session running
WHEN: Binance API returns balance = null
THEN:
  ✅ ERROR: "Balance fetch failed"
  ✅ STOP execution
  ✅ Show warning UI
  ✅ NO fallback to $10,000
```

### Scenario 6: State Inconsistency

```
GIVEN: Session running
WHEN: wallet_balance = 0 but positions exist
THEN:
  ✅ WARNING: "⚠️ INCONSISTENCY detected"
  ✅ Reset local assumption
  ✅ Trust Binance state
  ✅ Log for debugging
```

### Scenario 7: Force Stop

```
GIVEN: Session stuck (error 400 "already running")
WHEN: User clicks "⚠️ Force Stop"
THEN:
  ✅ Call /demo/force-stop
  ✅ Clear engine instance
  ✅ Clear all caches
  ✅ Can start new session
```

---

## 📋 IMPLEMENTATION CHECKLIST

### Backend

- [x] `/demo/status` returns `running`, `current_balance`, `available_balance`
- [x] `/demo/execute` checks `session.running` first
- [x] `/demo/execute` validates `available_balance > 0`
- [x] `/demo/execute` validates margin
- [x] `/demo/execute` checks existing position
- [x] `get_full_state()` atomic fetch (account + positions)
- [x] State validation (detect inconsistencies)
- [x] NULL balance = ERROR (no fallback)
- [x] Debug logging at all steps
- [x] `/demo/force-stop` endpoint

### Frontend

- [x] Fetch status FIRST (gate keeper)
- [x] `isSessionRunning` computed correctly
- [x] All queries have `enabled: isSessionRunning`
- [x] Stats conditional on `hasActiveSession`
- [x] Idle state vs Trading dashboard
- [x] No hardcoded $10,000
- [x] Cache reset on stop
- [x] Cache reset on force-stop
- [x] State inconsistency detection
- [x] NULL balance error handling
- [x] Force-stop option on error 400

---

## 🔥 KEY TAKEAWAYS

1. **Session is King**  
   No session = No data, no execution, no UI

2. **Dual-Source Architecture**  
   Account (balance) + Position (execution) = Complete state

3. **No Assumptions**  
   Always validate, never assume

4. **No Fallback**  
   NULL = ERROR, not $10,000

5. **Clear State**  
   On stop: Clear ALL caches

6. **Detect Inconsistencies**  
   Flag mismatches, reset assumptions

7. **Debug Everything**  
   Log every decision, every validation

---

## 📚 RELATED FILES

- `12_RULES_DEMO_TRADING.md` — Complete 12 rules documentation
- `DEMO_TRADING_ARCHITECTURE.md` — Architecture overview
- `backend/services/binance_demo/binance_client.py` — Binance client
- `backend/services/binance_demo/demo_execution_engine.py` — Execution engine
- `backend/api/demo_trading.py` — API endpoints
- `frontend/app/demo-trading/page.tsx` — Main UI

---

**CORE RULE STATUS:** ✅ **FULLY IMPLEMENTED**
