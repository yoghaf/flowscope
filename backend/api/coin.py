from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from backend.schemas import CoinDetailResponse

router = APIRouter(tags=["coin"])


@router.get("/coin/{symbol}", response_model=CoinDetailResponse)
async def get_coin(
    symbol: str,
    request: Request,
    timeframe: str = Query(..., pattern="^(15m|1h|4h|24h)$"),
    snapshot_id: str = Query(..., min_length=3),
) -> CoinDetailResponse:
    service = request.app.state.signal_service
    try:
        return await service.get_coin_detail(symbol, timeframe, snapshot_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Snapshot not found") from exc
