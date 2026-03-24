# FlowScope Production Deployment Guide

Guide ini dipertahankan untuk deployment berbasis Docker. Untuk local development tanpa Docker, gunakan [`RUN_LOCAL.md`](./RUN_LOCAL.md).

## Tujuan

Docker configuration di project ini diposisikan untuk deployment atau environment yang menyerupai production, bukan untuk default local development.

## Service Yang Disediakan

- `database`: PostgreSQL + TimescaleDB
- `backend`: FastAPI API + websocket + signal engine
- `frontend`: Next.js app

## Jalankan Dengan Docker

1. Siapkan environment file:

```powershell
cd C:\Code\flowscope
Copy-Item .env.example .env
```

2. Jalankan stack:

```powershell
docker compose up --build
```

3. Akses service:

- Frontend: `http://localhost:3000`
- Backend docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

## Command Penting

Lihat log:

```powershell
docker compose logs -f
```

Lihat log backend:

```powershell
docker compose logs -f backend
```

Stop service:

```powershell
docker compose down
```

Reset volume database:

```powershell
docker compose down -v
```

## Catatan

- Untuk development harian di Windows, gunakan [`RUN_LOCAL.md`](./RUN_LOCAL.md)
- `FLOWSCOPE_DEMO_MODE=true` tetap bisa dipakai di deployment non-production untuk demo data
