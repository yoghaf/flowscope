# Demo Trading System Architecture

## 📊 Dual Data Source Design

This system uses **TWO SEPARATE** Binance API endpoints for complete state management:

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA SOURCES                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  1. /fapi/v2/account (POSITION RISK)                        │
│     → Balance validation                                     │
│     → Risk control                                           │
│     → Margin monitoring                                      │
│                                                              │
│  2. /fapi/v2/positionRisk (POSITIONS)                       │
│     → Execution state                                        │
│     → Position management                                    │
│     → PnL calculation                                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## 🔄 Execution Flow

### STEP 1: Fetch Full State

```python
# Atomic fetch of BOTH account + positions
full_state = await client.get_full_state()

account = full_state["account"]      # From /fapi/v2/account
positions = full_state["positions"]  # From /fapi/v2/positionRisk
```

### STEP 2: Balance Validation

```python
available_balance = account["available_balance"]

IF available_balance <= 0:
    → REJECT trade
    → Log error: "available_balance <= 0"
```

### STEP 3: Position Check

```python
existing_position = None
for pos in positions:
    if pos["symbol"] == symbol:
        existing_position = pos
        break

IF existing_position exists:
    → Manage (hold / close / reverse)
    → Reject new signal on same symbol

ELSE:
    → Open new position
```

### STEP 4: Margin Validation

```python
required_margin = quantity * entry_price

IF available_balance < required_margin:
    → REJECT order
    → Log: "available_balance < required_margin"
```

### STEP 5: Execute Order

```python
IF all validations pass:
    → Place order on Binance Testnet
    → Log trade to database
    → Return success
```

## 🧩 Account State Model

```typescript
interface AccountState {
  wallet_balance: number; // Total wallet balance
  available_balance: number; // Available for trading
  total_unrealized_pnl: number; // Unrealized PnL from positions
  margin_balance: number; // Total margin balance
  initial_margin: number; // Initial margin for open positions
  maint_margin: number; // Maintenance margin required
  withdrawable_balance: number; // Withdrawable balance
}
```

## 🧩 Position Model

```typescript
interface Position {
  symbol: string;
  side: "LONG" | "SHORT";
  size: number;
  entry_price: number;
  mark_price: number;
  unrealized_pnl: number;
  leverage: number;
  position_amt: number; // Raw position amount (negative for short)
  notional: number; // Position notional value
  timestamp: Date;
}
```

## 🚨 Validation Rules

### Rule 1: Available Balance Check

```python
if available_balance <= 0:
    return {"success": False, "error": "available_balance <= 0"}
```

### Rule 2: Position Existence Check

```python
if position_exists(symbol):
    return {"success": False, "error": "Position already exists"}
```

### Rule 3: Margin Requirement Check

```python
if available_balance < required_margin:
    return {"success": False, "error": "Insufficient margin"}
```

## 🔌 API Endpoints

### /fapi/v2/account

**Purpose:** Balance validation + risk control

**Response Fields:**

- `totalWalletBalance` → `account.wallet_balance`
- `availableBalance` → `account.available_balance`
- `totalUnrealizedPnl` → `account.total_unrealized_pnl`
- `totalMarginBalance` → `account.margin_balance`
- `initialMargin` → `account.initial_margin`
- `maintMargin` → `account.maint_margin`
- `withdrawableBalance` → `account.withdrawable_balance`

### /fapi/v2/positionRisk

**Purpose:** Execution state + position management

**Response Fields:**

- `symbol` → `position.symbol`
- `positionAmt` → `position.position_amt`
- `entryPrice` → `position.entry_price`
- `markPrice` → `position.mark_price`
- `unRealizedProfit` → `position.unrealized_pnl`
- `leverage` → `position.leverage`
- `notional` → `position.notional`

## 🧪 Debug Output

### Account State Logging

```python
logger.info(f"[ACCOUNT STATE] wallet_balance={wallet:.2f}, "
           f"available_balance={available:.2f}, "
           f"unrealized_pnl={unrealized:.2f}")
```

### Position Logging

```python
logger.info(f"[POSITIONS] Found {len(positions)} open positions")
logger.debug(f"[POSITION] {symbol}: {side} {size} @ {entry}, PnL={pnl:.2f}")
```

### Execution Logging

```python
logger.info(f"[EXECUTE] Account: wallet={wallet:.2f}, "
           f"available={available:.2f}, unrealized_pnl={unrealized:.2f}")
logger.info(f"[EXECUTE] Found {len(positions)} open positions")
logger.info(f"[EXECUTE] Order validation passed: "
           f"quantity={qty:.4f}, required_margin={margin:.2f}")
```

## ⚠️ Error Handling

### Balance = Null

```python
# In get_status(), return explicit null (no silent fallback)
if error:
    return {
        "current_balance": None,  # Explicit null
        "available_balance": None,
        "error": str(e),
    }
```

### Frontend Handling

```typescript
// NO FALLBACK to 10000
const stats = {
  balance: status?.current_balance ?? 0,  // Explicit 0, not 10000
  balanceChange: status?.current_balance && status?.initial_balance
    ? status.current_balance - status.initial_balance
    : 0,
};

// Show warning if session not started
{!hasActiveSession && (
  <div className="warning">
    ⚠️ Demo session not started
  </div>
)}

// Show error if balance fetch failed
{hasActiveSession && status?.current_balance === null && (
  <div className="error">
    🚨 Failed to fetch balance from Binance Testnet
  </div>
)}
```

## 🎯 Key Principles

1. **Position ≠ Balance**
   - Position data is PARTIAL state
   - Account endpoint is FULL state
   - NEVER rely on position endpoint for balance

2. **Dual Source Required**
   - ALWAYS fetch BOTH account + positions
   - Use account for validation
   - Use positions for execution

3. **Strict Validation**
   - IF available_balance <= 0 → REJECT
   - IF position exists → MANAGE
   - IF margin insufficient → REJECT

4. **No Silent Fallback**
   - Balance = null → RAISE ERROR
   - Do NOT fallback to default value
   - Show explicit error to user

5. **Debug Transparency**
   - Print ALL balance fields
   - Print ALL positions
   - Log ALL validation decisions

## 📝 Implementation Files

- `backend/services/binance_demo/binance_client.py`
  - `get_account_state()` - Fetch from /fapi/v2/account
  - `get_open_positions()` - Fetch from /fapi/v2/positionRisk
  - `get_full_state()` - Atomic fetch of both

- `backend/services/binance_demo/demo_execution_engine.py`
  - `execute_signal()` - Uses dual source with validation
  - `get_status()` - Returns complete state

- `frontend/app/demo-trading/page.tsx`
  - No fallback to 10000
  - Session state warning
  - Balance error warning

## ✅ Verification

```bash
# 1. Check account endpoint
curl http://localhost:8000/api/demo/status | jq .data.current_balance

# 2. Check positions endpoint
curl http://localhost:8000/api/demo/positions | jq .

# 3. Verify both are used
curl http://localhost:8000/api/demo/status | jq '.data | {balance: .current_balance, positions: .positions_count}'
```

Expected output:

```json
{
  "balance": 12345.67,
  "positions": 3
}
```

## 🔥 META RULE

> **Position data is PARTIAL state. Account endpoint is FULL state.**
>
> System MUST NOT rely on position endpoints for balance.
>
> ALWAYS use BOTH sources for complete state management.
