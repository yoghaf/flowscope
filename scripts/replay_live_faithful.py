from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
import time
from bisect import bisect_right
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import get_settings
from backend.models import MarketDataBucket, TradeSignal
from backend.services.binance_demo.demo_execution_engine import (
    DEFAULT_MAX_ENTRY_DRIFT_PCT,
    DEFAULT_MAX_MARKET_TP1_PROGRESS_PCT,
    DEFAULT_MAX_PULLBACK_TP1_PROGRESS_PCT,
    ENTRY_MODE_MARKET_PULLBACK_LIMIT,
)
from backend.services.timeframe_aggregator import TimeframeBucket
from scripts.replay_full_strategy import _evaluate_trade_bucket

UTC = timezone.utc
EPS = 1e-12
CLOSED = {"win", "loss", "breakeven", "timeout"}
DEFAULT_DB = "flowscope_replay_vps_20260507_123757"
CANDIDATE_NAMES = {
    "baseline",
    "guarded",
    "context_guard",
    "quality_soft",
    "balanced_soft",
    "tf_profile",
    "qmid_p06",
    "qmid_p07",
    "qmid_p06_4h_only",
    "qmid_p06_15m_only",
    "qmid_p06_15m_strict",
    "qmid_p06_ema",
    "qmid_p06_ema_pullback",
    "qmid_p07_ema",
    "ema_only",
    "ema_pullback_only",
    "qmid_p06_4h_runner_2r",
    "qmid_p06_4h_runner_3r",
    "qmid_p06_failfast",
    "tf_simple",
}


@dataclass(slots=True)
class Position:
    trade: TradeSignal
    next_bucket_idx: int
    entry_kind: str


@dataclass(slots=True)
class IndicatorPoint:
    timestamp: datetime
    ema30: float
    ema100: float
    ema30_slope: float


INDICATOR_TIMES: dict[tuple[str, str], list[datetime]] = {}
INDICATOR_POINTS: dict[tuple[str, str], list[IndicatorPoint]] = {}


class Log:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.fh = path.open("w", encoding="utf-8", newline="\n")

    def write(self, text: str) -> None:
        print(text, flush=True)
        self.fh.write(text + "\n")
        self.fh.flush()

    def close(self) -> None:
        self.fh.close()


class DummyService:
    def __init__(self) -> None:
        self.states_by_timeframe: dict[str, dict[str, Any]] = defaultdict(dict)

    def record_continuation_feedback_trade(self, trade: TradeSignal) -> None:
        return None


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def iso(value: datetime | None) -> str:
    value = as_utc(value)
    return value.isoformat() if value is not None else ""


def parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    return as_utc(datetime.fromisoformat(raw.replace("Z", "+00:00")))


def read_env(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.exists():
        return data
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def db_url(db_name: str, explicit: str | None) -> str:
    raw = explicit
    if raw is None:
        env = read_env(ROOT / ".env")
        raw = (
            os.environ.get("FLOWSCOPE_REPLAY_DATABASE_URL")
            or os.environ.get("FLOWSCOPE_DATABASE_URL")
            or env.get("FLOWSCOPE_REPLAY_DATABASE_URL")
            or env.get("FLOWSCOPE_DATABASE_URL")
        )
    if not raw:
        raise RuntimeError("Database URL missing")
    if raw.startswith("postgresql://"):
        raw = "postgresql+asyncpg://" + raw[len("postgresql://") :]
    if raw.startswith("postgres://"):
        raw = "postgresql+asyncpg://" + raw[len("postgres://") :]
    parts = urlsplit(raw)
    return urlunsplit((parts.scheme, parts.netloc, f"/{db_name}", parts.query, parts.fragment))


def masked(url: str) -> str:
    parts = urlsplit(url)
    host = parts.hostname or "localhost"
    netloc = host if parts.port is None else f"{host}:{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def signal_time(trade: TradeSignal) -> datetime | None:
    return as_utc(getattr(trade, "created_at", None) or getattr(trade, "timestamp", None))


def features(trade: TradeSignal) -> dict[str, Any]:
    value = getattr(trade, "entry_features", None)
    return value if isinstance(value, dict) else {}


def f_float(trade: TradeSignal, key: str) -> float | None:
    try:
        value = features(trade).get(key)
        return float(value) if value is not None and value != "" else None
    except (TypeError, ValueError):
        return None


def f_bool(trade: TradeSignal, key: str) -> bool | None:
    value = features(trade).get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.lower().strip()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    return None


def r_multiple(trade: TradeSignal) -> float:
    entry = float(getattr(trade, "entry_price", 0.0) or 0.0)
    stop = float(getattr(trade, "invalidation_price", 0.0) or 0.0)
    pnl_pct = float(getattr(trade, "pnl_pct", 0.0) or 0.0)
    if entry <= EPS or stop <= EPS:
        return 0.0
    risk_pct = abs(entry - stop) / entry * 100
    return pnl_pct / risk_pct if risk_pct > EPS else 0.0


def size_mult(trade: TradeSignal) -> float:
    try:
        return max(0.0, float(features(trade).get("position_size_multiplier", 1.0) or 1.0))
    except (TypeError, ValueError):
        return 1.0


def build_indicator_cache(buckets: dict[tuple[str, str], list[TimeframeBucket]]) -> None:
    INDICATOR_TIMES.clear()
    INDICATOR_POINTS.clear()
    alpha30 = 2.0 / (30.0 + 1.0)
    alpha100 = 2.0 / (100.0 + 1.0)
    for key, rows in buckets.items():
        ema30: float | None = None
        ema100: float | None = None
        points: list[IndicatorPoint] = []
        times: list[datetime] = []
        for bucket in rows:
            close = float(bucket.close_price or 0.0)
            if close <= EPS:
                continue
            previous_ema30 = ema30 if ema30 is not None else close
            ema30 = close if ema30 is None else (alpha30 * close) + ((1.0 - alpha30) * ema30)
            ema100 = close if ema100 is None else (alpha100 * close) + ((1.0 - alpha100) * ema100)
            timestamp = as_utc(bucket.last_timestamp)
            if timestamp is None:
                continue
            times.append(timestamp)
            points.append(
                IndicatorPoint(
                    timestamp=timestamp,
                    ema30=float(ema30),
                    ema100=float(ema100),
                    ema30_slope=float(ema30 - previous_ema30),
                )
            )
        if points:
            INDICATOR_TIMES[key] = times
            INDICATOR_POINTS[key] = points


def indicator_at(trade: TradeSignal) -> IndicatorPoint | None:
    timestamp = signal_time(trade)
    if timestamp is None:
        return None
    key = (str(getattr(trade, "symbol", "")), str(getattr(trade, "timeframe", "")))
    times = INDICATOR_TIMES.get(key)
    points = INDICATOR_POINTS.get(key)
    if not times or not points:
        return None
    index = bisect_right(times, timestamp) - 1
    if 0 <= index < len(points):
        return points[index]
    return None


def ema_gate_reason(
    trade: TradeSignal,
    *,
    max_extension_atr: float | None = None,
    require_slope: bool = False,
) -> str | None:
    indicator = indicator_at(trade)
    if indicator is None:
        return "guard_ema_missing"
    try:
        entry = float(getattr(trade, "entry_price", 0.0) or 0.0)
    except (TypeError, ValueError):
        entry = 0.0
    if entry <= EPS:
        return "guard_ema_entry_missing"

    bias = str(getattr(trade, "bias", "") or "")
    if bias == "Bullish":
        if not (indicator.ema30 > indicator.ema100 and entry > indicator.ema30):
            return "guard_ema_trend_not_aligned"
        if require_slope and indicator.ema30_slope <= 0:
            return "guard_ema_slope_not_aligned"
    elif bias == "Bearish":
        if not (indicator.ema30 < indicator.ema100 and entry < indicator.ema30):
            return "guard_ema_trend_not_aligned"
        if require_slope and indicator.ema30_slope >= 0:
            return "guard_ema_slope_not_aligned"
    else:
        return "guard_ema_bias_missing"

    if max_extension_atr is not None:
        timeframe = str(getattr(trade, "timeframe", "") or "")
        atr = f_float(trade, f"atr_{timeframe}")
        if atr is None or atr <= EPS:
            return "guard_atr_missing"
        extension_atr = abs(entry - indicator.ema30) / max(float(atr), EPS)
        if extension_atr > max_extension_atr:
            return "guard_ema_extension_too_far"
    return None


def context_guard_reason(trade: TradeSignal, *, reject_1h: bool = True) -> str | None:
    if getattr(trade, "volatility_regime", None) == "Low":
        return "guard_low_volatility"
    if reject_1h and getattr(trade, "timeframe", None) == "1h":
        return "guard_timeframe_1h"
    pressure = f_float(trade, "market_pressure_4h")
    if pressure is not None and pressure >= 0.50:
        return "guard_market_pressure_4h_high"
    volume_z_4h = f_float(trade, "volume_z_4h")
    if volume_z_4h is not None and volume_z_4h >= 10.0:
        return "guard_volume_z_4h_extreme"
    oi_delta_z_1h = f_float(trade, "oi_delta_z_1h")
    if oi_delta_z_1h is not None and oi_delta_z_1h >= 3.0:
        return "guard_oi_delta_z_1h_extreme"
    return None


def quality_mid_reason(trade: TradeSignal, *, require_ready: bool) -> str | None:
    ready = f_bool(trade, "continuation_quality_ready")
    if ready is not True:
        return "guard_quality_not_ready" if require_ready else None
    quality = f_float(trade, "continuation_quality_score")
    if quality is None:
        return "guard_quality_score_missing" if require_ready else None
    if quality < 0.35 or quality >= 0.55:
        return "guard_quality_score_outside_mid"
    return None


def tf_profile_reason(trade: TradeSignal) -> str | None:
    timeframe = getattr(trade, "timeframe", None)
    if getattr(trade, "volatility_regime", None) == "Low":
        return "guard_low_volatility"
    if timeframe == "1h":
        return "guard_timeframe_1h"

    volume_z_4h = f_float(trade, "volume_z_4h")
    if volume_z_4h is not None and volume_z_4h >= 10.0:
        return "guard_volume_z_4h_extreme"
    oi_delta_z_1h = f_float(trade, "oi_delta_z_1h")
    if oi_delta_z_1h is not None and oi_delta_z_1h >= 3.0:
        return "guard_oi_delta_z_1h_extreme"

    pressure = f_float(trade, "market_pressure_4h")
    if pressure is not None and pressure >= 0.50:
        return "guard_market_pressure_4h_high"

    if timeframe == "15m":
        reason = quality_mid_reason(trade, require_ready=True)
        if reason:
            return reason
        volume_z_15m = f_float(trade, "volume_z_15m")
        if volume_z_15m is None:
            return "guard_volume_z_15m_missing"
        if volume_z_15m < 1.0:
            return "guard_volume_z_15m_weak"

    return None


def pressure_reason(trade: TradeSignal, threshold: float, *, require_present: bool = True) -> str | None:
    pressure = f_float(trade, "market_pressure_4h")
    if pressure is None:
        return "guard_market_pressure_4h_missing" if require_present else None
    if pressure >= threshold:
        return "guard_market_pressure_4h_high"
    return None


def qmid_pressure_reason(trade: TradeSignal, threshold: float) -> str | None:
    reason = quality_mid_reason(trade, require_ready=True)
    return reason or pressure_reason(trade, threshold)


def timeframe_reason(trade: TradeSignal, allowed: set[str]) -> str | None:
    timeframe = str(getattr(trade, "timeframe", "") or "")
    if timeframe not in allowed:
        return f"guard_timeframe_{timeframe or 'missing'}"
    return None


def qmid_p06_reason(trade: TradeSignal) -> str | None:
    return qmid_pressure_reason(trade, 0.60)


def qmid_p07_reason(trade: TradeSignal) -> str | None:
    return qmid_pressure_reason(trade, 0.70)


def strict_15m_reason(trade: TradeSignal) -> str | None:
    reason = timeframe_reason(trade, {"15m"})
    if reason:
        return reason
    reason = qmid_p06_reason(trade)
    if reason:
        return reason
    flow_alignment = f_float(trade, "flow_alignment")
    if flow_alignment is None or flow_alignment < 0.70:
        return "guard_flow_alignment_15m_weak"
    volume_z = f_float(trade, "volume_z_15m")
    if volume_z is None or volume_z < 1.0:
        return "guard_volume_z_15m_weak"
    taker_delta = f_float(trade, "taker_buy_sell_ratio_delta_15m")
    direction = 1 if getattr(trade, "bias", None) == "Bullish" else -1 if getattr(trade, "bias", None) == "Bearish" else 0
    if direction == 0 or taker_delta is None or direction * taker_delta <= 0:
        return "guard_taker_15m_not_aligned"
    return None


def tf_simple_reason(trade: TradeSignal) -> str | None:
    timeframe = getattr(trade, "timeframe", None)
    if getattr(trade, "volatility_regime", None) == "Low":
        return "guard_low_volatility"
    if timeframe == "1h":
        return "guard_timeframe_1h"
    if timeframe == "15m":
        reason = quality_mid_reason(trade, require_ready=True)
        if reason:
            return reason
        return pressure_reason(trade, 0.40, require_present=False)
    if timeframe == "4h":
        return pressure_reason(trade, 0.60, require_present=False)
    return None


def guard_reason(candidate: str, trade: TradeSignal) -> str | None:
    if candidate == "baseline" or getattr(trade, "setup_type", None) != "Continuation":
        return None
    if candidate == "guarded":
        reason = context_guard_reason(trade)
        return reason or quality_mid_reason(trade, require_ready=True)
    if candidate == "context_guard":
        return context_guard_reason(trade)
    if candidate == "quality_soft":
        if getattr(trade, "volatility_regime", None) == "Low":
            return "guard_low_volatility"
        if getattr(trade, "timeframe", None) == "1h":
            return "guard_timeframe_1h"
        return quality_mid_reason(trade, require_ready=False)
    if candidate == "balanced_soft":
        reason = context_guard_reason(trade)
        return reason or quality_mid_reason(trade, require_ready=False)
    if candidate == "tf_profile":
        return tf_profile_reason(trade)
    if candidate == "qmid_p06":
        return qmid_p06_reason(trade)
    if candidate == "qmid_p07":
        return qmid_p07_reason(trade)
    if candidate == "qmid_p06_4h_only":
        return timeframe_reason(trade, {"4h"}) or qmid_p06_reason(trade)
    if candidate == "qmid_p06_15m_only":
        return timeframe_reason(trade, {"15m"}) or qmid_p06_reason(trade)
    if candidate == "qmid_p06_15m_strict":
        return strict_15m_reason(trade)
    if candidate == "qmid_p06_ema":
        return qmid_p06_reason(trade) or ema_gate_reason(trade)
    if candidate == "qmid_p06_ema_pullback":
        return qmid_p06_reason(trade) or ema_gate_reason(trade, max_extension_atr=2.0, require_slope=True)
    if candidate == "qmid_p07_ema":
        return qmid_p07_reason(trade) or ema_gate_reason(trade)
    if candidate == "ema_only":
        return ema_gate_reason(trade)
    if candidate == "ema_pullback_only":
        return ema_gate_reason(trade, max_extension_atr=2.0, require_slope=True)
    if candidate == "qmid_p06_4h_runner_2r":
        return timeframe_reason(trade, {"4h"}) or qmid_p06_reason(trade)
    if candidate == "qmid_p06_4h_runner_3r":
        return timeframe_reason(trade, {"4h"}) or qmid_p06_reason(trade)
    if candidate == "qmid_p06_failfast":
        return qmid_p06_reason(trade)
    if candidate == "tf_simple":
        return tf_simple_reason(trade)
    raise ValueError(f"Unsupported candidate: {candidate}")
    return None


def entry_guard(
    *,
    bias: str,
    current_price: float,
    entry_price: float,
    stop_loss: float,
    tp1: float,
    max_entry_drift_pct: float | None,
    max_market_tp1_progress_pct: float | None,
    max_pullback_tp1_progress_pct: float | None,
    entry_mode: str,
) -> tuple[str | None, list[str]]:
    direction = 1 if bias == "Bullish" else -1
    adverse = max((current_price - entry_price) * direction, 0.0)
    risk = abs(entry_price - stop_loss)
    tp1_dist = abs(tp1 - entry_price)
    market_reasons: list[str] = []
    pullback_reasons: list[str] = []

    if (current_price - stop_loss) * direction <= EPS:
        market_reasons.append("price_already_touched_sl_before_entry")
        pullback_reasons.append("price_already_touched_sl_before_entry")
    if risk <= EPS:
        market_reasons.append("entry_risk_distance_invalid")
        pullback_reasons.append("entry_risk_distance_invalid")
    elif max_entry_drift_pct is not None and adverse / risk * 100 > max_entry_drift_pct:
        market_reasons.append("entry_drift_too_far")
    if tp1_dist <= EPS:
        market_reasons.append("market_tp1_progress_unavailable")
        pullback_reasons.append("pullback_tp1_progress_unavailable")
    else:
        progress = adverse / tp1_dist * 100
        if max_market_tp1_progress_pct is not None and progress > max_market_tp1_progress_pct:
            market_reasons.append("market_tp1_progress_too_far")
        if max_pullback_tp1_progress_pct is not None and progress >= max_pullback_tp1_progress_pct:
            pullback_reasons.append("pullback_tp1_progress_too_far")

    if entry_mode != ENTRY_MODE_MARKET_PULLBACK_LIMIT:
        pullback_reasons.append("pullback_limit_mode_disabled")
    if (current_price - tp1) * direction >= -EPS:
        pullback_reasons.append("tp1_already_touched_before_entry")

    if not market_reasons:
        return "market", []
    if not pullback_reasons:
        return "pending_limit", market_reasons
    return None, market_reasons + pullback_reasons


class Replay:
    def __init__(self, args: argparse.Namespace, candidate: str, signals: list[TradeSignal], buckets: dict[tuple[str, str], list[TimeframeBucket]], log: Log) -> None:
        self.args = args
        self.candidate = candidate
        self.signals = signals
        self.buckets = buckets
        self.times = {key: [as_utc(bucket.last_timestamp) for bucket in rows] for key, rows in buckets.items()}
        self.log = log
        self.settings = get_settings().model_copy()
        if candidate == "qmid_p06_failfast":
            self.settings.fail_fast_max_candles = 2
            self.settings.fail_fast_min_mfe_r = 0.25
        self.service = DummyService()
        self.active: dict[str, Position] = {}
        self.trades: list[TradeSignal] = []
        self.skips: list[dict[str, Any]] = []
        self.skip_counts: Counter[str] = Counter()
        self.entry_guard_counts: Counter[str] = Counter()
        self.market_entries = 0
        self.pending_entries = 0

    def current_price(self, symbol: str, timeframe: str, when: datetime, fallback: float) -> float:
        key = (symbol, timeframe)
        index = bisect_right(self.times.get(key, []), when) - 1
        rows = self.buckets.get(key, [])
        if 0 <= index < len(rows) and rows[index].close_price > EPS:
            return float(rows[index].close_price)
        return fallback

    def next_idx(self, symbol: str, timeframe: str, when: datetime) -> int:
        return bisect_right(self.times.get((symbol, timeframe), []), when)

    def record_skip(self, source: TradeSignal, reason: str, details: str = "") -> None:
        self.skip_counts[reason] += 1
        row = {
            "candidate": self.candidate,
            "source_signal_id": getattr(source, "id", None),
            "symbol": getattr(source, "symbol", ""),
            "timeframe": getattr(source, "timeframe", ""),
            "setup_type": getattr(source, "setup_type", ""),
            "bias": getattr(source, "bias", ""),
            "signal_time": iso(signal_time(source)),
            "reason": reason,
            "details": details,
        }
        self.skips.append(row)
        if self.args.log_events:
            self.log.write(f"[skip] {row['signal_time']} {row['symbol']} {row['timeframe']} {reason} {details}".strip())

    def eval_active_until(self, when: datetime) -> None:
        for symbol, pos in list(self.active.items()):
            trade = pos.trade
            key = (trade.symbol, trade.timeframe)
            rows = self.buckets.get(key, [])
            times = self.times.get(key, [])
            while pos.next_bucket_idx < len(rows) and times[pos.next_bucket_idx] <= when and trade.result == "open":
                _evaluate_trade_bucket(trade=trade, bucket=rows[pos.next_bucket_idx], service=self.service, settings=self.settings)
                pos.next_bucket_idx += 1
            if trade.result != "open":
                self.active.pop(symbol, None)
                if self.args.log_events:
                    self.log.write(f"[close] {iso(trade.closed_at)} {trade.symbol} {trade.timeframe} {trade.result} r={r_multiple(trade):.3f} {trade.close_reason}")

    def make_trade(self, source: TradeSignal, when: datetime, entry_kind: str) -> TradeSignal:
        entry_features = dict(features(source))
        indicator = indicator_at(source)
        if indicator is not None:
            entry_features.update({
                "ema30": round(indicator.ema30, 8),
                "ema100": round(indicator.ema100, 8),
                "ema30_slope": round(indicator.ema30_slope, 10),
            })
            try:
                entry = float(getattr(source, "entry_price", 0.0) or 0.0)
                atr = f_float(source, f"atr_{getattr(source, 'timeframe', '')}")
                if entry > EPS and atr is not None and atr > EPS:
                    entry_features["ema30_extension_atr"] = round(abs(entry - indicator.ema30) / atr, 4)
            except (TypeError, ValueError):
                pass
        entry_features.update({
            "replay_candidate": self.candidate,
            "replay_entry_kind": entry_kind,
            "replay_source_signal_id": getattr(source, "id", None),
        })
        trade = TradeSignal(
            symbol=source.symbol,
            timeframe=source.timeframe,
            timestamp=when,
            state=source.state,
            bias=source.bias,
            setup_type=source.setup_type,
            status="Triggered" if entry_kind == "market" else "Open",
            market_regime=source.market_regime,
            volatility_regime=source.volatility_regime,
            entry_price=source.entry_price,
            invalidation_price=source.invalidation_price,
            target_price=source.target_price,
            target_price_1=source.target_price_1 or source.target_price,
            target_price_2=source.target_price_2 or source.target_price,
            trailing_stop_price=None,
            tp1_hit=False,
            fill_count=1,
            entry_touched_at=when if entry_kind == "market" else None,
            entry_flow_alignment=source.entry_flow_alignment or f_float(source, "flow_alignment"),
            closed_at=None,
            close_reason=None,
            risk_level=source.risk_level,
            quality_score=source.quality_score,
            confidence=source.confidence,
            result="open",
            pnl_pct=0.0,
            max_drawdown_pct=0.0,
            max_profit_pct=0.0,
            engine_tag=source.engine_tag,
            entry_features=entry_features,
            exit_features=None,
            history_logs=[],
            autopsy_rationale=None,
            created_at=when,
            updated_at=when,
        )
        trade.id = getattr(source, "id", None)
        self.apply_candidate_trade_profile(trade)
        return trade

    def apply_candidate_trade_profile(self, trade: TradeSignal) -> None:
        if self.candidate == "qmid_p06_4h_runner_2r":
            self.retarget_trade_to_r(trade, tp1_r=1.0, tp2_r=2.0)
        elif self.candidate == "qmid_p06_4h_runner_3r":
            self.retarget_trade_to_r(trade, tp1_r=1.0, tp2_r=3.0)

    @staticmethod
    def retarget_trade_to_r(trade: TradeSignal, *, tp1_r: float, tp2_r: float) -> None:
        if trade.entry_price is None or trade.invalidation_price is None:
            return
        direction = 1 if trade.bias == "Bullish" else -1 if trade.bias == "Bearish" else 0
        if direction == 0:
            return
        risk = abs(float(trade.entry_price) - float(trade.invalidation_price))
        if risk <= EPS:
            return
        trade.target_price_1 = float(trade.entry_price) + (direction * risk * tp1_r)
        trade.target_price_2 = float(trade.entry_price) + (direction * risk * tp2_r)
        trade.target_price = trade.target_price_2
        entry_features = dict(trade.entry_features or {})
        entry_features["replay_target_profile"] = f"tp1_{tp1_r:.1f}r_tp2_{tp2_r:.1f}r"
        trade.entry_features = entry_features

    def try_enter(self, source: TradeSignal, when: datetime) -> None:
        entry = float(source.entry_price or 0.0)
        stop = float(source.invalidation_price or 0.0)
        tp1 = float((source.target_price_1 or source.target_price or 0.0))
        if entry <= EPS:
            return self.record_skip(source, "entry_missing")
        if stop <= EPS:
            return self.record_skip(source, "stop_loss_missing")
        if tp1 <= EPS:
            return self.record_skip(source, "take_profit_missing")
        if source.bias not in {"Bullish", "Bearish"}:
            return self.record_skip(source, "bias_not_executable")
        current = self.current_price(source.symbol, source.timeframe, when, entry)
        entry_kind, reasons = entry_guard(
            bias=source.bias,
            current_price=current,
            entry_price=entry,
            stop_loss=stop,
            tp1=tp1,
            max_entry_drift_pct=self.args.max_entry_drift_pct,
            max_market_tp1_progress_pct=self.args.max_market_tp1_progress_pct,
            max_pullback_tp1_progress_pct=self.args.max_pullback_tp1_progress_pct,
            entry_mode=self.args.entry_mode,
        )
        for reason in reasons:
            self.entry_guard_counts[reason] += 1
        if entry_kind is None:
            return self.record_skip(source, "entry_guard_rejected", ",".join(reasons))
        trade = self.make_trade(source, when, entry_kind)
        self.trades.append(trade)
        self.active[source.symbol] = Position(trade, self.next_idx(source.symbol, source.timeframe, when), entry_kind)
        if entry_kind == "market":
            self.market_entries += 1
        else:
            self.pending_entries += 1
        if self.args.log_events:
            self.log.write(f"[exec] {iso(when)} {trade.symbol} {trade.timeframe} {trade.setup_type} {trade.bias} {entry_kind}")

    def progress(self, idx: int, total: int, when: datetime) -> None:
        closed = [trade for trade in self.trades if trade.result in CLOSED]
        total_r = sum(r_multiple(trade) for trade in closed)
        top_skips = " ".join(f"{k}={v}" for k, v in self.skip_counts.most_common(4))
        self.log.write(
            f"[replay:{self.candidate}] {idx}/{total} {(idx / max(total, 1) * 100):5.1f}% "
            f"sim_time={iso(when)} active={len(self.active)} entered={len(self.trades)} "
            f"closed={len(closed)} R={total_r:.2f} skips={sum(self.skip_counts.values())}"
            + (f" {top_skips}" if top_skips else "")
        )

    def run(self) -> dict[str, Any]:
        started = time.time()
        total = len(self.signals)
        self.log.write(f"[replay:{self.candidate}] start signals={total} progress_every={self.args.progress_every}")
        for idx, source in enumerate(self.signals, start=1):
            when = signal_time(source)
            if when is None:
                self.record_skip(source, "signal_time_missing")
                continue
            self.eval_active_until(when)
            symbol = str(source.symbol or "").upper()
            timeframe = str(source.timeframe or "")
            if not symbol or not timeframe:
                self.record_skip(source, "symbol_or_timeframe_missing")
            elif (symbol, timeframe) not in self.buckets:
                self.record_skip(source, "market_buckets_missing")
            elif symbol in self.active:
                active = self.active[symbol].trade
                reason = "symbol_locked_pending_order" if active.entry_touched_at is None else "symbol_locked_open_position"
                self.record_skip(source, reason)
            else:
                reason = guard_reason(self.candidate, source)
                if reason:
                    self.record_skip(source, reason)
                else:
                    self.try_enter(source, when)
            if idx == 1 or idx == total or idx % self.args.progress_every == 0:
                self.progress(idx, total, when)

        latest = max((time for times in self.times.values() for time in times), default=None)
        if latest is not None:
            self.eval_active_until(latest)
        summary = summarize(self.candidate, self.trades, self.skip_counts, self.entry_guard_counts)
        summary.update({
            "processed_signals": total,
            "market_entries": self.market_entries,
            "pending_entries": self.pending_entries,
            "elapsed_seconds": round(time.time() - started, 3),
        })
        self.log.write(
            f"[replay:{self.candidate}] finish entered={summary['entered_trades']} "
            f"closed={summary['closed_trades']} open={summary['open_trades']} "
            f"winrate={summary['winrate_pct']:.2f}% R={summary['total_r']:.3f} "
            f"allocated_R={summary['allocated_r']:.3f}"
        )
        return summary


def summarize(candidate: str, trades: list[TradeSignal], skip_counts: Counter[str], entry_guard_counts: Counter[str]) -> dict[str, Any]:
    closed = [trade for trade in trades if trade.result in CLOSED]
    wins = [trade for trade in closed if trade.result == "win"]
    losses = [trade for trade in closed if trade.result == "loss"]
    total_r = sum(r_multiple(trade) for trade in closed)
    allocated_r = sum(r_multiple(trade) * size_mult(trade) for trade in closed)
    gross_win_r = sum(max(r_multiple(trade), 0.0) for trade in closed)
    gross_loss_r = sum(abs(min(r_multiple(trade), 0.0)) for trade in closed)
    equity_r = 0.0
    peak_r = 0.0
    max_drawdown_r = 0.0
    loss_streak = 0
    max_loss_streak = 0
    win_streak = 0
    max_win_streak = 0
    for trade in sorted(closed, key=lambda item: as_utc(getattr(item, "closed_at", None)) or as_utc(getattr(item, "created_at", None)) or datetime.min.replace(tzinfo=UTC)):
        trade_r = r_multiple(trade)
        equity_r += trade_r
        peak_r = max(peak_r, equity_r)
        max_drawdown_r = min(max_drawdown_r, equity_r - peak_r)
        if trade_r > 0:
            win_streak += 1
            loss_streak = 0
        elif trade_r < 0:
            loss_streak += 1
            win_streak = 0
        max_loss_streak = max(max_loss_streak, loss_streak)
        max_win_streak = max(max_win_streak, win_streak)
    by_tf: dict[str, dict[str, Any]] = {}
    for timeframe in sorted({trade.timeframe for trade in closed}):
        rows = [trade for trade in closed if trade.timeframe == timeframe]
        w = sum(1 for trade in rows if trade.result == "win")
        l = sum(1 for trade in rows if trade.result == "loss")
        by_tf[timeframe] = {
            "closed": len(rows),
            "wins": w,
            "losses": l,
            "winrate_pct": round(w / (w + l) * 100, 4) if w + l else 0.0,
            "total_r": round(sum(r_multiple(trade) for trade in rows), 6),
            "allocated_r": round(sum(r_multiple(trade) * size_mult(trade) for trade in rows), 6),
        }
    return {
        "candidate": candidate,
        "entered_trades": len(trades),
        "closed_trades": len(closed),
        "open_trades": sum(1 for trade in trades if trade.result == "open"),
        "wins": len(wins),
        "losses": len(losses),
        "breakevens": sum(1 for trade in closed if trade.result == "breakeven"),
        "timeouts": sum(1 for trade in closed if trade.result == "timeout"),
        "winrate_pct": round(len(wins) / (len(wins) + len(losses)) * 100, 4) if wins or losses else 0.0,
        "total_r": round(total_r, 6),
        "avg_r": round(total_r / len(closed), 6) if closed else 0.0,
        "allocated_r": round(allocated_r, 6),
        "avg_allocated_r": round(allocated_r / len(closed), 6) if closed else 0.0,
        "gross_win_r": round(gross_win_r, 6),
        "gross_loss_r": round(gross_loss_r, 6),
        "profit_factor_r": round(gross_win_r / gross_loss_r, 6) if gross_loss_r > EPS else None,
        "max_drawdown_r": round(max_drawdown_r, 6),
        "max_loss_streak": max_loss_streak,
        "max_win_streak": max_win_streak,
        "skipped_signals": sum(skip_counts.values()),
        "skip_counts": dict(skip_counts.most_common()),
        "entry_guard_counts": dict(entry_guard_counts.most_common()),
        "by_timeframe": by_tf,
    }


async def load_signals(session: Any, args: argparse.Namespace) -> list[TradeSignal]:
    start = parse_dt(args.from_time)
    end = parse_dt(args.to_time)
    if args.days > 0:
        latest = as_utc((await session.execute(select(func.max(TradeSignal.created_at)))).scalar_one_or_none())
        if latest is not None:
            cutoff = latest - timedelta(days=args.days)
            start = max(start, cutoff) if start else cutoff
    stmt = select(TradeSignal).where(TradeSignal.engine_tag == args.engine_tag)
    if start:
        stmt = stmt.where(TradeSignal.created_at >= start)
    if end:
        stmt = stmt.where(TradeSignal.created_at <= end)
    stmt = stmt.order_by(TradeSignal.created_at.asc(), TradeSignal.id.asc())
    if args.limit > 0:
        stmt = stmt.limit(args.limit)
    return list((await session.execute(stmt)).scalars().all())


async def load_buckets(session: Any, signals: list[TradeSignal], log: Log) -> dict[tuple[str, str], list[TimeframeBucket]]:
    symbols = sorted({trade.symbol for trade in signals})
    timeframes = sorted({trade.timeframe for trade in signals})
    start = min((signal_time(trade) for trade in signals if signal_time(trade)), default=None)
    stmt = select(MarketDataBucket).where(
        MarketDataBucket.symbol.in_(symbols),
        MarketDataBucket.timeframe.in_(timeframes),
    )
    if start is not None:
        stmt = stmt.where(MarketDataBucket.last_timestamp >= start - timedelta(days=2))
    stmt = stmt.order_by(MarketDataBucket.symbol, MarketDataBucket.timeframe, MarketDataBucket.last_timestamp)
    grouped: dict[tuple[str, str], list[TimeframeBucket]] = defaultdict(list)
    count = 0
    stream = await session.stream_scalars(stmt.execution_options(yield_per=5000))
    async for row in stream:
        bucket = TimeframeBucket.from_record(row)
        grouped[(bucket.symbol, bucket.timeframe)].append(bucket)
        count += 1
        if count == 1 or count % 100000 == 0:
            log.write(f"[load] buckets={count:,}")
    log.write(f"[load] bucket load complete rows={count:,} symbol_tf={len(grouped):,}")
    return dict(grouped)


def trade_rows(candidate: str, trades: list[TradeSignal]) -> list[dict[str, Any]]:
    rows = []
    for trade in trades:
        rows.append({
            "candidate": candidate,
            "source_signal_id": trade.id,
            "symbol": trade.symbol,
            "timeframe": trade.timeframe,
            "setup_type": trade.setup_type,
            "bias": trade.bias,
            "market_regime": trade.market_regime,
            "volatility_regime": trade.volatility_regime,
            "entry_kind": features(trade).get("replay_entry_kind", ""),
            "signal_time": iso(trade.created_at),
            "entry_touched_at": iso(trade.entry_touched_at),
            "closed_at": iso(trade.closed_at),
            "result": trade.result,
            "close_reason": trade.close_reason or "",
            "pnl_pct": round(float(trade.pnl_pct or 0.0), 8),
            "r_multiple": round(r_multiple(trade), 8),
            "position_size_multiplier": round(size_mult(trade), 8),
            "allocated_r": round(r_multiple(trade) * size_mult(trade), 8),
            "entry_price": trade.entry_price,
            "stop_loss": trade.invalidation_price,
            "target_price_1": trade.target_price_1,
            "target_price_2": trade.target_price_2,
            "continuation_quality_ready": features(trade).get("continuation_quality_ready", ""),
            "continuation_quality_score": features(trade).get("continuation_quality_score", ""),
            "market_pressure_4h": features(trade).get("market_pressure_4h", ""),
            "flow_alignment": features(trade).get("flow_alignment", ""),
            "volume_z_15m": features(trade).get("volume_z_15m", ""),
            "oi_delta_z_15m": features(trade).get("oi_delta_z_15m", ""),
            "taker_buy_sell_ratio_delta_15m": features(trade).get("taker_buy_sell_ratio_delta_15m", ""),
            "ema30": features(trade).get("ema30", ""),
            "ema100": features(trade).get("ema100", ""),
            "ema30_slope": features(trade).get("ema30_slope", ""),
            "ema30_extension_atr": features(trade).get("ema30_extension_atr", ""),
            "mae_r": features(trade).get("mae_r", ""),
            "mfe_r": features(trade).get("mfe_r", ""),
            "entry_efficiency": features(trade).get("entry_efficiency", ""),
        })
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]], fallback_fields: list[str]) -> None:
    fields = list(rows[0].keys()) if rows else fallback_fields
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(out: Path, stamp: str, candidate: str, summary: dict[str, Any], replay: Replay) -> dict[str, str]:
    out.mkdir(parents=True, exist_ok=True)
    summary_path = out / f"live_faithful_{candidate}_{stamp}.json"
    trades_path = out / f"live_faithful_{candidate}_{stamp}_trades.csv"
    skips_path = out / f"live_faithful_{candidate}_{stamp}_skips.csv"
    summary_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    write_csv(trades_path, trade_rows(candidate, replay.trades), ["candidate", "source_signal_id", "symbol", "result", "r_multiple"])
    write_csv(skips_path, replay.skips, ["candidate", "source_signal_id", "symbol", "timeframe", "reason", "details"])
    return {"summary": str(summary_path), "trades": str(trades_path), "skips": str(skips_path)}


def candidates(raw: str) -> list[str]:
    if raw == "all":
        return [
            "baseline",
            "qmid_p06",
            "qmid_p07",
            "qmid_p06_4h_only",
            "qmid_p06_15m_only",
            "qmid_p06_15m_strict",
            "qmid_p06_ema",
            "qmid_p06_ema_pullback",
            "qmid_p07_ema",
            "ema_only",
            "ema_pullback_only",
            "qmid_p06_4h_runner_2r",
            "qmid_p06_4h_runner_3r",
            "qmid_p06_failfast",
            "tf_simple",
            "context_guard",
            "quality_soft",
            "balanced_soft",
            "tf_profile",
            "guarded",
        ]
    result = [item.strip() for item in raw.split(",") if item.strip()]
    bad = [item for item in result if item not in CANDIDATE_NAMES]
    if bad:
        raise argparse.ArgumentTypeError(f"Unsupported candidate: {', '.join(bad)}")
    return result


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Live-faithful replay for stored trade_signals.")
    p.add_argument("--database-url")
    p.add_argument("--database-name", default=DEFAULT_DB)
    p.add_argument("--engine-tag", default="v2_balanced")
    p.add_argument("--candidate", type=candidates, default=candidates("all"))
    p.add_argument("--from-time")
    p.add_argument("--to-time")
    p.add_argument("--days", type=int, default=0)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--progress-every", type=int, default=25)
    p.add_argument("--log-events", action="store_true")
    p.add_argument("--output-dir", default="export")
    p.add_argument("--entry-mode", default=ENTRY_MODE_MARKET_PULLBACK_LIMIT)
    p.add_argument("--max-entry-drift-pct", type=float, default=DEFAULT_MAX_ENTRY_DRIFT_PCT)
    p.add_argument("--max-market-tp1-progress-pct", type=float, default=DEFAULT_MAX_MARKET_TP1_PROGRESS_PCT)
    p.add_argument("--max-pullback-tp1-progress-pct", type=float, default=DEFAULT_MAX_PULLBACK_TP1_PROGRESS_PCT)
    return p


async def async_main(args: argparse.Namespace) -> int:
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    out = Path(args.output_dir)
    log = Log(out / f"live_faithful_replay_{stamp}.log")
    try:
        url = db_url(args.database_name, args.database_url)
        log.write(f"[setup] database={masked(url)} engine_tag={args.engine_tag} candidates={','.join(args.candidate)}")
        engine = create_async_engine(url, future=True)
        Session = async_sessionmaker(engine, expire_on_commit=False)
        async with Session() as session:
            signals = await load_signals(session, args)
            signals = [trade for trade in signals if signal_time(trade) is not None]
            if not signals:
                log.write("[setup] no signals found")
                return 2
            window_start = min(signal_time(trade) for trade in signals if signal_time(trade))
            window_end = max(signal_time(trade) for trade in signals if signal_time(trade))
            log.write(f"[load] signals={len(signals):,} window={iso(window_start)}->{iso(window_end)}")
            buckets = await load_buckets(session, signals, log)
        await engine.dispose()
        build_indicator_cache(buckets)
        log.write(f"[load] indicator cache ready symbol_tf={len(INDICATOR_POINTS):,}")

        combined = {
            "created_at": datetime.now(UTC).isoformat(),
            "database": masked(url),
            "engine_tag": args.engine_tag,
            "signal_count": len(signals),
            "assumptions": {
                "event_order": "created_at asc, id asc",
                "execution_lock": "one active position or pending order per symbol",
                "entry_guard": "market plus pullback limit guard mirrors demo defaults",
                "exit_model": "scripts.replay_full_strategy._evaluate_trade_bucket",
                "indicator_tests": "EMA30/EMA100 gates use the replay bucket close available at or before signal_time.",
            },
            "candidates": {},
            "outputs": {},
        }
        for name in args.candidate:
            replay = Replay(args, name, signals, buckets, log)
            summary = replay.run()
            paths = write_outputs(out, stamp, name, summary, replay)
            combined["candidates"][name] = summary
            combined["outputs"][name] = paths
            log.write(f"[output:{name}] summary={paths['summary']} trades={paths['trades']} skips={paths['skips']}")
        combined_path = out / f"live_faithful_summary_{stamp}.json"
        combined_path.write_text(json.dumps(combined, indent=2, default=str), encoding="utf-8")
        log.write(f"[output] combined_summary={combined_path}")
        return 0
    finally:
        log.close()


def main() -> int:
    return asyncio.run(async_main(parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
