from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response

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


@router.get("/performance/report")
async def download_performance_report(
    request: Request,
    symbol: str = Query("ALL", min_length=1),
    timeframe: str = Query("ALL", pattern="^(15m|1h|4h|24h|ALL)$"),
    setup_type: str | None = Query(None),
    capital_per_trade: float = Query(100.0, gt=0),
) -> Response:
    performance_engine = request.app.state.signal_service.performance_engine
    csv_content = await performance_engine.export_trade_report_csv(
        symbol=symbol,
        timeframe=timeframe,
        setup_type=setup_type,
        capital_per_trade=capital_per_trade,
    )
    filename = f"flowscope-performance-report-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}.csv"
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
