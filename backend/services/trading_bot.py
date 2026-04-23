from __future__ import annotations

import asyncio
import logging
import math
from datetime import datetime, timezone

UTC = timezone.utc

from binance.client import Client
from binance.enums import (
    SIDE_BUY,
    SIDE_SELL,
    ORDER_TYPE_MARKET,
    ORDER_TYPE_STOP_MARKET,
    ORDER_TYPE_TAKE_PROFIT_MARKET,
    FUTURE_ORDER_TYPE_LIMIT,
)
from sqlalchemy import select, update

from backend.config import Settings
from backend.database import DatabaseManager
from backend.models import DemoTrade, TradeSignal

logger = logging.getLogger(__name__)

# Binance Futures Testnet/Demo URL (latest official endpoint)
TESTNET_FUTURES_URL = "https://testnet.binancefuture.com/fapi"
DEMO_FUTURES_URL = "https://demo-fapi.binance.com"


class TradingBotService:
    """Autonomous demo trading bot that executes signals on Binance Futures."""

    def __init__(self, settings: Settings, database: DatabaseManager) -> None:
        self.settings = settings
        self.database = database
        self.client: Client | None = None
        self._monitor_task: asyncio.Task | None = None
        self._running = False
        self._exchange_info: dict | None = None

    # ─── Lifecycle ────────────────────────────────────────────────

    async def start(self) -> None:
        """Initialize Binance client and start position monitor."""
        if not self.settings.demo_trading_enabled:
            logger.info("🤖 Demo trading is DISABLED. Skipping bot initialization.")
            return

        if not self.settings.binance_api_key or not self.settings.binance_api_secret:
            logger.warning("🤖 Demo trading enabled but API key/secret missing. Skipping.")
            return

        try:
            self.client = Client(
                self.settings.binance_api_key,
                self.settings.binance_api_secret,
            )
            if self.settings.demo_trading_use_testnet:
                self.client.FUTURES_URL = TESTNET_FUTURES_URL
                logger.info("🤖 Connected to Binance Futures TESTNET")
            else:
                logger.info("🤖 Connected to Binance Futures LIVE")

            # Pre-load exchange info for quantity precision
            self._exchange_info = self.client.futures_exchange_info()

            self._running = True
            self._monitor_task = asyncio.create_task(self._monitor_loop())
            logger.info("🤖 Trading bot started. Capital: $%.2f", self.settings.demo_trading_capital_usdt)
        except Exception as e:
            logger.error("🤖 Failed to initialize trading bot: %s", e)

    async def stop(self) -> None:
        """Gracefully stop the monitor loop."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("🤖 Trading bot stopped.")

    # ─── Signal Hook ──────────────────────────────────────────────

    async def on_new_signal(self, trade: TradeSignal) -> None:
        """Called by SignalService when a new V2 signal is created."""
        if not self._running or not self.client:
            return

        try:
            # Check max open positions
            open_count = await self._count_open_positions()
            if open_count >= self.settings.demo_trading_max_open_positions:
                logger.info("🤖 Max open positions (%d) reached. Skipping %s.", open_count, trade.symbol)
                return

            # Check if already have open position for this symbol
            if await self._has_open_position(trade.symbol):
                logger.info("🤖 Already have open position for %s. Skipping.", trade.symbol)
                return

            # Calculate quantity
            side = SIDE_BUY if trade.bias == "Bullish" else SIDE_SELL
            size_multiplier = getattr(trade, "position_size_multiplier", None) or 1.0
            notional = self.settings.demo_trading_base_size_usdt * size_multiplier
            entry_price = trade.entry_price

            if not entry_price or entry_price <= 0:
                logger.warning("🤖 Invalid entry price for %s. Skipping.", trade.symbol)
                return

            quantity = self._calculate_quantity(trade.symbol, notional, entry_price)
            if quantity <= 0:
                logger.warning("🤖 Calculated quantity is 0 for %s. Skipping.", trade.symbol)
                return

            logger.info(
                "🤖 EXECUTING %s %s | Qty: %.6f | Notional: $%.2f | SL: %s | TP2: %s",
                side, trade.symbol, quantity, notional,
                trade.invalidation_price, trade.target_price_2,
            )

            # 1. Place Market Order (Entry)
            entry_order = self.client.futures_create_order(
                symbol=trade.symbol,
                side=side,
                type=ORDER_TYPE_MARKET,
                quantity=quantity,
            )
            entry_order_id = str(entry_order.get("orderId", ""))
            fill_price = float(entry_order.get("avgPrice", entry_price))
            logger.info("🤖 Entry filled: %s @ %.6f (Order: %s)", trade.symbol, fill_price, entry_order_id)

            # 2. Place Stop Loss Order
            sl_order_id = None
            if trade.invalidation_price:
                sl_side = SIDE_SELL if side == SIDE_BUY else SIDE_BUY
                try:
                    sl_order = self.client.futures_create_order(
                        symbol=trade.symbol,
                        side=sl_side,
                        type=ORDER_TYPE_STOP_MARKET,
                        stopPrice=self._format_price(trade.symbol, trade.invalidation_price),
                        closePosition="true",
                    )
                    sl_order_id = str(sl_order.get("orderId", ""))
                    logger.info("🤖 SL placed: %s @ %.6f", trade.symbol, trade.invalidation_price)
                except Exception as e:
                    logger.error("🤖 Failed to place SL for %s: %s", trade.symbol, e)

            # 3. Place Take Profit Order (TP2 = full close)
            tp_order_id = None
            if trade.target_price_2:
                tp_side = SIDE_SELL if side == SIDE_BUY else SIDE_BUY
                try:
                    tp_order = self.client.futures_create_order(
                        symbol=trade.symbol,
                        side=tp_side,
                        type=ORDER_TYPE_TAKE_PROFIT_MARKET,
                        stopPrice=self._format_price(trade.symbol, trade.target_price_2),
                        closePosition="true",
                    )
                    tp_order_id = str(tp_order.get("orderId", ""))
                    logger.info("🤖 TP2 placed: %s @ %.6f", trade.symbol, trade.target_price_2)
                except Exception as e:
                    logger.error("🤖 Failed to place TP for %s: %s", trade.symbol, e)

            # 4. Save to database
            demo_trade = {
                "trade_signal_id": trade.id,
                "symbol": trade.symbol,
                "side": side,
                "entry_price": fill_price,
                "quantity": quantity,
                "notional_usdt": notional,
                "sl_price": trade.invalidation_price,
                "tp1_price": trade.target_price_1,
                "tp2_price": trade.target_price_2,
                "status": "open",
                "pnl_usdt": 0.0,
                "pnl_pct": 0.0,
                "binance_entry_order_id": entry_order_id,
                "binance_sl_order_id": sl_order_id,
                "binance_tp_order_id": tp_order_id,
                "position_size_multiplier": size_multiplier,
            }
            await self._save_demo_trade(demo_trade)
            logger.info("🤖 ✅ Demo trade saved for %s", trade.symbol)

        except Exception as e:
            logger.error("🤖 ❌ Failed to execute signal for %s: %s", trade.symbol, e, exc_info=True)
            # Save failed attempt
            await self._save_demo_trade({
                "trade_signal_id": trade.id,
                "symbol": trade.symbol,
                "side": "BUY" if trade.bias == "Bullish" else "SELL",
                "entry_price": trade.entry_price or 0,
                "quantity": 0,
                "notional_usdt": 0,
                "status": "error",
                "error_message": str(e)[:500],
            })

    # ─── Position Monitor ─────────────────────────────────────────

    async def _monitor_loop(self) -> None:
        """Background loop that checks position status every N seconds."""
        while self._running:
            try:
                await asyncio.sleep(self.settings.demo_trading_monitor_interval_seconds)
                await self._check_positions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("🤖 Monitor error: %s", e, exc_info=True)
                await asyncio.sleep(10)

    async def _check_positions(self) -> None:
        """Check Binance for filled SL/TP orders and update our records."""
        if not self.client:
            return

        open_trades = await self._list_open_trades()
        for trade in open_trades:
            try:
                # Get current position from Binance
                positions = self.client.futures_position_information(symbol=trade.symbol)
                position = next(
                    (p for p in positions if p["symbol"] == trade.symbol and float(p["positionAmt"]) != 0),
                    None,
                )

                if position is None:
                    # Position was closed (SL or TP hit)
                    await self._resolve_closed_position(trade)
                else:
                    # Position still open — update unrealized PnL
                    unrealized_pnl = float(position.get("unRealizedProfit", 0))
                    entry_price = float(position.get("entryPrice", trade.entry_price))
                    mark_price = float(position.get("markPrice", entry_price))
                    direction = 1 if trade.side == "BUY" else -1
                    pnl_pct = ((mark_price - entry_price) / entry_price) * direction * 100

                    await self._update_demo_trade(trade.id, {
                        "pnl_usdt": unrealized_pnl,
                        "pnl_pct": round(pnl_pct, 4),
                    })

            except Exception as e:
                logger.error("🤖 Error checking position %s: %s", trade.symbol, e)

    async def _resolve_closed_position(self, trade: DemoTrade) -> None:
        """Resolve a closed position by checking order fills."""
        if not self.client:
            return

        try:
            # Check all recent trades for this symbol
            fills = self.client.futures_account_trades(symbol=trade.symbol, limit=20)
            # Find the closing fill
            closing_fills = [
                f for f in fills
                if (f["side"] == "SELL" and trade.side == "BUY") or
                   (f["side"] == "BUY" and trade.side == "SELL")
            ]

            exit_price = trade.entry_price
            if closing_fills:
                # Use last closing fill as exit price
                exit_price = float(closing_fills[-1]["price"])

            direction = 1 if trade.side == "BUY" else -1
            pnl_pct = ((exit_price - trade.entry_price) / trade.entry_price) * direction * 100
            pnl_usdt = trade.notional_usdt * (pnl_pct / 100)

            # Determine result
            result = "win" if pnl_pct > 0.05 else ("loss" if pnl_pct < -0.05 else "breakeven")

            # Determine close reason by checking which order was filled
            close_reason = "Unknown"
            if trade.binance_sl_order_id:
                try:
                    sl_order = self.client.futures_get_order(
                        symbol=trade.symbol, orderId=int(trade.binance_sl_order_id)
                    )
                    if sl_order.get("status") == "FILLED":
                        close_reason = "Stop Loss"
                except Exception:
                    pass
            if trade.binance_tp_order_id and close_reason == "Unknown":
                try:
                    tp_order = self.client.futures_get_order(
                        symbol=trade.symbol, orderId=int(trade.binance_tp_order_id)
                    )
                    if tp_order.get("status") == "FILLED":
                        close_reason = "Take Profit"
                except Exception:
                    pass

            await self._update_demo_trade(trade.id, {
                "status": "closed",
                "result": result,
                "exit_price": exit_price,
                "pnl_usdt": round(pnl_usdt, 4),
                "pnl_pct": round(pnl_pct, 4),
                "closed_at": datetime.now(UTC),
                "close_reason": close_reason,
            })

            # Cancel any remaining open orders for this symbol
            try:
                self.client.futures_cancel_all_open_orders(symbol=trade.symbol)
            except Exception:
                pass

            logger.info(
                "🤖 Position CLOSED: %s | %s | PnL: $%.2f (%.2f%%) | Reason: %s",
                trade.symbol, result.upper(), pnl_usdt, pnl_pct, close_reason,
            )

        except Exception as e:
            logger.error("🤖 Error resolving position %s: %s", trade.symbol, e)

    # ─── Manual Actions ───────────────────────────────────────────

    async def close_position(self, demo_trade_id: int) -> dict:
        """Manually close a demo trade position."""
        if not self.client:
            return {"error": "Bot not connected"}

        trade = await self._get_demo_trade(demo_trade_id)
        if not trade or trade.status != "open":
            return {"error": "Trade not found or already closed"}

        try:
            close_side = SIDE_SELL if trade.side == "BUY" else SIDE_BUY
            self.client.futures_create_order(
                symbol=trade.symbol,
                side=close_side,
                type=ORDER_TYPE_MARKET,
                quantity=trade.quantity,
            )
            # Cancel pending orders
            try:
                self.client.futures_cancel_all_open_orders(symbol=trade.symbol)
            except Exception:
                pass

            await self._resolve_closed_position(trade)
            return {"success": True, "message": f"Position {trade.symbol} closed."}
        except Exception as e:
            return {"error": str(e)}

    # ─── Quantity & Precision ─────────────────────────────────────

    def _calculate_quantity(self, symbol: str, notional_usdt: float, price: float) -> float:
        """Calculate order quantity respecting Binance lot size rules."""
        raw_qty = notional_usdt / price

        # Find precision from exchange info
        precision = 3  # default
        if self._exchange_info:
            for s in self._exchange_info.get("symbols", []):
                if s["symbol"] == symbol:
                    for f in s.get("filters", []):
                        if f["filterType"] == "LOT_SIZE":
                            step_size = float(f["stepSize"])
                            precision = max(0, int(round(-math.log10(step_size))))
                            break
                    break

        qty = math.floor(raw_qty * (10 ** precision)) / (10 ** precision)
        return qty

    def _format_price(self, symbol: str, price: float) -> str:
        """Format price to the correct tick size for Binance."""
        precision = 2  # default
        if self._exchange_info:
            for s in self._exchange_info.get("symbols", []):
                if s["symbol"] == symbol:
                    for f in s.get("filters", []):
                        if f["filterType"] == "PRICE_FILTER":
                            tick_size = float(f["tickSize"])
                            precision = max(0, int(round(-math.log10(tick_size))))
                            break
                    break
        return f"{price:.{precision}f}"

    # ─── Database Helpers ─────────────────────────────────────────

    async def _save_demo_trade(self, data: dict) -> int | None:
        try:
            async with self.database.session_factory() as session:
                demo = DemoTrade(**data)
                session.add(demo)
                await session.commit()
                await session.refresh(demo)
                return demo.id
        except Exception as e:
            logger.error("🤖 Failed to save demo trade: %s", e)
            return None

    async def _update_demo_trade(self, trade_id: int, data: dict) -> None:
        try:
            async with self.database.session_factory() as session:
                await session.execute(
                    update(DemoTrade).where(DemoTrade.id == trade_id).values(**data)
                )
                await session.commit()
        except Exception as e:
            logger.error("🤖 Failed to update demo trade %d: %s", trade_id, e)

    async def _get_demo_trade(self, trade_id: int) -> DemoTrade | None:
        try:
            async with self.database.session_factory() as session:
                result = await session.execute(
                    select(DemoTrade).where(DemoTrade.id == trade_id)
                )
                return result.scalars().first()
        except Exception:
            return None

    async def _list_open_trades(self) -> list[DemoTrade]:
        try:
            async with self.database.session_factory() as session:
                result = await session.execute(
                    select(DemoTrade).where(DemoTrade.status == "open")
                )
                return list(result.scalars().all())
        except Exception:
            return []

    async def _count_open_positions(self) -> int:
        try:
            async with self.database.session_factory() as session:
                result = await session.execute(
                    select(DemoTrade).where(DemoTrade.status == "open")
                )
                return len(result.scalars().all())
        except Exception:
            return 0

    async def _has_open_position(self, symbol: str) -> bool:
        try:
            async with self.database.session_factory() as session:
                result = await session.execute(
                    select(DemoTrade).where(
                        DemoTrade.status == "open",
                        DemoTrade.symbol == symbol,
                    )
                )
                return result.scalars().first() is not None
        except Exception:
            return False

    async def list_all_trades(self, status: str = "all", limit: int = 50) -> list[DemoTrade]:
        """List demo trades for the API."""
        try:
            async with self.database.session_factory() as session:
                query = select(DemoTrade).order_by(DemoTrade.id.desc()).limit(limit)
                if status == "open":
                    query = query.where(DemoTrade.status == "open")
                elif status == "closed":
                    query = query.where(DemoTrade.status == "closed")
                result = await session.execute(query)
                return list(result.scalars().all())
        except Exception:
            return []

    async def get_stats(self) -> dict:
        """Get aggregate stats for the demo trading dashboard."""
        try:
            all_trades = await self.list_all_trades(status="all", limit=500)
            closed = [t for t in all_trades if t.status == "closed"]
            open_trades = [t for t in all_trades if t.status == "open"]

            wins = [t for t in closed if t.result == "win"]
            losses = [t for t in closed if t.result == "loss"]

            total_pnl = sum(t.pnl_usdt for t in closed)
            win_rate = len(wins) / len(closed) * 100 if closed else 0
            avg_win = sum(t.pnl_usdt for t in wins) / len(wins) if wins else 0
            avg_loss = sum(t.pnl_usdt for t in losses) / len(losses) if losses else 0
            current_capital = self.settings.demo_trading_capital_usdt + total_pnl

            return {
                "capital": round(current_capital, 2),
                "initial_capital": self.settings.demo_trading_capital_usdt,
                "total_pnl": round(total_pnl, 2),
                "total_pnl_pct": round(total_pnl / self.settings.demo_trading_capital_usdt * 100, 2),
                "total_trades": len(closed),
                "open_positions": len(open_trades),
                "wins": len(wins),
                "losses": len(losses),
                "win_rate": round(win_rate, 1),
                "avg_win": round(avg_win, 2),
                "avg_loss": round(avg_loss, 2),
                "bot_enabled": self.settings.demo_trading_enabled,
                "use_testnet": self.settings.demo_trading_use_testnet,
                "base_size": self.settings.demo_trading_base_size_usdt,
                "max_positions": self.settings.demo_trading_max_open_positions,
            }
        except Exception as e:
            logger.error("🤖 Failed to get stats: %s", e)
            return {"error": str(e)}
