# FlowScope Demo Trading - Frontend

Binance Testnet paper trading interface untuk V3 Adaptive Strategy.

## 📁 Struktur File

```
demo-trading/
├── page.tsx                  # Main container (DemoTradingPage)
├── README.md                 # Dokumentasi ini
└── components/
    ├── ControlPanel.tsx      # Start/Stop buttons, status indicator
    ├── StatCard.tsx          # Statistics cards (Balance, PnL, Win Rate, etc.)
    ├── EquityChart.tsx       # Lightweight-charts equity curve
    ├── PositionList.tsx      # Active positions table
    ├── SignalLog.tsx         # Real-time signal feed
    ├── TradeHistory.tsx      # Closed trades history
    ├── SignalBadge.tsx       # Long/Short badge component
    ├── SetupBadge.tsx        # Continuation/Trap/Squeeze badge
    ├── PnLIndicator.tsx      # PnL display dengan arrow & warna
    └── StatusDot.tsx         # Animated status indicator dot
```

## 🎨 Design System

### Warna

- **Long (Bullish)**: Emerald green (`#10B981`)
- **Short (Bearish)**: Red (`#EF4444`)
- **Neutral**: Gray (`#6B7280`)
- **Background**: Dark slate (`#0F172A`)
- **Cards**: Slate 800 (`#1E293B`)

### Layout

- **Header**: Hero section dengan gradient background
- **Control Panel**: Start/Stop buttons + status indicator
- **Stats Grid**: 4 kolom (Balance, Unrealized PnL, Total Trades, Win Rate)
- **Main Content**: 2 kolom (70% Chart + 30% Positions)
- **Bottom**: Signal Log + Trade History (full width)

## 🔄 Data Flow

```
Binance Testnet (WS)
    ↓
Backend Python (FastAPI)
    ↓ REST API
Frontend Next.js
    ↓ React Query
Browser (Real-time updates)
```

### API Endpoints

| Endpoint              | Method | Deskripsi                    | Refresh Interval |
| --------------------- | ------ | ---------------------------- | ---------------- |
| `/api/demo/status`    | GET    | Status demo trading, balance | 5 detik          |
| `/api/demo/positions` | GET    | Active positions             | 3 detik          |
| `/api/demo/trades`    | GET    | Trade history                | 10 detik         |
| `/api/demo/signals`   | GET    | Signal events                | 2 detik          |
| `/api/demo/start`     | POST   | Start demo trading           | -                |
| `/api/demo/stop`      | POST   | Stop demo trading            | -                |

### React Query Configuration

```typescript
// Status
useQuery({
  queryKey: ["demo", "status"],
  queryFn: () => api.getDemoStatus(),
  refetchInterval: 5000,
});

// Positions
useQuery({
  queryKey: ["demo", "positions"],
  queryFn: () => api.getDemoPositions(),
  refetchInterval: 3000,
});

// Trades
useQuery({
  queryKey: ["demo", "trades"],
  queryFn: () => api.getDemoTrades(),
  refetchInterval: 10000,
});

// Signals
useQuery({
  queryKey: ["demo", "signals"],
  queryFn: () => api.getDemoSignals(),
  refetchInterval: 2000,
});
```

## 🧩 Komponen

### ControlPanel

- Start/Stop buttons dengan loading states
- Status indicator (running/stopped)
- Manual refresh button

### StatCard

- Title, value, change indicator
- Icon dengan warna dinamis (up/down/neutral)
- Trend indicators

### EquityChart

- Lightweight-charts area chart
- Equity curve dari trade history
- Responsive resize handling

### PositionList

- Active positions table
- Entry price, current price, unrealized PnL
- Setup type badges
- Position age

### SignalLog

- Real-time signal feed
- Filter: All | Long | Short | Wins | Losses
- Signal details (clarity, PnL, timestamp)

### TradeHistory

- Closed trades table
- Sortable columns (date, PnL, R multiple)
- Export to CSV functionality
- Exit reason display

## 🛠️ Dependencies

Sudah terinstal:

- `lightweight-charts` - Charting library
- `@tanstack/react-query` - State management
- `lucide-react` - Icon library
- `tailwindcss` - Styling

## 🚀 Running the Frontend

```bash
# Navigate to frontend folder
cd frontend

# Install dependencies (if needed)
npm install

# Run development server
npm run dev
```

Akses halaman demo trading di: `http://localhost:3000/demo-trading`

## 📝 Notes

- Backend API endpoints belum diimplementasi
- Types didefinisikan di `@/lib/types.ts`
- API client methods ada di `@/lib/api.ts`
- Semua komponen menggunakan Tailwind CSS utility classes
- Responsive design: mobile-first approach
