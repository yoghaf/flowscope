# 🐳 Whale Radar

Standalone whale accumulation radar — detects smart money footprints across 300+ Binance Futures markets.

## Features

- **Squeeze Hunter** — Detects short squeeze setups (negative funding + rising price)
- **Ambush Scanner** — Low market cap + sideways accumulation + OI spikes
- **Comprehensive Overview** — Balanced scoring across all metrics
- 10-minute in-memory cache, auto-refresh every 60s

## Deploy to Vercel

```bash
# 1. Push this folder as its own repo
git init && git add . && git commit -m "init"

# 2. Connect to Vercel
npx vercel

# 3. Done! API route has maxDuration=60s for the scan
```

## Run Locally

```bash
npm install
npm run dev
# Open http://localhost:3000
```

## Architecture

- `src/app/api/scan/route.ts` — API route that scans Binance Futures (ported from Python)
- `src/app/page.tsx` — Dashboard UI
- No database needed — pure serverless + in-memory cache
