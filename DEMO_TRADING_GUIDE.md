# FlowScope Demo Trading Guide

## Overview

Sistem demo trading yang terhubung ke **Binance Testnet** untuk paper trading dengan data pasar real-time. Sistem ini menggunakan strategi V3 Adaptive yang sama dengan backtest.

## Fitur

### Backend

- ✅ Koneksi ke Binance Testnet API
- ✅ Execution engine dengan manajemen risiko V3
- ✅ Position sizing dinamis berdasarkan confidence
- ✅ Auto-calculation stop loss & take profit
- ✅ Logging semua trade ke database
- ✅ REST API endpoints untuk kontrol demo trading

### Frontend

- ✅ Dashboard real-time dengan statistik
- ✅ Kurva ekuitas interaktif (Chart.js)
- ✅ Tabel posisi aktif dengan PnL live
- ✅ Log eksekusi sinyal
- ✅ Kontrol Start/Stop demo trading
- ✅ Auto-refresh setiap 5 detik

## Setup

### 1. Instal Dependensi

```powershell
# Install python-binance untuk koneksi ke Binance Testnet
pip install python-binance

# Atau jika menggunakan requirements.txt
pip install -r backend/services/binance_demo/requirements.txt
```

### 2. Dapatkan Binance Testnet API Keys

1. Kunjungi: https://testnet.binancefuture.com
2. Login dengan akun GitHub atau email
3. Generate API Key di menu **API Key**
4. Copy **API Key** dan **Secret Key**

### 3. Konfigurasi Environment

Edit file `.env` di root project:

```bash
FLOWSCOPE_BINANCE_TESTNET_API_KEY=your_testnet_api_key_here
FLOWSCOPE_BINANCE_TESTNET_SECRET_KEY=your_testnet_secret_key_here
```

### 4. Jalankan Backend

```powershell
# Pastikan virtual environment aktif
source /c/Code/flowscope/venv/Scripts/activate

# Jalankan backend API
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. Jalankan Frontend

Buka file `frontend/demo/index.html` di browser, atau gunakan simple HTTP server:

```powershell
# Opsi 1: Python HTTP Server
cd frontend/demo
python -m http.server 3000

# Opsi 2: Live Server (VS Code Extension)
# Klik kanan pada index.html -> "Open with Live Server"
```

Akses dashboard di: **http://localhost:3000**

## Cara Menggunakan

### 1. Start Demo Session

- Klik tombol **▶ Start Demo** di dashboard
- Session akan dimulai dengan balance awal $10,000
- Sistem akan terhubung ke Binance Testnet

### 2. Monitor Posisi

Dashboard akan menampilkan:

- **Balance**: Total balance akun
- **Unrealized PnL**: Profit/loss belum direalisasi
- **Total Trades**: Jumlah trade yang dieksekusi
- **Win Rate**: Persentase trade winning
- **Active Positions**: Posisi yang sedang terbuka
- **Equity Curve**: Grafik performa ekuitas

### 3. Close Posisi Manual

Klik tombol **Close** pada tabel posisi untuk menutup posisi manual.

### 4. Stop Demo Session

- Klik tombol **⏹ Stop Demo**
- Semua posisi terbuka akan ditutup otomatis
- Session akan dicatat ke database

## API Endpoints

### POST `/api/demo/start`

Memulai sesi demo trading.

```json
{
  "initial_balance": 10000.0,
  "description": "Demo trading session"
}
```

### POST `/api/demo/stop`

Menghentikan sesi demo trading.

### GET `/api/demo/status`

Mendapatkan status demo trading (posisi, balance, statistik).

### POST `/api/demo/execute`

Eksekusi sinyal trading manual.

```json
{
  "symbol": "BTCUSDT",
  "signal_type": "Continuation",
  "bias": "Bullish",
  "setup_type": "Continuation Breakout",
  "confidence": 0.85,
  "position_size_multiplier": 1.0
}
```

### POST `/api/demo/close`

Tutup posisi terbuka.

```json
{
  "symbol": "BTCUSDT",
  "reason": "Manual Close"
}
```

### GET `/api/demo/positions`

Daftar posisi terbuka.

### GET `/api/demo/history?limit=50`

Riwayat trade.

## Manajemen Risiko V3

Sistem menggunakan parameter V3 Adaptive untuk position sizing:

- **Base Risk**: 1% per trade
- **Dynamic Sizing**: Multiplier berdasarkan confidence (0.5x - 2.0x)
- **Stop Loss**: ATR-based (1.5x - 2.5x tergantung setup type)
- **Take Profit**: 2R (risk-reward ratio 1:2)

### Setup Type Multipliers

| Setup Type   | Size Multiplier | SL Multiplier |
| ------------ | --------------- | ------------- |
| Trap         | 0.5x            | 2.5x ATR      |
| Squeeze      | 0.7x - 1.25x    | 2.0x ATR      |
| Continuation | 1.0x            | 1.5x ATR      |

## Database Schema

### `demo_trades`

Menyimpan semua trade eksekusi:

- Session ID, symbol, signal type, bias, setup type
- Entry price, quantity, stop loss, take profit
- Exit price, PnL, status (OPEN/CLOSED)
- Metadata (JSON) untuk data tambahan

### `demo_sessions`

Log sesi trading:

- Session ID, initial/final balance
- Total trades, winning/losing trades
- Started/ended timestamp

## Troubleshooting

### Error: "Binance Testnet API credentials not configured"

- Pastikan `.env` sudah dikonfigurasi dengan benar
- Restart backend setelah mengubah `.env`

### Error: "Failed to connect to Binance Testnet"

- Periksa koneksi internet
- Verifikasi API key di https://testnet.binancefuture.com
- Pastikan IP tidak di-banned

### Frontend tidak connect ke backend

- Pastikan backend berjalan di port 8000
- Periksa CORS settings di `backend/main.py`
- Buka browser console untuk error details

## Keamanan

⚠️ **PENTING**:

- Gunakan **HANYA** Binance Testnet (bukan live!)
- Jangan pernah commit `.env` ke Git
- API keys disimpan di server, tidak terekspos ke frontend
- Frontend hanya mengakses via REST API

## Reset Demo

Untuk mereset semua data demo:

```sql
-- Hapus semua trade demo
TRUNCATE TABLE demo_trades CASCADE;

-- Hapus semua session demo
TRUNCATE TABLE demo_sessions CASCADE;
```

## Next Steps

1. **Integrasi dengan Signal Service**: Auto-execute sinyal dari strategy V3
2. **Backtest Comparison**: Compare live demo performance vs backtest
3. **Advanced Risk Management**: Implement portfolio-level risk limits
4. **Alerts**: Telegram notifications untuk trade execution

## Support

Untuk pertanyaan atau issue, buka GitHub Issues atau hubungi tim development.
