# FlowScope Local Development Run Guide

Guide ini untuk menjalankan FlowScope di Windows tanpa Docker.

## Environment

- OS: Windows
- Python: 3.11+
- Node.js: 22+
- npm: 10+
- PostgreSQL: local installation

## Default Ports

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`

## 1. Siapkan Environment File

Jalankan dari root project:

```powershell
cd C:\Code\flowscope
Copy-Item .env.example .env
```

Default penting untuk local development:

```env
FLOWSCOPE_DEMO_MODE=true
FLOWSCOPE_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/flowscope_db
FLOWSCOPE_BOOTSTRAP_FROM_DATABASE=true
FLOWSCOPE_BACKFILL_ENABLED=true
FLOWSCOPE_BACKFILL_PROVIDER=binance
FLOWSCOPE_BACKFILL_LOOKBACK_DAYS=3
NEXT_PUBLIC_API_URL=http://localhost:8000
```

`FLOWSCOPE_DEMO_MODE=true` membuat aplikasi tetap bisa jalan dalam demo mode walaupun database belum tersedia atau tidak aktif.

## Jalur Paling Cepat: Jalan Tanpa PostgreSQL Dulu

Kalau tujuan Anda sekarang cuma ingin FlowScope jalan di local, Anda bisa skip setup database dulu.

Langkah yang langsung bisa dijalankan:

### Backend

Jalankan ini di PowerShell:

```powershell
cd C:\Code\flowscope
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

### Frontend

Buka terminal PowerShell baru:

```powershell
cd C:\Code\flowscope\frontend
npm install
npm run dev
```

Lalu buka:

- Frontend: `http://localhost:3000`
- Backend docs: `http://localhost:8000/docs`

## Jalur Lengkap: Pakai PostgreSQL Lokal

## 2. Setup Database Lokal

Gunakan PostgreSQL lokal, lalu buat database:

### Opsi A: Langsung dari PowerShell

Jalankan ini di PowerShell:

```powershell
psql -U postgres -d postgres -c "CREATE DATABASE flowscope_db;"
```

### Opsi B: Masuk ke `psql` dulu

1. Jalankan ini di PowerShell:

```powershell
psql -U postgres -d postgres
```

2. Setelah prompt berubah menjadi semacam:

```text
postgres=#
```

baru jalankan SQL berikut di dalam `psql`, bukan di PowerShell:

```sql
CREATE DATABASE flowscope_db;
```

### Apply migration

Jalankan ini di PowerShell:

```powershell
psql -U postgres -d flowscope_db -f .\database\migrations\001_initial_schema.sql
psql -U postgres -d flowscope_db -f .\database\migrations\002_market_data_buckets.sql
psql -U postgres -d flowscope_db -f .\database\migrations\003_alert_preferences.sql
psql -U postgres -d flowscope_db -f .\database\migrations\004_add_taker_ratio.sql
psql -U postgres -d flowscope_db -f .\database\migrations\005_trade_signals.sql
psql -U postgres -d flowscope_db -f .\database\migrations\006_trade_signals_positioning.sql
psql -U postgres -d flowscope_db -f .\database\migrations\007_trade_signals_volatility.sql
```

Migration `002_market_data_buckets.sql` menambahkan storage bucket timeframe 15m/1h/4h untuk aggregate OHLC dan metric scanner/dashboard. Migration `003_alert_preferences.sql` menambahkan storage preferences alert per user. Migration `004_add_taker_ratio.sql` menambahkan storage taker buy/sell ratio per bucket. Migration `005_trade_signals.sql` menambahkan tabel tracking trade & hasil evaluasi. Migration `006_trade_signals_positioning.sql` menambahkan kolom regime, TP1/TP2, trailing stop. Migration `007_trade_signals_volatility.sql` menambahkan volatility regime untuk expectancy per kondisi.

Kalau username, password, atau port PostgreSQL lokal Anda berbeda, sesuaikan `.env`.

Kalau `psql` tidak dikenali di PowerShell, biasanya PostgreSQL `bin` belum masuk `PATH`. Alternatifnya jalankan dengan full path, contohnya:

```powershell
& "C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres -d postgres -c "CREATE DATABASE flowscope_db;"
```

## 3. Jalankan Backend

Jalankan ini di PowerShell dari root project:

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

Backend akan tersedia di:

- `http://localhost:8000`
- `http://localhost:8000/docs`

## 4. Jalankan Frontend

Buka terminal PowerShell baru, lalu jalankan:

```powershell
cd frontend
npm install
npm run dev
```

Frontend akan tersedia di:

- `http://localhost:3000`

## 5. Verifikasi

Checklist cepat:

1. Buka `http://localhost:3000`
2. Buka `http://localhost:8000/docs`
3. Coba `GET /dashboard`
4. Coba `GET /scanner`
5. Pastikan data tampil di Dashboard

## 6. Catatan Development

- Frontend sudah default mengarah ke `http://localhost:8000`
- Docker tidak dibutuhkan untuk local development
- Docker config tetap disimpan untuk production deployment
- Bila PostgreSQL belum siap, backend tetap bisa start dalam demo mode karena `FLOWSCOPE_DEMO_MODE=true`
- Kalau `psql` tidak dikenali, kemungkinan PostgreSQL memang belum terpasang di Windows Anda
- Untuk live mode, set `FLOWSCOPE_DEMO_MODE=false`. Saat startup backend akan mencoba:
  1. rehydrate bucket 15m/1h/4h dari `market_data_buckets`
  2. kalau bucket belum ada, bootstrap historical bucket dari Binance public API
  3. setelah itu baru lanjut snapshot live dan websocket realtime
