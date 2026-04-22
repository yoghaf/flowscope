from __future__ import annotations

from datetime import datetime, timezone
UTC = timezone.utc
from typing import Any

from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import JSONResponse

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

    active_tag = getattr(settings, "trade_signals_active_tag", None)
    active_since = getattr(settings, "trade_signals_active_since", None)
    if scope == "active":
        if active_tag:
            trades = [t for t in trades if getattr(t, "engine_tag", None) == active_tag]
        elif active_since is not None:
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
        entry = t.entry_features if isinstance(t.entry_features, dict) else {}
        insights = entry.get("insights", [])

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
            "engine_tag": getattr(t, "engine_tag", None),
            "insights": insights,
            "strategy_version": entry.get("strategy_version", "unknown"),
            "position_size_multiplier": round(float(entry.get("position_size_multiplier", 1.0) or 1.0), 4),
            "confidence_score": round(float(entry.get("confidence_score", 0.0) or 0.0), 4),
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
        "active_tag": active_tag if scope == "active" and active_tag else None,
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


@router.get("/signals/{trade_id}")
async def get_signal_detail(
    request: Request,
    trade_id: int = Path(..., ge=1),
) -> dict[str, Any]:
    """Return full detail for a single trade signal."""
    db = request.app.state.db
    trade = await db.get_trade_signal_by_id(trade_id)
    if trade is None:
        return JSONResponse(status_code=404, content={"detail": "Signal not found"})

    entry = trade.entry_features if isinstance(trade.entry_features, dict) else {}
    insights = entry.get("insights", [])

    return {
        "id": trade.id,
        "symbol": trade.symbol,
        "timeframe": trade.timeframe,
        "timestamp": trade.timestamp.isoformat() if trade.timestamp else None,
        "state": trade.state,
        "bias": trade.bias,
        "setup_type": trade.setup_type,
        "status": trade.status,
        "result": trade.result,
        "market_regime": trade.market_regime,
        "volatility_regime": trade.volatility_regime,
        "entry_price": trade.entry_price,
        "invalidation_price": trade.invalidation_price,
        "target_price": trade.target_price,
        "target_price_1": trade.target_price_1,
        "target_price_2": trade.target_price_2,
        "trailing_stop_price": trade.trailing_stop_price,
        "tp1_hit": trade.tp1_hit,
        "fill_count": trade.fill_count,
        "entry_flow_alignment": trade.entry_flow_alignment,
        "risk_level": trade.risk_level,
        "quality_score": trade.quality_score,
        "confidence": round(trade.confidence * 100, 1),
        "pnl_pct": round(trade.pnl_pct, 2),
        "max_drawdown_pct": round(trade.max_drawdown_pct, 2),
        "max_profit_pct": round(trade.max_profit_pct, 2),
        "engine_tag": getattr(trade, "engine_tag", None),
        "close_reason": trade.close_reason,
        "insights": insights,
        "strategy_version": entry.get("strategy_version", "unknown"),
        "position_size_multiplier": round(float(entry.get("position_size_multiplier", 1.0) or 1.0), 4),
        "confidence_score": round(float(entry.get("confidence_score", 0.0) or 0.0), 4),
        # Market interpretation fields
        "flow_alignment": entry.get("flow_alignment"),
        "structure_strength": entry.get("structure_strength"),
        "clarity_confidence": entry.get("clarity_confidence"),
        "trap_risk": entry.get("trap_risk"),
        "conflict_score": entry.get("conflict_score"),
        "trend_alignment": entry.get("trend_alignment"),
        "trend": entry.get("trend"),
        "control": entry.get("control"),
        "structure_label": entry.get("structure_label"),
        "structure_shift": entry.get("structure_shift"),
        # Phase
        "phase": entry.get("phase"),
        "phase_score": entry.get("phase_score"),
        "phase_confidence": entry.get("phase_confidence"),
        # Scenario
        "scenario_label": entry.get("scenario_label"),
        "scenario_score": entry.get("scenario_score"),
        "scenario_disposition": entry.get("scenario_disposition"),
        "scenario_rationale": entry.get("scenario_rationale"),
        "scenario_reasons": entry.get("scenario_reasons"),
        # Decision
        "decision_market_regime": entry.get("decision_market_regime"),
        "decision_volatility_regime": entry.get("decision_volatility_regime"),
        "decision_bias": entry.get("decision_bias"),
        "decision_setup_gate": entry.get("decision_setup_gate"),
        "decision_signal": entry.get("decision_signal"),
        "action_opportunity_score": entry.get("action_opportunity_score"),
        # Flow metrics (selected key ones for display)
        "oi_change_1h": entry.get("oi_change_1h"),
        "oi_change_4h": entry.get("oi_change_4h"),
        "oi_change_24h": entry.get("oi_change_24h"),
        "funding_level_1h": entry.get("funding_level_1h"),
        "funding_level_4h": entry.get("funding_level_4h"),
        "volume_change_1h": entry.get("volume_change_1h"),
        "volume_change_4h": entry.get("volume_change_4h"),
        "long_short_ratio_level_1h": entry.get("long_short_ratio_level_1h"),
        "long_short_ratio_delta_1h": entry.get("long_short_ratio_delta_1h"),
        "compression_score_1h": entry.get("compression_score_1h"),
        "compression_score_4h": entry.get("compression_score_4h"),
        "market_pressure_1h": entry.get("market_pressure_1h"),
        "market_pressure_4h": entry.get("market_pressure_4h"),
        "liq_pressure_1h": entry.get("liq_pressure_1h"),
        "liq_pressure_4h": entry.get("liq_pressure_4h"),
        "volume_z_1h": entry.get("volume_z_1h"),
        "volume_z_4h": entry.get("volume_z_4h"),
        "atr_1h": entry.get("atr_1h"),
        "atr_4h": entry.get("atr_4h"),
        # Timestamps
        "created_at": trade.created_at.isoformat() if trade.created_at else None,
        "entry_touched_at": trade.entry_touched_at.isoformat() if trade.entry_touched_at else None,
        "closed_at": trade.closed_at.isoformat() if trade.closed_at else None,
        "updated_at": trade.updated_at.isoformat() if trade.updated_at else None,
    }
