# 📋 Panduan Setup Binance Testnet API

## 🎯 Apa itu Binance Testnet?

Binance Testnet adalah **environment testing** dari Binance Futures yang memungkinkan Anda trading dengan **uang virtual (demo)** tanpa risiko kehilangan uang sungguhan.

## 🔑 Cara Mendapatkan API Keys

### Langkah 1: Buka Binance Testnet

Buka browser dan kunjungi:

```
https://testnet.binancefuture.com
```

### Langkah 2: Login/Register

1. Klik **"Register"** jika belum punya akun
2. Gunakan email Anda untuk registrasi
3. Verifikasi email Anda
4. Login dengan kredensial yang sudah dibuat

### Langkah 3: Generate API Keys

1. Setelah login, klik **ikon profile** di pojok kanan atas
2. Pilih **"API Management"** atau **"API Keys"**
3. Klik **"Create API Key"**
4. Beri nama untuk API key Anda (contoh: `FlowScope Demo`)
5. **Copy dan simpan** kedua keys berikut:
   - **API Key** (public key)
   - **Secret Key** (private key - hanya muncul sekali!)

⚠️ **PENTING**: Secret Key hanya ditampilkan **sekali**! Simpan dengan aman.

### Langkah 4: Konfigurasi API Key Permissions

Pastikan API key memiliki permissions berikut:

- ✅ **Enable Reading**
- ✅ **Enable Futures**
- ✅ **Enable Spot & Margin Trading** (opsional)

## 🔧 Setup di FlowScope

### 1. Edit File `.env`

Buka file `.env` di root project FlowScope:

```env
# Binance Testnet API Configuration (Demo Trading)
FLOWSCOPE_BINANCE_TESTNET_API_KEY=your_api_key_here
FLOWSCOPE_BINANCE_TESTNET_API_SECRET=your_secret_key_here
```

Ganti:

- `your_api_key_here` dengan **API Key** dari Binance Testnet
- `your_secret_key_here` dengan **Secret Key** dari Binance Testnet

### 2. Restart Backend

Setelah menyimpan `.env`, restart backend:

```powershell
# Stop backend (Ctrl+C)
# Kemudian start ulang
uvicorn backend.main:app --reload --port 8000
```

### 3. Verifikasi Koneksi

1. Buka browser: `http://localhost:8000/docs`
2. Scroll ke bagian **"Demo Trading"**
3. Coba endpoint `/demo/start` untuk memulai sesi demo

## 🚀 Cara Menggunakan Demo Trading

### Via Frontend UI

1. Buka `http://localhost:3000`
2. Login dengan PIN (default: `123456`)
3. Klik menu **"Demo Trading"** di navbar
4. Klik **"Start Demo Session"** untuk memulai
5. Sistem akan otomatis execute sinyal trading dari strategy

### Via API

```bash
# Start demo session
curl -X POST "http://localhost:8000/demo/start" \
  -H "Content-Type: application/json" \
  -d '{"initial_balance": 10000.0}'

# Get demo status
curl "http://localhost:8000/demo/status"

# Get active positions
curl "http://localhost:8000/demo/positions"

# Stop demo session
curl -X POST "http://localhost:8000/demo/stop"
```

## 📊 Fitur Demo Trading

✅ **Real-time Execution** - Execute sinyal trading secara realtime
✅ **Paper Trading** - Trading dengan uang virtual
✅ **Risk Management** - Menggunakan V3 adaptive risk management
✅ **Position Tracking** - Monitor open positions
✅ **PnL Calculation** - Hitung profit/loss realtime
✅ **Trade History** - Export hasil trading ke CSV
✅ **Equity Curve** - Visualisasi performance

## ⚠️ Troubleshooting

### Error: "Binance Testnet API credentials not configured"

**Solusi:**

1. Pastikan `.env` sudah diisi dengan benar
2. Pastikan prefix `FLOWSCOPE_` ada di variable name
3. Restart backend setelah edit `.env`

### Error: "Invalid API-key"

**Solusi:**

1. Check apakah API key sudah di-copy dengan benar (tidak ada spasi)
2. Pastikan API key sudah di-enable untuk Futures trading
3. Regenerate API key jika perlu

### Error: "Failed to connect to Binance Testnet"

**Solusi:**

1. Check koneksi internet
2. Pastikan firewall tidak memblokir akses ke `testnet.binancefuture.com`
3. Coba akses manual: `https://testnet.binancefuture.com`

## 💡 Tips

- **Gunakan email terpisah** untuk Binance Testnet agar tidak tercampur dengan akun utama
- **Backup API keys** di password manager (1Password, Bitwarden, dll)
- **Jangan commit `.env`** ke Git (sudah ada di `.gitignore`)
- **Monitor balance** demo secara berkala
- **Export trade history** untuk analisis performance

## 🔗 Link Penting

- Binance Testnet: https://testnet.binancefuture.com
- Binance API Docs: https://binance-docs.github.io/apidocs/futures/en/
- FlowScope Demo Trading: `http://localhost:3000/demo-trading`

---

**Happy Paper Trading! 🚀**
