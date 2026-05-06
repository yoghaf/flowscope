"""
Demo Execution Engine
Translates trading signals into Binance Testnet orders with V3 risk management.
"""

import logging
from typing import Any
from datetime import datetime, timezone
from decimal import Decimal

from backend.services.binance_demo.binance_client import BinanceTestnetClient
from backend.database import DatabaseManager
from backend.config import Settings

logger = logging.getLogger(__name__)


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
            self.session_id = f"demo_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            self.running = True
            self.total_trades = 0
            self.winning_trades = 0
            self.losing_trades = 0

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
            self.running = False

            # Close all open positions
            positions = await self.client.get_open_positions()
            closed_positions = []

            for pos in positions:
                side = "SELL" if pos["side"] == "LONG" else "BUY"
                result = await self.client.place_order(
                    symbol=pos["symbol"],
                    side=side,
                    quantity=pos["size"],
                    order_type="MARKET",
                )
                closed_positions.append({
                    "symbol": pos["symbol"],
                    "side": side,
                    "result": result,
                })

            # Disconnect from Binance Testnet
            await self.client.disconnect()

            # Log session end
            await self._log_session_end()

            logger.info(f"Demo trading session stopped: {self.session_id}")

            return {
                "success": True,
                "session_id": self.session_id,
                "closed_positions": closed_positions,
                "total_trades": self.total_trades,
                "winning_trades": self.winning_trades,
                "losing_trades": self.losing_trades,
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
        position_size_multiplier: float = 1.0,
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
            
            # STEP 3: Check if position already exists
            existing_position = None
            for pos in positions:
                if pos["symbol"] == symbol.upper().replace("USDT", "") + "USDT":
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

            # Determine order side
            side = "BUY" if bias == "Bullish" else "SELL"

            # Get current price if not provided
            if entry_price is None:
                entry_price = await self.client.get_current_price(symbol)
            
            if entry_price is None or entry_price <= 0:
                return {"success": False, "error": "Invalid entry price"}

            # STEP 4: V3 position sizing with balance validation
            base_risk_pct = 0.01  # 1% risk per trade
            adjusted_risk_pct = base_risk_pct * position_size_multiplier
            
            # Calculate position size based on available balance
            risk_amount = available_balance * adjusted_risk_pct
            quantity = risk_amount / entry_price if entry_price > 0 else 0
            
            if quantity <= 0:
                return {"success": False, "error": "Insufficient balance or invalid price"}
            
            # Calculate required margin (simplified: quantity * price / leverage)
            # Assuming 1x leverage for conservative sizing
            required_margin = quantity * entry_price
            
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
            logger.info(f"[EXECUTE] Placing order: {side} {quantity} {symbol} @ MARKET")
            order_result = await self.client.place_order(
                symbol=symbol,
                side=side,
                quantity=quantity,
                order_type="MARKET",
            )

            if order_result.get("error"):
                logger.error(f"[EXECUTE] Order failed: {order_result.get('error')}")
                return order_result

            # Calculate TP/SL levels
            tp_level = take_profit
            sl_level = stop_loss

            if tp_level is None and sl_level is None:
                # Auto-calculate based on setup type
                if setup_type == "Trap":
                    atr_multiplier = 2.5
                elif setup_type == "Squeeze":
                    atr_multiplier = 2.0
                else:
                    atr_multiplier = 1.5

                # Simple ATR approximation (2% of price)
                atr_approx = entry_price * 0.02
                risk = atr_approx * atr_multiplier

                if bias == "Bullish":
                    sl_level = entry_price - risk
                    tp_level = entry_price + (risk * 2.0)
                else:
                    sl_level = entry_price + risk
                    tp_level = entry_price - (risk * 2.0)

            # Log trade to database
            trade_record = {
                "session_id": self.session_id,
                "symbol": symbol,
                "signal_type": signal_type,
                "bias": bias,
                "setup_type": setup_type,
                "confidence": confidence,
                "side": side,
                "entry_price": entry_price,
                "quantity": quantity,
                "stop_loss": sl_level,
                "take_profit": tp_level,
                "position_size_multiplier": position_size_multiplier,
                "order_id": order_result.get("order_id"),
                "timestamp": datetime.now(timezone.utc),
                "status": "OPEN",
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
                "entry_price": entry_price,
                "stop_loss": sl_level,
                "take_profit": tp_level,
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

            # Update statistics
            self.total_trades += 1
            if position["unrealized_pnl"] > 0:
                self.winning_trades += 1
            elif position["unrealized_pnl"] < 0:
                self.losing_trades += 1

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

            # Calculate total unrealized PnL from positions
            total_unrealized_pnl = sum(pos.get("unrealized_pnl", 0) for pos in positions)

            # Get trade history for this session
            trade_history = await self._get_session_trades()

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
                "statistics": {
                    "total_trades": self.total_trades,
                    "winning_trades": self.winning_trades,
                    "losing_trades": self.losing_trades,
                    "winrate": (
                        self.winning_trades / self.total_trades * 100
                        if self.total_trades > 0
                        else 0
                    ),
                },
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
