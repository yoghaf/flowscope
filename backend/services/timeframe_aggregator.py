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
    short_liquidations_close: float
    short_liquidations_total: float
    exchange_count_sum: int
    sample_count: int
    score: float = 0.0
    signal_type: str = "Neutral"
    breakdown_open_interest: float = 0.0
    breakdown_volume: float = 0.0
    breakdown_compression: float = 0.0
    breakdown_funding: float = 0.0

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
            high_price=max(open_price, close_price),
            low_price=min(open_price, close_price),
            close_price=close_price,
            open_interest_open=open_interest_open,
            open_interest_high=max(open_interest_open, open_interest_close),
            open_interest_low=min(open_interest_open, open_interest_close),
            open_interest_close=open_interest_close,
            spot_volume_open=spot_volume_open,
            spot_volume_close=spot_volume_close,
            spot_volume_delta=max(spot_volume_close - spot_volume_open, 0.0),
            futures_volume_open=futures_volume_open,
            futures_volume_close=futures_volume_close,
            futures_volume_delta=max(futures_volume_close - futures_volume_open, 0.0),
            funding_rate_sum=point.funding_rate,
            funding_rate_close=point.funding_rate,
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

        self.spot_volume_delta += max(point.spot_volume - self.spot_volume_close, 0.0)
        self.futures_volume_delta += max(point.futures_volume - self.futures_volume_close, 0.0)
        self.spot_volume_close = point.spot_volume
        self.futures_volume_close = point.futures_volume

        self.funding_rate_sum += point.funding_rate
        self.funding_rate_close = point.funding_rate
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
        }


class TimeframeAggregateStore:
    def __init__(self, retention_points: int) -> None:
        self.flow_engine = FlowEngine()
        self.buckets: dict[str, defaultdict[str, deque[TimeframeBucket]]] = {
            timeframe: defaultdict(lambda: deque(maxlen=retention_points))
            for timeframe in TIMEFRAME_ORDER
        }

    def ingest(self, symbol: str, point: HistoryPoint) -> dict[str, TimeframeBucket]:
        updated: dict[str, TimeframeBucket] = {}
        for timeframe in TIMEFRAME_ORDER:
            bucket_start = floor_timestamp(point.timestamp, timeframe)
            history = self.buckets[timeframe][symbol]
            previous_bucket = history[-1] if history else None

            if history and history[-1].bucket_start == bucket_start:
                history[-1].apply_point(point)
            else:
                history.append(
                    TimeframeBucket.from_point(
                        symbol,
                        timeframe,
                        point,
                        previous_bucket=previous_bucket,
                    )
                )

            updated[timeframe] = history[-1]

        return updated

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
            volume_z = self._z_score(
                symbol,
                timeframe,
                lambda item: item.volume_delta,
                closed_only=closed_only,
                now=current_time,
            )
            oi_delta_z = self._z_score(
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
            liq_z_score = self._z_score(
                symbol,
                timeframe,
                lambda item: item.long_liquidations_total - item.short_liquidations_total,
                closed_only=closed_only,
                now=current_time,
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

            values.update(
                {
                    f"data_status_{timeframe}": data_status,
                    f"history_length_{timeframe}": history_length,
                    f"price_change_{timeframe}": price_change,
                    f"oi_change_{timeframe}": oi_change,
                    f"volume_change_{timeframe}": volume_change,
                    f"funding_level_{timeframe}": funding_level,
                    f"funding_extreme_{timeframe}": abs(funding_level) >= float(profile["funding_extreme"]),
                    f"oi_delta_{timeframe}": oi_delta,
                    f"oi_delta_z_{timeframe}": oi_delta_z,
                    f"oi_percentile_{timeframe}": oi_percentile,
                    f"funding_trend_{timeframe}": funding_impulse,
                    f"long_short_ratio_level_{timeframe}": ls_level,
                    f"long_short_ratio_delta_{timeframe}": ls_impulse,
                    f"taker_buy_sell_ratio_level_{timeframe}": taker_level,
                    f"taker_buy_sell_ratio_delta_{timeframe}": taker_impulse,
                    f"liq_delta_{timeframe}": liq_delta,
                    f"liq_z_score_{timeframe}": liq_z_score,
                    f"liq_pressure_{timeframe}": liq_pressure,
                    f"atr_{timeframe}": atr,
                    f"volume_z_{timeframe}": volume_z,
                    f"compression_score_{timeframe}": compression_score,
                    f"wick_ratio_{timeframe}": self._wick_ratio(symbol, timeframe, closed_only=closed_only, now=current_time),
                    f"high_wick_candle_{timeframe}": self._high_wick_candle(symbol, timeframe, closed_only=closed_only, now=current_time),
                    f"market_pressure_{timeframe}": self._pressure_index(symbol, timeframe, closed_only=closed_only, now=current_time),
                    f"recent_high_{timeframe}": structure["recent_high"],
                    f"recent_low_{timeframe}": structure["recent_low"],
                    f"range_mid_{timeframe}": structure["range_mid"],
                }
            )
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
    ) -> float | None:
        history = self.history_for(symbol, timeframe, limit=window + 1, closed_only=closed_only, now=now)
        if len(history) < 6:
            return None
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

    def _pressure_index(
        self,
        symbol: str,
        timeframe: str,
        closed_only: bool = False,
        now: datetime | None = None,
    ) -> float:
        price_change = self._current_bucket_change(
            symbol,
            timeframe,
            lambda item: item.close_price,
            lambda item: item.open_price,
            closed_only=closed_only,
            now=now,
        )
        oi_change = self._current_bucket_change(
            symbol,
            timeframe,
            lambda item: item.open_interest_close,
            lambda item: item.open_interest_open,
            closed_only=closed_only,
            now=now,
        )
        funding_trend = self._trend_delta(
            symbol,
            timeframe,
            lambda item: item.funding_rate_close,
            closed_only=closed_only,
            now=now,
        ) or 0.0
        ls_delta = self._trend_delta(
            symbol,
            timeframe,
            lambda item: item.long_short_ratio_close,
            closed_only=closed_only,
            now=now,
        ) or 0.0
        liq_pressure = self._bucket_delta(
            symbol,
            timeframe,
            lambda item: self._liquidation_pressure(item),
            closed_only=closed_only,
            now=now,
        )

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
        return math.tanh(raw_pressure * 3)

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

    def _robust_z_score(self, current: float, samples: list[float]) -> float:
        cleaned = [value for value in samples if math.isfinite(value)]
        if len(cleaned) < 6:
            return 0.0
        median = self._median(cleaned)
        deviations = [abs(value - median) for value in cleaned]
        mad = self._median(deviations)
        scale = (1.4826 * mad) + ROBUST_EPSILON
        return (current - median) / scale

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
