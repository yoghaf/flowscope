# 🎯 GRAND INSTRUKSI FINAL — DEMO FUTURES (FULL FIX)

**Status:** ✅ **FULLY IMPLEMENTED**  
**Date:** 2026-05-04

---

## 🔑 PRINCIPLE UTAMA

```
Backend = satu-satunya sumber kebenaran (session)
Frontend = hanya refleksi (tidak boleh punya state sendiri)
```

**Satu Kalimat:**  
**"Frontend TIDAK BOLEH punya state sendiri. SEMUA HARUS IKUT BACKEND."**

---

## 📋 IMPLEMENTATION SUMMARY

### ✅ BAGIAN 1 — BACKEND (SESSION PERSIST)

**Global Engine (WAJIB):**

```python
# backend/api/demo_trading.py
_demo_engine: DemoExecutionEngine | None = None
```

**Start Endpoint:**

```python
@router.post("/start")
async def start_demo_session():
    global _demo_engine

    if _demo_engine and _demo_engine.running:
        raise HTTPException(400, "Demo session already running")

    # Create NEW engine
    client = BinanceTestnetClient(...)
    _demo_engine = DemoExecutionEngine(client=client, ...)

    await _demo_engine.start_session()
    return {"success": True}
```

**Status Endpoint (SUMBER KEBENARAN):**

```python
@router.get("/status")
async def get_demo_status():
    global _demo_engine

    if not _demo_engine:
        return {"running": False, "data": None}

    status = await _demo_engine.get_status()

    return {
        "success": True,
        "running": _demo_engine.running,
        "data": status,  # current_balance, available_balance, positions
    }
```

**Stop Endpoint:**

```python
@router.post("/stop")
async def stop_demo_session():
    global _demo_engine

    if _demo_engine:
        await _demo_engine.stop_session()
        _demo_engine = None  # Clear instance

    return {"success": True}
```

**Larangan Backend:**

```python
# ❌ JANGAN BUAT ENGINE BARU TIAP REQUEST
# engine = DemoExecutionEngine()  # WRONG!

# ✅ BENAR
global _demo_engine
if _demo_engine is None:
    _demo_engine = DemoExecutionEngine()
```

---

### ✅ BAGIAN 2 — FRONTEND (HAPUS STATE LOKAL)

**REMOVED:**

```typescript
// ❌ SALAH - HAPUS INI
const [isRunning, setIsRunning] = useState(false);
```

**SINGLE SOURCE OF TRUTH:**

```typescript
// ✅ BENAR - Dari backend
const { data: statusResponse } = useQuery({
  queryKey: ["demo", "status"],
  queryFn: () => api.getDemoStatus(),
  refetchInterval: 5000,
  refetchOnMount: true,
});

const isSessionRunning =
  statusResponse?.success === true && statusResponse?.running === true;
```

**Frontend TIDAK BOLEH:**

```typescript
// ❌ NEVER DO THIS
setIsRunning(true);
setIsRunning(false);
```

---

### ✅ BAGIAN 3 — CONDITIONAL FETCH

```typescript
// ONLY fetch if session running (from backend)
const { data: positions } = useQuery({
  queryKey: ["demo", "positions"],
  queryFn: () => api.getDemoPositions(),
  refetchInterval: 3000,
  enabled: isSessionRunning, // 🔥 CRITICAL: From backend status
});

const { data: trades } = useQuery({
  queryKey: ["demo", "trades"],
  queryFn: () => api.getDemoTrades(),
  refetchInterval: 10000,
  enabled: isSessionRunning, // 🔥 CRITICAL
});

const { data: signals } = useQuery({
  queryKey: ["demo", "signals"],
  queryFn: () => api.getDemoSignals(),
  refetchInterval: 2000,
  enabled: isSessionRunning, // 🔥 CRITICAL
});
```

---

### ✅ BAGIAN 4 — UI RENDER

```typescript
// Idle state (session not running)
{!isSessionRunning && !statusLoading && (
  <div className="no-session">
    <h3>No Active Demo Session</h3>
    <p>Click "▶ Start Demo" to begin trading</p>
  </div>
)}

// Trading dashboard (session running)
{isSessionRunning && status && (
  <>
    <StatCard balance={status.current_balance ?? 0} />
    <PositionList positions={positions} />
    <EquityChart trades={trades} />
  </>
)}
```

---

### ✅ BAGIAN 5 — BUTTON LOGIC

```typescript
// ControlPanel receives isRunning from backend
<ControlPanel
  isRunning={isSessionRunning}  // ✅ From backend
  status={status}
  isLoading={statusLoading}
  onStart={() => startMutation.mutate()}
  onStop={() => stopMutation.mutate()}
  onForceStop={() => forceStopMutation.mutate()}
  isStarting={startMutation.isPending}
  isStopping={stopMutation.isPending}
  isForceStopping={forceStopMutation.isPending}
/>
```

**Inside ControlPanel:**

```typescript
<button
  onClick={onStart}
  disabled={isRunning || isStarting}  // ✅ From backend
>
  {isStarting ? "Starting..." : "▶ Start Demo"}
</button>

<button
  onClick={onStop}
  disabled={!isRunning || isStopping}  // ✅ From backend
>
  {isStopping ? "Stopping..." : "⏹ Stop Demo"}
</button>
```

---

### ✅ BAGIAN 6 — START / STOP FLOW

**Start Flow:**

```typescript
const startMutation = useMutation({
  mutationFn: () => api.startDemo(),
  onSuccess: () => {
    // Invalidate status - frontend will reflect backend state
    queryClient.invalidateQueries({ queryKey: ["demo", "status"] });
    // DO NOT call setIsRunning(true)
  },
});
```

**Stop Flow:**

```typescript
const stopMutation = useMutation({
  mutationFn: () => api.stopDemo(),
  onSuccess: () => {
    // Clear data queries
    queryClient.removeQueries({ queryKey: ["demo", "positions"] });
    queryClient.removeQueries({ queryKey: ["demo", "trades"] });
    queryClient.removeQueries({ queryKey: ["demo", "signals"] });
    // Invalidate status
    queryClient.invalidateQueries({ queryKey: ["demo", "status"] });
    // DO NOT call setIsRunning(false)
  },
});
```

**Force Stop Flow:**

```typescript
const forceStopMutation = useMutation({
  mutationFn: () => api.forceStopDemo(),
  onSuccess: () => {
    // Clear data queries
    queryClient.removeQueries({ queryKey: ["demo", "positions"] });
    queryClient.removeQueries({ queryKey: ["demo", "trades"] });
    queryClient.removeQueries({ queryKey: ["demo", "signals"] });
    // Invalidate status
    queryClient.invalidateQueries({ queryKey: ["demo", "status"] });
    // DO NOT call setIsRunning(false)
  },
});
```

---

### ✅ BAGIAN 7 — NO FALLBACK

```typescript
// ❌ SALAH
balance ?? 10000;

// ✅ BENAR
balance ?? 0;

// Implementation
const stats =
  isSessionRunning && status
    ? {
        balance: status.current_balance ?? 0, // ✅ OK
      }
    : {
        balance: 0, // Idle state
      };
```

---

### ✅ BAGIAN 8 — FLOW AKHIR

```
USER CLICK START
  ↓
Backend: _demo_engine.running = true
  ↓
Frontend: queryClient.invalidateQueries(["demo", "status"])
  ↓
Frontend: refetch /demo/status
  ↓
Frontend: isSessionRunning = true (from backend)
  ↓
Frontend: fetch positions + balance (enabled: isSessionRunning)
  ↓
UI: tampil data real dari Binance
```

**Stop Flow:**

```
USER CLICK STOP
  ↓
Backend: _demo_engine.stop() → _demo_engine = None
  ↓
Frontend: queryClient.removeQueries(["demo"])
  ↓
Frontend: refetch /demo/status
  ↓
Frontend: isSessionRunning = false (from backend)
  ↓
Frontend: skip fetch positions + balance
  ↓
UI: balik idle state (zeros)
```

---

## ✅ FINAL CHECKLIST

### Backend

- [x] `_demo_engine` global variable
- [x] `/demo/start` creates engine if None
- [x] `/demo/start` checks if already running
- [x] `/demo/status` returns `running`, `current_balance`, `available_balance`
- [x] `/demo/stop` stops engine and sets to None
- [x] `/demo/force-stop` endpoint exists
- [x] No new engine per request

### Frontend

- [x] **REMOVED** `const [isRunning, setIsRunning] = useState(false)`
- [x] `isSessionRunning` computed from backend status
- [x] All queries have `enabled: isSessionRunning`
- [x] Start mutation: invalidate status only
- [x] Stop mutation: remove queries + invalidate status
- [x] No `setIsRunning(true)` or `setIsRunning(false)`
- [x] UI follows backend state
- [x] No hardcoded $10,000 fallback

---

## 🧪 TEST SCENARIOS

### Scenario 1: Sebelum Start

```
GIVEN: Session not running
WHEN: User opens /demo-trading
THEN:
  ✅ UI shows "No Active Session"
  ✅ Only "▶ Start Demo" button visible
  ✅ NO API calls to /demo/positions
  ✅ Balance = $0.00 (not $10,000)
```

### Scenario 2: Setelah Start

```
GIVEN: User clicks "▶ Start Demo"
WHEN: Backend returns success
THEN:
  ✅ Frontend refetches /demo/status
  ✅ isSessionRunning = true (from backend)
  ✅ Balance muncul (REAL dari Binance)
  ✅ Posisi muncul (REAL dari Binance)
  ✅ Dashboard tampil
```

### Scenario 3: Refresh Page

```
GIVEN: Session running
WHEN: User refreshes page
THEN:
  ✅ Backend _demo_engine.running still true
  ✅ Frontend fetches /demo/status
  ✅ isSessionRunning = true (from backend)
  ✅ Balance + positions reappear
  ✅ Session TIDAK reset (persist)
```

### Scenario 4: Stop Session

```
GIVEN: Session running
WHEN: User clicks "⏹ Stop Demo"
THEN:
  ✅ Backend stops engine, sets to None
  ✅ Frontend clears queries
  ✅ Frontend refetches /demo/status
  ✅ isSessionRunning = false (from backend)
  ✅ UI balik idle state (zeros)
```

### Scenario 5: Force Stop

```
GIVEN: Session stuck (error 400)
WHEN: User clicks "⚠️ Force Stop"
THEN:
  ✅ Backend clears engine
  ✅ Frontend clears queries
  ✅ Frontend refetches /demo/status
  ✅ Can start new session
```

---

## 🎨 STATE DIAGRAM

```
┌─────────────────────────────────────────────────┐
│            BACKEND (Single Source)               │
├─────────────────────────────────────────────────┤
│                                                 │
│  _demo_engine = None                            │
│     ↓                                           │
│  /demo/start → _demo_engine.running = true      │
│     ↓                                           │
│  /demo/status → { running: true, ... }          │
│     ↓                                           │
│  /demo/stop → _demo_engine = None               │
│                                                 │
└─────────────────────────────────────────────────┘
                      ↓
                      ↓ (HTTP)
                      ↓
┌─────────────────────────────────────────────────┐
│            FRONTEND (Reflection Only)            │
├─────────────────────────────────────────────────┤
│                                                 │
│  NO useState for isRunning                      │
│     ↓                                           │
│  const isSessionRunning =                       │
│    status?.success && status?.running           │
│     ↓                                           │
│  enabled: isSessionRunning                      │
│     ↓                                           │
│  UI = isSessionRunning ? Dashboard : Idle       │
│                                                 │
└─────────────────────────────────────────────────┘
```

---

## 🔥 KEY PRINCIPLES

### 1. Backend = Truth

```
Backend state (session) = SUMBER KEBENARAN
Frontend state = REFLEKSI saja
```

### 2. No Local State

```
Frontend TIDAK BOLEH:
- useState untuk isRunning
- setIsRunning(true/false)
- Asumsi state tanpa fetch dari backend
```

### 3. Query-Driven UI

```
UI = f(status from backend)

Bukan:
UI = f(local state + backend)
```

### 4. Invalidate, Don't Set

```
On action success:
- queryClient.invalidateQueries()
- queryClient.removeQueries()

BUKAN:
- setIsRunning(true)
- setIsRunning(false)
```

### 5. Session Persist

```
Backend _demo_engine persists across:
- Page refresh
- Navigation
- Component unmount

KECUALI:
- Server restart (uvicorn --reload)
- Manual stop/force-stop
```

---

## 📝 FILES MODIFIED

### Backend (No Changes Needed)

- ✅ `backend/api/demo_trading.py` - Already correct

### Frontend

- ✅ `frontend/app/demo-trading/page.tsx`
  - REMOVED: `const [isRunning, setIsRunning] = useState(false)`
  - UPDATED: startMutation.onSuccess (invalidate only)
  - UPDATED: stopMutation.onSuccess (remove + invalidate)
  - UPDATED: forceStopMutation.onSuccess (remove + invalidate)
  - UPDATED: ControlPanel props (isSessionRunning from backend)

### Components (No Changes Needed)

- ✅ `frontend/app/demo-trading/components/ControlPanel.tsx` - Already correct (receives props)

---

## 🚀 DEPLOYMENT NOTE

**Development Mode (`uvicorn --reload`):**

```
Every file save → server restart → _demo_engine reset → session lost
```

**Production Mode:**

```
Server runs continuously → _demo_engine persists → session stable
```

**Solution for Dev:**

```bash
# Run without --reload for stable session
uvicorn backend.main:app --port 8000
```

---

## 🎯 SATU KALIMAT BIAR NANCEP

**"Frontend itu cuma CERMIN. Backend yang PEGANG KENDALI."**

---

## 📚 RELATED DOCUMENTATION

- `CORE_RULE_SESSION_GATE.md` — Core rule implementation
- `12_RULES_DEMO_TRADING.md` — Complete 12 rules
- `DEMO_TRADING_ARCHITECTURE.md` — Architecture overview

---

**GRAND INSTRUKSI STATUS:** ✅ **FULLY IMPLEMENTED**  
**FRONTEND STATE:** ✅ **REMOVED (useState deleted)**  
**BACKEND PERSIST:** ✅ **CORRECT (global \_demo_engine)**  
**READY FOR TESTING:** 🚀
