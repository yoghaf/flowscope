from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import insert, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from backend.config import Settings
from backend.models import AlertPreference, Base, LatestAssetState, MarketData, MarketDataBucket, SignalRecord, TradeSignal
from backend.schemas import AlertEntry, AssetSnapshot

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.engine: AsyncEngine = create_async_engine(
            settings.database_url,
            echo=settings.debug,
            pool_pre_ping=True,
        )
        self.session_factory = async_sessionmaker(
            bind=self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        self.enabled = False

    async def init(self) -> None:
        try:
            async with self.engine.begin() as connection:
                await connection.run_sync(Base.metadata.create_all)
                await connection.execute(
                    text(
                        "ALTER TABLE alert_preferences "
                        "ADD COLUMN IF NOT EXISTS timeframes JSON NOT NULL DEFAULT '[]'::json"
                    )
                )
                await connection.execute(
                    text(
                        "ALTER TABLE alert_preferences "
                        "ADD COLUMN IF NOT EXISTS telegram_enabled BOOLEAN NOT NULL DEFAULT FALSE"
                    )
                )
                await connection.execute(
                    text(
                        "ALTER TABLE alert_preferences "
                        "ADD COLUMN IF NOT EXISTS telegram_chat_id VARCHAR(80)"
                    )
                )
                await connection.execute(
                    text(
                        "ALTER TABLE trade_signals "
                        "ADD COLUMN IF NOT EXISTS entry_touched_at TIMESTAMPTZ"
                    )
                )
                await connection.execute(
                    text(
                        "ALTER TABLE trade_signals "
                        "ADD COLUMN IF NOT EXISTS entry_flow_alignment DOUBLE PRECISION"
                    )
                )
                await connection.execute(
                    text(
                        "ALTER TABLE trade_signals "
                        "ADD COLUMN IF NOT EXISTS fill_count INTEGER NOT NULL DEFAULT 1"
                    )
                )
                await connection.execute(
                    text(
                        "ALTER TABLE trade_signals "
                        "ADD COLUMN IF NOT EXISTS last_scale_in_at TIMESTAMPTZ"
                    )
                )
                await connection.execute(
                    text(
                        "ALTER TABLE trade_signals "
                        "ADD COLUMN IF NOT EXISTS entry_notification_sent_at TIMESTAMPTZ"
                    )
                )
                await connection.execute(
                    text(
                        "ALTER TABLE trade_signals "
                        "ADD COLUMN IF NOT EXISTS closed_at TIMESTAMPTZ"
                    )
                )
                await connection.execute(
                    text(
                        "ALTER TABLE trade_signals "
                        "ADD COLUMN IF NOT EXISTS close_reason VARCHAR(32)"
                    )
                )
            self.enabled = True
        except Exception as exc:
            logger.warning("Database initialization skipped: %s", exc)
            self.enabled = False

    async def close(self) -> None:
        await self.engine.dispose()

    async def save_market_snapshots(self, assets: Iterable[AssetSnapshot]) -> None:
        if not self.enabled:
            return

        rows = [
            {
                "timestamp": asset.timestamp,
                "symbol": asset.symbol,
                "price": asset.price,
                "volume": asset.volume,
                "spot_volume": asset.spot_volume,
                "futures_volume": asset.futures_volume,
                "open_interest": asset.open_interest,
                "funding_rate": asset.funding_rate,
                "long_short_ratio": asset.long_short_ratio,
                "long_liquidations": asset.long_liquidations,
                "short_liquidations": asset.short_liquidations,
                "exchange_count": asset.exchange_count,
                "score": asset.score,
                "signal_type": asset.signal,
            }
            for asset in assets
        ]
        if not rows:
            return

        async with self.session_factory() as session:
            await session.execute(insert(MarketData), rows)
            await session.commit()

    async def save_signal(self, alert: AlertEntry, details: dict[str, float] | None = None) -> None:
        if not self.enabled:
            return

        async with self.session_factory() as session:
            await session.execute(
                insert(SignalRecord).values(
                    timestamp=alert.timestamp,
                    symbol=alert.symbol,
                    signal_type=alert.signal,
                    score=alert.score,
                    details=details or {},
                )
            )
            await session.commit()

    async def save_market_buckets(self, rows: Iterable[dict[str, object]]) -> None:
        if not self.enabled:
            return

        payload = list(rows)
        if not payload:
            return

        statement = pg_insert(MarketDataBucket).values(payload)
        excluded = statement.excluded
        upsert = statement.on_conflict_do_update(
            index_elements=["symbol", "timeframe", "bucket_start"],
            set_={
                "bucket_end": excluded.bucket_end,
                "last_timestamp": excluded.last_timestamp,
                "open_price": excluded.open_price,
                "high_price": excluded.high_price,
                "low_price": excluded.low_price,
                "close_price": excluded.close_price,
                "open_interest_open": excluded.open_interest_open,
                "open_interest_high": excluded.open_interest_high,
                "open_interest_low": excluded.open_interest_low,
                "open_interest_close": excluded.open_interest_close,
                "spot_volume_open": excluded.spot_volume_open,
                "spot_volume_close": excluded.spot_volume_close,
                "spot_volume_delta": excluded.spot_volume_delta,
                "futures_volume_open": excluded.futures_volume_open,
                "futures_volume_close": excluded.futures_volume_close,
                "futures_volume_delta": excluded.futures_volume_delta,
                "volume_delta": excluded.volume_delta,
                "funding_rate_avg": excluded.funding_rate_avg,
                "funding_rate_close": excluded.funding_rate_close,
                "long_short_ratio_avg": excluded.long_short_ratio_avg,
                "long_short_ratio_close": excluded.long_short_ratio_close,
                "taker_buy_sell_ratio_avg": excluded.taker_buy_sell_ratio_avg,
                "taker_buy_sell_ratio_close": excluded.taker_buy_sell_ratio_close,
                "long_liquidations_total": excluded.long_liquidations_total,
                "short_liquidations_total": excluded.short_liquidations_total,
                "exchange_count_avg": excluded.exchange_count_avg,
                "sample_count": excluded.sample_count,
                "score": excluded.score,
                "signal_type": excluded.signal_type,
                "breakdown_open_interest": excluded.breakdown_open_interest,
                "breakdown_volume": excluded.breakdown_volume,
                "breakdown_compression": excluded.breakdown_compression,
                "breakdown_funding": excluded.breakdown_funding,
            },
        )

        async with self.session_factory() as session:
            await session.execute(upsert)
            await session.commit()

    async def save_latest_asset_states(self, snapshots: Iterable[AssetSnapshot]) -> None:
        if not self.enabled:
            return

        payload = [
            {
                "symbol": snapshot.symbol,
                "timeframe": snapshot.timeframe,
                "updated_at": snapshot.timestamp,
                "snapshot": snapshot.model_dump(mode="json"),
            }
            for snapshot in snapshots
        ]
        if not payload:
            return

        statement = pg_insert(LatestAssetState).values(payload)
        excluded = statement.excluded
        upsert = statement.on_conflict_do_update(
            index_elements=["symbol", "timeframe"],
            set_={
                "updated_at": excluded.updated_at,
                "snapshot": excluded.snapshot,
            },
        )

        async with self.session_factory() as session:
            await session.execute(upsert)
            await session.commit()

    async def save_trade_signal(self, payload: dict[str, object]) -> int | None:
        if not self.enabled:
            return None

        async with self.session_factory() as session:
            result = await session.execute(insert(TradeSignal).values(payload).returning(TradeSignal.id))
            await session.commit()
            row = result.first()
            return row[0] if row else None

    async def update_trade_signal(self, trade_id: int, payload: dict[str, object]) -> None:
        if not self.enabled:
            return

        async with self.session_factory() as session:
            await session.execute(
                update(TradeSignal)
                .where(TradeSignal.id == trade_id)
                .values(**payload)
            )
            await session.commit()

    async def load_open_trade_signals(self) -> list[TradeSignal]:
        if not self.enabled:
            return []

        statement = select(TradeSignal).where(TradeSignal.result == "open")
        async with self.session_factory() as session:
            result = await session.scalars(statement)
            return list(result)

    async def has_open_trade_signal(
        self,
        *,
        symbol: str,
        timeframe: str,
        state: str,
        setup_type: str,
        bias: str,
    ) -> bool:
        if not self.enabled:
            return False

        statement = (
            select(TradeSignal.id)
            .where(TradeSignal.symbol == symbol)
            .where(TradeSignal.timeframe == timeframe)
            .where(TradeSignal.state == state)
            .where(TradeSignal.setup_type == setup_type)
            .where(TradeSignal.bias == bias)
            .where(TradeSignal.result == "open")
            .limit(1)
        )
        async with self.session_factory() as session:
            result = await session.execute(statement)
            return result.first() is not None

    async def get_open_trade_signal(
        self,
        *,
        symbol: str,
        timeframe: str,
    ) -> TradeSignal | None:
        if not self.enabled:
            return None

        statement = (
            select(TradeSignal)
            .where(TradeSignal.symbol == symbol)
            .where(TradeSignal.timeframe == timeframe)
            .where(TradeSignal.result == "open")
            .order_by(TradeSignal.created_at.desc(), TradeSignal.id.desc())
            .limit(1)
        )
        async with self.session_factory() as session:
            result = await session.execute(statement)
            return result.scalar_one_or_none()

    async def has_trade_signal_event(
        self,
        *,
        symbol: str,
        timeframe: str,
        state: str,
        setup_type: str,
        bias: str,
        timestamp: datetime,
    ) -> bool:
        if not self.enabled:
            return False

        statement = (
            select(TradeSignal.id)
            .where(TradeSignal.symbol == symbol)
            .where(TradeSignal.timeframe == timeframe)
            .where(TradeSignal.state == state)
            .where(TradeSignal.setup_type == setup_type)
            .where(TradeSignal.bias == bias)
            .where(TradeSignal.timestamp == timestamp)
            .limit(1)
        )
        async with self.session_factory() as session:
            result = await session.execute(statement)
            return result.first() is not None

    async def list_trade_signals(self, result_filter: str | None = None) -> list[TradeSignal]:
        if not self.enabled:
            return []

        statement = select(TradeSignal)
        if result_filter:
            statement = statement.where(TradeSignal.result == result_filter)
        async with self.session_factory() as session:
            result = await session.scalars(statement)
            return list(result)

    async def get_alert_preferences(self, user_id: str) -> AlertPreference | None:
        if not self.enabled:
            return None
        async with self.session_factory() as session:
            return await session.get(AlertPreference, user_id)

    async def list_alert_preferences(self) -> list[AlertPreference]:
        if not self.enabled:
            return []
        statement = select(AlertPreference).order_by(AlertPreference.updated_at.desc())
        async with self.session_factory() as session:
            result = await session.scalars(statement)
            return list(result)

    async def upsert_alert_preferences(self, payload: dict[str, object]) -> None:
        if not self.enabled:
            return

        statement = pg_insert(AlertPreference).values(payload)
        excluded = statement.excluded
        upsert = statement.on_conflict_do_update(
            index_elements=["user_id"],
            set_={
                "timeframes": excluded.timeframes,
                "signal_types": excluded.signal_types,
                "watchlist": excluded.watchlist,
                "min_score": excluded.min_score,
                "debounce_minutes": excluded.debounce_minutes,
                "enabled": excluded.enabled,
                "telegram_enabled": excluded.telegram_enabled,
                "telegram_chat_id": excluded.telegram_chat_id,
                "updated_at": excluded.updated_at,
            },
        )

        async with self.session_factory() as session:
            await session.execute(upsert)
            await session.commit()

    async def load_market_buckets(
        self,
        symbols: Iterable[str],
        since: datetime,
        timeframes: Iterable[str],
    ) -> list[MarketDataBucket]:
        if not self.enabled:
            return []

        symbol_list = list(symbols)
        timeframe_list = list(timeframes)
        if not symbol_list or not timeframe_list:
            return []

        statement = (
            select(MarketDataBucket)
            .where(MarketDataBucket.symbol.in_(symbol_list))
            .where(MarketDataBucket.timeframe.in_(timeframe_list))
            .where(MarketDataBucket.bucket_start >= since)
            .order_by(
                MarketDataBucket.symbol.asc(),
                MarketDataBucket.timeframe.asc(),
                MarketDataBucket.bucket_start.asc(),
            )
        )

        async with self.session_factory() as session:
            result = await session.scalars(statement)
            return list(result)

    async def load_latest_asset_states(
        self,
        symbols: Iterable[str],
        timeframes: Iterable[str],
    ) -> list[AssetSnapshot]:
        if not self.enabled:
            return []

        symbol_list = list(symbols)
        timeframe_list = list(timeframes)
        if not symbol_list or not timeframe_list:
            return []

        statement = (
            select(LatestAssetState)
            .where(LatestAssetState.symbol.in_(symbol_list))
            .where(LatestAssetState.timeframe.in_(timeframe_list))
            .order_by(LatestAssetState.symbol.asc(), LatestAssetState.timeframe.asc())
        )

        async with self.session_factory() as session:
            result = await session.scalars(statement)
            rows = list(result)
        return [AssetSnapshot.model_validate(row.snapshot) for row in rows]

    async def load_latest_buckets_all(
        self,
        timeframes: list[str] | None = None,
    ) -> list[MarketDataBucket]:
        """Load the most recent bucket per symbol per timeframe.

        Used at startup to warm the in-memory cache from DB so the
        frontend has data to serve immediately.
        """
        if not self.enabled:
            return []

        from sqlalchemy import func as sa_func

        target_timeframes = timeframes or ["15m", "1h", "4h", "24h"]

        # Subquery: max bucket_start per (symbol, timeframe)
        subq = (
            select(
                MarketDataBucket.symbol,
                MarketDataBucket.timeframe,
                sa_func.max(MarketDataBucket.bucket_start).label("max_start"),
            )
            .where(MarketDataBucket.timeframe.in_(target_timeframes))
            .group_by(MarketDataBucket.symbol, MarketDataBucket.timeframe)
            .subquery()
        )

        statement = (
            select(MarketDataBucket)
            .join(
                subq,
                (MarketDataBucket.symbol == subq.c.symbol)
                & (MarketDataBucket.timeframe == subq.c.timeframe)
                & (MarketDataBucket.bucket_start == subq.c.max_start),
            )
        )

        async with self.session_factory() as session:
            result = await session.scalars(statement)
            return list(result)
