from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
UTC = timezone.utc
import logging
from typing import Any

import httpx

from backend.config import Settings


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ExchangeSnapshot:
    exchange: str
    symbol: str
    timestamp: datetime
    price: float = 0.0
    spot_volume: float = 0.0
    futures_volume: float = 0.0
    open_interest: float = 0.0
    funding_rate: float = 0.0
    long_short_ratio: float = 1.0
    taker_buy_sell_ratio: float = 1.0
    long_liquidations: float = 0.0
    short_liquidations: float = 0.0
    
    # Timeframe-specific volumes (Official Kline Quote Volume)
    futures_volume_15m: float = 0.0
    futures_volume_1h: float = 0.0
    futures_volume_4h: float = 0.0
    futures_volume_24h: float = 0.0

    # Timeframe-specific OHLCV (Official Kline Ground Truth)
    futures_ohlc_15m: dict[str, float] | None = None
    futures_ohlc_1h: dict[str, float] | None = None
    futures_ohlc_4h: dict[str, float] | None = None
    futures_ohlc_24h: dict[str, float] | None = None

    # Data Quality Metadata
    price_updated_at: datetime | None = None
    spot_volume_updated_at: datetime | None = None
    futures_volume_updated_at: datetime | None = None
    open_interest_updated_at: datetime | None = None
    funding_rate_updated_at: datetime | None = None
    long_short_ratio_updated_at: datetime | None = None
    taker_buy_sell_ratio_updated_at: datetime | None = None
    liquidation_updated_at: datetime | None = None

    price_source: str = "missing"
    volume_source: str = "missing"
    open_interest_source: str = "missing"
    funding_source: str = "missing"
    long_short_ratio_source: str = "missing"
    taker_ratio_source: str = "missing"
    liquidation_source: str = "missing"

    data_was_coalesced: bool = False
    liquidation_is_reset_suspected: bool = False


class BaseCollector:
    exchange_name = "base"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = httpx.AsyncClient(
            timeout=settings.exchange_timeout_seconds,
            limits=httpx.Limits(
                max_connections=settings.exchange_request_concurrency,
                max_keepalive_connections=settings.exchange_request_concurrency,
            ),
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def fetch_snapshots(self, symbols: list[str]) -> dict[str, ExchangeSnapshot]:
        raise NotImplementedError

    async def stream_prices(
        self,
        symbols: list[str],
        callback: Callable[[ExchangeSnapshot], Awaitable[None]],
    ) -> None:
        while True:
            await asyncio.sleep(60)

    @staticmethod
    def utcnow() -> datetime:
        return datetime.now(UTC)

    @staticmethod
    def chunked(items: Iterable[str], size: int) -> list[list[str]]:
        chunk: list[str] = []
        chunks: list[list[str]] = []
        for item in items:
            chunk.append(item)
            if len(chunk) == size:
                chunks.append(chunk)
                chunk = []
        if chunk:
            chunks.append(chunk)
        return chunks

    @staticmethod
    def parse_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    async def gather_symbol_map(
        self,
        symbols: list[str],
        worker: Callable[[str], Awaitable[tuple[str, float]]],
    ) -> dict[str, float]:
        semaphore = asyncio.Semaphore(self.settings.exchange_request_concurrency)

        async def guarded(symbol: str) -> tuple[str, float] | None:
            async with semaphore:
                try:
                    return await worker(symbol)
                except Exception as exc:
                    logger.error("[CollectorError] %s: %s", symbol, exc)
                    return None

        results = await asyncio.gather(*(guarded(symbol) for symbol in symbols))
        return {
            symbol: value
            for result in results
            if result is not None
            for symbol, value in [result]
        }
