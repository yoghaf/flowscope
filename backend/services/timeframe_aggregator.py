from __future__ import annotations

from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
UTC = timezone.utc
import logging
import math
from typing import Any

from backend.config import TIMEFRAME_PROFILES
from backend.engines.flow_engine import FlowEngine, HistoryPoint
from backend.schemas import FlowMetrics

TIMEFRAME_DELTAS: dict[str, timedelta] = {
    "15m": timedelta(minutes=15),
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
    "24h": timedelta(hours=24),
}
TIMEFRAME_ORDER = tuple(TIMEFRAME_DELTAS.keys())
VOLUME_BASELINE_FLOOR = 1.0
DELTA_EPSILON = 1e-12
ROBUST_EPSILON = 1e-9
DEFAULT_Z_WINDOW = 20
DEFAULT_PERCENTILE_WINDOW = 100
DEFAULT_STRUCTURE_WINDOW = 20
MIN_MAD_THRESHOLD = 1e-6
Z_SCORE_CLAMP = 20.0
FUNDING_PROVENANCE_SLA_SECONDS = 30.0

logger = logging.getLogger(__name__)


def floor_timestamp(timestamp: datetime, timeframe: str) -> datetime:
    normalized = timestamp.astimezone(UTC)
    bucket_seconds = int(TIMEFRAME_DELTAS[timeframe].total_seconds())
    epoch_seconds = int(normalized.timestamp())
    floored_seconds = epoch_seconds - (epoch_seconds % bucket_seconds)
    return datetime.fromtimestamp(floored_seconds, tz=UTC)


@dataclass(slots=True)
class TimeframeBucket:
    symbol: str
    timeframe: str
    bucket_start: datetime
    bucket_end: datetime
    last_timestamp: datetime
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    open_interest_open: float
    open_interest_high: float
    open_interest_low: float
    open_interest_close: float
    spot_volume_open: float
    spot_volume_close: float
    spot_volume_delta: float
    futures_volume_open: float
    futures_volume_close: float
    futures_volume_delta: float
    funding_rate_sum: float
    funding_rate_close: float
    long_short_ratio_sum: float
    long_short_ratio_close: float
    taker_buy_sell_ratio_sum: float
    taker_buy_sell_ratio_close: float
    long_liquidations_close: float
    long_liquidations_total: float
    short_liquidations_close: float = 0.0
    short_liquidations_total: float = 0.0
    exchange_count_sum: int = 0
    sample_count: int = 0

    # Data Quality Aggregates
    coalesced_sample_count: int = 0
    liquidation_reset_suspected: bool = False
    
    # Sources (latest in bucket)
    price_source: str = "missing"
    volume_source: str = "missing"
    oi_source: str = "missing"
    liq_source: str = "missing"
    funding_rate_updated_at: datetime | None = None
    funding_source: str = "missing"
    
    # OI Boundary Alignment
    oi_open_timestamp: datetime | None = None
    oi_close_timestamp: datetime | None = None
    oi_open_age: float | None = None
    oi_close_age: float | None = None
    oi_alignment_status: str = "MISSING"
    oi_delta_reliable: bool = False

    score: float = 0.0
    signal_type: str = "Neutral"
    breakdown_open_interest: float = 0.0
    breakdown_volume: float = 0.0
    breakdown_compression: float = 0.0
    breakdown_funding: float = 0.0
    
    foundation_version: str = "v2_option_a"
    
    # Data Quality & Reliability (Shadow Audit)
    bucket_is_closed: bool = False
    bucket_completion_pct: float = 0.0
    volume_z_reliable: bool = True
    oi_delta_z_reliable: bool = True
    zscore_baseline_status: str = "NORMAL"

    @classmethod
    def from_record(cls, source: Any) -> TimeframeBucket:
        if isinstance(source, dict):
            getter = source.get
        else:
            getter = lambda key, default=None: getattr(source, key, default)
        sample_count = getter("sample_count", 0) or 0
        divisor = max(sample_count, 1)

        return cls(
            symbol=getter("symbol", ""),
            timeframe=getter("timeframe", "15m"),
            bucket_start=getter("bucket_start"),
            bucket_end=getter("bucket_end"),
            last_timestamp=getter("last_timestamp"),
            open_price=getter("open_price", 0.0),
            high_price=getter("high_price", 0.0),
            low_price=getter("low_price", 0.0),
            close_price=getter("close_price", 0.0),
            open_interest_open=getter("open_interest_open", 0.0),
            open_interest_high=getter("open_interest_high", 0.0),
            open_interest_low=getter("open_interest_low", 0.0),
            open_interest_close=getter("open_interest_close", 0.0),
            spot_volume_open=getter("spot_volume_open", 0.0),
            spot_volume_close=getter("spot_volume_close", 0.0),
            spot_volume_delta=getter("spot_volume_delta", 0.0),
            futures_volume_open=getter("futures_volume_open", 0.0),
            futures_volume_close=getter("futures_volume_close", 0.0),
            futures_volume_delta=getter("futures_volume_delta", 0.0),
            funding_rate_sum=getter("funding_rate_avg", 0.0) * divisor,
            funding_rate_close=getter("funding_rate_close", 0.0),
            long_short_ratio_sum=getter("long_short_ratio_avg", 1.0) * divisor,
            long_short_ratio_close=getter("long_short_ratio_close", 1.0),
            taker_buy_sell_ratio_sum=getter("taker_buy_sell_ratio_avg", 1.0) * divisor,
            taker_buy_sell_ratio_close=getter("taker_buy_sell_ratio_close", 1.0),
            long_liquidations_close=getter("long_liquidations_total", 0.0),
            long_liquidations_total=getter("long_liquidations_total", 0.0),
            short_liquidations_close=getter("short_liquidations_total", 0.0),
            short_liquidations_total=getter("short_liquidations_total", 0.0),
            exchange_count_sum=getter("exchange_count_avg", 0) * divisor,
            sample_count=sample_count,
            score=getter("score", 0.0),
            signal_type=getter("signal_type", "Neutral"),
            breakdown_open_interest=getter("breakdown_open_interest", 0.0),
            breakdown_volume=getter("breakdown_volume", 0.0),
            breakdown_compression=getter("breakdown_compression", 0.0),
            breakdown_funding=getter("breakdown_funding", 0.0),
            foundation_version=getter("foundation_version", "v1_reconstructed"),
            oi_open_timestamp=getter("oi_open_timestamp"),
            oi_close_timestamp=getter("oi_close_timestamp"),
            oi_open_age=getter("oi_open_age"),
            oi_close_age=getter("oi_close_age"),
            oi_alignment_status=getter("oi_alignment_status", "MISSING"),
            oi_delta_reliable=bool(getter("oi_delta_reliable", False)),
            funding_rate_updated_at=getter("funding_rate_updated_at"),
            funding_source=getter("funding_source", "missing"),
        )

    @classmethod
    def from_point(
        cls,
        symbol: str,
        timeframe: str,
        point: HistoryPoint,
        previous_bucket: TimeframeBucket | None = None,
    ) -> TimeframeBucket:
        bucket_start = floor_timestamp(point.timestamp, timeframe)
        open_price = previous_bucket.close_price if previous_bucket is not None else point.price
        close_price = point.price if point.price > 0 else open_price
        open_interest_open = (
            previous_bucket.open_interest_close if previous_bucket is not None else point.open_interest
        )
        open_interest_close = point.open_interest if point.open_interest > 0 else open_interest_open
        spot_volume_open = (
            previous_bucket.spot_volume_close if previous_bucket is not None else point.spot_volume
        )
        spot_volume_close = point.spot_volume if point.spot_volume > 0 else spot_volume_open
        futures_volume_open = (
            previous_bucket.futures_volume_close if previous_bucket is not None else point.futures_volume
        )
        futures_volume_close = (
            point.futures_volume if point.futures_volume > 0 else futures_volume_open
        )
        spot_volume_delta = cls._volume_increment(spot_volume_open, spot_volume_close)
        futures_volume_delta = 0.0
        official = None
        if timeframe == "15m":
            official = point.futures_ohlc_15m
        elif timeframe == "1h":
            official = point.futures_ohlc_1h
        elif timeframe == "4h":
            official = point.futures_ohlc_4h
        elif timeframe == "24h":
            official = point.futures_ohlc_24h
            
        if official:
            open_price = official["open"]
            close_price = official["close"]
            futures_volume_delta = official["volume"]
            futures_volume_close = official["volume"]
        else:
            futures_volume_delta = cls._volume_increment(futures_volume_open, futures_volume_close)
        long_liquidations_close = max(point.long_liquidations, 0.0)
        short_liquidations_close = max(point.short_liquidations, 0.0)
        long_liquidations_baseline = (
            previous_bucket.long_liquidations_close if previous_bucket is not None else 0.0
        )
        short_liquidations_baseline = (
            previous_bucket.short_liquidations_close if previous_bucket is not None else 0.0
        )
        return cls(
            symbol=symbol,
            timeframe=timeframe,
            bucket_start=bucket_start,
            bucket_end=bucket_start + TIMEFRAME_DELTAS[timeframe],
            last_timestamp=point.timestamp,
            open_price=open_price,
            high_price=max(open_price, close_price, official["high"] if official else 0.0),
            low_price=min(open_price, close_price, official["low"] if official else 999999.0),
            close_price=close_price,
            open_interest_open=open_interest_open,
            open_interest_high=max(open_interest_open, open_interest_close),
            open_interest_low=min(open_interest_open, open_interest_close),
            open_interest_close=open_interest_close,
            spot_volume_open=spot_volume_open,
            spot_volume_close=spot_volume_close,
            spot_volume_delta=spot_volume_delta if (previous_bucket is not None or (official and official["volume"] > 0)) else 0.0,
            futures_volume_open=futures_volume_open,
            futures_volume_close=futures_volume_close,
            futures_volume_delta=futures_volume_delta if (previous_bucket is not None or (official and official["volume"] > 0)) else 0.0,
            funding_rate_sum=point.funding_rate,
            funding_rate_close=point.funding_rate,
            funding_rate_updated_at=point.funding_rate_updated_at,
            funding_source=point.funding_source,
            long_short_ratio_sum=point.long_short_ratio,
            long_short_ratio_close=point.long_short_ratio,
            taker_buy_sell_ratio_sum=point.taker_buy_sell_ratio,
            taker_buy_sell_ratio_close=point.taker_buy_sell_ratio,
            long_liquidations_close=long_liquidations_close,
            long_liquidations_total=max(long_liquidations_close - long_liquidations_baseline, 0.0),
            short_liquidations_close=short_liquidations_close,
            short_liquidations_total=max(short_liquidations_close - short_liquidations_baseline, 0.0),
            exchange_count_sum=max(point.exchange_count, 0),
            sample_count=1,
            coalesced_sample_count=1 if point.data_was_coalesced else 0,
            liquidation_reset_suspected=point.liquidation_is_reset_suspected,
            price_source=point.price_source,
            volume_source=point.volume_source,
            oi_source=point.open_interest_source,
            liq_source=point.liquidation_source,
        )

    @property
    def volume_delta(self) -> float:
        return self.spot_volume_delta + self.futures_volume_delta

    @property
    def avg_funding_rate(self) -> float:
        if not self.sample_count:
            return 0.0
        return self.funding_rate_sum / self.sample_count

    @property
    def avg_long_short_ratio(self) -> float:
        if not self.sample_count:
            return 1.0
        return self.long_short_ratio_sum / self.sample_count

    @property
    def avg_taker_buy_sell_ratio(self) -> float:
        if not self.sample_count:
            return 1.0
        return self.taker_buy_sell_ratio_sum / self.sample_count

    @property
    def avg_exchange_count(self) -> int:
        if not self.sample_count:
            return 0
        return round(self.exchange_count_sum / self.sample_count)

    def apply_point(self, point: HistoryPoint) -> None:
        self.last_timestamp = point.timestamp
        self.high_price = max(self.high_price, point.price)
        self.low_price = min(self.low_price, point.price)
        self.close_price = point.price

        self.open_interest_high = max(self.open_interest_high, point.open_interest)
        self.open_interest_low = min(self.open_interest_low, point.open_interest)
        self.open_interest_close = point.open_interest

        self.spot_volume_delta += self._volume_increment(self.spot_volume_close, point.spot_volume)
        
        # Use official ground truth if available for this timeframe
        official = None
        if self.timeframe == "15m":
            official = point.futures_ohlc_15m
        elif self.timeframe == "1h":
            official = point.futures_ohlc_1h
        elif self.timeframe == "4h":
            official = point.futures_ohlc_4h
        elif self.timeframe == "24h":
            official = point.futures_ohlc_24h
            
        if official:
            self.high_price = max(self.high_price, official["high"])
            self.low_price = min(self.low_price, official["low"])
            self.close_price = official["close"]
            self.futures_volume_delta = official["volume"]
            self.futures_volume_close = official["volume"]
        else:
            self.high_price = max(self.high_price, point.price)
            self.low_price = min(self.low_price, point.price)
            self.close_price = point.price
            # Fallback to reconstruction from 1m snapshots
            self.futures_volume_delta += self._volume_increment(self.futures_volume_close, point.futures_volume)
            self.futures_volume_close = point.futures_volume

        self.spot_volume_close = point.spot_volume

        self.funding_rate_sum += point.funding_rate
        self.funding_rate_close = point.funding_rate
        if point.funding_source not in ("missing", "missing_at_startup"):
            if point.funding_rate_updated_at is not None:
                self.funding_rate_updated_at = point.funding_rate_updated_at
                self.funding_source = point.funding_source
            elif point.funding_source != "carry_forward":
                self.funding_source = point.funding_source
            elif self.funding_rate_updated_at is not None:
                self.funding_source = "carry_forward"

        self.long_short_ratio_sum += point.long_short_ratio
        self.long_short_ratio_close = point.long_short_ratio

        self.taker_buy_sell_ratio_sum += point.taker_buy_sell_ratio
        self.taker_buy_sell_ratio_close = point.taker_buy_sell_ratio

        self.long_liquidations_total += max(point.long_liquidations - self.long_liquidations_close, 0.0)
        self.short_liquidations_total += max(point.short_liquidations - self.short_liquidations_close, 0.0)
        self.long_liquidations_close = max(point.long_liquidations, 0.0)
        self.short_liquidations_close = max(point.short_liquidations, 0.0)
        self.exchange_count_sum += max(point.exchange_count, 0)
        self.sample_count += 1
        
        # DQ Tracking
        if point.data_was_coalesced:
            self.coalesced_sample_count += 1
        if point.liquidation_is_reset_suspected:
            self.liquidation_reset_suspected = True
            
        self.price_source = point.price_source
        self.volume_source = point.volume_source
        self.oi_source = point.open_interest_source
        self.liq_source = point.liquidation_source

    @staticmethod
    def _volume_increment(previous_value: float, current_value: float) -> float:
        if current_value <= 0.0:
            return 0.0
        if previous_value <= 0.0:
            return current_value
        if current_value >= previous_value:
            return current_value - previous_value
        return current_value

    def apply_signal(
        self,
        score: float,
        signal_type: str,
        breakdown: dict[str, float],
    ) -> None:
        self.score = score
        self.signal_type = signal_type
        self.breakdown_open_interest = breakdown.get("open_interest", 0.0)
        self.breakdown_volume = breakdown.get("volume", 0.0)
        self.breakdown_compression = breakdown.get("compression", 0.0)
        self.breakdown_funding = breakdown.get("funding", 0.0)

    def to_history_point(self) -> HistoryPoint:
        return HistoryPoint(
            timestamp=self.last_timestamp,
            price=self.close_price,
            volume=self.volume_delta,
            open_interest=self.open_interest_close,
            funding_rate=self.funding_rate_close,
            long_short_ratio=self.long_short_ratio_close,
            taker_buy_sell_ratio=self.taker_buy_sell_ratio_close,
            spot_volume=self.spot_volume_delta,
            futures_volume=self.futures_volume_delta,
            long_liquidations=self.long_liquidations_total,
            short_liquidations=self.short_liquidations_total,
            exchange_count=self.avg_exchange_count,
        )

    def to_snapshot_point(self) -> HistoryPoint:
        return HistoryPoint(
            timestamp=self.last_timestamp,
            price=self.close_price,
            volume=self.spot_volume_close + self.futures_volume_close,
            open_interest=self.open_interest_close,
            funding_rate=self.funding_rate_close,
            long_short_ratio=self.long_short_ratio_close,
            taker_buy_sell_ratio=self.taker_buy_sell_ratio_close,
            spot_volume=self.spot_volume_close,
            futures_volume=self.futures_volume_close,
            long_liquidations=self.long_liquidations_close,
            short_liquidations=self.short_liquidations_close,
            exchange_count=self.avg_exchange_count,
        )

    def to_record(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "bucket_start": self.bucket_start,
            "bucket_end": self.bucket_end,
            "last_timestamp": self.last_timestamp,
            "open_price": self.open_price,
            "high_price": self.high_price,
            "low_price": self.low_price,
            "close_price": self.close_price,
            "open_interest_open": self.open_interest_open,
            "open_interest_high": self.open_interest_high,
            "open_interest_low": self.open_interest_low,
            "open_interest_close": self.open_interest_close,
            "spot_volume_open": self.spot_volume_open,
            "spot_volume_close": self.spot_volume_close,
            "spot_volume_delta": self.spot_volume_delta,
            "futures_volume_open": self.futures_volume_open,
            "futures_volume_close": self.futures_volume_close,
            "futures_volume_delta": self.futures_volume_delta,
            "volume_delta": self.volume_delta,
            "funding_rate_avg": self.avg_funding_rate,
            "funding_rate_close": self.funding_rate_close,
            "long_short_ratio_avg": self.avg_long_short_ratio,
            "long_short_ratio_close": self.long_short_ratio_close,
            "taker_buy_sell_ratio_avg": self.avg_taker_buy_sell_ratio,
            "taker_buy_sell_ratio_close": self.taker_buy_sell_ratio_close,
            "long_liquidations_total": self.long_liquidations_total,
            "short_liquidations_total": self.short_liquidations_total,
            "exchange_count_avg": self.avg_exchange_count,
            "sample_count": self.sample_count,
            "score": self.score,
            "signal_type": self.signal_type,
            "breakdown_open_interest": self.breakdown_open_interest,
            "breakdown_volume": self.breakdown_volume,
            "breakdown_compression": self.breakdown_compression,
            "breakdown_funding": self.breakdown_funding,
            "foundation_version": self.foundation_version,
            "bucket_is_closed": self.bucket_is_closed,
            "bucket_completion_pct": self.bucket_completion_pct,
            # OI Alignment (Persistent fields)
            "oi_open_timestamp": self.oi_open_timestamp,
            "oi_close_timestamp": self.oi_close_timestamp,
            "oi_open_age": self.oi_open_age,
            "oi_close_age": self.oi_close_age,
            "oi_alignment_status": self.oi_alignment_status,
            "oi_delta_reliable": self.oi_delta_reliable,
        }



OI_ALIGNMENT_TOLERANCE = {
    "15m": 120,
    "1h": 300,
    "4h": 600,
    "24h": 1800,
}


class TimeframeAggregateStore:
    def __init__(self, retention_points: int) -> None:
        self.flow_engine = FlowEngine()
        self.buckets: dict[str, defaultdict[str, deque[TimeframeBucket]]] = {
            timeframe: defaultdict(lambda: deque(maxlen=retention_points))
            for timeframe in TIMEFRAME_ORDER
        }

    def _update_bucket_lifecycle(self, bucket: TimeframeBucket, now: datetime) -> None:
        """Update bucket completion and closed status based on time."""
        tf_seconds = TIMEFRAME_DELTAS[bucket.timeframe].total_seconds()
        elapsed = (bucket.last_timestamp - bucket.bucket_start).total_seconds()
        bucket.bucket_completion_pct = round(min(max(elapsed / tf_seconds, 0.0), 1.0), 4)
        
        # A bucket is closed if the current time has passed its end
        if now >= bucket.bucket_end:
            bucket.bucket_is_closed = True
            bucket.bucket_completion_pct = 1.0

    def _finalize_bucket(self, bucket: TimeframeBucket, oi_history: deque[tuple[datetime, float]] | None = None) -> None:
        """Lock bucket state and perform final boundary alignment."""
        bucket.bucket_is_closed = True
        bucket.bucket_completion_pct = 1.0
        # Ensure last_timestamp doesn't leak into next bucket
        if bucket.last_timestamp > bucket.bucket_end:
            bucket.last_timestamp = bucket.bucket_end
            
        if oi_history is not None:
            self._align_oi_boundary(bucket, oi_history, update_open=False)

    def ingest(self, symbol: str, point: HistoryPoint, oi_history: dict[str, deque[tuple[datetime, float]]] | None = None) -> dict[str, list[TimeframeBucket]]:
        updated: dict[str, list[TimeframeBucket]] = {}
        symbol_oi_history = oi_history.get(symbol, deque()) if oi_history else None

        for timeframe in TIMEFRAME_ORDER:
            bucket_start = floor_timestamp(point.timestamp, timeframe)
            history = self.buckets[timeframe][symbol]
            previous_bucket = history[-1] if history else None
            
            timeframe_updated = []

            if previous_bucket and previous_bucket.bucket_start == bucket_start:
                # Still in same bucket
                bucket = previous_bucket
                bucket.apply_point(point)
                if symbol_oi_history is not None:
                    # Ongoing alignment for open bucket
                    # Retry open alignment if it's currently missing/stale
                    retry_open = bucket.oi_open_timestamp is None or bucket.oi_alignment_status == "MISSING"
                    self._align_oi_boundary(bucket, symbol_oi_history, update_open=retry_open)
            else:
                # Rollover detected or first bucket
                if previous_bucket:
                    self._finalize_bucket(previous_bucket, symbol_oi_history)
                    timeframe_updated.append(previous_bucket)
                
                new_bucket = TimeframeBucket.from_point(
                    symbol,
                    timeframe,
                    point,
                    previous_bucket=previous_bucket,
                )
                
                # Minimal inheritance logic (Preferred safe fix)
                if previous_bucket:
                    tolerance = OI_ALIGNMENT_TOLERANCE.get(timeframe, 600)
                    if (previous_bucket.oi_close_timestamp is not None and 
                        previous_bucket.oi_close_age is not None and 
                        previous_bucket.oi_close_age <= tolerance and
                        previous_bucket.bucket_end == new_bucket.bucket_start):
                        
                        new_bucket.oi_open_timestamp = previous_bucket.oi_close_timestamp
                        new_bucket.oi_open_age = previous_bucket.oi_close_age
                        new_bucket.open_interest_open = previous_bucket.open_interest_close
                        
                        logger.debug(
                            "OI Inherit [%s %s]: start=%s, inherited_ts=%s, age=%.1fs",
                            symbol, timeframe, new_bucket.bucket_start, 
                            new_bucket.oi_open_timestamp, new_bucket.oi_open_age
                        )

                if symbol_oi_history is not None:
                    # Initial alignment for new bucket
                    self._align_oi_boundary(new_bucket, symbol_oi_history, update_open=True)
                
                history.append(new_bucket)
                bucket = new_bucket

            # Always update lifecycle for the active bucket
            self._update_bucket_lifecycle(bucket, point.timestamp)
            timeframe_updated.append(bucket)
            updated[timeframe] = timeframe_updated

        return updated

    def _align_oi_boundary(
        self, 
        bucket: TimeframeBucket, 
        history: deque[tuple[datetime, float]], 
        update_open: bool = True,
    ) -> None:
        if not history:
            # If we already have inherited boundaries, don't revert to MISSING
            if bucket.oi_open_timestamp is None and bucket.oi_close_timestamp is None:
                bucket.oi_alignment_status = "MISSING"
            return

        tolerance = OI_ALIGNMENT_TOLERANCE.get(bucket.timeframe, 600)
        
        # 1. Find nearest to bucket_start
        if update_open:
            # Preserve existing valid boundary (e.g. from inheritance) 
            # unless we find a better one in history.
            current_age = bucket.oi_open_age if bucket.oi_open_age is not None else float('inf')
            
            open_snap = self._find_nearest_snapshot(history, bucket.bucket_start)
            if open_snap:
                ts, val = open_snap
                new_age = abs((ts - bucket.bucket_start).total_seconds())
                
                logger.debug(
                    "OI ALIGN [%s %s] OPEN: snap=%s, age=%.1fs, tolerance=%ds, current_age=%s",
                    bucket.symbol, bucket.timeframe, ts, new_age, tolerance, current_age
                )
                
                # Only update if new snap is better (closer) than existing
                if new_age < current_age:
                    bucket.oi_open_timestamp = ts
                    bucket.oi_open_age = new_age
                    if new_age <= tolerance:
                        bucket.open_interest_open = val
                elif current_age <= tolerance:
                    # Keep inherited value as it is better
                    pass
                else:
                    # Both are bad, but let's keep the newer one if it exists
                    pass
            # If no snap found in history, keep existing (inherited) values

        # 2. Find nearest to bucket_end (Only if closed or near completion)
        should_update_close = bucket.bucket_is_closed or bucket.bucket_completion_pct >= 0.9
        
        if should_update_close:
            close_snap = self._find_nearest_snapshot(history, bucket.bucket_end)
            if close_snap:
                ts, val = close_snap
                bucket.oi_close_timestamp = ts
                bucket.oi_close_age = abs((ts - bucket.bucket_end).total_seconds())
                if bucket.oi_close_age <= tolerance:
                    bucket.open_interest_close = val
            else:
                # Only clear if we actually looked and found nothing
                bucket.oi_close_timestamp = None
                bucket.oi_close_age = None
        else:
            # For open buckets far from end, we don't look for close_timestamp yet.
            # Preserve existing if it was loaded from DB and is still valid (rare case)
            if bucket.oi_close_age is not None and bucket.oi_close_age > tolerance:
                bucket.oi_close_timestamp = None
                bucket.oi_close_age = None

        # 3. Determine status via helper
        self._sanitize_oi_boundary_state(bucket)

    def _sanitize_oi_boundary_state(self, bucket: TimeframeBucket) -> None:
        """Runtime sanitization of OI fields to prevent stale/misaligned data leak."""
        tolerance = OI_ALIGNMENT_TOLERANCE.get(bucket.timeframe, 600)

        # OI boundary timestamps are valid relative to their bucket boundary,
        # not relative to current wall-clock time. Closed/historical buckets may
        # legitimately have old timestamps.
        open_exists = bucket.oi_open_timestamp is not None
        close_exists = bucket.oi_close_timestamp is not None

        if open_exists:
            bucket.oi_open_age = abs((bucket.oi_open_timestamp - bucket.bucket_start).total_seconds())
        else:
            bucket.oi_open_age = None

        if close_exists:
            bucket.oi_close_age = abs((bucket.oi_close_timestamp - bucket.bucket_end).total_seconds())
        else:
            bucket.oi_close_age = None

        open_ok = bucket.oi_open_age is not None and bucket.oi_open_age <= tolerance
        close_ok = bucket.oi_close_age is not None and bucket.oi_close_age <= tolerance

        if bucket.bucket_is_closed:
            if open_ok and close_ok:
                bucket.oi_alignment_status = "ALIGNED"
                bucket.oi_delta_reliable = True
            elif open_ok or close_ok:
                bucket.oi_alignment_status = "PARTIAL"
                bucket.oi_delta_reliable = False
            elif open_exists or close_exists:
                bucket.oi_alignment_status = "MISALIGNED"
                bucket.oi_delta_reliable = False
            else:
                bucket.oi_alignment_status = "MISSING"
                bucket.oi_delta_reliable = False
        else:
            # For open buckets: status = PARTIAL if valid open exists, MISSING if neither valid.
            # Do not require a close boundary and do not mark MISALIGNED.
            if open_ok:
                bucket.oi_alignment_status = "PARTIAL"
            else:
                bucket.oi_alignment_status = "MISSING"
            bucket.oi_delta_reliable = False

    @staticmethod
    def _oi_export_alignment(bucket: TimeframeBucket) -> tuple[float | None, float | None, str, bool]:
        """Compute OI export alignment without mutating bucket state."""
        tolerance = OI_ALIGNMENT_TOLERANCE.get(bucket.timeframe, 600)
        open_age = (
            abs((bucket.oi_open_timestamp - bucket.bucket_start).total_seconds())
            if bucket.oi_open_timestamp is not None
            else None
        )
        close_age = (
            abs((bucket.oi_close_timestamp - bucket.bucket_end).total_seconds())
            if bucket.oi_close_timestamp is not None
            else None
        )
        open_ok = open_age is not None and open_age <= tolerance
        close_ok = close_age is not None and close_age <= tolerance

        if bucket.bucket_is_closed and open_ok and close_ok:
            return open_age, close_age, "ALIGNED", True
        if open_ok or close_ok:
            return open_age, close_age, "PARTIAL", False
        return open_age, close_age, "MISSING", False

    @staticmethod
    def _funding_export_provenance(bucket: TimeframeBucket, now: datetime) -> tuple[datetime | None, float | None, str, bool]:
        """Compute funding export provenance without mutating bucket state."""
        timestamp = bucket.funding_rate_updated_at
        source = bucket.funding_source or "missing"
        age = abs((now - timestamp).total_seconds()) if timestamp is not None else None

        if source == "carry_forward" and timestamp is None:
            export_source = "MISSING_TIMESTAMP"
        elif source == "missing":
            export_source = "missing_at_startup"
        else:
            export_source = source

        reliable = (
            timestamp is not None
            and export_source not in {"missing", "missing_at_startup", "MISSING_TIMESTAMP"}
            and age is not None
            and age <= FUNDING_PROVENANCE_SLA_SECONDS
        )
        return timestamp, age, export_source, reliable

    @staticmethod
    def _find_nearest_snapshot(history: deque[tuple[datetime, float]], target: datetime) -> tuple[datetime, float] | None:
        """Find the nearest (timestamp, value) pair to the target datetime."""
        if not history:
            return None
            
        best = None
        min_diff = float('inf')
        
        # Assume history is chronological
        for ts, val in history:
            diff = abs((ts - target).total_seconds())
            if diff < min_diff:
                min_diff = diff
                best = (ts, val)
            elif diff > min_diff:
                # If we're getting further away in a sorted list, we've passed the nearest point
                break
        return best

    def latest_bucket(
        self,
        symbol: str,
        timeframe: str,
        closed_only: bool = False,
        now: datetime | None = None,
    ) -> TimeframeBucket | None:
        history = self.buckets[timeframe].get(symbol)
        if not history:
            return None
        if not closed_only:
            return history[-1]
        return self._latest_closed_bucket(history, now or datetime.now(UTC))

    @staticmethod
    def _latest_closed_bucket(
        history: deque[TimeframeBucket],
        now: datetime,
    ) -> TimeframeBucket | None:
        for bucket in reversed(history):
            if bucket.bucket_end <= now:
                return bucket
        return None

    def seed_bucket(self, bucket: TimeframeBucket) -> None:
        now = datetime.now(UTC)
        if bucket.bucket_end > now:
            bucket.last_timestamp = min(bucket.last_timestamp, now)
            bucket.spot_volume_close = 0.0
            bucket.futures_volume_close = 0.0
            bucket.spot_volume_delta = 0.0
            bucket.futures_volume_delta = 0.0
        history = self.buckets[bucket.timeframe][bucket.symbol]
        existing_by_start = {item.bucket_start: item for item in history}
        existing_by_start[bucket.bucket_start] = bucket

        ordered = [existing_by_start[key] for key in sorted(existing_by_start)]
        maxlen = history.maxlen

        # Sanitize stale OI fields for seeded buckets
        self._sanitize_oi_boundary_state(bucket)

        history.clear()
        for item in (ordered[-maxlen:] if maxlen else ordered):
            history.append(item)

    def latest_buckets_for_symbols(
        self,
        symbols: list[str],
        timeframes: tuple[str, ...] = TIMEFRAME_ORDER,
        closed_timeframes: set[str] | None = None,
        now: datetime | None = None,
    ) -> list[TimeframeBucket]:
        closed_timeframes = closed_timeframes or set()
        current_time = now or datetime.now(UTC)
        buckets: list[TimeframeBucket] = []
        for timeframe in timeframes:
            closed_only = timeframe in closed_timeframes
            for symbol in symbols:
                bucket = self.latest_bucket(symbol, timeframe, closed_only=closed_only, now=current_time)
                if bucket is not None:
                    buckets.append(bucket)
        return buckets

    def history_for(
        self,
        symbol: str,
        timeframe: str,
        limit: int | None = None,
        closed_only: bool = False,
        now: datetime | None = None,
        max_timestamp: datetime | None = None,
    ) -> list[TimeframeBucket]:
        history = list(self.buckets[timeframe].get(symbol, []))
        if closed_only or max_timestamp is not None:
            cutoff = max_timestamp or (now or datetime.now(UTC))
            history = [
                bucket
                for bucket in history
                if (bucket.bucket_end <= cutoff if closed_only else bucket.last_timestamp <= cutoff)
            ]
        if limit is None:
            return history
        return history[-limit:]

    def apply_signal(
        self,
        symbol: str,
        timeframe: str,
        score: float,
        signal_type: str,
        breakdown: dict[str, float],
        closed_only: bool = False,
        now: datetime | None = None,
    ) -> None:
        bucket = self.latest_bucket(symbol, timeframe, closed_only=closed_only, now=now)
        if bucket is None:
            return
        bucket.apply_signal(score, signal_type, breakdown)

    def build_flow_metrics(
        self,
        symbol: str,
        closed_timeframes: set[str] | None = None,
        now: datetime | None = None,
    ) -> FlowMetrics:
        closed_timeframes = closed_timeframes or set()
        current_time = now or datetime.now(UTC)
        values: dict[str, Any] = {}
        compression_values: list[float] = []
        data_valid = True

        for timeframe in TIMEFRAME_ORDER:
            closed_only = timeframe in closed_timeframes
            profile = TIMEFRAME_PROFILES.get(timeframe, TIMEFRAME_PROFILES["1h"])
            bucket = self.latest_bucket(symbol, timeframe, closed_only=closed_only, now=current_time)
            history = self.history_for(symbol, timeframe, limit=200, closed_only=closed_only, now=current_time)
            history_length = len(history)

            price_change = self._current_bucket_change(
                symbol,
                timeframe,
                lambda item: item.close_price,
                lambda item: item.open_price,
                closed_only=closed_only,
                now=current_time,
            )
            oi_change = self._current_bucket_change(
                symbol,
                timeframe,
                lambda item: item.open_interest_close,
                lambda item: item.open_interest_open,
                closed_only=closed_only,
                now=current_time,
            )
            volume_change = self._bucket_delta_change(
                symbol,
                timeframe,
                lambda item: item.volume_delta,
                closed_only=closed_only,
                now=current_time,
            )
            oi_delta = self._bucket_delta(
                symbol,
                timeframe,
                lambda item: item.open_interest_close - item.open_interest_open,
                closed_only=closed_only,
                now=current_time,
            )
            liq_delta = self._bucket_delta(
                symbol,
                timeframe,
                lambda item: item.long_liquidations_total - item.short_liquidations_total,
                closed_only=closed_only,
                now=current_time,
            )
            # Calculate volume and OI Z-scores with diagnostics
            volume_z, volume_reliable, volume_status = self._z_score_diagnostic(
                symbol, timeframe, lambda item: item.volume_delta, closed_only=closed_only, now=current_time
            )
            oi_delta_z, oi_reliable, oi_status = self._z_score_diagnostic(
                symbol, timeframe, lambda item: item.open_interest_close - item.open_interest_open, closed_only=closed_only, now=current_time
            )
            liq_z_score, liq_reliable, liq_status = self._z_score_diagnostic(
                symbol, timeframe, lambda item: item.long_liquidations_total - item.short_liquidations_total, closed_only=closed_only, now=current_time
            )
            funding_impulse = self._ema_impulse(
                history,
                lambda item: item.funding_rate_close,
                window=int(profile.get("trend_window", 8)),
            )
            ls_impulse = self._ema_impulse(
                history,
                lambda item: math.log(max(item.long_short_ratio_close, ROBUST_EPSILON)),
                window=int(profile.get("trend_window", 8)),
            )
            taker_impulse = self._ema_impulse(
                history,
                lambda item: math.log(max(item.taker_buy_sell_ratio_close, ROBUST_EPSILON)),
                window=int(profile.get("trend_window", 8)),
            )
            if bucket is None:
                data_status = "NO_DATA"
            elif any(
                value is None
                for value in (
                    oi_delta_z,
                    volume_z,
                    funding_impulse,
                    ls_impulse,
                    taker_impulse,
                )
            ):
                data_status = "INSUFFICIENT_HISTORY"
            else:
                data_status = "VALID"
            data_valid = data_valid and data_status == "VALID"

            compression_score = self._compression_score(
                symbol,
                timeframe,
                closed_only=closed_only,
                now=current_time,
            )
            structure = self._market_structure(history)
            funding_level = bucket.funding_rate_close if bucket is not None else 0.0
            funding_timestamp, funding_age, funding_source, funding_reliable = (
                self._funding_export_provenance(bucket, current_time)
                if bucket is not None
                else (None, None, "missing_at_startup", False)
            )
            ls_level = self._latest_level(
                history,
                lambda item: math.log(max(item.long_short_ratio_close, ROBUST_EPSILON)),
            )
            taker_level = self._latest_level(
                history,
                lambda item: math.log(max(item.taker_buy_sell_ratio_close, ROBUST_EPSILON)),
            )
            oi_percentile = self._percentile_rank(
                history,
                lambda item: item.open_interest_close,
                window=DEFAULT_PERCENTILE_WINDOW,
            )
            liq_pressure = self._liquidation_pressure(bucket)
            atr = self._atr_percent(symbol, timeframe, closed_only=closed_only, now=current_time)

            # Price Change Disambiguation
            body_change = price_change
            c2c_change = 0.0
            if len(history) >= 2:
                prev_c = history[-2].close_price
                curr_c = history[-1].close_price
                if prev_c > 0:
                    c2c_change = (curr_c - prev_c) / prev_c
            
            # Rolling change: last N bars (proxy for timeframe duration)
            rolling_change = c2c_change # Simplification for now, using 1-bar shift
            
            # Market Pressure Diagnostic
            pressure_diag = self._pressure_diagnostic(symbol, timeframe, closed_only=closed_only, now=current_time)

            values.update(
                {
                    f"data_status_{timeframe}": data_status,
                    f"history_length_{timeframe}": history_length,
                    f"price_change_{timeframe}": body_change, # Alias
                    f"body_change_{timeframe}": body_change,
                    f"close_to_close_change_{timeframe}": c2c_change,
                    f"rolling_change_{timeframe}": rolling_change,
                    f"oi_change_{timeframe}": oi_change,
                    f"volume_change_{timeframe}": volume_change,
                    f"funding_level_{timeframe}": funding_level,
                    f"funding_extreme_{timeframe}": abs(funding_level) >= float(profile["funding_extreme"]),
                    f"funding_timestamp_{timeframe}": funding_timestamp,
                    f"funding_age_seconds_{timeframe}": funding_age,
                    f"funding_source_{timeframe}": funding_source,
                    f"funding_reliable_{timeframe}": funding_reliable,
                    f"oi_delta_z_{timeframe}": oi_delta_z,
                    f"oi_delta_z_reliable_{timeframe}": oi_reliable,
                    f"oi_percentile_{timeframe}": oi_percentile,
                    f"funding_trend_{timeframe}": funding_impulse,
                    f"long_short_ratio_level_{timeframe}": ls_level,
                    f"long_short_ratio_delta_{timeframe}": ls_impulse,
                    f"taker_buy_sell_ratio_level_{timeframe}": taker_level,
                    f"taker_buy_sell_ratio_delta_{timeframe}": taker_impulse,
                    f"liq_delta_{timeframe}": liq_delta,
                    f"liq_z_score_{timeframe}": liq_z_score,
                    f"liq_z_score_reliable_{timeframe}": liq_reliable,
                    f"liq_pressure_{timeframe}": liq_pressure,
                    f"atr_{timeframe}": atr,
                    f"volume_z_{timeframe}": volume_z,
                    f"volume_z_reliable_{timeframe}": volume_reliable,
                    f"zscore_baseline_status_{timeframe}": volume_status if volume_status != "NORMAL" else oi_status,
                    f"compression_score_{timeframe}": compression_score,
                    f"wick_ratio_{timeframe}": self._wick_ratio(symbol, timeframe, closed_only=closed_only, now=current_time),
                    f"high_wick_candle_{timeframe}": self._high_wick_candle(symbol, timeframe, closed_only=closed_only, now=current_time),
                    f"market_pressure_{timeframe}": pressure_diag["value"],
                    f"market_pressure_status_{timeframe}": pressure_diag["status"],
                    f"market_pressure_component_count_{timeframe}": pressure_diag["count"],
                    f"market_pressure_missing_components_{timeframe}": pressure_diag["missing"],
                    f"market_pressure_stale_components_{timeframe}": pressure_diag["stale"],
                    f"market_pressure_valid_{timeframe}": pressure_diag["valid"],
                    f"recent_high_{timeframe}": structure["recent_high"],
                    f"recent_low_{timeframe}": structure["recent_low"],
                    f"range_mid_{timeframe}": structure["range_mid"],
                }
            )
            
            # Map OI Alignment from Bucket
            if bucket:
                # OI delta reliability is sourced from the last closed bucket
                # because open buckets cannot have a reliable close boundary.
                oi_ref_bucket = self.latest_bucket(symbol, timeframe, closed_only=True, now=current_time) or bucket

                # Morphology
                body_ratio = self._body_ratio(bucket)
                upper_wick = self._upper_wick_ratio(bucket)
                lower_wick = self._lower_wick_ratio(bucket)
                close_pos = self._close_position_in_range(bucket)
                
                # effort vs result (Patch 1)
                er_diag = self._calculate_effort_result_diagnostics(
                    volume_z=volume_z,
                    body_ratio=body_ratio,
                    upper_wick=upper_wick,
                    lower_wick=lower_wick,
                    close_pos=close_pos,
                    rolling_change=rolling_change,
                    price_change=body_change
                )
                
                oi_open_age, oi_close_age, oi_alignment_status, oi_delta_reliable = self._oi_export_alignment(oi_ref_bucket)

                # OI Semantic (Patch 2)
                oi_diag = self._calculate_oi_semantic_diagnostics(
                    oi_delta=oi_delta,
                    price_change=body_change,
                    rolling_change=rolling_change,
                    taker_delta=taker_impulse,
                    volume_z=volume_z,
                    compression=compression_score,
                    reliable=oi_delta_reliable
                )
                
                # Taker Divergence (Patch 3)
                taker_diag = self._calculate_taker_price_diagnostics(
                    taker_delta=taker_impulse,
                    price_change=body_change,
                    body_ratio=body_ratio,
                    upper_wick=upper_wick,
                    lower_wick=lower_wick
                )
                
                # Crowding (Patch 4)
                crowd_diag = self._calculate_crowding_diagnostics(
                    funding_level=funding_level,
                    ls_delta=ls_impulse,
                    oi_percentile=oi_percentile,
                    price_change_4h=body_change
                )
                
                # Liquidation (Patch 5)
                liq_diag = self._calculate_liquidation_diagnostics(
                    long_liq=bucket.long_liquidations_total,
                    short_liq=bucket.short_liquidations_total,
                    volume=bucket.futures_volume_delta,
                    price_change=body_change,
                    oi_delta=oi_delta
                )
                
                for diag in [er_diag, oi_diag, taker_diag, crowd_diag, liq_diag]:
                    for k, v in diag.items():
                        values[f"{k}_{timeframe}"] = v

                values.update({
                    f"oi_open_timestamp_{timeframe}": oi_ref_bucket.oi_open_timestamp,
                    f"oi_close_timestamp_{timeframe}": oi_ref_bucket.oi_close_timestamp,
                    f"oi_open_age_seconds_{timeframe}": oi_open_age,
                    f"oi_close_age_seconds_{timeframe}": oi_close_age,
                    f"oi_alignment_status_{timeframe}": oi_alignment_status,
                    f"oi_delta_reliable_{timeframe}": oi_delta_reliable,
                    f"foundation_version_{timeframe}": bucket.foundation_version,
                    f"volume_metric_status_{timeframe}": (
                        "VALID" if bucket.foundation_version == "v2_option_a" else "LEGACY_UNTRUSTED"
                    ),
                    f"volume_metric_reliable_{timeframe}": bucket.foundation_version == "v2_option_a",
                })

            compression_values.append(compression_score)
            logger.debug(
                "flow_metrics_trace symbol=%s timeframe=%s history_length=%s oi_delta=%s volume_delta=%s oi_delta_z=%s volume_z=%s",
                symbol,
                timeframe,
                history_length,
                oi_delta,
                self._bucket_delta(symbol, timeframe, lambda item: item.volume_delta, closed_only=closed_only, now=current_time),
                oi_delta_z,
                volume_z,
            )

        values["compression_score"] = max(compression_values) if compression_values else 0.0
        values["data_valid"] = data_valid
        metrics = FlowMetrics(**values)
        logger.debug("flow_metrics symbol=%s metrics=%s", symbol, metrics.model_dump())
        self._validate_compression_metrics(symbol, metrics, closed_timeframes, current_time)
        return metrics

    def _current_bucket_change(
        self,
        symbol: str,
        timeframe: str,
        current_extractor: Callable[[TimeframeBucket], float],
        baseline_extractor: Callable[[TimeframeBucket], float],
        closed_only: bool = False,
        now: datetime | None = None,
    ) -> float:
        bucket = self.latest_bucket(symbol, timeframe, closed_only=closed_only, now=now)
        if bucket is None:
            return 0.0

        current = current_extractor(bucket)
        baseline = baseline_extractor(bucket)
        return self.flow_engine.calculate_change(current, baseline)

    def _bucket_delta_change(
        self,
        symbol: str,
        timeframe: str,
        extractor: Callable[[TimeframeBucket], float],
        closed_only: bool = False,
        now: datetime | None = None,
    ) -> float:
        history = self.history_for(symbol, timeframe, limit=4, closed_only=closed_only, now=now)
        if len(history) < 2:
            return 0.0

        current = extractor(history[-1])
        baseline_samples = [extractor(item) for item in history[:-1] if extractor(item) > 0]
        if not baseline_samples:
            return 0.0

        baseline = sum(baseline_samples) / len(baseline_samples)
        if baseline <= VOLUME_BASELINE_FLOOR:
            return 0.0

        change = self.flow_engine.calculate_change(current, baseline)
        return max(change, -0.95)

    def _bucket_delta(
        self,
        symbol: str,
        timeframe: str,
        extractor: Callable[[TimeframeBucket], float],
        closed_only: bool = False,
        now: datetime | None = None,
    ) -> float:
        bucket = self.latest_bucket(symbol, timeframe, closed_only=closed_only, now=now)
        if bucket is None:
            return 0.0
        return extractor(bucket)

    def _trend_delta(
        self,
        symbol: str,
        timeframe: str,
        extractor: Callable[[TimeframeBucket], float],
        window: int | None = None,
        closed_only: bool = False,
        now: datetime | None = None,
    ) -> float | None:
        profile = TIMEFRAME_PROFILES.get(timeframe, TIMEFRAME_PROFILES["1h"])
        lookback_window = int(profile.get("trend_window", 8)) if window is None else window
        if lookback_window < 2:
            return None
        history = self.history_for(
            symbol,
            timeframe,
            limit=max(lookback_window * 2, lookback_window + 2),
            closed_only=closed_only,
            now=now,
        )
        if len(history) < 2:
            return None
        window = int(profile.get("trend_window", 8)) if window is None else window
        return self._ema_impulse(history, extractor, window=window)

    def _z_score(
        self,
        symbol: str,
        timeframe: str,
        extractor: Callable[[TimeframeBucket], float],
        window: int = 20,
        closed_only: bool = False,
        now: datetime | None = None,
    ) -> float:
        z, _, _ = self._z_score_diagnostic(symbol, timeframe, extractor, window, closed_only, now)
        return z

    def _z_score_diagnostic(
        self,
        symbol: str,
        timeframe: str,
        extractor: Callable[[TimeframeBucket], float],
        window: int = 20,
        closed_only: bool = False,
        now: datetime | None = None,
    ) -> tuple[float, bool, str]:
        history = self.history_for(symbol, timeframe, limit=window + 1, closed_only=closed_only, now=now)
        if len(history) < 6:
            return 0.0, False, "INSUFFICIENT_HISTORY"

        current = extractor(history[-1])
        samples = [extractor(item) for item in history[:-1]]
        return self._robust_z_score(current, samples)

    def _atr_percent(
        self,
        symbol: str,
        timeframe: str,
        window: int = 14,
        closed_only: bool = False,
        now: datetime | None = None,
    ) -> float:
        history = self.history_for(symbol, timeframe, limit=window + 1, closed_only=closed_only, now=now)
        if len(history) < 2:
            return 0.0

        true_ranges: list[float] = []
        previous_close = history[0].close_price
        for bucket in history[1:]:
            high_low = bucket.high_price - bucket.low_price
            high_close = abs(bucket.high_price - previous_close)
            low_close = abs(bucket.low_price - previous_close)
            true_ranges.append(max(high_low, high_close, low_close))
            previous_close = bucket.close_price

        atr = sum(true_ranges) / len(true_ranges)
        current_price = history[-1].close_price
        if current_price <= 0:
            return 0.0
        return atr / current_price

    def _pressure_diagnostic(
        self,
        symbol: str,
        timeframe: str,
        closed_only: bool = False,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        bucket = self.latest_bucket(symbol, timeframe, closed_only=closed_only, now=now)
        
        missing = []
        stale = []
        
        # Helper to check freshness (300s threshold for L1 components)
        def check(val, name, updated_at=None):
            if val is None or val == 0 and name != "price":
                missing.append(name)
                return 0.0
            if updated_at:
                age = (now - updated_at).total_seconds() if now else 0
                if age > 300:
                    stale.append(name)
            return val

        price_change = self._current_bucket_change(symbol, timeframe, lambda i: i.close_price, lambda i: i.open_price, closed_only, now)
        oi_change = self._current_bucket_change(symbol, timeframe, lambda i: i.open_interest_close, lambda i: i.open_interest_open, closed_only, now)
        
        funding_trend = self._trend_delta(symbol, timeframe, lambda i: i.funding_rate_close, closed_only=closed_only, now=now) or 0.0
        ls_delta = self._trend_delta(symbol, timeframe, lambda i: i.long_short_ratio_close, closed_only=closed_only, now=now) or 0.0
        liq_pressure = self._bucket_delta(symbol, timeframe, lambda i: self._liquidation_pressure(i), closed_only, now)

        # Basic presence checks
        if not bucket: missing.append("all")
        if abs(oi_change) < 1e-9: # Likely no update
             pass # OI can be flat

        price_score = math.tanh(price_change * 12)
        oi_score = math.tanh(oi_change * 12)
        funding_score = math.tanh(funding_trend * 2200)
        ls_score = math.tanh(ls_delta * 4)
        liq_score = math.tanh(-liq_pressure * 2)

        raw_pressure = (
            (0.30 * oi_score)
            + (0.30 * price_score)
            + (0.15 * funding_score)
            + (0.15 * ls_score)
            + (0.10 * liq_score)
        )
        
        score = math.tanh(raw_pressure * 3)
        count = 5 - len(missing)
        
        status = "VALID"
        if "all" in missing: status = "MISSING"
        elif len(missing) >= 2: status = "PARTIAL"
        elif stale: status = "STALE"
        
        return {
            "value": score if status != "MISSING" else 0.0,
            "status": status,
            "missing": missing,
            "stale": stale,
            "count": count,
            "valid": status == "VALID"
        }

    def _compression_score(
        self,
        symbol: str,
        timeframe: str,
        closed_only: bool = False,
        now: datetime | None = None,
    ) -> float:
        recent = self.history_for(symbol, timeframe, limit=6, closed_only=closed_only, now=now)
        if len(recent) < 2:
            return 0.0

        highs = [bucket.high_price for bucket in recent if bucket.high_price]
        lows = [bucket.low_price for bucket in recent if bucket.low_price]
        if not highs or not lows:
            return 0.0

        lower_bound = min(lows)
        if not lower_bound:
            return 0.0

        price_range = (max(highs) - lower_bound) / lower_bound
        profile = TIMEFRAME_PROFILES.get(timeframe, TIMEFRAME_PROFILES["1h"])
        threshold = float(profile.get("compression_threshold", 0.03))
        if threshold <= 0:
            return 0.0
        score = 1.0 - min(price_range / threshold, 1.0)
        return max(0.0, min(score, 1.0))

    @staticmethod
    def _median(values: list[float]) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        mid = len(ordered) // 2
        if len(ordered) % 2 == 1:
            return ordered[mid]
        return (ordered[mid - 1] + ordered[mid]) / 2

    def _robust_z_score(self, current: float, samples: list[float]) -> tuple[float, bool, str]:
        cleaned = [value for value in samples if math.isfinite(value)]
        if len(cleaned) < 6:
            return 0.0, False, "INSUFFICIENT_HISTORY"
            
        median = self._median(cleaned)
        deviations = [abs(value - median) for value in cleaned]
        mad = self._median(deviations)
        
        # Defensive handling of flat baseline
        if mad < MIN_MAD_THRESHOLD:
            if abs(current - median) < MIN_MAD_THRESHOLD:
                return 0.0, True, "FLAT_BASELINE"
            else:
                # Capped explosion
                z = Z_SCORE_CLAMP if current > median else -Z_SCORE_CLAMP
                return z, False, "FLAT_BASELINE"
        
        scale = (1.4826 * mad) + 1e-9 # ROBUST_EPSILON
        z = (current - median) / scale
        
        # Clamp to sane range
        clamped_z = max(-Z_SCORE_CLAMP, min(Z_SCORE_CLAMP, z))
        return clamped_z, True, "NORMAL"

    @staticmethod
    def _ema(values: list[float], window: int) -> float:
        if not values:
            return 0.0
        if window <= 1:
            return values[-1]
        alpha = 2.0 / (window + 1.0)
        ema = values[0]
        for value in values[1:]:
            ema = (alpha * value) + ((1.0 - alpha) * ema)
        return ema

    def _ema_impulse(
        self,
        history: list[TimeframeBucket],
        extractor: Callable[[TimeframeBucket], float],
        window: int,
    ) -> float | None:
        if len(history) < 2:
            return None
        series = [extractor(item) for item in history]
        current = series[-1]
        baseline = self._ema(series[:-1], max(window, 2))
        impulse = current - baseline
        return 0.0 if math.isclose(impulse, 0.0, abs_tol=DELTA_EPSILON) else impulse

    @staticmethod
    def _latest_level(
        history: list[TimeframeBucket],
        extractor: Callable[[TimeframeBucket], float],
    ) -> float:
        if not history:
            return 0.0
        return extractor(history[-1])

    def _percentile_rank(
        self,
        history: list[TimeframeBucket],
        extractor: Callable[[TimeframeBucket], float],
        window: int = DEFAULT_PERCENTILE_WINDOW,
    ) -> float:
        if len(history) < 2:
            return 0.0
        recent = history[-min(len(history), window + 1):]
        current = extractor(recent[-1])
        baseline = [extractor(item) for item in recent[:-1]]
        if not baseline:
            return 0.0
        count = sum(1 for value in baseline if value <= current)
        return count / len(baseline)

    @staticmethod
    def _market_structure(history: list[TimeframeBucket], window: int = DEFAULT_STRUCTURE_WINDOW) -> dict[str, float]:
        recent = history[-min(len(history), window):]
        highs = [bucket.high_price for bucket in recent if bucket.high_price > 0]
        lows = [bucket.low_price for bucket in recent if bucket.low_price > 0]
        if not highs or not lows:
            return {"recent_high": 0.0, "recent_low": 0.0, "range_mid": 0.0}
        recent_high = max(highs)
        recent_low = min(lows)
        return {
            "recent_high": recent_high,
            "recent_low": recent_low,
            "range_mid": (recent_high + recent_low) / 2.0,
        }

    @staticmethod
    def _liquidation_pressure(bucket: TimeframeBucket | None) -> float:
        if bucket is None:
            return 0.0
        total = bucket.long_liquidations_total + bucket.short_liquidations_total
        if total <= 0:
            return 0.0
        return max(-1.0, min(1.0, (bucket.long_liquidations_total - bucket.short_liquidations_total) / total))

    def _validate_compression_metrics(
        self,
        symbol: str,
        metrics: FlowMetrics,
        closed_timeframes: set[str],
        now: datetime,
    ) -> None:
        sufficient = all(
            len(self.history_for(symbol, timeframe, limit=6, closed_only=timeframe in closed_timeframes, now=now)) >= 6
            for timeframe in TIMEFRAME_ORDER
        )
        if not sufficient:
            return
        compression_values = [getattr(metrics, f"compression_score_{timeframe}", 0.0) for timeframe in TIMEFRAME_ORDER]
        if all(math.isclose(value, 0.0, abs_tol=DELTA_EPSILON) for value in compression_values):
            logger.debug("compression_score_all_zero symbol=%s", symbol)

    def _wick_ratio(
        self,
        symbol: str,
        timeframe: str,
        closed_only: bool = False,
        now: datetime | None = None,
    ) -> float:
        bucket = self.latest_bucket(symbol, timeframe, closed_only=closed_only, now=now)
        if bucket is None:
            return 0.0
        return self.flow_engine.calculate_wick_ratio(
            bucket.high_price,
            bucket.low_price,
            bucket.open_price,
        )

    def _high_wick_candle(
        self,
        symbol: str,
        timeframe: str,
        closed_only: bool = False,
        now: datetime | None = None,
    ) -> bool:
        bucket = self.latest_bucket(symbol, timeframe, closed_only=closed_only, now=now)
        if bucket is None:
            return False
        price_change = self._current_bucket_change(
            symbol,
            timeframe,
            lambda item: item.close_price,
            lambda item: item.open_price,
            closed_only=closed_only,
            now=now,
        )
        wick_ratio = self.flow_engine.calculate_wick_ratio(
            bucket.high_price,
            bucket.low_price,
            bucket.open_price,
        )
        return self.flow_engine.is_high_wick_candle(wick_ratio, price_change, timeframe)
    def _body_ratio(self, bucket: TimeframeBucket) -> float:
        total_range = bucket.high_price - bucket.low_price
        if total_range <= 0:
            return 0.0
        return abs(bucket.close_price - bucket.open_price) / total_range

    def _upper_wick_ratio(self, bucket: TimeframeBucket) -> float:
        total_range = bucket.high_price - bucket.low_price
        if total_range <= 0:
            return 0.0
        high_body = max(bucket.open_price, bucket.close_price)
        return (bucket.high_price - high_body) / total_range

    def _lower_wick_ratio(self, bucket: TimeframeBucket) -> float:
        total_range = bucket.high_price - bucket.low_price
        if total_range <= 0:
            return 0.0
        low_body = min(bucket.open_price, bucket.close_price)
        return (low_body - bucket.low_price) / total_range

    def _close_position_in_range(self, bucket: TimeframeBucket) -> float:
        total_range = bucket.high_price - bucket.low_price
        if total_range <= 0:
            return 0.5
        return (bucket.close_price - bucket.low_price) / total_range

    def _calculate_effort_result_diagnostics(
        self,
        volume_z: float,
        body_ratio: float,
        upper_wick: float,
        lower_wick: float,
        close_pos: float,
        rolling_change: float,
        price_change: float,
    ) -> dict[str, object]:
        volume_z = volume_z or 0.0
        effort = max(volume_z, 0.0)
        result = abs(price_change)
        
        ratio = effort / result if result > 1e-6 else effort * 100.0
        
        state = "Normal"
        absorption = False
        efficient = False
        climax = False
        
        # 1. Absorption
        if volume_z >= 2.0 and body_ratio <= 0.25 and (upper_wick >= 0.4 or lower_wick >= 0.4):
            state = "Absorption"
            absorption = True
            
        # 2. Efficient Move
        elif volume_z >= 1.0 and body_ratio >= 0.5:
            # close position supports direction
            if (price_change > 0 and close_pos >= 0.7) or (price_change < 0 and close_pos <= 0.3):
                state = "Efficient"
                efficient = True
                
        # 3. Climax
        if volume_z >= 2.5 and abs(rolling_change) >= 0.05: # Using 5% as extended
            if (rolling_change > 0 and (upper_wick >= 0.5 or close_pos <= 0.4)) or \
               (rolling_change < 0 and (lower_wick >= 0.5 or close_pos >= 0.6)):
                state = "Climax"
                climax = True
                
        return {
            "effort_vs_result_ratio": round(ratio, 4),
            "effort_result_state": state,
            "absorption_candidate": absorption,
            "efficient_move_candidate": efficient,
            "climax_candidate": climax
        }

    def _calculate_oi_semantic_diagnostics(
        self,
        oi_delta: float,
        price_change: float,
        rolling_change: float,
        taker_delta: float,
        volume_z: float,
        compression: float,
        reliable: bool,
    ) -> dict[str, object]:
        oi_delta = oi_delta or 0.0
        price_change = price_change or 0.0
        rolling_change = rolling_change or 0.0
        taker_delta = taker_delta or 0.0
        volume_z = volume_z or 0.0
        compression = compression or 0.0
        
        if not reliable:
            return {
                "oi_build_type": "unknown",
                "oi_semantic_state": "unreliable",
                "oi_semantic_reliable": False
            }
            
        build_type = "ambiguous"
        state = "Neutral"
        
        # Price follow taker check
        price_follows_taker = (price_change * taker_delta) > 0
        directional_bullish = price_change > 0 and rolling_change > 0
        directional_bearish = price_change < 0 and rolling_change < 0
        
        if oi_delta > 0:
            if directional_bullish and taker_delta > 0.02 and price_follows_taker:
                build_type = "aggressive_long_build"
                state = "Strong Long Build"
            elif directional_bearish and taker_delta < -0.02 and price_follows_taker:
                build_type = "aggressive_short_build"
                state = "Strong Short Build"
            elif abs(price_change) < 0.002 and (volume_z >= 1.5 or compression >= 0.3):
                build_type = "passive_build"
                state = "Accumulation/Absorption"
        elif oi_delta < 0:
            if price_change > 0.005:
                build_type = "short_covering"
                state = "Short Squeeze"
            elif price_change < -0.005:
                build_type = "long_unwind"
                state = "Long Liquidation/Unwind"
                
        return {
            "oi_build_type": build_type,
            "oi_semantic_state": state,
            "oi_semantic_reliable": True
        }

    def _calculate_taker_price_diagnostics(
        self,
        taker_delta: float,
        price_change: float,
        body_ratio: float,
        upper_wick: float,
        lower_wick: float,
    ) -> dict[str, object]:
        taker_delta = taker_delta or 0.0
        price_change = price_change or 0.0
        body_ratio = body_ratio or 0.0
        upper_wick = upper_wick or 0.0
        lower_wick = lower_wick or 0.0
        
        threshold = 0.02
        alignment = False
        divergence = False
        buyer_abs = False
        seller_abs = False
        
        if (taker_delta > threshold and price_change > 0) or (taker_delta < -threshold and price_change < 0):
            alignment = True
        
        if (taker_delta > threshold and price_change <= 0) or (taker_delta < -threshold and price_change >= 0):
            divergence = True
            
        if taker_delta > threshold and (price_change <= 0.001 or body_ratio <= 0.3 or upper_wick >= 0.4):
            buyer_abs = True
            
        if taker_delta < -threshold and (price_change >= -0.001 or body_ratio <= 0.3 or lower_wick >= 0.4):
            seller_abs = True
            
        return {
            "taker_price_alignment": alignment,
            "taker_price_divergence": divergence,
            "buyer_absorption_candidate": buyer_abs,
            "seller_absorption_candidate": seller_abs
        }

    def _calculate_crowding_diagnostics(
        self,
        funding_level: float,
        ls_delta: float,
        oi_percentile: float,
        price_change_4h: float,
    ) -> dict[str, object]:
        funding_level = funding_level or 0.0
        ls_delta = ls_delta or 0.0
        oi_percentile = oi_percentile or 0.0
        price_change_4h = price_change_4h or 0.0
        
        # Crowding score: 0 to 1
        score = (abs(funding_level) * 1000.0) + (abs(ls_delta) * 5.0) + oi_percentile
        score = min(score, 1.0)
        
        status = "neutral"
        side = "none"
        
        if funding_level > 0.0003 or ls_delta > 0.05:
            side = "long"
            status = "crowded_long"
            if funding_level > 0.0006 or oi_percentile > 0.9:
                status = "extreme_crowded_long"
        elif funding_level < -0.0003 or ls_delta < -0.05:
            side = "short"
            status = "crowded_short"
            if funding_level < -0.0006 or oi_percentile > 0.9:
                status = "extreme_crowded_short"
                
        return {
            "crowding_score": round(score, 4),
            "crowding_status": status,
            "crowding_side": side
        }

    def _calculate_liquidation_diagnostics(
        self,
        long_liq: float,
        short_liq: float,
        volume: float,
        price_change: float,
        oi_delta: float,
    ) -> dict[str, object]:
        long_liq = long_liq or 0.0
        short_liq = short_liq or 0.0
        volume = volume or 0.0
        price_change = price_change or 0.0
        oi_delta = oi_delta or 0.0
        
        total_liq = long_liq + short_liq
        ratio = total_liq / volume if volume > 0 else 0.0
        
        context = "liquidation_noise"
        if ratio >= 0.1:
            if price_change * (short_liq - long_liq) > 0:
                context = "squeeze_continuation"
            else:
                context = "liquidation_flush"
                
        if ratio >= 0.2 and abs(price_change) < 0.005:
            context = "reversal_candidate"
            
        return {
            "liq_contribution_ratio": round(ratio, 4),
            "liquidation_context": context
        }
