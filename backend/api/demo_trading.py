from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/demo", tags=["demo-trading"])


@router.get("/positions")
async def get_demo_positions(
    request: Request,
    status: str = Query("all", pattern="^(all|open|closed)$"),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    """List demo trading positions."""
    bot = request.app.state.trading_bot
    trades = await bot.list_all_trades(status=status, limit=limit)

    items = []
    for t in trades:
        items.append({
            "id": t.id,
            "trade_signal_id": t.trade_signal_id,
            "symbol": t.symbol,
            "side": t.side,
            "entry_price": t.entry_price,
            "quantity": t.quantity,
            "notional_usdt": t.notional_usdt,
            "sl_price": t.sl_price,
            "tp1_price": t.tp1_price,
            "tp2_price": t.tp2_price,
            "exit_price": t.exit_price,
            "status": t.status,
            "result": t.result,
            "pnl_usdt": t.pnl_usdt,
            "pnl_pct": t.pnl_pct,
            "position_size_multiplier": t.position_size_multiplier,
            "error_message": t.error_message,
            "opened_at": t.opened_at.isoformat() if t.opened_at else None,
            "closed_at": t.closed_at.isoformat() if t.closed_at else None,
            "close_reason": t.close_reason,
        })

    return {"positions": items, "count": len(items)}


@router.get("/stats")
async def get_demo_stats(request: Request) -> dict[str, Any]:
    """Get demo trading statistics."""
    bot = request.app.state.trading_bot
    return await bot.get_stats()


@router.post("/close/{trade_id}")
async def close_demo_position(
    request: Request,
    trade_id: int = Path(..., ge=1),
) -> dict[str, Any]:
    """Manually close a demo position."""
    bot = request.app.state.trading_bot
    result = await bot.close_position(trade_id)
    if "error" in result:
        return JSONResponse(status_code=400, content=result)
    return result


@router.post("/toggle")
async def toggle_demo_trading(request: Request) -> dict[str, Any]:
    """Toggle demo trading on/off."""
    bot = request.app.state.trading_bot
    settings = request.app.state.settings

    if bot._running:
        await bot.stop()
        settings.demo_trading_enabled = False
        return {"enabled": False, "message": "Demo trading DISABLED"}
    else:
        settings.demo_trading_enabled = True
        await bot.start()
        
        if not bot._running:
            settings.demo_trading_enabled = False
            # Check if keys are missing vs other errors
            if not settings.binance_api_key or not settings.binance_api_secret:
                return JSONResponse(status_code=400, content={"error": "Binance API keys are missing in .env"})
            return JSONResponse(status_code=400, content={"error": "Failed to connect to Binance. Check API keys or IP whitelist."})
            
        return {"enabled": True, "message": "Demo trading ENABLED"}
