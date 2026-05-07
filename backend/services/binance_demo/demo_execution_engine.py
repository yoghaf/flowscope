"""
Demo Execution Engine
Translates trading signals into Binance Testnet orders with V3 risk management.
"""

import logging
import asyncio
from typing import Any
from datetime import datetime, timezone
from collections import defaultdict

from backend.services.binance_demo.binance_client import BinanceTestnetClient
from backend.database import DatabaseManager
from backend.config import Settings

logger = logging.getLogger(__name__)

UTC = timezone.utc
VALUE_EPSILON = 1e-9
STATS_CACHE_TTL_SECONDS = 30
DEMO_STATS_SYMBOLS = (
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
ENTRY_MODE_MARKET_ONLY = "market_only"
ENTRY_MODE_MARKET_PULLBACK_LIMIT = "market_pullback_limit"
DEFAULT_MAX_ENTRY_DRIFT_PCT = 10.0
DEFAULT_MAX_MARKET_TP1_PROGRESS_PCT = 30.0
DEFAULT_MAX_PULLBACK_TP1_PROGRESS_PCT = 60.0


class DemoExecutionEngine:
    """
    Execution engine for demo trading on Binance Testnet.
    Implements V3 adaptive risk management.
    """

    def __init__(
        self,
        client: BinanceTestnetClient,
        database: DatabaseManager,
        settings: Settings,
    ) -> None:
        """
        Initialize demo execution engine.

        Args:
            client: Binance Testnet client
            database: Database manager for trade logging
            settings: Application settings
        """
        self.client = client
        self.database = database
        self.settings = settings
        self.running = False
        self.session_id: str | None = None
        self.initial_balance: float = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self._connected = False
        self.started_at: datetime | None = None
        self._start_position_qty: dict[str, float] = {}
        self._statistics_cache: dict[str, Any] | None = None
        self._statistics_cache_at: datetime | None = None
        self._managed_positions: dict[str, dict[str, Any]] = {}
        self._pending_entries: dict[str, dict[str, Any]] = {}
        self._protection_task: asyncio.Task[None] | None = None

    async def is_healthy(self) -> bool:
        """
        Check if the execution engine is healthy and connected.
        
        Returns:
            True if engine is running and Binance connection is active
        """
        if not self.running:
            return False
        
        if not self.client or not self.client.connected:
            return False
        
        # Try to ping Binance API to verify connection
        try:
            await self.client.get_account_state()
            return True
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False

    async def start_session(self, initial_balance: float | None = None) -> dict[str, Any]:
        """
        Start a new demo trading session.

        Args:
            initial_balance: Deprecated. Actual Binance wallet balance is used.

        Returns:
            Session information dictionary
        """
        try:
            # Connect to Binance Testnet
            connected = await self.client.connect()
            if not connected:
                return {"success": False, "error": "Failed to connect to Binance Testnet"}

            balance_info = await self.client.get_balance()
            binance_wallet_balance = float(balance_info.get("total_wallet_balance", 0.0))
            self.initial_balance = binance_wallet_balance
            self.started_at = datetime.now(UTC)
            self.session_id = f"demo_{self.started_at.strftime('%Y%m%d_%H%M%S')}"
            self.running = True
            self.total_trades = 0
            self.winning_trades = 0
            self.losing_trades = 0
            self._statistics_cache = None
            self._statistics_cache_at = None
            self._start_position_qty = await self._snapshot_open_position_qty()
            self._managed_positions = {}
            self._pending_entries = {}
            self._protection_task = asyncio.create_task(self._protection_loop())

            # Log session start
            await self._log_session_start(self.initial_balance)

            logger.info(f"Demo trading session started: {self.session_id}")

            return {
                "success": True,
                "session_id": self.session_id,
                "initial_balance": self.initial_balance,
                "current_balance": binance_wallet_balance,
            }

        except Exception as e:
            logger.error(f"Error starting demo session: {e}")
            return {"success": False, "error": str(e)}

    async def stop_session(self) -> dict[str, Any]:
        """
        Stop the current demo trading session.

        Returns:
            Session summary dictionary
        """
        try:
            await self._cancel_all_pending_entries(reason="Stop Demo")

            # Close all open positions
            positions = await self.client.get_open_positions()
            closed_positions = []

            for pos in positions:
                result = await self.close_position(
                    symbol=pos["symbol"],
                    reason="Stop Demo",
                )
                closed_positions.append({
                    "symbol": pos["symbol"],
                    "result": result,
                })

            stats = await self._calculate_statistics(positions=[], force_refresh=True)
            self.running = False
            await self._stop_protection_loop()

            # Disconnect from Binance Testnet
            await self.client.disconnect()

            # Log session end
            await self._log_session_end()

            logger.info(f"Demo trading session stopped: {self.session_id}")

            return {
                "success": True,
                "session_id": self.session_id,
                "closed_positions": closed_positions,
                "total_trades": stats["total_trades"],
                "winning_trades": stats["winning_trades"],
                "losing_trades": stats["losing_trades"],
            }

        except Exception as e:
            logger.error(f"Error stopping demo session: {e}")
            return {"success": False, "error": str(e)}

    async def execute_signal(
        self,
        symbol: str,
        signal_type: str,
        bias: str,
        setup_type: str,
        confidence: float,
        entry_price: float | None = None,
        stop_loss: float | None = None,
        take_profit: float | None = None,
        take_profit_1: float | None = None,
        take_profit_2: float | None = None,
        position_size_multiplier: float = 1.0,
        risk_usdt: float | None = None,
        max_slippage_pct: float | None = None,
        max_entry_drift_pct: float | None = DEFAULT_MAX_ENTRY_DRIFT_PCT,
        max_market_tp1_progress_pct: float | None = DEFAULT_MAX_MARKET_TP1_PROGRESS_PCT,
        max_pullback_tp1_progress_pct: float | None = DEFAULT_MAX_PULLBACK_TP1_PROGRESS_PCT,
        entry_mode: str = ENTRY_MODE_MARKET_PULLBACK_LIMIT,
        tp1_close_pct: float = 50.0,
    ) -> dict[str, Any]:
        """
        Execute a trading signal on Binance Testnet.
        Uses BOTH position and account data for validation.

        EXECUTION FLOW:
        1. Fetch latest account + positions
        2. Check: IF available_balance <= 0 → REJECT trade
        3. Check position: IF exists → manage, ELSE → open new
        4. Validate: available_balance > required_margin before order

        Args:
            symbol: Trading pair symbol
            signal_type: "Continuation", "Trap", "Squeeze", etc.
            bias: "Bullish" or "Bearish"
            setup_type: Setup type from execution engine
            confidence: Signal confidence score
            entry_price: Optional entry price
            stop_loss: Optional stop loss price
            take_profit: Optional take profit price
            position_size_multiplier: V3 dynamic position sizing multiplier
            risk_usdt: Fixed USDT risk amount. If provided with stop_loss,
                quantity is sized so SL loss approximates this value.
            max_slippage_pct: Deprecated absolute price guard, used only when
                SL-based drift cannot be calculated.
            max_entry_drift_pct: Reject market entry when adverse movement from
                planned entry exceeds this percentage of SL risk distance.
            max_market_tp1_progress_pct: Reject market entry when price has
                already moved this far toward TP1.
            max_pullback_tp1_progress_pct: Keep/allow pullback limit only while
                TP1 progress stays below this threshold.
            entry_mode: "market_only" or "market_pullback_limit".
            tp1_close_pct: Percentage closed at TP1 when TP1/TP2 are available.

        Returns:
            Execution result dictionary
        """
        if not self.running:
            return {"success": False, "error": "Demo session not running"}

        try:
            # STEP 1: Fetch latest account + positions atomically
            logger.info(f"[EXECUTE] Fetching full state for signal: {symbol} {bias}")
            full_state = await self.client.get_full_state()
            
            account = full_state["account"]
            positions = full_state["positions"]
            
            # Extract balance fields
            available_balance = account["available_balance"]
            wallet_balance = account["wallet_balance"]
            unrealized_pnl = account["total_unrealized_pnl"]
            
            # DEBUG: Print account state
            logger.info(f"[EXECUTE] Account: wallet={wallet_balance:.2f}, "
                       f"available={available_balance:.2f}, unrealized_pnl={unrealized_pnl:.2f}")
            logger.info(f"[EXECUTE] Found {len(positions)} open positions")
            
            # STEP 2: Validation - Check available balance
            if available_balance <= 0:
                error_msg = f"REJECTED: available_balance={available_balance:.2f} <= 0"
                logger.error(f"[EXECUTE] {error_msg}")
                return {"success": False, "error": error_msg}
            
            # 🧪 STATE VALIDATION: Check for inconsistencies
            # If wallet_balance is 0 but we expect positions, flag inconsistency
            if wallet_balance == 0 and len(positions) > 0:
                logger.warning(f"[EXECUTE] ⚠️ INCONSISTENCY: wallet_balance=0 but {len(positions)} positions exist")
                logger.warning(f"[EXECUTE] Resetting local assumption - trusting Binance state")
            
            # If available_balance is null/None, ERROR and STOP
            if available_balance is None:
                error_msg = "REJECTED: available_balance is NULL - Binance API error"
                logger.error(f"[EXECUTE] 🚨 {error_msg}")
                return {"success": False, "error": error_msg}
            
            clean_symbol = self._normalize_symbol(symbol) or symbol.upper()

            # STEP 3: Check if position or pending entry already exists
            existing_position = None
            for pos in positions:
                if self._normalize_symbol(pos.get("symbol")) == clean_symbol:
                    existing_position = pos
                    break
            
            if existing_position:
                logger.info(f"[EXECUTE] Position exists for {symbol}: "
                           f"{existing_position['side']} {existing_position['size']}")
                # Position management logic (hold / close / reverse)
                # For now, we'll reject new signals on existing positions
                return {
                    "success": False,
                    "error": f"Position already exists for {symbol}",
                    "existing_position": existing_position,
                }
            else:
                logger.info(f"[EXECUTE] No existing position for {symbol}, opening new")

            if clean_symbol in self._pending_entries:
                return {
                    "success": False,
                    "error": f"Pending demo entry already exists for {clean_symbol}",
                    "pending_entry": self._pending_entries[clean_symbol],
                }

            # Determine order side
            side = "BUY" if bias == "Bullish" else "SELL"
            close_side = "SELL" if side == "BUY" else "BUY"
            if bias not in {"Bullish", "Bearish"}:
                return {"success": False, "error": f"Unsupported bias for demo execution: {bias}"}

            # Get current price if not provided
            current_price = await self.client.get_current_price(clean_symbol)
            if entry_price is None:
                entry_price = current_price
            
            if entry_price is None or entry_price <= 0:
                return {"success": False, "error": "Invalid entry price"}
            if current_price is None or current_price <= 0:
                current_price = entry_price

            # Calculate TP/SL levels before entry decision so market and
            # fallback limit can use the same risk structure.
            tp1_level = take_profit_1 or take_profit
            tp2_level = take_profit_2 or take_profit
            tp_level = tp2_level or tp1_level
            sl_level = stop_loss

            if tp_level is None and sl_level is None:
                sl_level, tp1_level, tp2_level = self._auto_trade_levels(
                    bias=bias,
                    setup_type=setup_type,
                    entry_price=entry_price,
                )
                tp_level = tp2_level or tp1_level

            entry_decision = self._entry_decision(
                bias=bias,
                current_price=current_price,
                entry_price=entry_price,
                stop_loss=sl_level,
                take_profit_1=tp1_level,
                max_slippage_pct=max_slippage_pct,
                max_entry_drift_pct=max_entry_drift_pct,
                max_market_tp1_progress_pct=max_market_tp1_progress_pct,
                max_pullback_tp1_progress_pct=max_pullback_tp1_progress_pct,
                entry_mode=entry_mode,
            )

            use_pullback_limit = False
            planned_order_type = "MARKET"
            order_price_basis = current_price
            if not entry_decision["market_allowed"]:
                if entry_decision["pullback_allowed"]:
                    use_pullback_limit = True
                    planned_order_type = "LIMIT"
                    order_price_basis = entry_price
                    logger.info(
                        "[EXECUTE] %s market skipped, placing pullback limit: %s",
                        clean_symbol,
                        entry_decision["market_reasons"],
                    )
                else:
                    return {
                        "success": False,
                        "error": (
                            f"Entry guard rejected {clean_symbol}: "
                            f"{'; '.join(entry_decision['market_reasons'] + entry_decision['pullback_reasons'])}"
                        ),
                        "entry_decision": entry_decision,
                    }

            # STEP 4: V3 position sizing with balance validation
            if risk_usdt is not None and risk_usdt > 0 and sl_level is not None:
                risk_per_unit = abs(order_price_basis - sl_level)
                if risk_per_unit <= VALUE_EPSILON:
                    return {"success": False, "error": "Invalid risk distance: entry and SL are too close"}
                risk_amount = risk_usdt * position_size_multiplier
                quantity = risk_amount / risk_per_unit
            else:
                base_risk_pct = 0.01  # 1% risk per trade
                adjusted_risk_pct = base_risk_pct * position_size_multiplier
                risk_amount = available_balance * adjusted_risk_pct
                quantity = risk_amount / order_price_basis if order_price_basis > 0 else 0
            
            if quantity <= 0:
                return {"success": False, "error": "Insufficient balance or invalid price"}
            
            # Calculate required margin (simplified: quantity * price / leverage)
            # Assuming 1x leverage for conservative sizing
            required_margin = quantity * order_price_basis
            
            # STEP 5: Validate available_balance > required_margin
            if available_balance < required_margin:
                error_msg = (f"REJECTED: available_balance ({available_balance:.2f}) < "
                           f"required_margin ({required_margin:.2f})")
                logger.error(f"[EXECUTE] {error_msg}")
                return {"success": False, "error": error_msg}
            
            # 🧪 STATE VALIDATION: Double-check position state
            if existing_position is None and len(positions) == 0:
                logger.info(f"[EXECUTE] ✅ State consistent: No existing positions, opening new")
            elif existing_position:
                logger.info(f"[EXECUTE] ✅ State consistent: Managing existing position")
            
            logger.info(f"[EXECUTE] Order validation passed: "
                       f"quantity={quantity:.4f}, required_margin={required_margin:.2f}")

            # Place order on Binance Testnet
            logger.info(
                "[EXECUTE] Placing order: %s %.8f %s @ %s",
                side,
                quantity,
                clean_symbol,
                planned_order_type if planned_order_type == "MARKET" else f"LIMIT {entry_price:.8f}",
            )
            order_result = await self.client.place_order(
                symbol=clean_symbol,
                side=side,
                quantity=quantity,
                order_type=planned_order_type,
                price=entry_price if use_pullback_limit else None,
            )

            if order_result.get("error"):
                logger.error(f"[EXECUTE] Order failed: {order_result.get('error')}")
                return order_result

            if use_pullback_limit:
                pending_entry = {
                    "symbol": clean_symbol,
                    "order_id": order_result.get("order_id"),
                    "side": side,
                    "close_side": close_side,
                    "bias": bias,
                    "quantity": quantity,
                    "entry_price": entry_price,
                    "stop_loss": sl_level,
                    "take_profit": tp_level,
                    "take_profit_1": tp1_level,
                    "take_profit_2": tp2_level,
                    "tp1_close_pct": tp1_close_pct,
                    "signal_type": signal_type,
                    "setup_type": setup_type,
                    "confidence": confidence,
                    "position_size_multiplier": position_size_multiplier,
                    "risk_usdt": risk_usdt,
                    "max_entry_drift_pct": max_entry_drift_pct,
                    "max_market_tp1_progress_pct": max_market_tp1_progress_pct,
                    "max_pullback_tp1_progress_pct": max_pullback_tp1_progress_pct,
                    "entry_mode": entry_mode,
                    "entry_decision": entry_decision,
                    "status": "PENDING_LIMIT",
                    "created_at": datetime.now(UTC).isoformat(),
                }
                self._pending_entries[clean_symbol] = pending_entry
                return {
                    "success": True,
                    "pending": True,
                    "order_id": order_result.get("order_id"),
                    "symbol": clean_symbol,
                    "side": side,
                    "quantity": quantity,
                    "entry_price": entry_price,
                    "stop_loss": sl_level,
                    "take_profit": tp_level,
                    "take_profit_1": tp1_level,
                    "take_profit_2": tp2_level,
                    "risk_usdt": risk_usdt,
                    "entry_decision": entry_decision,
                    "message": (
                        f"Market entry skipped for {clean_symbol}; pullback limit placed at "
                        f"{entry_price:.8f}"
                    ),
                    "timestamp": datetime.now(UTC),
                }

            actual_entry_price = (
                float(order_result.get("avg_price") or 0)
                or float(order_result.get("price") or 0)
                or current_price
            )

            protective = await self._place_protective_orders(
                symbol=clean_symbol,
                close_side=close_side,
                quantity=quantity,
                entry_price=actual_entry_price,
                stop_loss=sl_level,
                take_profit_1=tp1_level,
                take_profit_2=tp2_level,
                tp1_close_pct=tp1_close_pct,
            )

            # Log trade to database
            trade_record = {
                "session_id": self.session_id,
                "symbol": clean_symbol,
                "signal_type": signal_type,
                "bias": bias,
                "setup_type": setup_type,
                "confidence": confidence,
                "side": side,
                "entry_price": actual_entry_price,
                "quantity": quantity,
                "stop_loss": sl_level,
                "take_profit": tp_level,
                "position_size_multiplier": position_size_multiplier,
                "order_id": order_result.get("order_id"),
                "timestamp": datetime.now(timezone.utc),
                "status": "OPEN",
                "extra_data": {
                    "planned_entry_price": entry_price,
                    "actual_entry_price": actual_entry_price,
                    "risk_usdt": risk_usdt,
                    "max_slippage_pct": max_slippage_pct,
                    "max_entry_drift_pct": max_entry_drift_pct,
                    "max_market_tp1_progress_pct": max_market_tp1_progress_pct,
                    "max_pullback_tp1_progress_pct": max_pullback_tp1_progress_pct,
                    "entry_mode": entry_mode,
                    "entry_decision": entry_decision,
                    "tp1_close_pct": tp1_close_pct,
                    "take_profit_1": tp1_level,
                    "take_profit_2": tp2_level,
                    "protective": protective,
                },
            }

            await self._save_trade(trade_record)

            logger.info(
                f"Executed {signal_type} {bias} signal on {symbol}: "
                f"{side} {quantity} @ {entry_price}"
            )

            return {
                "success": True,
                "order_id": order_result.get("order_id"),
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "entry_price": actual_entry_price,
                "stop_loss": sl_level,
                "take_profit": tp_level,
                "take_profit_1": tp1_level,
                "take_profit_2": tp2_level,
                "risk_usdt": risk_usdt,
                "protected": protective.get("protected", False),
                "protective": protective,
                "entry_decision": entry_decision,
                "timestamp": trade_record["timestamp"],
            }

        except Exception as e:
            logger.error(f"Error executing signal: {e}")
            return {"success": False, "error": str(e)}

    async def close_position(
        self,
        symbol: str,
        reason: str = "Manual Close",
    ) -> dict[str, Any]:
        """
        Close an open position.

        Args:
            symbol: Trading pair symbol
            reason: Reason for closing

        Returns:
            Close result dictionary
        """
        try:
            positions = await self.client.get_open_positions()
            position = None

            for pos in positions:
                if pos["symbol"] == symbol.upper():
                    position = pos
                    break

            if not position:
                return {"success": False, "error": f"No open position for {symbol}"}

            # Close position
            side = "SELL" if position["side"] == "LONG" else "BUY"
            close_result = await self.client.place_order(
                symbol=position["symbol"],
                side=side,
                quantity=position["size"],
                order_type="MARKET",
            )

            if close_result.get("error"):
                return close_result

            # Update trade record
            await self._update_trade_on_close(
                symbol=symbol,
                exit_price=close_result.get("price", position["mark_price"]),
                pnl=position["unrealized_pnl"],
                reason=reason,
            )
            await self._cancel_symbol_orders(symbol)
            clean_symbol = self._normalize_symbol(symbol) or symbol.upper()
            self._managed_positions.pop(clean_symbol, None)
            self._pending_entries.pop(clean_symbol, None)

            # Update statistics
            self.total_trades += 1
            if position["unrealized_pnl"] > 0:
                self.winning_trades += 1
            elif position["unrealized_pnl"] < 0:
                self.losing_trades += 1
            self._statistics_cache = None
            self._statistics_cache_at = None

            logger.info(f"Closed position for {symbol}: {reason}, PnL: {position['unrealized_pnl']}")

            return {
                "success": True,
                "symbol": symbol,
                "exit_price": close_result.get("price"),
                "pnl": position["unrealized_pnl"],
                "reason": reason,
            }

        except Exception as e:
            logger.error(f"Error closing position: {e}")
            return {"success": False, "error": str(e)}

    async def get_status(self) -> dict[str, Any]:
        """
        Get current demo trading status.
        Uses BOTH /fapi/v2/account (balance) and /fapi/v2/positionRisk (positions).

        Returns:
            Status dictionary with positions, balance, and statistics
        """
        try:
            # Fetch full state from Binance (both account + positions)
            full_state = await self.client.get_full_state()
            account = full_state["account"]
            positions = full_state["positions"]
            await self._reconcile_managed_positions(positions)
            await self._reconcile_pending_entries(positions)

            # Calculate total unrealized PnL from positions
            total_unrealized_pnl = sum(pos.get("unrealized_pnl", 0) for pos in positions)

            # Get trade history for this session
            trade_history = await self._get_session_trades()
            statistics = await self._calculate_statistics(positions=positions)

            status = {
                "session_id": self.session_id,
                "running": self.running,
                "initial_balance": self.initial_balance,
                # Account state from /fapi/v2/account
                "current_balance": account["wallet_balance"],
                "available_balance": account["available_balance"],
                "total_unrealized_pnl": account["total_unrealized_pnl"],
                "margin_balance": account["margin_balance"],
                # Position state from /fapi/v2/positionRisk
                "positions": positions,
                "positions_count": len(positions),
                "statistics": statistics,
                "protection": list(self._managed_positions.values()),
                "pending_entries": list(self._pending_entries.values()),
                "recent_trades": trade_history[:10],
            }
            
            logger.debug(f"[STATUS] Balance: {status['current_balance']:.2f}, "
                        f"Available: {status['available_balance']:.2f}, "
                        f"Positions: {len(positions)}")

            return status

        except Exception as e:
            logger.error(f"Error getting status: {e}")
            # Return explicit error state (no silent fallback)
            return {
                "session_id": self.session_id,
                "running": self.running,
                "error": str(e),
                "current_balance": None,  # Explicit null - no fallback
                "available_balance": None,
            }

    def _auto_trade_levels(
        self,
        *,
        bias: str,
        setup_type: str,
        entry_price: float,
    ) -> tuple[float, float, float]:
        if setup_type == "Trap":
            atr_multiplier = 2.5
        elif setup_type == "Squeeze":
            atr_multiplier = 2.0
        else:
            atr_multiplier = 1.5

        atr_approx = entry_price * 0.02
        risk = atr_approx * atr_multiplier
        if bias == "Bullish":
            stop_loss = entry_price - risk
            take_profit = entry_price + (risk * 2.0)
        else:
            stop_loss = entry_price + risk
            take_profit = entry_price - (risk * 2.0)
        return stop_loss, take_profit, take_profit

    def _entry_decision(
        self,
        *,
        bias: str,
        current_price: float,
        entry_price: float,
        stop_loss: float | None,
        take_profit_1: float | None,
        max_slippage_pct: float | None,
        max_entry_drift_pct: float | None,
        max_market_tp1_progress_pct: float | None,
        max_pullback_tp1_progress_pct: float | None,
        entry_mode: str,
    ) -> dict[str, Any]:
        metrics = self._entry_progress_metrics(
            bias=bias,
            current_price=current_price,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit_1=take_profit_1,
        )
        market_reasons: list[str] = []
        pullback_reasons: list[str] = []

        if metrics["sl_touched"]:
            market_reasons.append("price already touched SL before entry")
            pullback_reasons.append("price already touched SL before entry")

        drift_pct = metrics["entry_drift_pct_of_risk"]
        if max_entry_drift_pct is not None:
            if drift_pct is None:
                market_reasons.append("SL risk distance unavailable for entry drift guard")
            elif drift_pct > max_entry_drift_pct:
                market_reasons.append(
                    f"entry drift {drift_pct:.2f}% of SL risk > max {max_entry_drift_pct:.2f}%"
                )
        elif max_slippage_pct is not None and max_slippage_pct >= 0:
            legacy_slippage_pct = metrics["entry_drift_pct_of_price"]
            if legacy_slippage_pct > max_slippage_pct:
                market_reasons.append(
                    f"legacy slippage {legacy_slippage_pct:.4f}% > max {max_slippage_pct:.4f}%"
                )

        market_progress = metrics["tp1_progress_pct"]
        if max_market_tp1_progress_pct is not None:
            if market_progress is None:
                market_reasons.append("TP1 progress unavailable for market guard")
            elif market_progress > max_market_tp1_progress_pct:
                market_reasons.append(
                    f"TP1 progress {market_progress:.2f}% > market max {max_market_tp1_progress_pct:.2f}%"
                )

        if entry_mode != ENTRY_MODE_MARKET_PULLBACK_LIMIT:
            pullback_reasons.append("pullback limit mode disabled")
        if metrics["risk_distance"] is None:
            pullback_reasons.append("SL risk distance unavailable for pullback limit")

        pullback_progress = metrics["tp1_progress_pct"]
        if max_pullback_tp1_progress_pct is not None:
            if pullback_progress is None:
                pullback_reasons.append("TP1 progress unavailable for pullback limit guard")
            elif pullback_progress >= max_pullback_tp1_progress_pct:
                pullback_reasons.append(
                    f"TP1 progress {pullback_progress:.2f}% >= pullback max {max_pullback_tp1_progress_pct:.2f}%"
                )

        if metrics["tp1_touched"]:
            pullback_reasons.append("TP1 already touched before entry")

        return {
            "market_allowed": not market_reasons,
            "pullback_allowed": not pullback_reasons,
            "market_reasons": market_reasons,
            "pullback_reasons": pullback_reasons,
            "metrics": metrics,
        }

    def _entry_progress_metrics(
        self,
        *,
        bias: str,
        current_price: float,
        entry_price: float,
        stop_loss: float | None,
        take_profit_1: float | None,
    ) -> dict[str, Any]:
        direction = 1 if bias == "Bullish" else -1
        adverse_move = max((current_price - entry_price) * direction, 0.0)
        risk_distance = (
            abs(entry_price - stop_loss)
            if stop_loss is not None and stop_loss > 0
            else None
        )
        tp1_distance = (
            abs(take_profit_1 - entry_price)
            if take_profit_1 is not None and take_profit_1 > 0
            else None
        )
        tp1_direction_valid = (
            take_profit_1 is not None
            and ((take_profit_1 - entry_price) * direction) > VALUE_EPSILON
        )

        entry_drift_pct_of_risk = (
            adverse_move / risk_distance * 100
            if risk_distance is not None and risk_distance > VALUE_EPSILON
            else None
        )
        tp1_progress_pct = (
            adverse_move / tp1_distance * 100
            if tp1_direction_valid and tp1_distance is not None and tp1_distance > VALUE_EPSILON
            else None
        )
        sl_touched = (
            stop_loss is not None
            and ((current_price - stop_loss) * direction) <= VALUE_EPSILON
        )
        tp1_touched = (
            tp1_direction_valid
            and take_profit_1 is not None
            and ((current_price - take_profit_1) * direction) >= -VALUE_EPSILON
        )

        return {
            "current_price": current_price,
            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "take_profit_1": take_profit_1,
            "adverse_move": adverse_move,
            "risk_distance": risk_distance,
            "tp1_distance": tp1_distance,
            "entry_drift_pct_of_risk": entry_drift_pct_of_risk,
            "entry_drift_pct_of_price": abs(current_price - entry_price) / entry_price * 100,
            "tp1_progress_pct": tp1_progress_pct,
            "sl_touched": sl_touched,
            "tp1_touched": bool(tp1_touched),
        }

    async def _protection_loop(self) -> None:
        """Backend fallback monitor for TP1 -> breakeven stop management."""
        while self.running:
            try:
                needs_reconcile = self._managed_positions or self._pending_entries
                if needs_reconcile and self.client and getattr(self.client, "connected", False):
                    positions = await self.client.get_open_positions()
                    await self._reconcile_managed_positions(positions)
                    await self._reconcile_pending_entries(positions)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("[DEMO PROTECTION] Background protection loop failed")
            await asyncio.sleep(3)

    async def _stop_protection_loop(self) -> None:
        task = self._protection_task
        self._protection_task = None
        if task is None or task.done():
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    async def _reconcile_pending_entries(self, positions: list[dict[str, Any]]) -> None:
        """Protect filled pullback limits and cancel stale-by-structure entries."""
        if not self._pending_entries:
            return

        by_symbol = {
            self._normalize_symbol(position.get("symbol")): position
            for position in positions
            if self._normalize_symbol(position.get("symbol"))
        }

        for symbol, meta in list(self._pending_entries.items()):
            position = by_symbol.get(symbol)
            if position is not None:
                await self._activate_filled_pending_entry(symbol=symbol, meta=meta, position=position)
                continue

            current_price = await self.client.get_current_price(symbol)
            if current_price is None or current_price <= 0:
                logger.warning("[DEMO ENTRY] Invalid current price while monitoring %s", symbol)
                continue
            metrics = self._entry_progress_metrics(
                bias=str(meta.get("bias") or "Bullish"),
                current_price=current_price,
                entry_price=self._to_float(meta.get("entry_price")),
                stop_loss=self._to_float(meta.get("stop_loss"), default=None),
                take_profit_1=self._to_float(meta.get("take_profit_1"), default=None),
            )
            max_pullback_progress = self._to_float(
                meta.get("max_pullback_tp1_progress_pct"),
                DEFAULT_MAX_PULLBACK_TP1_PROGRESS_PCT,
            )
            if metrics["sl_touched"]:
                await self._cancel_pending_entry(symbol=symbol, meta=meta, reason="SL touched before entry")
                continue
            progress_pct = metrics["tp1_progress_pct"]
            if progress_pct is not None and progress_pct >= max_pullback_progress:
                await self._cancel_pending_entry(
                    symbol=symbol,
                    meta=meta,
                    reason=f"TP1 progress {progress_pct:.2f}% >= {max_pullback_progress:.2f}%",
                )
                continue

            if not await self._pending_entry_order_is_open(symbol=symbol, meta=meta):
                logger.info("[DEMO ENTRY] Pending entry for %s no longer open; removing local state", symbol)
                self._pending_entries.pop(symbol, None)

    async def _activate_filled_pending_entry(
        self,
        *,
        symbol: str,
        meta: dict[str, Any],
        position: dict[str, Any],
    ) -> None:
        quantity = self._to_float(position.get("size")) or self._to_float(meta.get("quantity"))
        entry_price = self._to_float(position.get("entry_price")) or self._to_float(meta.get("entry_price"))
        if quantity <= VALUE_EPSILON or entry_price <= VALUE_EPSILON:
            return

        protective = await self._place_protective_orders(
            symbol=symbol,
            close_side=str(meta.get("close_side") or ""),
            quantity=quantity,
            entry_price=entry_price,
            stop_loss=self._to_float(meta.get("stop_loss"), default=None),
            take_profit_1=self._to_float(meta.get("take_profit_1"), default=None),
            take_profit_2=self._to_float(meta.get("take_profit_2"), default=None),
            tp1_close_pct=self._to_float(meta.get("tp1_close_pct"), 50.0),
        )
        await self._save_trade(
            {
                "session_id": self.session_id,
                "symbol": symbol,
                "signal_type": meta.get("signal_type"),
                "bias": meta.get("bias"),
                "setup_type": meta.get("setup_type"),
                "confidence": meta.get("confidence"),
                "side": meta.get("side"),
                "entry_price": entry_price,
                "quantity": quantity,
                "stop_loss": meta.get("stop_loss"),
                "take_profit": meta.get("take_profit"),
                "position_size_multiplier": meta.get("position_size_multiplier"),
                "order_id": meta.get("order_id"),
                "timestamp": datetime.now(UTC),
                "status": "OPEN",
                "extra_data": {
                    "entry_mode": ENTRY_MODE_MARKET_PULLBACK_LIMIT,
                    "planned_entry_price": meta.get("entry_price"),
                    "actual_entry_price": entry_price,
                    "risk_usdt": meta.get("risk_usdt"),
                    "take_profit_1": meta.get("take_profit_1"),
                    "take_profit_2": meta.get("take_profit_2"),
                    "protective": protective,
                    "filled_from_pending_limit": True,
                },
            }
        )
        self._pending_entries.pop(symbol, None)
        logger.info("[DEMO ENTRY] %s pullback limit filled; protective orders armed", symbol)

    async def _pending_entry_order_is_open(self, *, symbol: str, meta: dict[str, Any]) -> bool:
        order_id = meta.get("order_id")
        if order_id is None:
            return True
        try:
            open_orders = await self.client.get_open_orders(symbol=symbol)
        except Exception as exc:
            logger.warning("[DEMO ENTRY] Failed to verify pending order for %s: %s", symbol, exc)
            return True

        for order in open_orders:
            current_id = order.get("orderId", order.get("order_id"))
            if current_id is not None and int(current_id) == int(order_id):
                return True
        return False

    async def _cancel_pending_entry(self, *, symbol: str, meta: dict[str, Any], reason: str) -> None:
        order_id = meta.get("order_id")
        if order_id is not None:
            result = await self.client.cancel_order(symbol=symbol, order_id=int(order_id))
            if result.get("error"):
                logger.warning("[DEMO ENTRY] Failed to cancel pending entry %s: %s", symbol, result.get("error"))
        self._pending_entries.pop(symbol, None)
        logger.info("[DEMO ENTRY] Pending entry for %s cancelled: %s", symbol, reason)

    async def _cancel_all_pending_entries(self, *, reason: str) -> None:
        for symbol, meta in list(self._pending_entries.items()):
            await self._cancel_pending_entry(symbol=symbol, meta=meta, reason=reason)

    async def _place_protective_orders(
        self,
        *,
        symbol: str,
        close_side: str,
        quantity: float,
        entry_price: float,
        stop_loss: float | None,
        take_profit_1: float | None,
        take_profit_2: float | None,
        tp1_close_pct: float,
    ) -> dict[str, Any]:
        """Place reduce-only SL/TP orders after market entry.

        Uses ``CONTRACT_PRICE`` (last-price) as the trigger type so that
        protective orders fire on the same price feed the signal engine
        uses to detect TP/SL hits.  ``MARK_PRICE`` (the previous default)
        often diverges on testnet, causing TP orders to never trigger.
        """
        clean_symbol = self._normalize_symbol(symbol) or symbol.upper()
        # Use CONTRACT_PRICE so TP/SL trigger on last-traded price (same as
        # the candle-based price the signal engine evaluates against).
        protective_working_type = "CONTRACT_PRICE"
        result: dict[str, Any] = {
            "protected": False,
            "tp1_armed": False,
            "tp2_armed": False,
            "warnings": [],
            "orders": {},
        }

        if quantity <= VALUE_EPSILON:
            result["warnings"].append("quantity_too_small")
            return result

        tp1_pct = max(1.0, min(99.0, tp1_close_pct)) / 100
        split_targets = (
            take_profit_1 is not None
            and take_profit_2 is not None
            and abs(take_profit_1 - take_profit_2) > VALUE_EPSILON
        )
        tp1_qty_raw = quantity * tp1_pct if split_targets else quantity
        # Round partial quantities to symbol lot-size to avoid Binance
        # LOT_SIZE filter rejections on the split TP orders.
        tp1_qty = await self.client._round_quantity(clean_symbol, tp1_qty_raw)
        tp2_qty_raw = max(quantity - tp1_qty, 0.0) if split_targets else 0.0
        tp2_qty = await self.client._round_quantity(clean_symbol, tp2_qty_raw) if tp2_qty_raw > VALUE_EPSILON else 0.0
        sl_order_id: int | None = None
        tp1_order_id: int | None = None
        tp2_order_id: int | None = None

        logger.info(
            "[PROTECTIVE] %s placing SL/TP: qty=%.8f tp1_qty=%.8f tp2_qty=%.8f "
            "SL=%s TP1=%s TP2=%s workingType=%s",
            clean_symbol, quantity, tp1_qty, tp2_qty,
            stop_loss, take_profit_1, take_profit_2, protective_working_type,
        )

        if stop_loss is not None:
            sl_order = await self.client.place_order(
                symbol=clean_symbol,
                side=close_side,
                quantity=quantity,
                order_type="STOP_MARKET",
                stop_price=stop_loss,
                reduce_only=True,
                working_type=protective_working_type,
            )
            result["orders"]["sl"] = sl_order
            if sl_order.get("error"):
                result["warnings"].append(f"sl_failed:{sl_order.get('error')}")
                logger.error("[PROTECTIVE] %s SL order FAILED: %s", clean_symbol, sl_order.get("error"))
            else:
                sl_order_id = sl_order.get("order_id")
                result["protected"] = True
                logger.info("[PROTECTIVE] %s SL armed at %.8f (order_id=%s)", clean_symbol, stop_loss, sl_order_id)

        if take_profit_1 is not None:
            tp1_order = await self.client.place_order(
                symbol=clean_symbol,
                side=close_side,
                quantity=tp1_qty,
                order_type="TAKE_PROFIT_MARKET",
                stop_price=take_profit_1,
                reduce_only=True,
                working_type=protective_working_type,
            )
            result["orders"]["tp1"] = tp1_order
            if tp1_order.get("error"):
                result["warnings"].append(f"tp1_failed:{tp1_order.get('error')}")
                logger.error("[PROTECTIVE] %s TP1 order FAILED: %s", clean_symbol, tp1_order.get("error"))
            else:
                tp1_order_id = tp1_order.get("order_id")
                result["tp1_armed"] = True
                logger.info("[PROTECTIVE] %s TP1 armed at %.8f qty=%.8f (order_id=%s)", clean_symbol, take_profit_1, tp1_qty, tp1_order_id)

        if split_targets and take_profit_2 is not None and tp2_qty > VALUE_EPSILON:
            tp2_order = await self.client.place_order(
                symbol=clean_symbol,
                side=close_side,
                quantity=tp2_qty,
                order_type="TAKE_PROFIT_MARKET",
                stop_price=take_profit_2,
                reduce_only=True,
                working_type=protective_working_type,
            )
            result["orders"]["tp2"] = tp2_order
            if tp2_order.get("error"):
                result["warnings"].append(f"tp2_failed:{tp2_order.get('error')}")
                logger.error("[PROTECTIVE] %s TP2 order FAILED: %s", clean_symbol, tp2_order.get("error"))
            else:
                tp2_order_id = tp2_order.get("order_id")
                result["tp2_armed"] = True
                logger.info("[PROTECTIVE] %s TP2 armed at %.8f qty=%.8f (order_id=%s)", clean_symbol, take_profit_2, tp2_qty, tp2_order_id)

        # Summarize protective order placement
        armed_count = sum([result["protected"], result["tp1_armed"], result["tp2_armed"]])
        if result["warnings"]:
            logger.warning("[PROTECTIVE] %s %d/%d orders armed, warnings: %s", clean_symbol, armed_count, 3 if split_targets else 2, result["warnings"])
        else:
            logger.info("[PROTECTIVE] %s all %d protective orders armed successfully", clean_symbol, armed_count)

        self._managed_positions[clean_symbol] = {
            "symbol": clean_symbol,
            "close_side": close_side,
            "entry_price": entry_price,
            "initial_qty": quantity,
            "tp1_qty": tp1_qty if split_targets else 0.0,
            "remaining_qty": tp2_qty if split_targets else quantity,
            "sl_order_id": sl_order_id,
            "tp1_order_id": tp1_order_id,
            "tp2_order_id": tp2_order_id,
            "tp1_price": take_profit_1,
            "tp2_price": take_profit_2,
            "tp1_hit": False,
            "be_stop_order_id": None,
            "created_at": datetime.now(UTC).isoformat(),
        }
        return result

    async def _reconcile_managed_positions(self, positions: list[dict[str, Any]]) -> None:
        """Move SL to breakeven after TP1 partial close is observed.

        Also acts as a **fallback TP monitor**: if the current price has
        already surpassed TP1 but the position is still at full size
        (meaning the TP order never fired or was rejected), we execute
        the TP1 partial close via an immediate market order so the
        position is not left unprotected.
        """
        if not self._managed_positions:
            return

        by_symbol = {
            self._normalize_symbol(position.get("symbol")): position
            for position in positions
            if self._normalize_symbol(position.get("symbol"))
        }
        for symbol, meta in list(self._managed_positions.items()):
            position = by_symbol.get(symbol)
            if position is None:
                self._managed_positions.pop(symbol, None)
                continue
            if meta.get("tp1_hit"):
                continue

            tp1_qty = self._to_float(meta.get("tp1_qty"))
            initial_qty = self._to_float(meta.get("initial_qty"))
            current_qty = self._to_float(position.get("size"))
            if tp1_qty <= VALUE_EPSILON or initial_qty <= VALUE_EPSILON:
                continue

            expected_after_tp1 = max(initial_qty - tp1_qty, 0.0)
            tp1_observed = (
                current_qty > VALUE_EPSILON
                and current_qty <= expected_after_tp1 + max(initial_qty * 0.01, VALUE_EPSILON)
            )
            if tp1_observed:
                await self._move_stop_to_breakeven(symbol=symbol, meta=meta, remaining_qty=current_qty)
                continue

            # --- Fallback TP monitor ---
            # Position is still at full size. Check if price already passed
            # TP1 — if so, the TAKE_PROFIT_MARKET order probably failed.
            await self._fallback_tp_check(symbol=symbol, meta=meta, current_qty=current_qty)

    async def _move_stop_to_breakeven(
        self,
        *,
        symbol: str,
        meta: dict[str, Any],
        remaining_qty: float,
    ) -> None:
        entry_price = self._to_float(meta.get("entry_price"))
        close_side = str(meta.get("close_side") or "")
        if entry_price <= VALUE_EPSILON or remaining_qty <= VALUE_EPSILON or close_side not in {"BUY", "SELL"}:
            return

        # Use CONTRACT_PRICE to match the protective order trigger type.
        protective_working_type = "CONTRACT_PRICE"
        old_sl_order_id = meta.get("sl_order_id")
        be_order = await self.client.place_order(
            symbol=symbol,
            side=close_side,
            quantity=remaining_qty,
            order_type="STOP_MARKET",
            stop_price=entry_price,
            reduce_only=True,
            working_type=protective_working_type,
        )
        if be_order.get("error") and old_sl_order_id:
            await self.client.cancel_order(symbol=symbol, order_id=int(old_sl_order_id))
            be_order = await self.client.place_order(
                symbol=symbol,
                side=close_side,
                quantity=remaining_qty,
                order_type="STOP_MARKET",
                stop_price=entry_price,
                reduce_only=True,
                working_type=protective_working_type,
            )
        elif old_sl_order_id:
            await self.client.cancel_order(symbol=symbol, order_id=int(old_sl_order_id))

        if not be_order.get("error"):
            meta["tp1_hit"] = True
            meta["be_stop_order_id"] = be_order.get("order_id")
            meta["sl_order_id"] = be_order.get("order_id")
            meta["remaining_qty"] = remaining_qty
            meta["moved_to_be_at"] = datetime.now(UTC).isoformat()
            logger.info("[DEMO PROTECTION] %s TP1 observed, SL moved to BE at %.8f", symbol, entry_price)
        else:
            logger.error("[DEMO PROTECTION] Failed to move %s SL to BE: %s", symbol, be_order.get("error"))

    async def _fallback_tp_check(
        self,
        *,
        symbol: str,
        meta: dict[str, Any],
        current_qty: float,
    ) -> None:
        """Active TP monitoring fallback.

        Called when position is still at full size (TP order didn't fire).
        Fetches current price and checks if TP1 has been passed — if so,
        executes an immediate market close for the TP1 portion and moves
        SL to breakeven.

        This covers the gap where TAKE_PROFIT_MARKET orders fail due to
        LOT_SIZE rejections, API errors, or mark/contract price divergence.
        """
        tp1_price = self._to_float(meta.get("tp1_price"), default=0.0)
        tp1_qty = self._to_float(meta.get("tp1_qty"))
        close_side = str(meta.get("close_side") or "")
        if tp1_price <= VALUE_EPSILON or tp1_qty <= VALUE_EPSILON:
            return
        if close_side not in {"BUY", "SELL"}:
            return

        current_price = await self.client.get_current_price(symbol)
        if current_price is None or current_price <= 0:
            return

        # Determine if price has passed TP1 based on position direction.
        # close_side == "SELL" means original position is LONG → TP1 hit when price >= tp1_price
        # close_side == "BUY" means original position is SHORT → TP1 hit when price <= tp1_price
        tp1_passed = (
            (close_side == "SELL" and current_price >= tp1_price)
            or (close_side == "BUY" and current_price <= tp1_price)
        )
        if not tp1_passed:
            return

        logger.warning(
            "[DEMO PROTECTION] %s FALLBACK TP1: price %.8f has passed TP1 %.8f "
            "but position still at full size %.8f — executing market close for TP1 portion",
            symbol, current_price, tp1_price, current_qty,
        )

        # Cancel the stale TP1 order if it exists
        tp1_order_id = meta.get("tp1_order_id")
        if tp1_order_id is not None:
            cancel_result = await self.client.cancel_order(symbol=symbol, order_id=int(tp1_order_id))
            if cancel_result.get("error"):
                logger.warning("[DEMO PROTECTION] %s failed to cancel stale TP1 order %s: %s",
                             symbol, tp1_order_id, cancel_result.get("error"))

        # Round the TP1 quantity for the market close
        rounded_tp1_qty = await self.client._round_quantity(symbol, tp1_qty)
        if rounded_tp1_qty <= VALUE_EPSILON:
            logger.error("[DEMO PROTECTION] %s TP1 qty rounded to zero, skipping fallback close", symbol)
            return

        # Execute market close for TP1 portion
        close_result = await self.client.place_order(
            symbol=symbol,
            side=close_side,
            quantity=rounded_tp1_qty,
            order_type="MARKET",
            reduce_only=True,
        )

        if close_result.get("error"):
            logger.error(
                "[DEMO PROTECTION] %s FALLBACK TP1 market close FAILED: %s",
                symbol, close_result.get("error"),
            )
            return

        logger.info(
            "[DEMO PROTECTION] %s FALLBACK TP1 market close SUCCESS: "
            "closed %.8f @ market (TP1 target was %.8f, actual price ~%.8f)",
            symbol, rounded_tp1_qty, tp1_price, current_price,
        )

        # Now move SL to breakeven for the remaining position
        remaining_qty = max(current_qty - rounded_tp1_qty, 0.0)
        if remaining_qty > VALUE_EPSILON:
            await self._move_stop_to_breakeven(
                symbol=symbol,
                meta=meta,
                remaining_qty=remaining_qty,
            )
        else:
            # Entire position was the TP1 portion (no split targets)
            meta["tp1_hit"] = True
            meta["remaining_qty"] = 0.0
            logger.info("[DEMO PROTECTION] %s FALLBACK: full position closed at TP1", symbol)

    async def _cancel_symbol_orders(self, symbol: str) -> None:
        clean_symbol = self._normalize_symbol(symbol) or symbol.upper()
        try:
            await self.client.cancel_all_open_orders(clean_symbol)
        except Exception as exc:
            logger.warning("[DEMO PROTECTION] Failed to cancel open orders for %s: %s", clean_symbol, exc)

    async def _snapshot_open_position_qty(self) -> dict[str, float]:
        """Capture positions that already exist when the demo session starts."""
        try:
            positions = await self.client.get_open_positions()
        except Exception as exc:
            logger.warning("Failed to snapshot start positions for demo stats: %s", exc)
            return {}

        snapshot: dict[str, float] = {}
        for position in positions:
            symbol = self._normalize_symbol(position.get("symbol"))
            if not symbol:
                continue
            qty = self._to_float(position.get("size"))
            if qty <= VALUE_EPSILON:
                continue
            signed_qty = qty if position.get("side") == "LONG" else -qty
            snapshot[symbol] = snapshot.get(symbol, 0.0) + signed_qty
        return snapshot

    async def _calculate_statistics(
        self,
        *,
        positions: list[dict[str, Any]],
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Calculate completed-trade stats from Binance fills, not local counters.

        Binance user trades are fill-level rows. For honest WR, we rebuild
        position cycles per symbol and count a trade only after net position
        returns to zero. Partial TP fills are tracked separately.
        """
        now = datetime.now(UTC)
        if (
            not force_refresh
            and self._statistics_cache is not None
            and self._statistics_cache_at is not None
            and (now - self._statistics_cache_at).total_seconds() < STATS_CACHE_TTL_SECONDS
        ):
            cached = dict(self._statistics_cache)
            cached["open_positions"] = len(positions)
            return cached

        fallback = self._fallback_statistics(open_positions=len(positions))
        if not self.client or not getattr(self.client, "connected", False):
            return fallback

        try:
            symbols = await self._statistics_symbols(positions)
            start_time_ms = (
                int(self.started_at.timestamp() * 1000)
                if self.started_at is not None
                else None
            )

            fills: list[dict[str, Any]] = []
            for symbol in symbols:
                try:
                    fills.extend(
                        await self.client.get_trade_history(
                            symbol=symbol,
                            limit=1000,
                            start_time=start_time_ms,
                        )
                    )
                except Exception as exc:
                    logger.warning("[DEMO STATS] Failed to fetch fills for %s: %s", symbol, exc)

            stats = self._summarize_position_cycles(fills=fills, open_positions=len(positions))
            self.total_trades = int(stats["total_trades"])
            self.winning_trades = int(stats["winning_trades"])
            self.losing_trades = int(stats["losing_trades"])
            self._statistics_cache = dict(stats)
            self._statistics_cache_at = now
            return stats
        except Exception as exc:
            logger.warning("[DEMO STATS] Falling back to local counters: %s", exc)
            return fallback

    async def _statistics_symbols(self, positions: list[dict[str, Any]]) -> list[str]:
        symbols: list[Any] = []
        symbols.extend(position.get("symbol") for position in positions)
        symbols.extend(self._start_position_qty.keys())
        symbols.extend(getattr(self.settings, "default_symbols", []) or [])
        symbols.extend(DEMO_STATS_SYMBOLS)

        for trade in await self._get_session_trades():
            symbols.append(trade.get("symbol"))

        return self._dedupe_symbols(symbols)

    def _summarize_position_cycles(
        self,
        *,
        fills: list[dict[str, Any]],
        open_positions: int,
    ) -> dict[str, Any]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for fill in fills:
            symbol = self._normalize_symbol(fill.get("symbol"))
            if not symbol:
                continue
            grouped[symbol].append(fill)

        completed: list[dict[str, Any]] = []
        partial_closes = 0
        raw_fills = 0
        realized_pnl = 0.0

        for symbol, symbol_fills in grouped.items():
            symbol_fills.sort(
                key=lambda fill: (
                    int(self._to_float(fill.get("time"), 0)),
                    int(self._to_float(fill.get("id"), 0)),
                )
            )
            net_qty = self._start_position_qty.get(symbol, 0.0)
            cycle_pnl = 0.0
            cycle_fills = 0
            cycle_started_at: int | None = (
                int(self.started_at.timestamp() * 1000)
                if net_qty and self.started_at is not None
                else None
            )
            last_fill_at: int | None = None

            for fill in symbol_fills:
                qty = abs(self._to_float(fill.get("qty")))
                if qty <= VALUE_EPSILON:
                    continue

                side = str(fill.get("side") or "").upper()
                if side not in {"BUY", "SELL"}:
                    continue

                signed_qty = qty if side == "BUY" else -qty
                previous_qty = net_qty
                fill_realized = self._to_float(fill.get("realizedPnl"))
                fill_time = int(self._to_float(fill.get("time"), 0))

                if abs(previous_qty) <= VALUE_EPSILON:
                    cycle_pnl = 0.0
                    cycle_fills = 0
                    cycle_started_at = fill_time or cycle_started_at

                is_reducing = previous_qty * signed_qty < -VALUE_EPSILON

                cycle_pnl += fill_realized
                realized_pnl += fill_realized
                raw_fills += 1
                cycle_fills += 1
                net_qty = previous_qty + signed_qty
                last_fill_at = fill_time or last_fill_at

                if is_reducing and abs(net_qty) > VALUE_EPSILON and previous_qty * net_qty > VALUE_EPSILON:
                    partial_closes += 1

                if abs(net_qty) <= VALUE_EPSILON and cycle_fills > 0:
                    completed.append(
                        {
                            "symbol": symbol,
                            "pnl": cycle_pnl,
                            "started_at": cycle_started_at,
                            "closed_at": last_fill_at,
                            "fills": cycle_fills,
                        }
                    )
                    cycle_pnl = 0.0
                    cycle_fills = 0
                    cycle_started_at = None
                    net_qty = 0.0
                elif previous_qty * net_qty < -VALUE_EPSILON:
                    completed.append(
                        {
                            "symbol": symbol,
                            "pnl": cycle_pnl,
                            "started_at": cycle_started_at,
                            "closed_at": last_fill_at,
                            "fills": cycle_fills,
                        }
                    )
                    cycle_pnl = 0.0
                    cycle_fills = 1
                    cycle_started_at = fill_time or last_fill_at

        wins = sum(1 for trade in completed if trade["pnl"] > VALUE_EPSILON)
        losses = sum(1 for trade in completed if trade["pnl"] < -VALUE_EPSILON)
        breakevens = len(completed) - wins - losses
        winrate_base = wins + losses
        winrate = (wins / winrate_base * 100) if winrate_base else 0.0

        return {
            "total_trades": len(completed),
            "closed_trades": len(completed),
            "winning_trades": wins,
            "losing_trades": losses,
            "breakeven_trades": breakevens,
            "open_positions": open_positions,
            "partial_closes": partial_closes,
            "raw_fills": raw_fills,
            "realized_pnl": round(realized_pnl, 8),
            "winrate": round(winrate, 4),
            "winrate_basis": "closed_position_cycles",
        }

    def _fallback_statistics(self, *, open_positions: int) -> dict[str, Any]:
        winrate = (
            self.winning_trades / self.total_trades * 100
            if self.total_trades > 0
            else 0.0
        )
        return {
            "total_trades": self.total_trades,
            "closed_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "breakeven_trades": 0,
            "open_positions": open_positions,
            "partial_closes": 0,
            "raw_fills": 0,
            "realized_pnl": 0.0,
            "winrate": winrate,
            "winrate_basis": "local_counter_fallback",
        }

    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        try:
            if value in (None, ""):
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _normalize_symbol(symbol: Any) -> str | None:
        if not symbol:
            return None
        normalized = str(symbol).upper().strip()
        if not normalized:
            return None
        return normalized if normalized.endswith("USDT") else f"{normalized}USDT"

    @classmethod
    def _dedupe_symbols(cls, symbols: list[Any]) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for symbol in symbols:
            normalized = cls._normalize_symbol(symbol)
            if normalized and normalized not in seen:
                seen.add(normalized)
                deduped.append(normalized)
        return deduped

    async def _save_trade(self, trade_record: dict[str, Any]) -> None:
        """Save trade record to database."""
        try:
            if self.database.enabled:
                await self.database.save_demo_trade(trade_record)
        except Exception as e:
            logger.error(f"Error saving trade to database: {e}")

    async def _update_trade_on_close(
        self,
        symbol: str,
        exit_price: float,
        pnl: float,
        reason: str,
    ) -> None:
        """Update trade record on close."""
        try:
            if self.database.enabled:
                await self.database.update_demo_trade(
                    symbol=symbol,
                    exit_price=exit_price,
                    pnl=pnl,
                    reason=reason,
                    status="CLOSED",
                )
        except Exception as e:
            logger.error(f"Error updating trade: {e}")

    async def _get_session_trades(self) -> list[dict[str, Any]]:
        """Get trade history for current session."""
        try:
            if self.database.enabled and self.session_id:
                return await self.database.get_demo_trades_by_session(self.session_id)
            return []
        except Exception as e:
            logger.error(f"Error getting session trades: {e}")
            return []

    async def _log_session_start(self, initial_balance: float) -> None:
        """Log session start to database."""
        try:
            if self.database.enabled:
                await self.database.log_demo_session_start(
                    session_id=self.session_id,
                    initial_balance=initial_balance,
                )
        except Exception as e:
            logger.error(f"Error logging session start: {e}")

    async def _log_session_end(self) -> None:
        """Log session end to database."""
        try:
            if self.database.enabled:
                await self.database.log_demo_session_end(
                    session_id=self.session_id,
                    total_trades=self.total_trades,
                    winning_trades=self.winning_trades,
                    losing_trades=self.losing_trades,
                )
        except Exception as e:
            logger.error(f"Error logging session end: {e}")
