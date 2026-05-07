"""
Binance Testnet Client
Handles connection to Binance Testnet API for paper trading.
"""

import logging
import asyncio
from typing import Any
from datetime import datetime, timezone
from decimal import Decimal

try:
    from binance.client import Client
    from binance.exceptions import BinanceAPIException
except ImportError:
    Client = None
    BinanceAPIException = None

logger = logging.getLogger(__name__)

UTC = timezone.utc
BINANCE_TESTNET_URL = "https://testnet.binancefuture.com"
BINANCE_TESTNET_WS_URL = "wss://testnet.binancefuture.com/ws"

# Retry configuration
MAX_CONNECT_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # seconds


class BinanceTestnetClient:
    """Client for Binance Testnet futures trading."""

    def __init__(self, api_key: str, api_secret: str) -> None:
        """
        Initialize Binance Testnet client.

        Args:
            api_key: Binance Testnet API key
            api_secret: Binance Testnet API secret
        """
        if Client is None:
            raise ImportError(
                "python-binance not installed. Run: pip install python-binance"
            )

        self.api_key = api_key
        self.api_secret = api_secret
        self.client: Client | None = None
        self.connected = False

    async def connect(self) -> bool:
        """
        Establish connection to Binance Testnet with retry logic.

        Uses ping=False to skip the constructor's spot testnet ping
        (which fails when spot testnet is down, even if futures testnet is up).
        Validates connection via futures_ping + futures_account instead.

        Returns:
            True if connection successful, False otherwise
        """
        for attempt in range(1, MAX_CONNECT_RETRIES + 1):
            try:
                # ping=False: Skip constructor spot ping — spot testnet
                # is frequently down and unrelated to futures testnet.
                self.client = Client(
                    api_key=self.api_key,
                    api_secret=self.api_secret,
                    testnet=True,
                    ping=False,
                )

                # Step 1: Verify futures testnet is reachable
                logger.info(f"[CONNECT] Attempt {attempt}/{MAX_CONNECT_RETRIES}: Pinging futures testnet...")
                self.client.futures_ping()

                # Step 2: Verify API credentials by fetching account
                logger.info("[CONNECT] Futures ping OK, verifying account credentials...")
                account_info = self.client.futures_account()

                self.connected = True
                wallet = float(account_info.get("totalWalletBalance", 0))
                logger.info(f"[CONNECT] ✅ Successfully connected to Binance Futures Testnet (wallet: ${wallet:.2f})")
                return True

            except Exception as e:
                error_msg = str(e)
                is_502 = "502" in error_msg or "Bad Gateway" in error_msg
                is_retryable = is_502 or "timeout" in error_msg.lower() or "connection" in error_msg.lower()

                if is_retryable and attempt < MAX_CONNECT_RETRIES:
                    wait_time = RETRY_BACKOFF_BASE ** attempt
                    logger.warning(
                        f"[CONNECT] Attempt {attempt}/{MAX_CONNECT_RETRIES} failed "
                        f"({'502 Bad Gateway - Testnet may be down' if is_502 else error_msg}). "
                        f"Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    if is_502:
                        logger.error(
                            f"[CONNECT] ❌ Binance Futures Testnet is DOWN (502 Bad Gateway). "
                            f"This is a Binance server issue, not a code bug. "
                            f"Check status at: https://testnet.binancefuture.com"
                        )
                    else:
                        logger.error(f"[CONNECT] ❌ Failed to connect after {attempt} attempts: {e}")
                    self.connected = False
                    return False

        self.connected = False
        return False

    async def disconnect(self) -> None:
        """Close connection to Binance Testnet."""
        if self.client:
            self.client.close_connection()
        self.connected = False
        logger.info("Disconnected from Binance Testnet")

    async def get_account_state(self) -> dict[str, Any]:
        """
        Get complete account state from /fapi/v2/account.
        Used for balance validation and risk control.

        Returns:
            Dictionary with full account state
        """
        if not self.connected:
            raise RuntimeError("Not connected to Binance Testnet")

        try:
            account_info = self.client.futures_account()
            
            # Extract ALL balance fields from account endpoint
            # Binance Futures API field names: https://binance-docs.github.io/apidocs/futures/en/#account-information-v2-user_data
            account_state = {
                "wallet_balance": float(account_info.get("totalWalletBalance", 0)),
                "available_balance": float(account_info.get("availableBalance", 0)),
                "total_unrealized_pnl": float(account_info.get("totalUnrealizedProfit", 0)),
                "margin_balance": float(account_info.get("totalMarginBalance", 0)),
                "initial_margin": float(account_info.get("totalInitialMargin", 0)),
                "maint_margin": float(account_info.get("totalMaintMargin", 0)),
                "withdrawable_balance": float(account_info.get("withdrawableBalance", 0)),
            }
            
            # DEBUG: Print account state
            logger.info(f"[ACCOUNT STATE] wallet_balance={account_state['wallet_balance']:.2f}, "
                       f"available_balance={account_state['available_balance']:.2f}, "
                       f"unrealized_pnl={account_state['total_unrealized_pnl']:.2f}")
            
            return account_state
            
        except BinanceAPIException as e:
            logger.error(f"Error getting account state: {e}")
            raise RuntimeError(f"Failed to fetch account balance from Binance: {e}")

    async def get_balance(self) -> dict[str, float]:
        """
        Get account balance information (legacy wrapper).
        Deprecated: Use get_account_state() instead.
        """
        account_state = await self.get_account_state()
        return {
            "total_wallet_balance": account_state["wallet_balance"],
            "available_balance": account_state["available_balance"],
            "total_unrealized_pnl": account_state["total_unrealized_pnl"],
            "total_margin_balance": account_state["margin_balance"],
        }

    async def get_full_state(self) -> dict[str, Any]:
        """
        Fetch BOTH account state and positions atomically.
        This ensures we have consistent data for decision making.

        Returns:
            Complete state: {
                "account": {wallet_balance, available_balance, ...},
                "positions": [{symbol, side, size, ...}]
            }
        """
        if not self.connected:
            raise RuntimeError("Not connected to Binance Testnet")

        try:
            # Fetch account state from /fapi/v2/account
            account_state = await self.get_account_state()
            
            # Fetch positions from /fapi/v2/positionRisk
            positions = await self.get_open_positions()
            
            logger.info(f"[FULL STATE] account.wallet={account_state['wallet_balance']:.2f}, "
                       f"account.available={account_state['available_balance']:.2f}, "
                       f"positions.count={len(positions)}")
            
            return {
                "account": account_state,
                "positions": positions,
            }
            
        except Exception as e:
            logger.error(f"Error fetching full state: {e}")
            raise

    async def get_open_positions(self) -> list[dict[str, Any]]:
        """
        Get all open positions from /fapi/v2/positionRisk.
        Used for execution state validation.

        Returns:
            List of position dictionaries
        """
        if not self.connected:
            raise RuntimeError("Not connected to Binance Testnet")

        try:
            positions = self.client.futures_position_information()
            open_positions = []

            for pos in positions:
                position_amt = float(pos.get("positionAmt", 0))
                if position_amt != 0:
                    position_data = {
                        "symbol": pos.get("symbol"),
                        "side": "LONG" if position_amt > 0 else "SHORT",
                        "size": abs(position_amt),
                        "entry_price": float(pos.get("entryPrice", 0)),
                        "mark_price": float(pos.get("markPrice", 0)),
                        "unrealized_pnl": float(pos.get("unRealizedProfit", 0)),
                        "leverage": int(pos.get("leverage", 1)),
                        "position_amt": position_amt,  # Raw position amount
                        "notional": float(pos.get("notional", 0)),
                        "timestamp": datetime.now(UTC),
                    }
                    open_positions.append(position_data)
                    logger.debug(f"[POSITION] {position_data['symbol']}: "
                               f"{position_data['side']} {position_data['size']} @ "
                               f"{position_data['entry_price']}, PnL={position_data['unrealized_pnl']:.2f}")

            logger.info(f"[POSITIONS] Found {len(open_positions)} open positions")
            return open_positions
            
        except BinanceAPIException as e:
            logger.error(f"Error getting positions: {e}")
            raise RuntimeError(f"Failed to fetch positions from Binance: {e}")

    async def place_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "MARKET",
        price: float | None = None,
        stop_price: float | None = None,
        time_in_force: str = "GTC",
        reduce_only: bool = False,
        working_type: str | None = "MARK_PRICE",
        new_order_resp_type: str | None = "RESULT",
    ) -> dict[str, Any]:
        """
        Place an order on Binance Testnet.

        Args:
            symbol: Trading pair symbol (e.g., "BTCUSDT")
            side: "BUY" or "SELL"
            quantity: Order quantity
            order_type: "MARKET", "LIMIT", "STOP_MARKET", "TAKE_PROFIT_MARKET"
            price: Limit price (required for LIMIT orders)
            stop_price: Stop price (required for STOP orders)
            time_in_force: Time in force for limit orders

        Returns:
            Order response dictionary
        """
        if not self.connected:
            raise RuntimeError("Not connected to Binance Testnet")

        try:
            # Normalize symbol
            symbol = symbol.upper().replace("USDT", "") + "USDT"

            # Round quantity to appropriate precision
            quantity = await self._round_quantity(symbol, quantity)

            order_params = {
                "symbol": symbol,
                "side": side,
                "type": order_type,
                "quantity": quantity,
            }
            if reduce_only:
                order_params["reduceOnly"] = "true"
            if new_order_resp_type:
                order_params["newOrderRespType"] = new_order_resp_type

            if order_type in ["LIMIT", "STOP_LIMIT"]:
                if price is None:
                    raise ValueError("Price required for LIMIT orders")
                order_params["price"] = price
                order_params["timeInForce"] = time_in_force

            if order_type in ["STOP_MARKET", "TAKE_PROFIT_MARKET"]:
                if stop_price is None:
                    raise ValueError("Stop price required for STOP orders")
                order_params["stopPrice"] = stop_price
                if working_type:
                    order_params["workingType"] = working_type

            order = self.client.futures_create_order(**order_params)

            logger.info(
                f"Order placed: {side} {quantity} {symbol} @ {order_type}"
            )

            return {
                "order_id": order.get("orderId"),
                "symbol": order.get("symbol"),
                "side": order.get("side"),
                "type": order.get("type"),
                "quantity": float(order.get("origQty", 0)),
                "price": float(order.get("price", 0)),
                "avg_price": float(order.get("avgPrice", 0) or 0),
                "stop_price": float(order.get("stopPrice", 0) or 0),
                "status": order.get("status"),
                "time": datetime.fromtimestamp(
                    order.get("updateTime", 0) / 1000, UTC
                ),
            }

        except BinanceAPIException as e:
            logger.error(f"Error placing order: {e}")
            return {"error": str(e), "success": False}
        except Exception as e:
            logger.error(f"Unexpected error placing order: {e}")
            return {"error": str(e), "success": False}

    async def get_open_orders(self, symbol: str | None = None) -> list[dict[str, Any]]:
        """
        Get all open orders from /fapi/v1/openOrders.
        
        Args:
            symbol: Optional symbol filter (e.g., "BTCUSDT")
            
        Returns:
            List of open order dictionaries
        """
        if not self.connected:
            raise RuntimeError("Not connected to Binance Testnet")
        
        try:
            if symbol:
                orders = self.client.futures_get_open_orders(symbol=symbol.upper())
            else:
                orders = self.client.futures_get_open_orders()
            
            open_orders = []
            for order in orders:
                orig_qty = float(order.get("origQty", order.get("qty", 0)))
                create_time = order.get("time") or order.get("createTime")
                order_data = {
                    "orderId": order.get("orderId"),
                    "symbol": order.get("symbol"),
                    "side": order.get("side"),
                    "type": order.get("type"),
                    "price": float(order.get("price", 0)),
                    "qty": orig_qty,
                    "origQty": orig_qty,
                    "executedQty": float(order.get("executedQty", 0)),
                    "status": order.get("status"),
                    "timeInForce": order.get("timeInForce"),
                    "reduceOnly": str(order.get("reduceOnly", "false")).lower() == "true",
                    "time": create_time,
                    "createTime": create_time,
                    "updateTime": order.get("updateTime"),
                }
                open_orders.append(order_data)
                logger.debug(f"[OPEN ORDER] {order_data['symbol']}: {order_data['side']} {order_data['type']} @ {order_data['price']}")
            
            logger.info(f"[OPEN ORDERS] Found {len(open_orders)} open orders")
            return open_orders
            
        except BinanceAPIException as e:
            logger.error(f"Error getting open orders: {e}")
            raise RuntimeError(f"Failed to fetch open orders from Binance: {e}")
    
    async def get_order_history(
        self, 
        symbol: str, 
        limit: int = 100,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get order history from /fapi/v1/allOrders.
        
        Args:
            symbol: Symbol to filter (required by Binance API)
            limit: Maximum number of orders (default: 100, max: 1000)
            start_time: Optional start timestamp in milliseconds
            end_time: Optional end timestamp in milliseconds
            
        Returns:
            List of order dictionaries
        """
        if not self.connected:
            raise RuntimeError("Not connected to Binance Testnet")
        
        try:
            params = {
                "symbol": symbol.upper(),
                "limit": min(limit, 1000),
            }
            if start_time:
                params["startTime"] = start_time
            if end_time:
                params["endTime"] = end_time
            
            orders = self.client.futures_get_all_orders(**params)
            
            order_history = []
            for order in orders:
                orig_qty = float(order.get("origQty", order.get("qty", 0)))
                create_time = order.get("time") or order.get("createTime")
                order_data = {
                    "orderId": order.get("orderId"),
                    "symbol": order.get("symbol"),
                    "side": order.get("side"),
                    "type": order.get("type"),
                    "status": order.get("status"),
                    "price": float(order.get("price", 0)),
                    "qty": orig_qty,
                    "origQty": orig_qty,
                    "executedQty": float(order.get("executedQty", 0)),
                    "timeInForce": order.get("timeInForce"),
                    "time": create_time,
                    "createTime": create_time,
                    "updateTime": order.get("updateTime"),
                    "avgPrice": float(order.get("avgPrice", 0)),
                }
                order_history.append(order_data)
            
            logger.info(f"[ORDER HISTORY] Found {len(order_history)} orders for {symbol}")
            return order_history
            
        except BinanceAPIException as e:
            logger.error(f"Error getting order history: {e}")
            raise RuntimeError(f"Failed to fetch order history from Binance: {e}")
    
    async def get_trade_history(
        self,
        symbol: str,
        limit: int = 100,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get trade history from /fapi/v1/userTrades.
        Returns filled orders with PnL information.
        
        Args:
            symbol: Symbol to filter (required by Binance API)
            limit: Maximum number of trades (default: 100, max: 1000)
            start_time: Optional start timestamp in milliseconds
            end_time: Optional end timestamp in milliseconds
            
        Returns:
            List of trade dictionaries with PnL data
        """
        if not self.connected:
            raise RuntimeError("Not connected to Binance Testnet")
        
        try:
            params = {
                "symbol": symbol.upper(),
                "limit": min(limit, 1000),
            }
            if start_time:
                params["startTime"] = start_time
            if end_time:
                params["endTime"] = end_time
            
            if hasattr(self.client, "futures_account_trades"):
                trades = self.client.futures_account_trades(**params)
            elif hasattr(self.client, "futures_my_trades"):
                trades = self.client.futures_my_trades(**params)
            else:
                raise RuntimeError("python-binance futures trade history method not available")
            
            trade_history = []
            for trade in trades:
                side = trade.get("side")
                if not side:
                    side = "BUY" if trade.get("buyer") else "SELL"
                trade_data = {
                    "id": trade.get("id"),
                    "orderId": trade.get("orderId"),
                    "symbol": trade.get("symbol"),
                    "side": side,
                    "price": float(trade.get("price", 0)),
                    "qty": float(trade.get("qty", 0)),
                    "realizedPnl": float(trade.get("realizedPnl", 0)),
                    "commission": float(trade.get("commission", 0)),
                    "commissionAsset": trade.get("commissionAsset") or "USDT",
                    "time": trade.get("time"),
                    "buyer": trade.get("buyer"),
                    "maker": trade.get("maker"),
                }
                trade_history.append(trade_data)
            
            logger.info(f"[TRADE HISTORY] Found {len(trade_history)} trades for {symbol}")
            return trade_history
            
        except BinanceAPIException as e:
            logger.error(f"Error getting trade history: {e}")
            raise RuntimeError(f"Failed to fetch trade history from Binance: {e}")
    
    async def cancel_order(self, symbol: str, order_id: int) -> dict[str, Any]:
        """
        Cancel an existing order.

        Args:
            symbol: Trading pair symbol
            order_id: Order ID to cancel

        Returns:
            Cancellation response
        """
        if not self.connected:
            raise RuntimeError("Not connected to Binance Testnet")

        try:
            result = self.client.futures_cancel_order(
                symbol=symbol, orderId=order_id
            )
            return {
                "success": True,
                "order_id": result.get("orderId"),
                "status": result.get("status"),
            }
        except BinanceAPIException as e:
            logger.error(f"Error canceling order: {e}")
            return {"error": str(e), "success": False}

    async def cancel_all_open_orders(self, symbol: str) -> list[dict[str, Any]]:
        """Cancel all open futures orders for one symbol."""
        if not self.connected:
            raise RuntimeError("Not connected to Binance Testnet")

        open_orders = await self.get_open_orders(symbol=symbol)
        results: list[dict[str, Any]] = []
        for order in open_orders:
            order_id = order.get("orderId")
            if order_id is None:
                continue
            results.append(await self.cancel_order(symbol=symbol, order_id=int(order_id)))
        return results

    async def get_symbol_info(self, symbol: str) -> dict[str, Any] | None:
        """
        Get symbol information including filters.

        Args:
            symbol: Trading pair symbol

        Returns:
            Symbol info dictionary or None if not found
        """
        try:
            # Use futures exchange info endpoint (not spot)
            exchange_info = self.client.futures_exchange_info()
            for s in exchange_info.get("symbols", []):
                if s.get("symbol") == symbol.upper():
                    return s
            return None
        except Exception as e:
            logger.error(f"Error getting symbol info: {e}")
            return None

    async def _round_quantity(self, symbol: str, quantity: float) -> float:
        """Round quantity to symbol's lot size precision."""
        # Default precision if we can't fetch symbol info
        precision = 3

        try:
            symbol_info = await self.get_symbol_info(symbol)
            if symbol_info:
                for f in symbol_info.get("filters", []):
                    if f.get("filterType") == "LOT_SIZE":
                        step_size = float(f.get("stepSize", 1))
                        precision = len(str(step_size).split(".")[-1].rstrip("0"))
                        break
        except Exception:
            pass

        return round(quantity, precision)

    async def get_current_price(self, symbol: str) -> float:
        """
        Get current mark price for a symbol.

        Args:
            symbol: Trading pair symbol

        Returns:
            Current price
        """
        try:
            mark_price = self.client.futures_mark_price(symbol=symbol.upper())
            return float(mark_price.get("markPrice", 0))
        except Exception as e:
            logger.error(f"Error getting mark price: {e}")
            return 0.0
