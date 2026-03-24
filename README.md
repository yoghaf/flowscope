# FlowScope

FlowScope is a full-stack crypto derivatives analytics platform built with FastAPI, Next.js, PostgreSQL/TimescaleDB, and WebSockets. The application ingests public exchange data, computes flow metrics, scores accumulation and squeeze setups, persists market history, and renders a realtime dashboard that follows the designer-provided UI in `/example`.

## Stack

- Backend: Python, FastAPI, asyncio, SQLAlchemy, httpx
- Frontend: Next.js, React Query, TailwindCSS, Recharts
- Database: PostgreSQL with TimescaleDB migration
- Realtime: FastAPI WebSockets broadcasting market and signal updates
- Deployment: Docker configuration is kept for production deployment

## Layout

- `backend`: API, collectors, flow engine, signal engine, services
- `frontend`: Next.js application matching the `/example` layout
- `database/migrations`: SQL schema and hypertable setup
- `docker`: container images for backend and frontend

## Development Run

Local development now runs without Docker by default.

Detailed local setup is available in [`RUN_LOCAL.md`](./RUN_LOCAL.md).

Quick start:

1. Copy `.env.example` to `.env`.
2. Create a local PostgreSQL database named `flowscope_db` and apply [`database/migrations/001_initial_schema.sql`](./database/migrations/001_initial_schema.sql), [`database/migrations/002_market_data_buckets.sql`](./database/migrations/002_market_data_buckets.sql), [`database/migrations/003_alert_preferences.sql`](./database/migrations/003_alert_preferences.sql), [`database/migrations/004_add_taker_ratio.sql`](./database/migrations/004_add_taker_ratio.sql), [`database/migrations/005_trade_signals.sql`](./database/migrations/005_trade_signals.sql), [`database/migrations/006_trade_signals_positioning.sql`](./database/migrations/006_trade_signals_positioning.sql), and [`database/migrations/007_trade_signals_volatility.sql`](./database/migrations/007_trade_signals_volatility.sql).
3. Run the backend locally on `http://localhost:8000`.
4. Run the frontend locally on `http://localhost:3000`.

`FLOWSCOPE_DEMO_MODE=true` is enabled by default so the app can still run in local development even if the database is unavailable.

When you switch to live mode with `FLOWSCOPE_DEMO_MODE=false`, FlowScope now bootstraps historical 15m/1h/4h buckets from Binance public endpoints and rehydrates from `market_data_buckets` on restart when the database is available. That means the scanner and charts do not need to warm up from zero after every restart.

## Production Deployment

Docker files are still available for production deployment workflows in:

- `docker-compose.yml`
- `docker/`
