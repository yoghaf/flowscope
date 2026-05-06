# 🔧 DEBUG TAB KOSONG - GUIDE LENGKAP

## ❗ MASALAH

Tab Open Orders, Order History, Trade History, dan Assets kosong.

---

## 🔍 STEP 1 — CEK BACKEND LOGS

Backend sekarang sudah dilengkapi logging detail. Cek terminal backend:

### **Expected Logs:**
```
[OPEN-ORDERS] Fetching from Binance API...
[OPEN-ORDERS] Raw count: 0
[OPEN-ORDERS] Returning 0 orders

[ORDER-HISTORY] Fetching limit=50...
[ORDER-HISTORY] BTCUSDT: 5 orders
[ORDER-HISTORY] ETHUSDT: 3 orders
[ORDER-HISTORY] Returning 8 orders

[TRADE-HISTORY] Fetching limit=50...
[TRADE-HISTORY] BTCUSDT: 10 trades
[TRADE-HISTORY] ETHUSDT: 5 trades
[TRADE-HISTORY] Returning 15 trades

[ASSETS] Fetching account status...
[ASSETS] wallet_balance=10000.00, available_balance=9500.00
```

### **Kalau tidak ada logs:**
👉 Endpoint tidak dipanggil → Frontend issue

### **Kalau ada logs tapi kosong:**
👉 Binance memang tidak punya data → NORMAL (kecuali Assets)

---

## 🔍 STEP 2 — CEK BROWSER CONSOLE

Buka DevTools (F12) → Console tab.

### **Expected Logs:**
```
📊 TAB DATA: {
  openOrders: [...],
  orderHistory: [...],
  tradeHistoryData: [...],
  assets: {...}
}

[OpenOrdersTable] orders: [...] isLoading: false
[OrderHistoryTable] orders: [...] isLoading: false
[TradeHistoryTable] trades: [...] isLoading: false
[AssetsPanel] assets: {...} isLoading: false
```

### **Kalau data `undefined`:**
👉 API response format salah

### **Kalau data `[]` (empty array):**
👉 Backend mengirim empty → Cek Step 1

---

## 🔍 STEP 3 — TEST MANUAL CURL

### **1. Open Orders**
```bash
curl http://localhost:8000/demo/open-orders
```

**Expected:**
```json
{
  "success": true,
  "orders": [],
  "count": 0
}
```

**Kalau kosong:**
- ✅ NORMAL kalau pakai market orders
- ✅ Tidak ada limit order pending

---

### **2. Order History**
```bash
curl http://localhost:8000/demo/order-history
```

**Expected:**
```json
{
  "success": true,
  "orders": [
    {
      "orderId": 123456,
      "symbol": "BTCUSDT",
      "side": "BUY",
      "type": "MARKET",
      "status": "FILLED",
      "price": 95000,
      "origQty": 0.01,
      "executedQty": 0.01,
      "time": 1714838400000
    }
  ],
  "count": 5
}
```

**Kalau kosong:**
- ❌ ABNORMAL - Harusnya ada history
- 🔧 FIX: Cek Binance connection

---

### **3. Trade History**
```bash
curl http://localhost:8000/demo/trade-history
```

**Expected:**
```json
{
  "success": true,
  "trades": [
    {
      "id": 789012,
      "symbol": "BTCUSDT",
      "side": "BUY",
      "price": 95000,
      "qty": 0.01,
      "realizedPnl": 0,
      "time": 1714838400000
    }
  ],
  "count": 10
}
```

**Kalau kosong:**
- ❌ ABNORMAL - Harusnya ada trades
- 🔧 FIX: Cek session running

---

### **4. Assets (PALING PENTING!)**
```bash
curl http://localhost:8000/demo/assets
```

**Expected:**
```json
{
  "success": true,
  "assets": {
    "wallet_balance": 10000.00,
    "available_balance": 9500.00,
    "unrealized_pnl": 50.00,
    "margin_balance": 10050.00,
    "initial_margin": 950.00,
    "maint_margin": 475.00,
    "withdrawable_balance": 9050.00
  }
}
```

**Kalau kosong:**
- ❌ CRITICAL - Assets HARUS ada
- 🔧 FIX: Cek `_demo_engine.get_status()`

---

## 🧠 DIAGNOSIS BERDASARKAN LOGS

### **Scenario 1: Backend logs tidak muncul**
```
[TIDAK ADA LOGS DI BACKEND]
```

**Diagnosis:** Frontend tidak memanggil API  
**Fix:**
1. Cek `isSessionRunning` di frontend
2. Pastikan session running (start demo)
3. Cek browser console untuk errors

---

### **Scenario 2: Backend logs muncul, data kosong**
```
[ORDER-HISTORY] Fetching limit=50...
[ORDER-HISTORY] BTCUSDT: 0 orders
[ORDER-HISTORY] Returning 0 orders
```

**Diagnosis:** Binance API tidak return data  
**Fix:**
1. Cek Binance connection
2. Pastikan ada order/trade yang pernah dilakukan
3. Test manual curl

---

### **Scenario 3: Backend logs muncul, data ada**
```
[ORDER-HISTORY] Fetching limit=50...
[ORDER-HISTORY] BTCUSDT: 5 orders
[ORDER-HISTORY] Returning 5 orders
```

**Diagnosis:** Backend OK, frontend issue  
**Fix:**
1. Cek browser console logs
2. Cek response format
3. Cek component mapping

---

### **Scenario 4: Assets kosong**
```
[ASSETS] Fetching account status...
[ASSETS] wallet_balance=0, available_balance=0
```

**Diagnosis:** Session tidak connect ke Binance  
**Fix:**
1. Restart demo session
2. Cek Binance API credentials
3. Cek `_demo_engine.client.connected`

---

## 🔥 QUICK FIXES

### **Fix 1: Force enable queries (DEBUG ONLY)**

Di `frontend/app/demo-trading/page.tsx`:

```typescript
const { data: assets } = useQuery({
  queryKey: ["demo", "assets"],
  queryFn: () => api.getDemoAssets(),
  refetchInterval: 5000,
  enabled: true, // 🔥 FORCE ENABLE (DEBUG)
  // enabled: isSessionRunning, // ← Comment ini dulu
});
```

**Kalau assets muncul:**
👉 Masalah di `isSessionRunning` → Cek status response

---

### **Fix 2: Increase limit**

Di `frontend/app/demo-trading/page.tsx`:

```typescript
const { data: orderHistory } = useQuery({
  queryKey: ["demo", "order-history"],
  queryFn: () => api.getDemoOrderHistory(500), // 🔥 INCREASE LIMIT
  // queryFn: () => api.getDemoOrderHistory(50), // ← Default
  refetchInterval: 10000,
  enabled: isSessionRunning,
});
```

---

### **Fix 3: Add more symbols**

Di `backend/api/demo_trading.py`:

```python
# Tambah symbols yang di-fetch
symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]  # 🔥 ADD MORE
```

---

## 📊 EXPECTED BEHAVIOR

| Tab           | Normal State | Empty = Problem? |
| ------------- | ------------ | ---------------- |
| Positions     | 0-10 items   | ❌ Kalau session running |
| Open Orders   | 0 items      | ✅ NORMAL (market orders) |
| Order History | >0 items     | ❌ HARUS ada |
| Trade History | >0 items     | ❌ HARUS ada |
| Assets        | Object       | ❌ CRITICAL |

---

## 🧪 TEST SCENARIOS

### **Test 1: Fresh Session**
```
1. Stop demo session (jika running)
2. Refresh page
3. Click "▶ Start Demo"
4. Check all tabs

Expected:
- Positions: 0 (OK)
- Open Orders: 0 (OK)
- Order History: 0 (PROBLEM)
- Trade History: 0 (PROBLEM)
- Assets: Should show balance (CRITICAL)
```

---

### **Test 2: After First Trade**
```
1. Execute signal (buy BTCUSDT)
2. Wait 5 seconds
3. Check all tabs

Expected:
- Positions: 1 (OK)
- Open Orders: 0 (OK)
- Order History: 1+ (OK)
- Trade History: 1+ (OK)
- Assets: Updated balance (OK)
```

---

### **Test 3: Navigate Between Tabs**
```
1. Click "Positions" tab
2. Click "Assets" tab
3. Click "Order History" tab
4. Check console logs

Expected:
- Logs show data for each tab
- No errors in console
- Data persists between tab switches
```

---

## 🔥 PRIORITY FIX ORDER

1. **Assets** - CRITICAL (harus selalu ada)
2. **Order History** - HIGH (harus ada setelah trade)
3. **Trade History** - HIGH (harus ada setelah trade)
4. **Open Orders** - LOW (normal kosong)

---

## 🚀 NEXT STEPS

1. **Start backend:** `uvicorn backend.main:app --reload --port 8000`
2. **Start frontend:** `cd frontend && npm run dev`
3. **Open browser:** `http://localhost:3000/demo-trading`
4. **Start demo session**
5. **Check console logs (F12)**
6. **Check backend logs (terminal)**
7. **Report findings**

---

## 📝 KIRIM INFO INI JIKA MASIH MASALAH

```
1. Backend logs (copy dari terminal):
   - [ASSETS] ...
   - [ORDER-HISTORY] ...
   - [TRADE-HISTORY] ...

2. Browser console logs (copy dari F12):
   - 📊 TAB DATA: {...}
   - [AssetsPanel] assets: ...

3. CURL results:
   - curl http://localhost:8000/demo/assets
   - curl http://localhost:8000/demo/order-history
```

---

**Status:** 🔍 **Debug logging added**  
**Backend:** ✅ **Logging di semua endpoint**  
**Frontend:** ✅ **Console.log di semua komponen**  
**Ready to diagnose:** 🚀
