from __future__ import annotations

from datetime import datetime, timezone
UTC = timezone.utc

from fastapi import APIRouter, Query, Request
from fastapi.responses import Response

from backend.schemas import PerformanceResponse, PerformanceTradeTableResponse

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


@router.get("/performance/report/data", response_model=PerformanceTradeTableResponse)
async def get_performance_report_data(
    request: Request,
    symbol: str = Query("ALL", min_length=1),
    timeframe: str = Query("ALL", pattern="^(15m|1h|4h|24h|ALL)$"),
    setup_type: str | None = Query(None),
    scope: str = Query("active", pattern="^(active|all)$"),
    strategy: str = Query("v2_balanced"),
    capital_per_trade: float = Query(100.0, gt=0),
    risk_per_trade: float | None = Query(None, gt=0),
) -> PerformanceTradeTableResponse:
    performance_engine = request.app.state.signal_service.performance_engine
    return await performance_engine.get_trade_report_table(
        symbol=symbol,
        timeframe=timeframe,
        setup_type=setup_type,
        scope=scope,
        strategy=strategy,
        capital_per_trade=capital_per_trade,
        risk_per_trade=risk_per_trade,
    )


@router.get("/performance/report")
async def download_performance_report(
    request: Request,
    symbol: str = Query("ALL", min_length=1),
    timeframe: str = Query("ALL", pattern="^(15m|1h|4h|24h|ALL)$"),
    setup_type: str | None = Query(None),
    scope: str = Query("active", pattern="^(active|all)$"),
    capital_per_trade: float = Query(100.0, gt=0),
    risk_per_trade: float | None = Query(None, gt=0),
    format: str = Query("html", pattern="^(html|csv)$"),
) -> Response:
    performance_engine = request.app.state.signal_service.performance_engine
    if format == "csv":
        content = await performance_engine.export_trade_report_csv(
            symbol=symbol,
            timeframe=timeframe,
            setup_type=setup_type,
            scope=scope,
            capital_per_trade=capital_per_trade,
            risk_per_trade=risk_per_trade,
        )
        media_type = "text/csv"
        extension = "csv"
    else:
        content = await performance_engine.export_trade_report_html(
            symbol=symbol,
            timeframe=timeframe,
            setup_type=setup_type,
            scope=scope,
            capital_per_trade=capital_per_trade,
            risk_per_trade=risk_per_trade,
        )
        media_type = "text/html"
        extension = "html"
    filename = f"flowscope-performance-report-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}.{extension}"
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
