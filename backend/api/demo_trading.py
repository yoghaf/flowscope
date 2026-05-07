"""
Demo Trading API Endpoints
FastAPI endpoints for controlling demo trading on Binance Testnet.
"""

from __future__ import annotations

import logging
from typing import Any
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from backend.database import DatabaseManager, get_database
from backend.config import get_settings, Settings
from backend.services.binance_demo.binance_client import BinanceTestnetClient
from backend.services.binance_demo.demo_execution_engine import (
    DEFAULT_MAX_ENTRY_DRIFT_PCT,
    DEFAULT_MAX_MARKET_TP1_PROGRESS_PCT,
    DEFAULT_MAX_PULLBACK_TP1_PROGRESS_PCT,
    ENTRY_MODE_MARKET_PULLBACK_LIMIT,
    DemoExecutionEngine,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/demo", tags=["Demo Trading"])

# Global execution engine instance
_demo_engine: DemoExecutionEngine | None = None
_demo_settings: "DemoSettings" | None = None

DEMO_HISTORY_SYMBOLS = (
    "BTCUSDT",
    "ETHUSDT",
    "BNBUSDT",
    "SOLUSDT",
    "TONUSDT",
    "ETCUSDT",
    "RENDERUSDT",
    "VIRTUALUSDT",
    "NEIROUSDT",
    "ONDOUSDT",
)
DEMO_REGIMES = ("Balanced", "Trending", "Ranging")


def get_demo_engine() -> DemoExecutionEngine | None:
    """Get the current demo execution engine instance."""
    return _demo_engine


def _to_float(value: Any, default: float = 0.0) -> float:
    """Convert Binance string/decimal fields to float without crashing rows."""
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_symbol(symbol: Any) -> str | None:
    if not symbol:
        return None
    normalized = str(symbol).upper().strip()
    if not normalized:
        return None
    return normalized if normalized.endswith("USDT") else f"{normalized}USDT"


def _dedupe_symbols(symbols: list[Any]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []

    for symbol in symbols:
        normalized = _normalize_symbol(symbol)
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(normalized)

    return deduped


async def _collect_history_symbols(
    client: BinanceTestnetClient,
    settings: Settings,
) -> list[str]:
    """Collect symbols worth scanning for order/trade history.

    Binance Futures history endpoints require a symbol, so we seed from open
    positions, income history, configured FlowScope symbols, and demo defaults.
    """
    symbols: list[Any] = []

    try:
        positions = client.client.futures_position_information()
        symbols.extend(
            pos.get("symbol")
            for pos in positions
            if _to_float(pos.get("positionAmt")) != 0
        )
    except Exception as exc:
        logger.warning("[HISTORY] Failed to collect position symbols: %s", exc)

    try:
        income = client.client.futures_income_history(limit=100)
        symbols.extend(item.get("symbol") for item in income if item.get("symbol"))
    except Exception as exc:
        logger.warning("[HISTORY] Failed to collect income symbols: %s", exc)

    symbols.extend(getattr(settings, "default_symbols", []) or [])
    symbols.extend(DEMO_HISTORY_SYMBOLS)

    return _dedupe_symbols(symbols)


class DemoStartRequest(BaseModel):
    """Request model for starting demo session."""
    initial_balance: float | None = Field(
        default=None,
        ge=100.0,
        le=1000000.0,
        description=(
            "Deprecated. Demo trading uses the actual Binance Testnet wallet "
            "balance as the session baseline."
        ),
    )
    description: str = Field(default="Demo trading session")


class DemoSignalRequest(BaseModel):
    """Request model for executing a demo signal."""
    symbol: str = Field(..., min_length=1)
    signal_type: str = Field(..., description="e.g., Continuation, Trap, Squeeze")
    bias: str = Field(..., description="Bullish or Bearish")
    setup_type: str = Field(..., description="Setup type from execution engine")
    confidence: float = Field(ge=0.0, le=1.0)
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    take_profit_1: float | None = None
    take_profit_2: float | None = None
    position_size_multiplier: float = Field(default=1.0, ge=0.1, le=2.0)
    risk_usdt: float | None = Field(default=None, ge=1.0, le=100000.0)
    max_slippage_pct: float | None = Field(default=None, ge=0.0, le=10.0)
    max_entry_drift_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    max_market_tp1_progress_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    max_pullback_tp1_progress_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    entry_mode: str | None = None
    tp1_close_pct: float | None = Field(default=None, ge=1.0, le=99.0)


class DemoSettings(BaseModel):
    """Demo auto-execution and risk settings."""
    auto_execute: bool = False
    risk_usdt: float = Field(default=10.0, ge=1.0, le=100000.0)
    max_slippage_pct: float | None = Field(default=None, ge=0.0, le=10.0)
    max_entry_drift_pct: float = Field(default=DEFAULT_MAX_ENTRY_DRIFT_PCT, ge=0.0, le=100.0)
    max_market_tp1_progress_pct: float = Field(
        default=DEFAULT_MAX_MARKET_TP1_PROGRESS_PCT,
        ge=0.0,
        le=100.0,
    )
    max_pullback_tp1_progress_pct: float = Field(
        default=DEFAULT_MAX_PULLBACK_TP1_PROGRESS_PCT,
        ge=0.0,
        le=100.0,
    )
    entry_mode: str = ENTRY_MODE_MARKET_PULLBACK_LIMIT
    tp1_close_pct: float = Field(default=50.0, ge=1.0, le=99.0)
    enabled_timeframes: list[str] = Field(default_factory=lambda: ["15m", "1h"])
    enabled_setups: list[str] = Field(default_factory=lambda: ["Continuation", "Squeeze", "Trap"])
    enabled_regimes: list[str] = Field(default_factory=lambda: list(DEMO_REGIMES))


class DemoSettingsUpdate(BaseModel):
    auto_execute: bool | None = None
    risk_usdt: float | None = Field(default=None, ge=1.0, le=100000.0)
    max_slippage_pct: float | None = Field(default=None, ge=0.0, le=10.0)
    max_entry_drift_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    max_market_tp1_progress_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    max_pullback_tp1_progress_pct: float | None = Field(default=None, ge=0.0, le=100.0)
    entry_mode: str | None = None
    tp1_close_pct: float | None = Field(default=None, ge=1.0, le=99.0)
    enabled_timeframes: list[str] | None = None
    enabled_setups: list[str] | None = None
    enabled_regimes: list[str] | None = None


class DemoCloseRequest(BaseModel):
    """Request model for closing a position."""
    symbol: str = Field(..., min_length=1)
    reason: str = Field(default="Manual Close")


def get_demo_settings() -> DemoSettings:
    global _demo_settings
    if _demo_settings is None:
        _demo_settings = DemoSettings()
    return _demo_settings


@router.get("/settings")
async def read_demo_settings() -> dict[str, Any]:
    settings = get_demo_settings()
    return settings.model_dump()


@router.put("/settings")
async def update_demo_settings(update: DemoSettingsUpdate) -> dict[str, Any]:
    global _demo_settings
    current = get_demo_settings().model_dump()
    patch = update.model_dump(exclude_unset=True)
    for key, value in patch.items():
        if value is not None:
            current[key] = value
    _demo_settings = DemoSettings(**current)
    return _demo_settings.model_dump()


@router.post("/start")
async def start_demo_session(
    request: DemoStartRequest,
    database: DatabaseManager = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """
    Start a new demo trading session on Binance Testnet.

    Creates a new DemoExecutionEngine instance and initializes
    connection to Binance Testnet.
    """
    global _demo_engine

    try:
        # Check if session already running
        if _demo_engine and _demo_engine.running:
            # FIX: Check if engine is actually healthy before rejecting
            is_healthy = await _demo_engine.is_healthy()
            if not is_healthy:
                logger.warning("Demo engine running but unhealthy, resetting...")
                _demo_engine = None
            else:
                logger.warning("Attempted to start demo session while one is already running")
                raise HTTPException(
                    status_code=400,
                    detail="Demo session already running. Please stop the current session first or refresh the page.",
                )

        # Get API credentials from settings
        api_key = settings.binance_testnet_api_key
        api_secret = settings.binance_testnet_api_secret

        if not api_key or not api_secret:
            raise HTTPException(
                status_code=500,
                detail="Binance Testnet API credentials not configured. Check .env file.",
            )

        # Create client and execution engine
        client = BinanceTestnetClient(api_key=api_key, api_secret=api_secret)
        _demo_engine = DemoExecutionEngine(
            client=client,
            database=database,
            settings=settings,
        )

        # Start session
        result = await _demo_engine.start_session()

        if not result.get("success"):
            error_msg = result.get("error", "Failed to start demo session")
            # Provide user-friendly error for known issues
            if "502" in error_msg or "Bad Gateway" in error_msg:
                detail = (
                    "Binance Futures Testnet is currently DOWN (502 Bad Gateway). "
                    "This is a Binance server issue. Please try again in a few minutes. "
                    "Check status: https://testnet.binancefuture.com"
                )
            elif "connect" in error_msg.lower():
                detail = f"Failed to connect to Binance Testnet: {error_msg}"
            else:
                detail = error_msg
            _demo_engine = None  # Clean up failed engine
            raise HTTPException(status_code=503, detail=detail)

        logger.info(f"Demo session started: {result.get('session_id')}")

        return {
            "success": True,
            "message": "Demo trading session started successfully",
            "data": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        error_str = str(e)
        logger.error(f"Error starting demo session: {error_str}")
        if "502" in error_str or "Bad Gateway" in error_str:
            _demo_engine = None
            raise HTTPException(
                status_code=503,
                detail=(
                    "Binance Futures Testnet is currently DOWN (502 Bad Gateway). "
                    "This is a Binance server issue, not a code bug. "
                    "Please try again later."
                ),
            )
        _demo_engine = None
        raise HTTPException(status_code=500, detail=error_str)


@router.post("/stop")
async def stop_demo_session() -> dict[str, Any]:
    """
    Stop the current demo trading session.

    Closes all open positions and disconnects from Binance Testnet.
    """
    global _demo_engine

    if not _demo_engine or not _demo_engine.running:
        raise HTTPException(
            status_code=400,
            detail="No active demo session found",
        )

    try:
        result = await _demo_engine.stop_session()

        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Failed to stop demo session"),
            )

        # Clear engine instance
        _demo_engine = None

        logger.info("Demo session stopped")

        return {
            "success": True,
            "message": "Demo trading session stopped successfully",
            "data": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping demo session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/force-stop")
async def force_stop_demo_session() -> dict[str, Any]:
    """
    Force stop demo session (for stuck sessions).
    
    Use this when normal stop fails or session is stuck.
    This will clear the engine instance without gracefully closing positions.
    """
    global _demo_engine

    if not _demo_engine:
        return {
            "success": True,
            "message": "No active session to force stop",
        }

    try:
        # Try to stop gracefully first
        if _demo_engine.running:
            await _demo_engine.stop_session()
        
        # Clear engine instance
        _demo_engine = None
        
        logger.info("Demo session force stopped")
        
        return {
            "success": True,
            "message": "Demo session force stopped successfully",
        }
        
    except Exception as e:
        logger.error(f"Error force stopping session: {e}")
        # Still clear the engine even if stop failed
        _demo_engine = None
        return {
            "success": True,
            "message": "Session cleared (stop may have failed)",
            "error": str(e),
        }


@router.get("/status")
async def get_demo_status() -> dict[str, Any]:
    """
    Get current demo trading status.
    
    RULE 2: STATUS FIRST (WAJIB)
    Returns: running, current_balance, available_balance
    
    RULE 7: NO FALLBACK - Returns null if session not running
    """
    global _demo_engine

    # RULE 1: SESSION AS SINGLE SOURCE OF TRUTH
    if not _demo_engine:
        return {
            "success": False,
            "message": "No demo session active",
            "running": False,
            # RULE 7: No fallback values
            "data": None,
        }

    try:
        status = await _demo_engine.get_status()

        # RULE 8: DEBUG OUTPUT
        logger.info(f"[STATUS] running={_demo_engine.running}, "
                   f"current_balance={status.get('current_balance')}, "
                   f"available_balance={status.get('available_balance')}")

        return {
            "success": True,
            "running": _demo_engine.running,
            "data": status,
        }

    except Exception as e:
        logger.error(f"Error getting demo status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute")
async def execute_demo_signal(
    request: DemoSignalRequest,
) -> dict[str, Any]:
    """
    Execute a trading signal on demo account.
    
    RULE 5: EXECUTION FLOW
    1. Check session.running
    2. Fetch latest account + positions
    3. Validate balance
    4. Check position
    5. Execute or reject
    
    RULE 12: FORBIDDEN BEHAVIOR
    - Do NOT execute if session inactive
    """
    global _demo_engine

    # RULE 1: SESSION GATE
    if not _demo_engine or not _demo_engine.running:
        logger.warning("[EXECUTE] REJECTED: session.running == false")
        raise HTTPException(
            status_code=400,
            detail="No active demo session. Start one first.",
        )

    try:
        demo_settings = get_demo_settings()
        result = await _demo_engine.execute_signal(
            symbol=request.symbol,
            signal_type=request.signal_type,
            bias=request.bias,
            setup_type=request.setup_type,
            confidence=request.confidence,
            entry_price=request.entry_price,
            stop_loss=request.stop_loss,
            take_profit=request.take_profit,
            take_profit_1=request.take_profit_1,
            take_profit_2=request.take_profit_2,
            position_size_multiplier=request.position_size_multiplier,
            risk_usdt=request.risk_usdt if request.risk_usdt is not None else demo_settings.risk_usdt,
            max_slippage_pct=(
                request.max_slippage_pct
                if request.max_slippage_pct is not None
                else demo_settings.max_slippage_pct
            ),
            max_entry_drift_pct=(
                request.max_entry_drift_pct
                if request.max_entry_drift_pct is not None
                else demo_settings.max_entry_drift_pct
            ),
            max_market_tp1_progress_pct=(
                request.max_market_tp1_progress_pct
                if request.max_market_tp1_progress_pct is not None
                else demo_settings.max_market_tp1_progress_pct
            ),
            max_pullback_tp1_progress_pct=(
                request.max_pullback_tp1_progress_pct
                if request.max_pullback_tp1_progress_pct is not None
                else demo_settings.max_pullback_tp1_progress_pct
            ),
            entry_mode=(
                request.entry_mode
                if request.entry_mode is not None
                else demo_settings.entry_mode
            ),
            tp1_close_pct=(
                request.tp1_close_pct
                if request.tp1_close_pct is not None
                else demo_settings.tp1_close_pct
            ),
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Failed to execute signal"),
            )

        logger.info(
            f"Demo signal executed: {request.signal_type} {request.bias} {request.symbol}"
        )

        return {
            "success": True,
            "message": "Signal executed successfully",
            "data": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error executing demo signal: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/close")
async def close_demo_position(
    request: DemoCloseRequest,
) -> dict[str, Any]:
    """
    Close an open position on demo account.
    """
    global _demo_engine

    if not _demo_engine or not _demo_engine.running:
        raise HTTPException(
            status_code=400,
            detail="No active demo session",
        )

    try:
        result = await _demo_engine.close_position(
            symbol=request.symbol,
            reason=request.reason,
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Failed to close position"),
            )

        logger.info(f"Demo position closed: {request.symbol}")

        return {
            "success": True,
            "message": "Position closed successfully",
            "data": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error closing demo position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/positions")
async def get_open_positions() -> dict[str, Any]:
    """
    Get all open positions from demo account.
    Returns COMPLETE position info including liquidation price, leverage, margin type, etc.
    """
    global _demo_engine

    if not _demo_engine or not _demo_engine.running:
        return {
            "success": False,
            "message": "No active demo session",
            "positions": [],
        }

    try:
        # Fetch positions directly from Binance API for latest data
        client = _demo_engine.client
        if not client or not client.connected:
            return {
                "success": False,
                "message": "Not connected to Binance",
                "positions": [],
            }
        
        # Get positions from Binance /fapi/v2/positionRisk
        raw_positions = client.client.futures_position_information()
        
        logger.info(f"[POSITIONS] Fetched {len(raw_positions)} raw positions from Binance")
        
        # Transform positions to match frontend DemoPosition interface
        from datetime import datetime, timezone
        
        positions = []
        for pos in raw_positions:
            position_amt = float(pos.get("positionAmt", 0))
            
            # Skip positions with no size
            if position_amt == 0:
                continue
            
            # Parse timestamp
            entry_time = datetime.now(timezone.utc)
            entry_time_str = entry_time.isoformat()
            
            # Calculate age in hours
            age_hours = 0.0
            
            # Determine side
            side = "LONG" if position_amt > 0 else "SHORT"
            
            # Extract raw values
            unrealized_pnl_val = float(pos.get("unRealizedProfit", 0))
            notional_val = float(pos.get("notional", 0))
            isolated_margin_val = float(pos.get("isolatedMargin", 0))
            
            # FIX BUG 2: Leverage - Binance returns as string, default to 20
            leverage = int(float(pos.get("leverage", 20)))
            
            # FIX BUG 3: ROE - Use correct formula with leverage
            # ROE = (unrealized_pnl / margin_used) * 100
            # For cross margin: margin_used = notional / leverage
            notional_abs = abs(notional_val)
            margin_used = notional_abs / leverage if leverage > 0 else notional_abs
            roe = (unrealized_pnl_val / margin_used) * 100 if margin_used > 0 else 0.0
            
            # FIX BUG 4: Margin display - For cross margin, calculate from notional/leverage
            margin_display = isolated_margin_val if isolated_margin_val > 0 else (notional_abs / leverage if leverage > 0 else 0)
            
            # Calculate margin ratio (maintMargin / marginBalance approximation)
            maint_margin_val = float(pos.get("maintMargin", 0))
            margin_ratio = (maint_margin_val / margin_used * 100) if margin_used > 0 else 0.0
            
            # Get all available fields from Binance
            transformed = {
                "id": f"{pos.get('symbol', 'UNKNOWN')}_{entry_time_str}",
                "symbol": pos.get("symbol", "UNKNOWN"),
                "side": side,
                # FIX BUG 1: Size always positive (abs)
                "size": abs(position_amt),
                "entry_price": float(pos.get("entryPrice", 0)),
                "current_price": float(pos.get("markPrice", 0)),
                "mark_price": float(pos.get("markPrice", 0)),
                "break_even_price": float(pos.get("breakEvenPrice", 0)),
                "unrealized_pnl": unrealized_pnl_val,
                "setup_type": "Unknown",  # Not available from Binance
                "entry_time": entry_time_str,
                "age_hours": age_hours,
                # Additional fields for complete position info
                "liquidation_price": float(pos.get("liquidationPrice", 0)),
                # FIX BUG 2: Leverage with correct default
                "leverage": leverage,
                "margin_type": pos.get("marginType", "CROSS").upper(),
                # FIX BUG 4: Use calculated margin_display instead of raw isolated_margin
                "isolated_margin": margin_display,
                "notional": notional_val,
                # REMOVED: position_amt (raw field with sign) - frontend should use size instead
                # FIX BUG 3 & 4: Pre-calculated ROE and margin
                "roe": roe,
                "margin_ratio": margin_ratio,
                "maintenance_margin": float(pos.get("maintMargin", 0)),
            }
            
            logger.debug(f"[POSITION] {transformed['symbol']}: {transformed['side']} {transformed['size']} @ {transformed['entry_price']}, PnL={transformed['unrealized_pnl']:.2f}")
            positions.append(transformed)

        logger.info(f"[POSITIONS] Returning {len(positions)} open positions")

        return {
            "success": True,
            "positions": positions,
            "count": len(positions),
        }

    except Exception as e:
        logger.error(f"Error getting positions: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/signals")
async def get_demo_signals() -> dict[str, Any]:
    """
    Get recent demo signal events.
    TODO: Implement signal event logging.
    """
    return {
        "success": True,
        "signals": [],
        "count": 0,
    }


@router.get("/trades")
@router.get("/history")
async def get_trade_history(
    limit: int = 50,
) -> dict[str, Any]:
    """
    Get recent trade history from demo session.
    """
    global _demo_engine

    if not _demo_engine:
        return {
            "success": False,
            "message": "No demo session found",
            "trades": [],
        }

    try:
        status = await _demo_engine.get_status()
        trades = status.get("recent_trades", [])[:limit]

        return {
            "success": True,
            "trades": trades,
            "count": len(trades),
        }

    except Exception as e:
        logger.error(f"Error getting trade history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/open-orders")
async def get_open_orders() -> list[dict[str, Any]]:
    """
    Get all open orders from demo account.
    GET /fapi/v1/openOrders - Returns FLAT array (no wrapper)
    """
    global _demo_engine

    if not _demo_engine or not _demo_engine.running:
        logger.warning("[OPEN-ORDERS] No active session")
        return []

    try:
        client = _demo_engine.client
        if not client or not client.connected:
            logger.error("[OPEN-ORDERS] Not connected to Binance")
            return []

        # Fetch open orders from Binance API using client method
        logger.info("[OPEN-ORDERS] Fetching from Binance API...")
        open_orders = await client.get_open_orders()
        logger.info(f"[OPEN-ORDERS] Raw count: {len(open_orders)}")
        
        # Return flat array with complete order info
        orders = []
        for o in open_orders:
            orig_qty = _to_float(o.get("origQty", o.get("qty")))
            create_time = o.get("createTime") or o.get("time")
            orders.append(
                {
                    "orderId": o.get("orderId"),
                    "symbol": o.get("symbol"),
                    "side": o.get("side"),
                    "type": o.get("type"),
                    "price": _to_float(o.get("price")),
                    "qty": orig_qty,
                    "origQty": orig_qty,
                    "executedQty": _to_float(o.get("executedQty")),
                    "status": o.get("status"),
                    "timeInForce": o.get("timeInForce"),
                    "time": create_time,
                    "createTime": create_time,
                    "updateTime": o.get("updateTime"),
                }
            )
        
        logger.info(f"[OPEN-ORDERS] Returning {len(orders)} orders")
        return orders

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting open orders: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/order-history")
async def get_order_history(
    limit: int = 100,
    settings: Settings = Depends(get_settings),
) -> list[dict[str, Any]]:
    """
    Get order history from demo account.
    GET /fapi/v1/allOrders - Returns FLAT array (no wrapper)
    Fetches from ALL symbols in the account.
    """
    global _demo_engine

    if not _demo_engine or not _demo_engine.running:
        logger.warning("[ORDER-HISTORY] No active session")
        return []

    try:
        client = _demo_engine.client
        if not client or not client.connected:
            logger.error("[ORDER-HISTORY] Not connected to Binance")
            return []

        logger.info(f"[ORDER-HISTORY] Fetching limit={limit}...")
        
        all_orders = []
        symbols_to_fetch = await _collect_history_symbols(client, settings)
        logger.info(f"[ORDER-HISTORY] Symbols to fetch: {symbols_to_fetch}")
        
        # Fetch order history for each symbol
        for symbol in symbols_to_fetch:
            try:
                orders = await client.get_order_history(symbol=symbol, limit=limit)
                logger.debug(f"[ORDER-HISTORY] {symbol}: {len(orders)} orders")
                all_orders.extend(orders)
            except Exception as e:
                logger.warning(f"[ORDER-HISTORY] Error fetching {symbol}: {e}")
                pass

        # Sort by time descending (newest first)
        all_orders.sort(
            key=lambda x: x.get("time") or x.get("createTime") or 0,
            reverse=True,
        )
        
        # Transform to flat structure with complete info
        orders = []
        for o in all_orders[:limit]:
            orig_qty = _to_float(o.get("origQty", o.get("qty")))
            create_time = o.get("createTime") or o.get("time")
            orders.append(
                {
                    "orderId": o.get("orderId"),
                    "symbol": o.get("symbol"),
                    "side": o.get("side"),
                    "type": o.get("type"),
                    "status": o.get("status"),
                    "price": _to_float(o.get("price")),
                    "qty": orig_qty,
                    "origQty": orig_qty,
                    "executedQty": _to_float(o.get("executedQty")),
                    "avgPrice": _to_float(o.get("avgPrice")),
                    "timeInForce": o.get("timeInForce"),
                    "time": create_time,
                    "createTime": create_time,
                    "updateTime": o.get("updateTime"),
                }
            )
        
        logger.info(f"[ORDER-HISTORY] Returning {len(orders)} orders")
        return orders

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting order history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trade-history")
async def get_user_trade_history(
    limit: int = 100,
    settings: Settings = Depends(get_settings),
) -> list[dict[str, Any]]:
    """
    Get user trade history from demo account.
    GET /fapi/v1/userTrades - Returns FLAT array (no wrapper)
    Fetches from ALL symbols in the account.
    """
    global _demo_engine

    if not _demo_engine or not _demo_engine.running:
        logger.warning("[TRADE-HISTORY] No active session")
        return []

    try:
        client = _demo_engine.client
        if not client or not client.connected:
            logger.error("[TRADE-HISTORY] Not connected to Binance")
            return []

        logger.info(f"[TRADE-HISTORY] Fetching limit={limit}...")
        
        all_trades = []
        symbols_to_fetch = await _collect_history_symbols(client, settings)
        logger.info(f"[TRADE-HISTORY] Symbols to fetch: {symbols_to_fetch}")
        
        # Fetch trade history for each symbol
        for symbol in symbols_to_fetch:
            try:
                trades = await client.get_trade_history(symbol=symbol, limit=limit)
                logger.debug(f"[TRADE-HISTORY] {symbol}: {len(trades)} trades")
                all_trades.extend(trades)
            except Exception as e:
                logger.warning(f"[TRADE-HISTORY] Error fetching {symbol}: {e}")
                pass

        # Sort by time descending (newest first)
        all_trades.sort(key=lambda x: x.get("time", 0), reverse=True)
        
        # Transform to flat structure with complete trade info
        trades = []
        for t in all_trades[:limit]:
            side = t.get("side")
            if not side:
                side = "BUY" if t.get("buyer") else "SELL"
            trades.append(
                {
                    "id": t.get("id"),
                    "orderId": t.get("orderId"),
                    "symbol": t.get("symbol"),
                    "side": side,
                    "price": _to_float(t.get("price")),
                    "qty": _to_float(t.get("qty")),
                    "realizedPnl": _to_float(t.get("realizedPnl")),
                    "commission": _to_float(t.get("commission")),
                    "commissionAsset": t.get("commissionAsset") or "USDT",
                    "time": t.get("time"),
                    "isMaker": bool(t.get("maker", t.get("isMaker", False))),
                }
            )
        
        logger.info(f"[TRADE-HISTORY] Returning {len(trades)} trades")
        return trades

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting trade history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/assets")
async def get_assets() -> dict[str, Any]:
    """
    Get account assets/balance from demo account.
    GET /fapi/v2/account - FLAT JSON (no wrapper)
    """
    global _demo_engine

    if not _demo_engine or not _demo_engine.running:
        logger.warning("[ASSETS] No active session")
        return {
            "wallet_balance": 0,
            "available_balance": 0,
            "unrealized_pnl": 0,
            "margin_balance": 0,
            "initial_margin": 0,
            "maintenance_margin": 0,
        }

    try:
        logger.info("[ASSETS] Fetching from Binance API...")
        client = _demo_engine.client
        if not client or not client.connected:
            logger.error("[ASSETS] Not connected to Binance")
            raise HTTPException(status_code=500, detail="Not connected to Binance")

        # Direct call to Binance API
        acc = client.client.futures_account()
        
        assets = {
            "wallet_balance": _to_float(acc.get("totalWalletBalance")),
            "available_balance": _to_float(acc.get("availableBalance")),
            "unrealized_pnl": _to_float(acc.get("totalUnrealizedProfit")),
            "margin_balance": _to_float(acc.get("totalMarginBalance")),
            "initial_margin": _to_float(acc.get("totalInitialMargin")),
            "maintenance_margin": _to_float(acc.get("totalMaintMargin")),
            "withdrawable_balance": _to_float(
                acc.get("maxWithdrawAmount", acc.get("withdrawableBalance"))
            ),
        }
        
        logger.info(f"[ASSETS] wallet_balance={assets['wallet_balance']}, "
                   f"available_balance={assets['available_balance']}")
        
        return assets

    except Exception as e:
        logger.error(f"Error getting assets: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/close-position")
async def close_position(symbol: str) -> dict[str, Any]:
    """
    Close a position for a specific symbol.
    """
    global _demo_engine

    if not _demo_engine or not _demo_engine.running:
        raise HTTPException(status_code=400, detail="No active demo session")

    try:
        result = await _demo_engine.close_position(
            symbol=symbol,
            reason="Manual close via UI",
        )

        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Failed to close position"),
            )

        return {
            "success": True,
            "message": f"Position {symbol} closed successfully",
            "data": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error closing position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reverse-position/{symbol}")
async def reverse_position(symbol: str) -> dict[str, Any]:
    """
    Reverse a position (close and open opposite side).
    """
    global _demo_engine

    if not _demo_engine or not _demo_engine.running:
        raise HTTPException(status_code=400, detail="No active demo session")

    try:
        # First close current position
        close_result = await _demo_engine.close_position(
            symbol=symbol,
            reason="Reverse position",
        )

        if not close_result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=close_result.get("error", "Failed to close position"),
            )

        # TODO: Implement opening opposite position
        # For now, just close
        
        return {
            "success": True,
            "message": f"Position {symbol} reversed (closed, opposite not implemented)",
            "data": close_result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reversing position: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cancel-order")
async def cancel_order(symbol: str, order_id: int) -> dict[str, Any]:
    """
    Cancel an open order.
    """
    global _demo_engine

    if not _demo_engine or not _demo_engine.running:
        raise HTTPException(status_code=400, detail="No active demo session")

    try:
        client = _demo_engine.client
        if not client or not client.connected:
            raise HTTPException(status_code=500, detail="Not connected to Binance")

        # Cancel order via Binance API
        result = client.client.futures_cancel_order(
            symbol=symbol,
            orderId=order_id,
        )

        return {
            "success": True,
            "message": f"Order {order_id} cancelled",
            "data": {
                "orderId": result.get("orderId"),
                "symbol": result.get("symbol"),
                "status": result.get("status"),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling order: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Force reload 1777907968.9784355
