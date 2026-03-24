from __future__ import annotations

from fastapi import APIRouter, Query, Request

from backend.schemas import DashboardResponse

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    request: Request,
    symbol: str = Query(..., min_length=1),
    timeframe: str = Query(..., pattern="^(15m|1h|4h|24h)$"),
    snapshot_id: str = Query(..., min_length=3),
) -> DashboardResponse:
    service = request.app.state.signal_service
    return await service.get_dashboard(symbol=symbol, timeframe=timeframe, snapshot_id=snapshot_id)
