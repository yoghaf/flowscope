from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Query, Request

router = APIRouter(tags=["signals"])


@router.get("/signals/live")
async def get_live_signals(
    request: Request,
    status: str = Query("all", pattern="^(all|open|closed)$"),
    scope: str = Query("active", pattern="^(active|all)$"),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """Return live trade signals with equity simulation."""
    db = request.app.state.db
    settings = request.app.state.signal_service.settings
    trades = await db.list_trade_signals()

    active_since = getattr(settings, "trade_signals_active_since", None)
    if scope == "active" and active_since is not None:
        trades = [t for t in trades if t.created_at and t.created_at >= active_since]

    if status == "open":
        trades = [t for t in trades if t.result == "open"]
    elif status == "closed":
        trades = [t for t in trades if t.result in ("win", "loss", "breakeven", "timeout")]

    # Sort newest first
    trades.sort(key=lambda t: t.created_at, reverse=True)
    trades = trades[:limit]

    serialized = []
    for t in trades:
        insights = []
        if t.entry_features and isinstance(t.entry_features, dict):
            insights = t.entry_features.get("insights", [])

        serialized.append({
            "id": t.id,
            "symbol": t.symbol,
            "timeframe": t.timeframe,
            "bias": t.bias,
            "setup_type": t.setup_type,
            "status": t.status,
            "result": t.result,
            "market_regime": t.market_regime,
            "volatility_regime": t.volatility_regime,
            "entry_price": t.entry_price,
            "invalidation_price": t.invalidation_price,
            "target_price_1": t.target_price_1,
            "target_price_2": t.target_price_2,
            "risk_level": t.risk_level,
            "quality_score": t.quality_score,
            "confidence": round(t.confidence * 100, 1),
            "pnl_pct": round(t.pnl_pct, 2),
            "max_drawdown_pct": round(t.max_drawdown_pct, 2),
            "max_profit_pct": round(t.max_profit_pct, 2),
            "tp1_hit": t.tp1_hit,
            "insights": insights,
            "created_at": t.created_at.isoformat() if t.created_at else None,
            "closed_at": t.closed_at.isoformat() if t.closed_at else None,
            "close_reason": t.close_reason,
        })

    # Summary stats
    closed = [t for t in trades if t.result in ("win", "loss")]
    wins = sum(1 for t in closed if t.result == "win")
    losses = sum(1 for t in closed if t.result == "loss")
    winrate = (wins / len(closed) * 100) if closed else 0

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "scope": scope,
        "active_since": active_since.isoformat() if scope == "active" and active_since is not None else None,
        "total": len(serialized),
        "summary": {
            "total_closed": len(closed),
            "wins": wins,
            "losses": losses,
            "winrate": round(winrate, 1),
            "open_trades": sum(1 for t in trades if t.result == "open"),
        },
        "signals": serialized,
    }
