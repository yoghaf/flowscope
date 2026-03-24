from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

import httpx
import websockets
import websockets.exceptions

from backend.config import Settings
from backend.data_collector.base import BaseCollector, ExchangeSnapshot

logger = logging.getLogger(__name__)

# Binance futures WS for all mark prices + funding (0 API weight)
_WS_MARK_PRICE_URL = "wss://fstream.binance.com/ws/!markPrice@arr"

# Bulk endpoints (1 call = all symbols)
_FAPI_TICKER_24HR = "/fapi/v1/ticker/24hr"        # weight 40
_SPOT_TICKER_24HR = "/api/v3/ticker/24hr"          # weight 40
_FAPI_OPEN_INTEREST = "/fapi/v1/openInterest"      # weight 1 per symbol
_FAPI_PREMIUM_INDEX = "/fapi/v1/premiumIndex"      # weight 10 (bulk, all symbols)
_FAPI_GLOBAL_LS_RATIO = "/futures/data/globalLongShortAccountRatio"  # weight 5
_FAPI_TAKER_LS_RATIO = "/futures/data/takerlongshortRatio"           # weight 5
_FAPI_KLINES = "/fapi/v1/klines"                   # weight 1-10

# Backfill endpoint
_FAPI_MARK_PRICE_KLINES = "/fapi/v1/markPriceKlines"  # weight 5


class BinanceCollector(BaseCollector):
    """Binance data collector optimised for minimal API weight usage.

    Architecture:
    1. WebSocket ``!markPrice@arr`` pushes price + funding for ALL symbols
       every 3 seconds at **zero** API weight cost.
    2. Bulk REST ``ticker/24hr`` fetches volume/24h stats for ALL symbols
       in a single call (weight 40).
    3. Rotary REST fetcher pulls OI / long-short ratio / taker ratio in
       small batches spread across minutes so we never exceed the 6000
       weight-per-minute hard cap.

    Weight budget per minute (steady state):
        WebSocket            :    0
        Bulk ticker (÷5 min) :    8  (amortised)
        OI  40 symbols/min   :   40
        Ratio 10 symbols/min :   50
        Taker 10 symbols/min :   50
        --------------------------
        Total                : ~148 / 6000  ✅
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
        self._liquidation_cache: dict[str, tuple[float, float]] = {}

        # ── rotary state ──────────────────────────────────────────────
        self._oi_batch_size = getattr(settings, "oi_batch_size", 40)
        self._ratio_batch_size = getattr(settings, "ratio_batch_size", 10)
        self._taker_batch_size = getattr(settings, "taker_batch_size", 10)
        self._oi_offset = 0
        self._ratio_offset = 0
        self._taker_offset = 0

        # ── WS state ─────────────────────────────────────────────────
        self._ws_task: asyncio.Task[None] | None = None
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
        self._rotary_tasks = [
            asyncio.create_task(self._rotary_oi_loop()),
            asyncio.create_task(self._rotary_ratio_loop()),
            asyncio.create_task(self._rotary_taker_loop()),
        ]
        logger.info(
            "BinanceCollector background started: %d symbols, "
            "OI batch=%d, ratio batch=%d, taker batch=%d",
            len(symbols),
            self._oi_batch_size,
            self._ratio_batch_size,
            self._taker_batch_size,
        )

    async def stop_background(self) -> None:
        self._running = False
        for task in self._rotary_tasks:
            task.cancel()
        if self._ws_task:
            self._ws_task.cancel()
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
                                    self._ws_prices[symbol] = self.parse_float(
                                        item.get("p")
                                    )
                                    self._ws_mark_prices[symbol] = self.parse_float(
                                        item.get("p")
                                    )
                                    self._ws_funding[symbol] = self.parse_float(
                                        item.get("r")
                                    )
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
            await asyncio.sleep(60)  # 40 calls/min = 40 weight/min

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
        semaphore = asyncio.Semaphore(self.settings.exchange_request_concurrency)

        async def fetch_one(symbol: str) -> None:
            async with semaphore:
                try:
                    response = await self.client.get(
                        f"{self.rest_url}{_FAPI_OPEN_INTEREST}",
                        params={"symbol": symbol},
                    )
                    response.raise_for_status()
                    data = response.json()
                    self._oi_cache[symbol] = self.parse_float(
                        data.get("openInterest")
                    )
                except Exception as exc:
                    logger.debug("OI fetch failed %s: %s", symbol, exc)

        await asyncio.gather(*(fetch_one(s) for s in symbols))

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
                            self._ls_ratio_cache[symbol] = long_account / short_account
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
                        self._taker_ratio_cache[symbol] = self.parse_float(
                            entries[0].get("buySellRatio"), 1.0
                        )
                except Exception as exc:
                    logger.debug("Taker fetch failed %s: %s", symbol, exc)

        await asyncio.gather(*(fetch_one(s) for s in symbols))

    # ─── main fetch interface ─────────────────────────────────────────

    async def fetch_snapshots(self, symbols: list[str]) -> dict[str, ExchangeSnapshot]:
        """Build snapshots by merging WS cache + bulk tickers + rotary caches.

        Called by SignalService._snapshot_cycle() every N seconds.
        Only the bulk ticker calls consume API weight here; everything
        else is already cached by background tasks.
        """
        # Refresh bulk tickers (weight 40 + 40 = 80 total, once per call)
        await asyncio.gather(
            self._fetch_bulk_tickers(),
            self._fetch_bulk_spot_tickers(),
        )

        timestamp = self.utcnow()
        snapshots: dict[str, ExchangeSnapshot] = {}

        for symbol in symbols:
            # Price: prefer WS, fall back to bulk ticker
            price = self._ws_prices.get(symbol, 0.0)
            if price <= 0:
                ticker = self._bulk_ticker.get(symbol, {})
                price = self.parse_float(ticker.get("lastPrice"))

            if price <= 0:
                continue  # skip symbols with no price data at all

            # Futures volume from bulk ticker
            futures_ticker = self._bulk_ticker.get(symbol, {})
            futures_volume = self.parse_float(futures_ticker.get("quoteVolume"))

            # Spot volume from bulk spot ticker
            spot_ticker = self._spot_ticker.get(symbol, {})
            spot_volume = self.parse_float(spot_ticker.get("quoteVolume"))

            # Funding from WS
            funding_rate = self._ws_funding.get(symbol, 0.0)

            # OI from rotary cache
            open_interest = self._oi_cache.get(symbol, 0.0)

            # Ratios from rotary cache
            long_short_ratio = self._ls_ratio_cache.get(symbol, 1.0)
            taker_ratio = self._taker_ratio_cache.get(symbol, 1.0)

            # Liquidations from cache (if available)
            liq = self._liquidation_cache.get(symbol, (0.0, 0.0))

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
                long_liquidations=liq[0],
                short_liquidations=liq[1],
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
        from backend.services.timeframe_aggregator import (
            TIMEFRAME_DELTAS,
            TimeframeBucket,
        )
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
                except Exception as exc:
                    logger.debug("Backfill kline failed %s/%s: %s", symbol, tf, exc)
                    return []

                buckets: list[Any] = []
                prev_bucket: TimeframeBucket | None = None
                for item in raw:
                    ts = datetime.fromtimestamp(item[0] / 1000, tz=UTC)
                    
                    total_vol = float(item[5])
                    taker_buy_vol = float(item[9]) if len(item) > 9 else 0.0
                    taker_sell_vol = total_vol - taker_buy_vol
                    # Calculate Taker Buy/Sell Ratio securely
                    taker_ratio = 1.0
                    if taker_sell_vol > 0:
                        taker_ratio = taker_buy_vol / taker_sell_vol
                    elif taker_buy_vol > 0:
                        taker_ratio = 10.0 # High cap if sell vol is 0
                        
                    point = HistoryPoint(
                        timestamp=ts,
                        price=float(item[4]),  # close
                        volume=total_vol,
                        open_interest=0.0,
                        funding_rate=0.0,
                        long_short_ratio=1.0,  # Cannot get from basic kline
                        taker_buy_sell_ratio=taker_ratio,
                        spot_volume=0.0,
                        futures_volume=float(item[7]) if len(item) > 7 else total_vol,
                        long_liquidations=0.0,
                        short_liquidations=0.0,
                        exchange_count=1,
                    )
                    bucket = TimeframeBucket.from_point(
                        symbol, tf, point, previous_bucket=prev_bucket
                    )
                    bucket.open_price = float(item[1])
                    bucket.high_price = float(item[2])
                    bucket.low_price = float(item[3])
                    bucket.close_price = float(item[4])
                    buckets.append(bucket)
                    prev_bucket = bucket

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
                    )
                    await callback(snapshot)
            await asyncio.sleep(3)