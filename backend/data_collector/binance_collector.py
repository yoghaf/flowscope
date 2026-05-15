from __future__ import annotations

import asyncio
import json
import logging
import random
from collections import defaultdict, deque
from datetime import datetime, timezone, timedelta
UTC = timezone.utc
from typing import Any

import httpx
import websockets
import websockets.exceptions

from backend.config import Settings
from backend.data_collector.base import BaseCollector, ExchangeSnapshot

logger = logging.getLogger(__name__)

# Binance futures WS for all mark prices + funding (0 API weight)
_WS_MARK_PRICE_URL = "wss://fstream.binance.com/market/ws/!markPrice@arr@1s"
_WS_FORCE_ORDER_URL = "wss://fstream.binance.com/ws/!forceOrder@arr"

# Bulk endpoints (1 call = all symbols)
_FAPI_TICKER_24HR = "/fapi/v1/ticker/24hr"        # weight 40
_SPOT_TICKER_24HR = "/api/v3/ticker/24hr"          # weight 40
_SPOT_KLINES = "/api/v3/klines"
_FAPI_OPEN_INTEREST = "/fapi/v1/openInterest"      # weight 1 per symbol
_FAPI_PREMIUM_INDEX = "/fapi/v1/premiumIndex"      # weight 10 (bulk, all symbols)
_FAPI_GLOBAL_LS_RATIO = "/futures/data/globalLongShortAccountRatio"  # weight 5
_FAPI_TAKER_LS_RATIO = "/futures/data/takerlongshortRatio"           # weight 5
_FAPI_OI_HIST = "/futures/data/openInterestHist"
_FAPI_FUNDING_RATE_HIST = "/fapi/v1/fundingRate"
_FAPI_KLINES = "/fapi/v1/klines"                   # weight 1-10

# Backfill endpoint
_FAPI_MARK_PRICE_KLINES = "/fapi/v1/markPriceKlines"  # weight 5


class BinanceCollector(BaseCollector):
    """Binance data collector optimised for minimal API weight usage.

    Architecture:
    1. WebSocket ``!markPrice@arr`` pushes price + funding for ALL symbols
       every 3 seconds at **zero** API weight cost.
    2. Bulk REST ``ticker/24hr`` provides price fallback for ALL symbols
       in a single call (weight 40).
    3. Rotary REST fetcher pulls OI / long-short ratio / taker ratio / 1m volume in
       small batches spread across minutes so we never exceed the 6000
       weight-per-minute hard cap.

    Weight budget per minute (steady state):
        WebSocket            :    0
        Bulk ticker (÷5 min) :    8  (amortised)
        OI  40 symbols/min   :   40
        Ratio 10 symbols/min :   50
        Taker 10 symbols/min :   50
        Volume 200x2/min     :  400
        --------------------------
        Total                : ~548 / 6000
    """

    exchange_name = "binance"

    def __init__(self, settings: Settings) -> None:
        super().__init__(settings)
        self.rest_url = settings.binance_rest_url.rstrip("/")
        self.spot_rest_url = settings.binance_spot_rest_url.rstrip("/")
        self.ws_url = settings.binance_ws_url.rstrip("/")

        # ── live caches (updated by WS + rotary) ──────────────────────
        self._ws_prices: dict[str, float] = {}
        self._ws_funding: dict[str, float] = {}
        self._ws_mark_prices: dict[str, float] = {}
        self._bulk_ticker: dict[str, dict[str, Any]] = {}
        self._spot_ticker: dict[str, dict[str, Any]] = {}
        self._oi_cache: dict[str, float] = {}
        self._ls_ratio_cache: dict[str, float] = {}
        self._taker_ratio_cache: dict[str, float] = {}
        from collections import deque
        self._oi_history: dict[str, deque[tuple[datetime, float]]] = defaultdict(lambda: deque(maxlen=1000))
        self._liquidation_events: dict[str, deque[tuple[datetime, float, float]]] = defaultdict(deque)
        self._futures_kline_volume_cache: dict[str, float] = {}
        self._spot_kline_volume_cache: dict[str, float] = {}
        
        # Official timeframe klines (OHLCV)
        self._futures_ohlc_15m: dict[str, dict[str, float]] = {}
        self._futures_ohlc_1h: dict[str, dict[str, float]] = {}
        self._futures_ohlc_4h: dict[str, dict[str, float]] = {}
        self._futures_ohlc_24h: dict[str, dict[str, float]] = {}
        
        self._last_snapshot_time: dict[str, datetime] = {}
        self._force_order_connected = False

        # ── freshness tracking ─────────────────────────────────────────
        self._price_updated_at: dict[str, datetime] = {}
        self._funding_updated_at: dict[str, datetime] = {}
        self._oi_updated_at: dict[str, datetime] = {}
        self._ls_ratio_updated_at: dict[str, datetime] = {}
        self._taker_ratio_updated_at: dict[str, datetime] = {}
        self._volume_updated_at: dict[str, datetime] = {}
        self._liquidation_updated_at: dict[str, datetime] = {}

        # ── source tracking ───────────────────────────────────────────
        self._price_source: dict[str, str] = {}
        self._volume_source: dict[str, str] = {}
        self._funding_source: dict[str, str] = {}
        self._oi_source: dict[str, str] = {}
        self._ls_ratio_source: dict[str, str] = {}
        self._taker_ratio_source: dict[str, str] = {}
        self._liquidation_source: dict[str, str] = {}

        # ── rotary state ──────────────────────────────────────────────
        self._oi_batch_size = getattr(settings, "oi_batch_size", 40)
        self._oi_poll_interval_seconds = getattr(settings, "oi_poll_interval_seconds", 30)
        self._oi_request_concurrency = getattr(settings, "oi_request_concurrency", 4)
        self._oi_429_backoff_seconds = getattr(settings, "oi_429_backoff_seconds", 60.0)
        self._oi_429_backoff_jitter_seconds = getattr(settings, "oi_429_backoff_jitter_seconds", 15.0)
        self._oi_backoff_until: datetime | None = None
        self._ratio_batch_size = getattr(settings, "ratio_batch_size", 10)
        self._taker_batch_size = getattr(settings, "taker_batch_size", 10)
        self._volume_batch_size = getattr(settings, "volume_batch_size", 50)
        self._volume_refresh_seconds = getattr(settings, "volume_refresh_seconds", 15)
        self._oi_offset = 0
        self._ratio_offset = 0
        self._taker_offset = 0
        self._volume_offset = 0

        # ── WS state ─────────────────────────────────────────────────
        self._ws_task: asyncio.Task[None] | None = None
        self._force_order_task: asyncio.Task[None] | None = None
        self._ws_connected = False
        self._ws_reconnect_delay = getattr(settings, "ws_reconnect_delay", 5)

        # ── background rotary tasks ──────────────────────────────────
        self._rotary_tasks: list[asyncio.Task[None]] = []
        self._symbols: list[str] = []
        self._running = False

    # ─── lifecycle ────────────────────────────────────────────────────

    async def start_background(self, symbols: list[str]) -> None:
        """Start WebSocket + rotary background loops."""
        self._symbols = list(symbols)
        self._running = True
        self._ws_task = asyncio.create_task(self._ws_loop())
        self._force_order_task = asyncio.create_task(self._force_order_loop())
        self._rotary_tasks = [
            asyncio.create_task(self._rotary_oi_loop()),
            asyncio.create_task(self._rotary_ratio_loop()),
            asyncio.create_task(self._rotary_taker_loop()),
            asyncio.create_task(self._rotary_volume_loop()),
        ]
        logger.info(
            "BinanceCollector background started: %d symbols, "
            "OI batch=%d, ratio batch=%d, taker batch=%d, volume batch=%d",
            len(symbols),
            self._oi_batch_size,
            self._ratio_batch_size,
            self._taker_batch_size,
            self._volume_batch_size,
        )

    async def stop_background(self) -> None:
        self._running = False
        for task in self._rotary_tasks:
            task.cancel()
        if self._ws_task:
            self._ws_task.cancel()
        if self._force_order_task:
            self._force_order_task.cancel()
        self._rotary_tasks.clear()

    async def close(self) -> None:
        await self.stop_background()
        await super().close()

    # ─── WebSocket loop ───────────────────────────────────────────────

    async def _ws_loop(self) -> None:
        """Maintain persistent WS connection to !markPrice@arr."""
        while self._running:
            try:
                logger.info("WS markPrice connecting to %s", _WS_MARK_PRICE_URL)
                async with websockets.connect(
                    _WS_MARK_PRICE_URL,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5,
                ) as ws:
                    self._ws_connected = True
                    logger.info("WS markPrice connected — receiving all symbols")
                    async for message in ws:
                        try:
                            data = json.loads(message)
                            if isinstance(data, list):
                                for item in data:
                                    symbol = item.get("s", "")
                                    now = self.utcnow()
                                    self._ws_prices[symbol] = self.parse_float(
                                        item.get("p")
                                    )
                                    self._ws_mark_prices[symbol] = self.parse_float(
                                        item.get("p")
                                    )
                                    self._ws_funding[symbol] = self.parse_float(
                                        item.get("r")
                                    )
                                    self._price_updated_at[symbol] = now
                                    self._funding_updated_at[symbol] = now
                                    self._price_source[symbol] = "ws_mark_price"
                                    self._funding_source[symbol] = "ws_mark_price"
                        except (json.JSONDecodeError, KeyError) as exc:
                            logger.debug("WS parse error: %s", exc)
            except websockets.exceptions.ConnectionClosed as exc:
                logger.warning("WS markPrice disconnected: %s", exc)
            except Exception as exc:
                logger.error("WS markPrice error: %s", exc)
            finally:
                self._ws_connected = False

            if self._running:
                logger.info(
                    "WS markPrice reconnecting in %ds", self._ws_reconnect_delay
                )
                await asyncio.sleep(self._ws_reconnect_delay)

    async def _force_order_loop(self) -> None:
        """Maintain liquidation cache from public force-order stream."""
        while self._running:
            try:
                logger.info("WS forceOrder connecting to %s", _WS_FORCE_ORDER_URL)
                async with websockets.connect(
                    _WS_FORCE_ORDER_URL,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5,
                ) as ws:
                    self._force_order_connected = True
                    logger.info("WS forceOrder connected")
                    async for message in ws:
                        try:
                            payload = json.loads(message)
                            order = payload.get("o") if isinstance(payload, dict) else None
                            if not isinstance(order, dict):
                                continue
                            symbol = order.get("s", "")
                            side = order.get("S", "")
                            filled_qty = self.parse_float(order.get("z") or order.get("q"))
                            avg_price = self.parse_float(order.get("ap") or order.get("p"))
                            liquidation_value = max(filled_qty * avg_price, 0.0)
                            if not symbol or liquidation_value <= 0.0:
                                continue
                             
                            now = self.utcnow()
                            long_val = liquidation_value if side == "SELL" else 0.0
                            short_val = liquidation_value if side == "BUY" else 0.0
                             
                            self._liquidation_events[symbol].append((now, long_val, short_val))
                            self._liquidation_updated_at[symbol] = now
                             
                            # drop events older than 24h
                            cutoff = now.timestamp() - 86400
                            while self._liquidation_events[symbol] and self._liquidation_events[symbol][0][0].timestamp() < cutoff:
                                self._liquidation_events[symbol].popleft()
                        except (json.JSONDecodeError, KeyError, TypeError) as exc:
                            logger.debug("WS forceOrder parse error: %s", exc)
            except websockets.exceptions.ConnectionClosed as exc:
                logger.warning("WS forceOrder disconnected: %s", exc)
            except Exception as exc:
                logger.error("WS forceOrder error: %s", exc)
            finally:
                self._force_order_connected = False

            if self._running:
                logger.info("WS forceOrder reconnecting in %ds", self._ws_reconnect_delay)
                await asyncio.sleep(self._ws_reconnect_delay)

    # ─── rotary REST loops ────────────────────────────────────────────

    async def _rotary_oi_loop(self) -> None:
        """Fetch open interest for a batch of symbols every ~60 seconds."""
        await asyncio.sleep(2)  # let WS connect first
        while self._running:
            try:
                batch = self._next_batch(
                    self._symbols, self._oi_batch_size, "_oi_offset"
                )
                await self._fetch_oi_batch(batch)
                logger.debug("OI batch done: %d symbols", len(batch))
            except Exception as exc:
                logger.error("OI rotary error: %s", exc)
            await asyncio.sleep(self._oi_poll_interval_seconds)

    async def _rotary_ratio_loop(self) -> None:
        """Fetch long/short ratio for a batch of symbols every ~60 seconds."""
        await asyncio.sleep(5)
        while self._running:
            try:
                batch = self._next_batch(
                    self._symbols, self._ratio_batch_size, "_ratio_offset"
                )
                await self._fetch_ratio_batch(batch)
                logger.debug("Ratio batch done: %d symbols", len(batch))
            except Exception as exc:
                logger.error("Ratio rotary error: %s", exc)
            await asyncio.sleep(60)  # 10 calls × 5 weight = 50 weight/min

    async def _rotary_taker_loop(self) -> None:
        """Fetch taker buy/sell ratio for a batch of symbols every ~60 seconds."""
        await asyncio.sleep(8)
        while self._running:
            try:
                batch = self._next_batch(
                    self._symbols, self._taker_batch_size, "_taker_offset"
                )
                await self._fetch_taker_batch(batch)
                logger.debug("Taker batch done: %d symbols", len(batch))
            except Exception as exc:
                logger.error("Taker rotary error: %s", exc)
            await asyncio.sleep(60)

    async def _rotary_volume_loop(self) -> None:
        """Fetch recent 1m kline quote volume for live volume metrics."""
        await asyncio.sleep(3)
        while self._running:
            try:
                batch = self._next_batch(
                    self._symbols, self._volume_batch_size, "_volume_offset"
                )
                await self._fetch_live_kline_batch(batch)
                logger.debug("Live kline batch done: %d symbols", len(batch))
            except Exception as exc:
                logger.error("Live volume rotary error: %s", exc)
            await asyncio.sleep(max(self._volume_refresh_seconds, 1))

    def _next_batch(self, symbols: list[str], size: int, offset_attr: str) -> list[str]:
        offset = getattr(self, offset_attr)
        batch = symbols[offset: offset + size]
        new_offset = offset + size
        if new_offset >= len(symbols):
            new_offset = 0
        setattr(self, offset_attr, new_offset)
        return batch

    # ─── bulk REST fetchers ───────────────────────────────────────────

    async def _fetch_bulk_tickers(self) -> None:
        """Fetch 24hr ticker for ALL futures symbols in 1 call (weight 40)."""
        try:
            response = await self.client.get(
                f"{self.rest_url}{_FAPI_TICKER_24HR}",
            )
            response.raise_for_status()
            for item in response.json():
                symbol = item.get("symbol", "")
                self._bulk_ticker[symbol] = item
        except Exception as exc:
            logger.error("Bulk futures ticker failed: %s", exc)

    async def _fetch_bulk_spot_tickers(self) -> None:
        """Fetch 24hr ticker for ALL spot symbols in 1 call (weight 40)."""
        try:
            response = await self.client.get(
                f"{self.spot_rest_url}{_SPOT_TICKER_24HR}",
            )
            response.raise_for_status()
            for item in response.json():
                symbol = item.get("symbol", "")
                self._spot_ticker[symbol] = item
        except Exception as exc:
            logger.error("Bulk spot ticker failed: %s", exc)

    async def _fetch_oi_batch(self, symbols: list[str]) -> None:
        """Fetch OI for a small batch (weight 1 per symbol)."""
        now = self.utcnow()
        if self._oi_backoff_until and now < self._oi_backoff_until:
            remaining = (self._oi_backoff_until - now).total_seconds()
            logger.info(
                "OI batch backoff active seconds=%.1f symbols=%d",
                remaining,
                len(symbols),
            )
            logger.info(
                "OI batch success=0 fail=0 rate_limited=0 symbols=%d",
                len(symbols),
            )
            return

        semaphore = asyncio.Semaphore(self._oi_request_concurrency)
        success = 0
        fail = 0
        rate_limited = 0

        async def fetch_one(symbol: str) -> None:
            nonlocal success, fail, rate_limited
            async with semaphore:
                current = self.utcnow()
                if self._oi_backoff_until and current < self._oi_backoff_until:
                    return

                try:
                    response = await self.client.get(
                        f"{self.rest_url}{_FAPI_OPEN_INTEREST}",
                        params={"symbol": symbol},
                    )
                    if response.status_code == 429:
                        rate_limited += 1
                        jitter = random.uniform(
                            0.0,
                            max(self._oi_429_backoff_jitter_seconds, 0.0),
                        )
                        backoff_seconds = max(self._oi_429_backoff_seconds, 0.0) + jitter
                        backoff_until = self.utcnow() + timedelta(seconds=backoff_seconds)
                        if (
                            self._oi_backoff_until is None
                            or backoff_until > self._oi_backoff_until
                        ):
                            self._oi_backoff_until = backoff_until
                        logger.debug(
                            "OI fetch rate limited %s; backing off until %s",
                            symbol,
                            self._oi_backoff_until.isoformat(),
                        )
                        return

                    response.raise_for_status()
                    data = response.json()
                    now = self.utcnow()
                    val = self.parse_float(data.get("openInterest"))
                    self._oi_cache[symbol] = val
                    self._oi_updated_at[symbol] = now
                    self._oi_source[symbol] = "open_interest_endpoint"
                    self._oi_history[symbol].append((now, val))
                    success += 1
                    if len(self._oi_history[symbol]) % 100 == 0:
                        logger.debug("OI FETCH SUCCESS [%s]: val=%.2f", symbol, val)
                except Exception as exc:
                    fail += 1
                    logger.debug("OI fetch failed %s: %s", symbol, exc)

        await asyncio.gather(*(fetch_one(s) for s in symbols))
        logger.info(
            "OI batch success=%d fail=%d rate_limited=%d symbols=%d",
            success,
            fail,
            rate_limited,
            len(symbols),
        )

    async def _fetch_ratio_batch(self, symbols: list[str]) -> None:
        """Fetch global long/short ratio (weight 5 per symbol)."""
        semaphore = asyncio.Semaphore(self.settings.exchange_request_concurrency)

        async def fetch_one(symbol: str) -> None:
            async with semaphore:
                try:
                    response = await self.client.get(
                        f"{self.rest_url}{_FAPI_GLOBAL_LS_RATIO}",
                        params={"symbol": symbol, "period": "5m", "limit": 1},
                    )
                    response.raise_for_status()
                    entries = response.json()
                    if entries:
                        long_account = self.parse_float(
                            entries[0].get("longAccount"), 0.5
                        )
                        short_account = self.parse_float(
                            entries[0].get("shortAccount"), 0.5
                        )
                        if short_account > 0:
                            now = self.utcnow()
                            self._ls_ratio_cache[symbol] = long_account / short_account
                            self._ls_ratio_updated_at[symbol] = now
                            self._ls_ratio_source[symbol] = "global_ls_ratio"
                except Exception as exc:
                    logger.debug("Ratio fetch failed %s: %s", symbol, exc)

        await asyncio.gather(*(fetch_one(s) for s in symbols))

    async def _fetch_taker_batch(self, symbols: list[str]) -> None:
        """Fetch taker buy/sell ratio (weight 5 per symbol)."""
        semaphore = asyncio.Semaphore(self.settings.exchange_request_concurrency)

        async def fetch_one(symbol: str) -> None:
            async with semaphore:
                try:
                    response = await self.client.get(
                        f"{self.rest_url}{_FAPI_TAKER_LS_RATIO}",
                        params={"symbol": symbol, "period": "5m", "limit": 1},
                    )
                    response.raise_for_status()
                    entries = response.json()
                    if entries:
                        now = self.utcnow()
                        self._taker_ratio_cache[symbol] = self.parse_float(
                            entries[0].get("buySellRatio"), 1.0
                        )
                        self._taker_ratio_updated_at[symbol] = now
                        self._taker_ratio_source[symbol] = "taker_ls_ratio"
                except Exception as exc:
                    logger.debug("Taker fetch failed %s: %s", symbol, exc)

        await asyncio.gather(*(fetch_one(s) for s in symbols))

    async def _fetch_live_kline_batch(self, symbols: list[str]) -> None:
        """Fetch current OHLCV for major timeframes to ensure foundation integrity."""
        semaphore = asyncio.Semaphore(self.settings.exchange_request_concurrency)

        async def fetch_one(symbol: str) -> None:
            async with semaphore:
                try:
                    # Helper to parse kline into dict
                    def parse_k(e):
                        if not e: return None
                        item = e[-1]
                        return {
                            "open": self.parse_float(item[1]),
                            "high": self.parse_float(item[2]),
                            "low": self.parse_float(item[3]),
                            "close": self.parse_float(item[4]),
                            "volume": self.parse_float(item[7]) # Quote volume
                        }

                    # 1m (Legacy fallback support)
                    r1m = await self.client.get(f"{self.rest_url}{_FAPI_KLINES}", params={"symbol": symbol, "interval": "1m", "limit": 1})
                    r1m.raise_for_status()
                    d1m = parse_k(r1m.json())
                    if d1m: self._futures_kline_volume_cache[symbol] = d1m["volume"]

                    # 15m
                    r15m = await self.client.get(f"{self.rest_url}{_FAPI_KLINES}", params={"symbol": symbol, "interval": "15m", "limit": 1})
                    r15m.raise_for_status()
                    self._futures_ohlc_15m[symbol] = parse_k(r15m.json())

                    # 1h
                    r1h = await self.client.get(f"{self.rest_url}{_FAPI_KLINES}", params={"symbol": symbol, "interval": "1h", "limit": 1})
                    r1h.raise_for_status()
                    self._futures_ohlc_1h[symbol] = parse_k(r1h.json())

                    # 4h
                    r4h = await self.client.get(f"{self.rest_url}{_FAPI_KLINES}", params={"symbol": symbol, "interval": "4h", "limit": 1})
                    r4h.raise_for_status()
                    self._futures_ohlc_4h[symbol] = parse_k(r4h.json())

                    # 24h
                    r1d = await self.client.get(f"{self.rest_url}{_FAPI_KLINES}", params={"symbol": symbol, "interval": "1d", "limit": 1})
                    r1d.raise_for_status()
                    self._futures_ohlc_24h[symbol] = parse_k(r1d.json())

                    self._volume_updated_at[symbol] = self.utcnow()
                    self._volume_source[symbol] = "official_klines"

                except Exception as exc:
                    logger.debug("Official kline fetch failed %s: %s", symbol, exc)

        await asyncio.gather(*(fetch_one(s) for s in symbols))

    # ─── main fetch interface ─────────────────────────────────────────

    async def fetch_snapshots(self, symbols: list[str]) -> dict[str, ExchangeSnapshot]:
        """Build snapshots by merging WS cache + bulk tickers + rotary caches.

        Called by SignalService._snapshot_cycle() every N seconds.
        Only the bulk ticker calls consume API weight here; everything
        else is already cached by background tasks.
        """
        # Refresh futures ticker for price fallback. Volume comes from live klines.
        await self._fetch_bulk_tickers()

        timestamp = self.utcnow()
        snapshots: dict[str, ExchangeSnapshot] = {}

        # Track last snapshot time to compute liquidation delta correctly
        if not hasattr(self, "_last_snapshot_time"):
            self._last_snapshot_time: dict[str, datetime] = {}

        for symbol in symbols:
            # Price: prefer WS, fall back to bulk ticker
            price = self._ws_prices.get(symbol, 0.0)
            price_source = self._price_source.get(symbol, "missing")
            
            if price <= 0:
                ticker = self._bulk_ticker.get(symbol, {})
                price = self.parse_float(ticker.get("lastPrice"))
                if price > 0:
                    price_source = "futures_ticker"
                    self._price_updated_at[symbol] = timestamp # Approximate since ticker is bulk

            if price <= 0:
                continue  # skip symbols with no price data at all

            # Quote volume from recent klines.
            futures_volume = self._futures_kline_volume_cache.get(symbol, 0.0)
            spot_volume = self._spot_kline_volume_cache.get(symbol, 0.0)
            volume_source = self._volume_source.get(symbol, "missing")

            # Funding from WS
            funding_rate = self._ws_funding.get(symbol, 0.0)
            funding_source = "ws_mark_price" if symbol in self._ws_funding else "missing"

            # OI from rotary cache
            open_interest = self._oi_cache.get(symbol, 0.0)
            oi_source = "open_interest_endpoint" if symbol in self._oi_cache else "missing"

            # Ratios from rotary cache
            long_short_ratio = self._ls_ratio_cache.get(symbol, 1.0)
            ls_source = "global_ls_ratio" if symbol in self._ls_ratio_cache else "default_neutral"
            
            taker_ratio = self._taker_ratio_cache.get(symbol, 1.0)
            taker_source = self._taker_ratio_source.get(symbol, "missing")
            
            ls_source = self._ls_ratio_source.get(symbol, "missing")
            oi_source = self._oi_source.get(symbol, "missing")

            # Liquidations from events deque
            last_time = self._last_snapshot_time.get(symbol, timestamp - timedelta(seconds=60))
            events = self._liquidation_events.get(symbol, deque())
            
            long_liq_delta = 0.0
            short_liq_delta = 0.0
            for ev_ts, l_val, s_val in events:
                if last_time < ev_ts <= timestamp:
                    long_liq_delta += l_val
                    short_liq_delta += s_val
            
            if (long_liq_delta + short_liq_delta) > 0:
                liq_source = "force_order_ws"
            elif self._force_order_connected:
                liq_source = "force_order_ws_zero"
                self._liquidation_updated_at[symbol] = timestamp
            else:
                liq_source = "missing"
            self._last_snapshot_time[symbol] = timestamp

            snapshots[symbol] = ExchangeSnapshot(
                exchange=self.exchange_name,
                symbol=symbol,
                timestamp=timestamp,
                price=price,
                spot_volume=spot_volume,
                futures_volume=futures_volume,
                open_interest=open_interest,
                funding_rate=funding_rate,
                long_short_ratio=long_short_ratio,
                taker_buy_sell_ratio=taker_ratio,
                long_liquidations=long_liq_delta,
                short_liquidations=short_liq_delta,
                
                # Official timeframe ground truth (Option A)
                futures_ohlc_15m=self._futures_ohlc_15m.get(symbol),
                futures_ohlc_1h=self._futures_ohlc_1h.get(symbol),
                futures_ohlc_4h=self._futures_ohlc_4h.get(symbol),
                futures_ohlc_24h=self._futures_ohlc_24h.get(symbol),
                
                # DQ Metadata
                price_updated_at=self._price_updated_at.get(symbol),
                spot_volume_updated_at=self._volume_updated_at.get(symbol),
                futures_volume_updated_at=self._volume_updated_at.get(symbol),
                open_interest_updated_at=self._oi_updated_at.get(symbol),
                funding_rate_updated_at=self._funding_updated_at.get(symbol),
                long_short_ratio_updated_at=self._ls_ratio_updated_at.get(symbol),
                taker_buy_sell_ratio_updated_at=self._taker_ratio_updated_at.get(symbol),
                liquidation_updated_at=self._liquidation_updated_at.get(symbol),
                
                price_source=price_source,
                volume_source=volume_source,
                open_interest_source=oi_source,
                funding_source=self._funding_source.get(symbol, "missing"),
                long_short_ratio_source=ls_source,
                taker_ratio_source=taker_source,
                liquidation_source=liq_source
            )

        logger.info(
            "BinanceCollector fetch_snapshots: %d/%d symbols, ws=%s, oi_cached=%d, ratio_cached=%d",
            len(snapshots),
            len(symbols),
            self._ws_connected,
            len(self._oi_cache),
            len(self._ls_ratio_cache),
        )
        return snapshots

    # ─── kline backfill (startup only) ────────────────────────────────

    async def fetch_klines(
        self,
        symbol: str,
        interval: str = "5m",
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        """Fetch kline data for a single symbol (weight 1-10 depending on limit).

        Used for DB backfill at startup — not called during normal operation.
        """
        try:
            response = await self.client.get(
                f"{self.rest_url}{_FAPI_KLINES}",
                params={
                    "symbol": symbol,
                    "interval": interval,
                    "limit": limit,
                },
            )
            response.raise_for_status()
            raw = response.json()
            return [
                {
                    "timestamp": datetime.fromtimestamp(item[0] / 1000, tz=UTC),
                    "open": float(item[1]),
                    "high": float(item[2]),
                    "low": float(item[3]),
                    "close": float(item[4]),
                    "volume": float(item[5]),
                    "close_time": datetime.fromtimestamp(item[6] / 1000, tz=UTC),
                    "quote_volume": float(item[7]),
                    "trades": int(item[8]),
                }
                for item in raw
            ]
        except Exception as exc:
            logger.error("Kline fetch failed %s: %s", symbol, exc)
            return []

    def _parse_long_short_ratio_entry(self, entry: dict[str, Any]) -> float:
        ratio = self.parse_float(entry.get("longShortRatio"), 0.0)
        if ratio > 0.0:
            return ratio

        long_account = self.parse_float(entry.get("longAccount"), 0.5)
        short_account = self.parse_float(entry.get("shortAccount"), 0.5)
        if short_account > 0.0:
            return long_account / short_account
        return 1.0

    async def fetch_historical_buckets(
        self,
        symbols: list[str],
        timeframes: tuple[str, ...],
        lookback_days: int = 3,
        limits_override: dict[str, dict[str, int]] | None = None,
    ) -> list[Any]:
        """Fetch historical kline data and convert to TimeframeBucket objects.

        Used for DB backfill at startup. Batches requests with delays
        to stay within rate limits.
        """
        from backend.services.timeframe_aggregator import TIMEFRAME_DELTAS, TimeframeBucket
        from backend.engines.flow_engine import HistoryPoint

        interval_map = {"15m": "15m", "1h": "1h", "4h": "4h", "24h": "1d"}
        default_limits = {
            "15m": min(1000, lookback_days * 96),
            "1h": min(1000, max(lookback_days * 24, 200)),  # At least 200 candles
            "4h": min(1000, max(lookback_days * 6, 200)),   # At least 200 candles
            "24h": min(1000, max(lookback_days, 100)),      # At least 100 candles
        }

        all_buckets: list[Any] = []
        semaphore = asyncio.Semaphore(5)  # max 5 concurrent kline requests

        async def fetch_one(symbol: str, tf: str) -> list[Any]:
            async with semaphore:
                override = (limits_override or {}).get(symbol, {})
                limit = override.get(tf, default_limits.get(tf, 500))
                interval = interval_map.get(tf, "1h")
                futures_klines: list[Any] = []
                spot_klines: list[Any] = []
                oi_entries: list[dict[str, Any]] = []
                ls_entries: list[dict[str, Any]] = []
                funding_entries: list[dict[str, Any]] = []

                async def fetch_futures_klines() -> None:
                    nonlocal futures_klines
                    response = await self.client.get(
                        f"{self.rest_url}{_FAPI_KLINES}",
                        params={"symbol": symbol, "interval": interval, "limit": limit},
                    )
                    response.raise_for_status()
                    futures_klines = response.json()

                async def fetch_spot_klines() -> None:
                    nonlocal spot_klines
                    response = await self.client.get(
                        f"{self.spot_rest_url}{_SPOT_KLINES}",
                        params={"symbol": symbol, "interval": interval, "limit": limit},
                    )
                    response.raise_for_status()
                    spot_klines = response.json()

                async def fetch_oi_history() -> None:
                    nonlocal oi_entries
                    response = await self.client.get(
                        f"{self.rest_url}{_FAPI_OI_HIST}",
                        params={"symbol": symbol, "period": interval, "limit": limit},
                    )
                    response.raise_for_status()
                    oi_entries = response.json()

                async def fetch_ls_history() -> None:
                    nonlocal ls_entries
                    response = await self.client.get(
                        f"{self.rest_url}{_FAPI_GLOBAL_LS_RATIO}",
                        params={"symbol": symbol, "period": interval, "limit": min(limit, 500)},
                    )
                    response.raise_for_status()
                    ls_entries = response.json()

                async def fetch_funding_history() -> None:
                    nonlocal funding_entries
                    response = await self.client.get(
                        f"{self.rest_url}{_FAPI_FUNDING_RATE_HIST}",
                        params={"symbol": symbol, "limit": min(max(limit, 50), 1000)},
                    )
                    response.raise_for_status()
                    funding_entries = response.json()

                futures_task = fetch_futures_klines()
                optional_tasks = [
                    fetch_spot_klines(),
                    fetch_oi_history(),
                    fetch_ls_history(),
                    fetch_funding_history(),
                ]

                futures_result, spot_result, oi_result, ls_result, funding_result = await asyncio.gather(
                    futures_task,
                    *optional_tasks,
                    return_exceptions=True,
                )

                if isinstance(futures_result, Exception):
                    logger.debug("Backfill kline failed %s/%s: %s", symbol, tf, futures_result)
                    return []
                if isinstance(spot_result, Exception):
                    logger.debug("Backfill spot kline unavailable %s/%s: %s", symbol, tf, spot_result)
                    spot_klines = []
                if isinstance(oi_result, Exception):
                    logger.debug("Backfill OI history unavailable %s/%s: %s", symbol, tf, oi_result)
                    oi_entries = []
                if isinstance(ls_result, Exception):
                    logger.debug("Backfill L/S history unavailable %s/%s: %s", symbol, tf, ls_result)
                    ls_entries = []
                if isinstance(funding_result, Exception):
                    logger.debug("Backfill funding history unavailable %s/%s: %s", symbol, tf, funding_result)
                    funding_entries = []

                spot_volume_map = {
                    int(item[0]): float(item[7]) if len(item) > 7 else float(item[5])
                    for item in spot_klines
                }
                oi_series = sorted(
                    (
                        (
                            int(str(entry.get("timestamp", "0"))),
                            self.parse_float(entry.get("sumOpenInterest")),
                        )
                        for entry in oi_entries
                    ),
                    key=lambda item: item[0],
                )
                funding_series = sorted(
                    (
                        (
                            int(entry.get("fundingTime", 0)),
                            self.parse_float(entry.get("fundingRate")),
                        )
                        for entry in funding_entries
                    ),
                    key=lambda item: item[0],
                )
                ls_series = sorted(
                    (
                        (
                            int(str(entry.get("timestamp", "0"))),
                            self._parse_long_short_ratio_entry(entry),
                        )
                        for entry in ls_entries
                    ),
                    key=lambda item: item[0],
                )

                def latest_series_sample(
                    series: list[tuple[int, float]],
                    timestamp_ms: int,
                ) -> tuple[int | None, float | None]:
                    sample_ts: int | None = None
                    value: float | None = None
                    for series_ts, series_value in series:
                        if series_ts <= timestamp_ms:
                            sample_ts = series_ts
                            value = series_value
                        else:
                            break
                    return sample_ts, value

                def latest_series_value(series: list[tuple[int, float]], timestamp_ms: int, default: float) -> float:
                    _, value = latest_series_sample(series, timestamp_ms)
                    return value if value is not None else default

                buckets: list[Any] = []
                previous_oi_close = 0.0
                previous_oi_close_ts: int | None = None
                for item in futures_klines:
                    ts = datetime.fromtimestamp(item[0] / 1000, tz=UTC)
                    bucket_end = ts + TIMEFRAME_DELTAS[tf]
                    close_ts = datetime.fromtimestamp(item[6] / 1000, tz=UTC)
                    timestamp_ms = int(item[0])
                    close_timestamp_ms = int(item[6])
                    total_vol = float(item[5])
                    taker_buy_vol = float(item[9]) if len(item) > 9 else 0.0
                    taker_sell_vol = total_vol - taker_buy_vol
                    taker_ratio = 1.0
                    if taker_sell_vol > 0:
                        taker_ratio = taker_buy_vol / taker_sell_vol
                    elif taker_buy_vol > 0:
                        taker_ratio = 10.0

                    spot_quote_volume = spot_volume_map.get(timestamp_ms, 0.0)
                    futures_quote_volume = float(item[7]) if len(item) > 7 else total_vol
                    open_oi_ts, open_oi_value = latest_series_sample(oi_series, timestamp_ms)
                    close_oi_ts, close_oi_value = latest_series_sample(oi_series, close_timestamp_ms)
                    oi_close = close_oi_value if close_oi_value is not None else previous_oi_close
                    oi_open = (
                        previous_oi_close
                        if previous_oi_close > 0.0
                        else open_oi_value
                        if open_oi_value is not None
                        else oi_close
                    )
                    open_boundary_present = oi_open > 0.0 and (
                        previous_oi_close_ts is not None or open_oi_ts is not None or close_oi_ts is not None
                    )
                    close_boundary_present = oi_close > 0.0 and close_oi_ts is not None
                    oi_open_timestamp = ts if open_boundary_present else None
                    oi_close_timestamp = bucket_end if close_boundary_present else None
                    if open_boundary_present and close_boundary_present:
                        oi_alignment_status = "ALIGNED"
                        oi_delta_reliable = True
                    elif open_boundary_present or close_boundary_present:
                        oi_alignment_status = "PARTIAL"
                        oi_delta_reliable = False
                    else:
                        oi_alignment_status = "MISSING"
                        oi_delta_reliable = False
                    funding_rate = latest_series_value(funding_series, int(item[6]), 0.0)
                    long_short_ratio = latest_series_value(ls_series, timestamp_ms, 1.0)

                    bucket = TimeframeBucket(
                        symbol=symbol,
                        timeframe=tf,
                        bucket_start=ts,
                        bucket_end=bucket_end,
                        last_timestamp=close_ts,
                        open_price=float(item[1]),
                        high_price=float(item[2]),
                        low_price=float(item[3]),
                        close_price=float(item[4]),
                        open_interest_open=oi_open,
                        open_interest_high=max(oi_open, oi_close),
                        open_interest_low=min(oi_open, oi_close),
                        open_interest_close=oi_close,
                        spot_volume_open=spot_quote_volume,
                        spot_volume_close=spot_quote_volume,
                        spot_volume_delta=spot_quote_volume,
                        futures_volume_open=futures_quote_volume,
                        futures_volume_close=futures_quote_volume,
                        futures_volume_delta=futures_quote_volume,
                        funding_rate_sum=funding_rate,
                        funding_rate_close=funding_rate,
                        long_short_ratio_sum=long_short_ratio,
                        long_short_ratio_close=long_short_ratio,
                        taker_buy_sell_ratio_sum=taker_ratio,
                        taker_buy_sell_ratio_close=taker_ratio,
                        long_liquidations_close=0.0,
                        long_liquidations_total=0.0,
                        short_liquidations_close=0.0,
                        short_liquidations_total=0.0,
                        exchange_count_sum=1,
                        sample_count=1,
                        bucket_is_closed=True,
                        bucket_completion_pct=1.0,
                        oi_open_timestamp=oi_open_timestamp,
                        oi_close_timestamp=oi_close_timestamp,
                        oi_open_age=0.0 if oi_open_timestamp is not None else None,
                        oi_close_age=0.0 if oi_close_timestamp is not None else None,
                        oi_alignment_status=oi_alignment_status,
                        oi_delta_reliable=oi_delta_reliable,
                    )
                    buckets.append(bucket)
                    previous_oi_close = oi_close
                    previous_oi_close_ts = close_timestamp_ms if close_boundary_present else previous_oi_close_ts

                return buckets

        # Process in batches with delay between them
        batch_size = 10
        for tf in timeframes:
            for i in range(0, len(symbols), batch_size):
                batch = symbols[i: i + batch_size]
                results = await asyncio.gather(
                    *(fetch_one(s, tf) for s in batch)
                )
                for result in results:
                    all_buckets.extend(result)
                # Small delay between batches to spread weight
                if i + batch_size < len(symbols):
                    await asyncio.sleep(1)

        logger.info(
            "Backfill complete: %d buckets for %d symbols × %s",
            len(all_buckets),
            len(symbols),
            timeframes,
        )
        return all_buckets

    # ─── stream_prices (existing interface, now uses WS internally) ───

    async def stream_prices(
        self,
        symbols: list[str],
        callback,
    ) -> None:
        """Stream live price updates using the WS data.

        The background WS loop already receives !markPrice@arr.
        This method just polls the cache and calls the callback.
        """
        if not self._ws_task:
            await self.start_background(symbols)

        while self._running:
            for symbol in symbols:
                price = self._ws_prices.get(symbol)
                if price and price > 0:
                    snapshot = ExchangeSnapshot(
                        exchange=self.exchange_name,
                        symbol=symbol,
                        timestamp=self.utcnow(),
                        price=price,
                        funding_rate=self._ws_funding.get(symbol, 0.0),
                        funding_rate_updated_at=self._funding_updated_at.get(symbol),
                        funding_source=self._funding_source.get(symbol, "missing"),
                    )
                    await callback(snapshot)
            await asyncio.sleep(3)
