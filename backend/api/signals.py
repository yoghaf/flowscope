from __future__ import annotations

from datetime import datetime, timezone
UTC = timezone.utc
from typing import Any

import httpx
from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["signals"])


TRADE_CLOSED_RESULTS = {"win", "loss", "breakeven", "timeout"}
TRADE_WR_RESULTS = {"win", "loss"}
REPORT_TIMEFRAMES = ("15m", "1h", "4h", "24h")
VALUE_EPSILON = 1e-12
KLINE_CACHE_TTL_SECONDS = 60
KLINE_CACHE: dict[tuple[str, str, int], tuple[datetime, list[dict[str, Any]]]] = {}


def _trade_opened_at(trade: Any) -> datetime | None:
    return (
        getattr(trade, "entry_touched_at", None)
        or getattr(trade, "created_at", None)
        or getattr(trade, "timestamp", None)
    )


def _month_key(value: datetime | None) -> str:
    anchor = value or datetime.now(UTC)
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=UTC)
    return anchor.astimezone(UTC).strftime("%Y-%m")


def _month_label(month: str) -> str:
    try:
        return datetime.strptime(month, "%Y-%m").strftime("%B %Y")
    except ValueError:
        return month


def _trade_direction(trade: Any) -> int:
    bias = getattr(trade, "bias", None)
    return 1 if bias == "Bullish" else -1 if bias == "Bearish" else 0


def _trade_risk_pct(trade: Any) -> float | None:
    entry = getattr(trade, "entry_price", None)
    stop = getattr(trade, "invalidation_price", None)
    if entry is None or stop is None or entry <= VALUE_EPSILON:
        return None
    return abs(entry - stop) / entry * 100


def _r_multiple(*, pnl_pct: float | None, risk_pct: float | None) -> float | None:
    if pnl_pct is None or risk_pct is None or risk_pct <= VALUE_EPSILON:
        return None
    return pnl_pct / risk_pct


def _distance_pct(*, target: float | None, price: float | None, direction: int) -> float | None:
    if target is None or price is None or price <= VALUE_EPSILON or direction == 0:
        return None
    return ((target - price) * direction / price) * 100


async def _monitor_snapshot(request: Request, trade: Any) -> dict[str, Any]:
    if getattr(trade, "result", None) != "open":
        return {
            "monitor_price": None,
            "monitor_price_at": None,
            "monitor_source": "closed",
            "monitor_pnl_pct": None,
            "monitor_r": None,
            "distance_to_stop_pct": None,
            "distance_to_tp1_pct": None,
            "distance_to_tp2_pct": None,
        }

    service = getattr(request.app.state, "signal_service", None)
    symbol = str(getattr(trade, "symbol", "") or "").upper()
    timeframe = str(getattr(trade, "timeframe", "") or "1h")
    price: float | None = None
    price_at: datetime | None = None
    source = "unavailable"

    if service is not None and symbol:
        if hasattr(service, "get_latest_price"):
            price = await service.get_latest_price(symbol, timeframe)
            if price is not None:
                source = "backend_state"

        state = getattr(service, "states_by_timeframe", {}).get(timeframe, {}).get(symbol)
        if state is not None:
            if price is None:
                price = getattr(state, "price", None)
                if price is not None:
                    source = "backend_state"
            price_at = getattr(state, "timestamp", None)

        if price is None:
            aggregate_store = getattr(service, "aggregate_store", None)
            if aggregate_store is not None:
                bucket = aggregate_store.latest_bucket(symbol, timeframe, closed_only=False)
                if bucket is not None:
                    price = getattr(bucket, "close_price", None)
                    price_at = getattr(bucket, "last_timestamp", None)
                    source = "latest_bucket"

    entry = getattr(trade, "entry_price", None)
    direction = _trade_direction(trade)
    pnl_pct = (
        ((price - entry) / entry) * 100 * direction
        if price is not None and entry is not None and entry > VALUE_EPSILON and direction != 0
        else None
    )
    risk_pct = _trade_risk_pct(trade)
    active_stop = (
        getattr(trade, "trailing_stop_price", None)
        if getattr(trade, "tp1_hit", False) and getattr(trade, "trailing_stop_price", None) is not None
        else getattr(trade, "invalidation_price", None)
    )
    monitor_r = _r_multiple(pnl_pct=pnl_pct, risk_pct=risk_pct)
    distance_to_stop_pct = _distance_pct(target=active_stop, price=price, direction=-direction)
    distance_to_tp1_pct = _distance_pct(target=getattr(trade, "target_price_1", None), price=price, direction=direction)
    distance_to_tp2_pct = _distance_pct(target=getattr(trade, "target_price_2", None), price=price, direction=direction)

    return {
        "monitor_price": round(price, 12) if price is not None else None,
        "monitor_price_at": price_at.isoformat() if price_at else None,
        "monitor_source": source,
        "monitor_pnl_pct": round(pnl_pct, 4) if pnl_pct is not None else None,
        "monitor_r": round(monitor_r, 4) if monitor_r is not None else None,
        "distance_to_stop_pct": round(distance_to_stop_pct, 4) if distance_to_stop_pct is not None else None,
        "distance_to_tp1_pct": round(distance_to_tp1_pct, 4) if distance_to_tp1_pct is not None else None,
        "distance_to_tp2_pct": round(distance_to_tp2_pct, 4) if distance_to_tp2_pct is not None else None,
    }


def _timeline_logs(trade: Any) -> list[dict[str, Any]]:
    raw_logs = getattr(trade, "history_logs", None)
    logs = [dict(log) for log in raw_logs if isinstance(log, dict)] if isinstance(raw_logs, list) else []
    if logs:
        return logs

    opened_at = _trade_opened_at(trade)
    if opened_at is None:
        return []

    return [
        {
            "timestamp": opened_at.isoformat(),
            "price": getattr(trade, "entry_price", None),
            "pnl_pct": 0.0,
            "r_multiple": 0.0,
            "event": "entry_touch" if getattr(trade, "entry_touched_at", None) is not None else "signal_opened",
            "reason": "Entry touched at signal creation"
            if getattr(trade, "entry_touched_at", None) is not None
            else "Signal opened",
            "source": "derived",
        }
    ]


def _serialize_signal(trade: Any, monitor: dict[str, Any] | None = None) -> dict[str, Any]:
    entry = trade.entry_features if isinstance(trade.entry_features, dict) else {}
    insights = entry.get("insights", [])
    opened_at = _trade_opened_at(trade)

    payload = {
        "id": trade.id,
        "symbol": trade.symbol,
        "timeframe": trade.timeframe,
        "bias": trade.bias,
        "setup_type": trade.setup_type,
        "status": trade.status,
        "result": trade.result,
        "market_regime": trade.market_regime,
        "volatility_regime": trade.volatility_regime,
        "entry_price": trade.entry_price,
        "invalidation_price": trade.invalidation_price,
        "target_price_1": trade.target_price_1,
        "target_price_2": trade.target_price_2,
        "trailing_stop_price": getattr(trade, "trailing_stop_price", None),
        "risk_level": trade.risk_level,
        "quality_score": trade.quality_score,
        "confidence": round(trade.confidence * 100, 1),
        "pnl_pct": round(trade.pnl_pct, 2),
        "max_drawdown_pct": round(trade.max_drawdown_pct, 2),
        "max_profit_pct": round(trade.max_profit_pct, 2),
        "tp1_hit": trade.tp1_hit,
        "engine_tag": getattr(trade, "engine_tag", None),
        "insights": insights,
        "strategy_version": entry.get("strategy_version", "unknown"),
        "position_size_multiplier": round(float(entry.get("position_size_multiplier", 1.0) or 1.0), 4),
        "confidence_score": round(float(entry.get("confidence_score", 0.0) or 0.0), 4),
        "opened_at": opened_at.isoformat() if opened_at else None,
        "cohort_month": _month_key(opened_at),
        "created_at": trade.created_at.isoformat() if trade.created_at else None,
        "closed_at": trade.closed_at.isoformat() if trade.closed_at else None,
        "close_reason": trade.close_reason,
    }
    if monitor is not None:
        payload.update(monitor)
    return payload


def _summarize_signals(trades: list[Any]) -> dict[str, Any]:
    closed = [trade for trade in trades if trade.result in TRADE_CLOSED_RESULTS]
    wr_closed = [trade for trade in trades if trade.result in TRADE_WR_RESULTS]
    wins = sum(1 for trade in wr_closed if trade.result == "win")
    losses = sum(1 for trade in wr_closed if trade.result == "loss")
    breakevens = sum(1 for trade in closed if trade.result == "breakeven")
    timeouts = sum(1 for trade in closed if trade.result == "timeout")
    open_trades = sum(1 for trade in trades if trade.result == "open")
    winrate = (wins / len(wr_closed) * 100) if wr_closed else 0.0
    realized_pnl = sum(float(getattr(trade, "pnl_pct", 0.0) or 0.0) for trade in closed)

    return {
        "total_signals": len(trades),
        "total_closed": len(closed),
        "closed_trades": len(closed),
        "wins": wins,
        "losses": losses,
        "breakevens": breakevens,
        "timeouts": timeouts,
        "winrate": round(winrate, 1),
        "open_trades": open_trades,
        "realized_pnl_pct": round(realized_pnl, 2),
        "avg_realized_pnl_pct": round(realized_pnl / len(closed), 2) if closed else 0.0,
        "report_status": "Live" if open_trades else "Final",
    }


def _month_options(trades: list[Any], selected_month: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[Any]] = {}
    for trade in trades:
        month = _month_key(_trade_opened_at(trade))
        grouped.setdefault(month, []).append(trade)
    grouped.setdefault(selected_month, [])

    options: list[dict[str, Any]] = []
    for month, month_trades in sorted(grouped.items(), reverse=True):
        summary = _summarize_signals(month_trades)
        options.append(
            {
                "value": month,
                "label": _month_label(month),
                "total_signals": summary["total_signals"],
                "open_trades": summary["open_trades"],
                "closed_trades": summary["closed_trades"],
                "report_status": summary["report_status"],
            }
        )
    return options


def _timeframe_reports(trades: list[Any]) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for timeframe in REPORT_TIMEFRAMES:
        timeframe_trades = [trade for trade in trades if getattr(trade, "timeframe", None) == timeframe]
        summary = _summarize_signals(timeframe_trades)
        reports.append(
            {
                "timeframe": timeframe,
                **summary,
            }
        )
    return reports


@router.get("/signals/klines")
async def get_signal_klines(
    request: Request,
    symbol: str = Query(..., min_length=3, max_length=20),
    interval: str = Query("15m", pattern="^(1m|5m|15m|1h|4h|1d)$"),
    limit: int = Query(500, ge=50, le=1000),
) -> dict[str, Any]:
    """Return cached Binance klines through the backend to avoid browser-side request spam."""
    clean_symbol = "".join(ch for ch in symbol.upper() if ch.isalnum())
    cache_key = (clean_symbol, interval, limit)
    now = datetime.now(UTC)
    cached = KLINE_CACHE.get(cache_key)
    if cached is not None:
        cached_at, items = cached
        if (now - cached_at).total_seconds() <= KLINE_CACHE_TTL_SECONDS:
            return {
                "symbol": clean_symbol,
                "interval": interval,
                "cached": True,
                "generated_at": cached_at.isoformat(),
                "items": items,
            }

    settings = request.app.state.signal_service.settings
    base_url = getattr(settings, "binance_spot_rest_url", "https://api.binance.com").rstrip("/")
    url = f"{base_url}/api/v3/klines"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            url,
            params={
                "symbol": clean_symbol,
                "interval": interval,
                "limit": limit,
            },
        )
        response.raise_for_status()
        raw_items = response.json()

    items = [
        {
            "time": int(row[0] / 1000),
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
        }
        for row in raw_items
        if isinstance(row, list) and len(row) >= 5
    ]
    KLINE_CACHE[cache_key] = (now, items)
    return {
        "symbol": clean_symbol,
        "interval": interval,
        "cached": False,
        "generated_at": now.isoformat(),
        "items": items,
    }


@router.get("/signals/live")
async def get_live_signals(
    request: Request,
    status: str = Query("all", pattern="^(all|open|closed)$"),
    scope: str = Query("active", pattern="^(active|all)$"),
    strategy: str = Query("v2_balanced"),
    regime: str = Query("all", pattern="^(all|Balanced|Trending|Ranging)$"),
    timeframe: str = Query("all", pattern="^(all|15m|1h|4h|24h)$"),
    month: str | None = Query(None, pattern=r"^\d{4}-\d{2}$"),
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

    if strategy and strategy != "all":
        trades = [
            t for t in trades
            if isinstance(t.entry_features, dict) and t.entry_features.get("strategy_version", "v1") == strategy
        ]

    if regime and regime != "all":
        trades = [t for t in trades if t.market_regime == regime]

    selected_month = month or datetime.now(UTC).strftime("%Y-%m")
    trades.sort(key=lambda t: _trade_opened_at(t) or datetime.min.replace(tzinfo=UTC), reverse=True)

    monthly_trades_all_timeframes = [trade for trade in trades if _month_key(_trade_opened_at(trade)) == selected_month]
    timeframe_reports = _timeframe_reports(monthly_trades_all_timeframes)
    if timeframe != "all":
        trades_for_month_options = [trade for trade in trades if getattr(trade, "timeframe", None) == timeframe]
        monthly_trades = [trade for trade in monthly_trades_all_timeframes if getattr(trade, "timeframe", None) == timeframe]
        active_open_trades = [
            trade
            for trade in trades
            if trade.result == "open" and getattr(trade, "timeframe", None) == timeframe
        ]
    else:
        trades_for_month_options = trades
        monthly_trades = monthly_trades_all_timeframes
        active_open_trades = [trade for trade in trades if trade.result == "open"]

    listed_trades = list(monthly_trades)
    if status == "open":
        listed_trades = [t for t in listed_trades if t.result == "open"]
    elif status == "closed":
        listed_trades = [t for t in listed_trades if t.result in TRADE_CLOSED_RESULTS]

    listed_trades = listed_trades[:limit]
    active_open_trades = active_open_trades[:limit]

    monitor_trades = {
        trade.id: trade
        for trade in [*listed_trades, *monthly_trades[:limit], *active_open_trades]
        if trade.result == "open"
    }
    monitors = {
        trade_id: await _monitor_snapshot(request, trade)
        for trade_id, trade in monitor_trades.items()
    }

    serialized = [_serialize_signal(t, monitors.get(t.id)) for t in listed_trades]
    monthly_serialized = [_serialize_signal(t, monitors.get(t.id)) for t in monthly_trades[:limit]]
    active_open_serialized = [_serialize_signal(t, monitors.get(t.id)) for t in active_open_trades]
    summary = _summarize_signals(listed_trades)
    monthly_summary = _summarize_signals(monthly_trades)

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "scope": scope,
        "active_tag": active_tag if scope == "active" and active_tag else None,
        "active_since": active_since.isoformat() if scope == "active" and active_since is not None else None,
        "selected_month": selected_month,
        "selected_month_label": _month_label(selected_month),
        "selected_timeframe": timeframe,
        "available_months": _month_options(trades_for_month_options, selected_month),
        "total": len(serialized),
        "summary": summary,
        "monthly_summary": monthly_summary,
        "timeframe_reports": timeframe_reports,
        "monthly_signals": monthly_serialized,
        "active_open_signals": active_open_serialized,
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
    monitor = await _monitor_snapshot(request, trade)
    timeline_logs = _timeline_logs(trade)

    response = {
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
        "history_logs": getattr(trade, "history_logs", []),
        "timeline_logs": timeline_logs,
        "exit_features": getattr(trade, "exit_features", {}),
        "autopsy_rationale": getattr(trade, "autopsy_rationale", None),
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
    response.update(monitor)
    return response
