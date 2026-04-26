from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
UTC = timezone.utc

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.api.alerts import router as alerts_router
from backend.api.coin import router as coin_router
from backend.api.dashboard import router as dashboard_router
from backend.api.demo_trading import router as demo_trading_router
from backend.api.performance import router as performance_router
from backend.api.scanner import router as scanner_router
from backend.api.signals import router as signals_router
from backend.config import get_settings
from backend.database import DatabaseManager
from backend.schemas import RealtimeEvent
from backend.services.realtime import RealtimeHub
from backend.services.signal_service import SignalService
from backend.services.trading_bot import TradingBotService

logging.basicConfig(level=logging.INFO)

settings = get_settings()
database = DatabaseManager(settings)
realtime_hub = RealtimeHub()
signal_service = SignalService(settings, database, realtime_hub)
trading_bot = TradingBotService(settings, database)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.settings = settings
    app.state.database = database
    app.state.db = database
    app.state.realtime_hub = realtime_hub
    app.state.signal_service = signal_service
    app.state.trading_bot = trading_bot
    signal_service.trading_bot = trading_bot
    await database.init()
    await trading_bot.start()
    await signal_service.start()
    yield
    await trading_bot.stop()
    await signal_service.stop()
    await database.close()


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(dashboard_router)
app.include_router(scanner_router)
app.include_router(coin_router)
app.include_router(alerts_router)
app.include_router(performance_router)
app.include_router(signals_router)
app.include_router(demo_trading_router)


@app.get("/health")
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.websocket("/ws/market")
async def market_socket(websocket: WebSocket) -> None:
    await realtime_hub.connect(websocket)
    await websocket.send_json(
        RealtimeEvent(
            type="snapshot",
            timestamp=datetime.now(UTC),
            symbols=signal_service.symbols[:50],
        ).model_dump(mode="json")
    )
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await realtime_hub.disconnect(websocket)
    except Exception:
        await realtime_hub.disconnect(websocket)
