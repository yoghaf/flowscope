from __future__ import annotations

from fastapi import APIRouter, Query, Request

from backend.schemas import ScannerResponse

router = APIRouter(tags=["scanner"])


@router.get("/scanner", response_model=ScannerResponse)
async def get_scanner(
    request: Request,
    symbol: str = Query(..., min_length=1),
    timeframe: str = Query(..., pattern="^(15m|1h|4h|24h)$"),
    snapshot_id: str = Query(..., min_length=3),
    signal_type: str | None = Query(default=None),
    min_score: float = Query(default=0.0, ge=0.0, le=1.0),
    max_score: float = Query(default=1.0, ge=0.0, le=1.0),
    search: str | None = Query(default=None),
) -> ScannerResponse:
    service = request.app.state.signal_service
    return await service.get_scanner(
        symbol=symbol,
        timeframe=timeframe,
        snapshot_id=snapshot_id,
        signal_type=signal_type,
        min_score=min_score,
        max_score=max_score,
        search=search,
    )
