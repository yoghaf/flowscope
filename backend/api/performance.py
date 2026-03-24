from __future__ import annotations

from fastapi import APIRouter, Query, Request

from backend.schemas import PerformanceResponse

router = APIRouter(tags=["performance"])


@router.get("/performance", response_model=PerformanceResponse)
async def get_performance(
    request: Request,
    symbol: str = Query(..., min_length=1),
    timeframe: str = Query(..., pattern="^(15m|1h|4h|24h)$"),
    snapshot_id: str = Query(..., min_length=3),
) -> PerformanceResponse:
    service = request.app.state.signal_service
    return await service.get_performance(symbol=symbol, timeframe=timeframe, snapshot_id=snapshot_id)
