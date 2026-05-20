from __future__ import annotations

import asyncio
import hashlib
import math
import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.config import get_settings
from backend.models import MarketDataBucket


OBSERVATIONS_PATH = REPO_ROOT / "artifacts" / "forward_shadow_observations.csv"
REGISTRY_PATH = REPO_ROOT / "artifacts" / "forward_shadow_observations_registry.csv"
OUTCOMES_PATH = REPO_ROOT / "artifacts" / "forward_shadow_outcomes.csv"
SUMMARY_PATH = REPO_ROOT / "artifacts" / "forward_shadow_outcome_summary.md"
TRACKING_TIMEFRAME = "15m"
HORIZONS: dict[str, timedelta] = {
    "15m": timedelta(minutes=15),
    "30m": timedelta(minutes=30),
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
}
OUTCOME_COLUMNS = [
    "observation_id",
    "observation_key",
    "symbol",
    "timeframe",
    "timestamp",
    "timestamp_floor",
    "price_at_observation",
    "after_15m_return",
    "after_30m_return",
    "after_1h_return",
    "after_4h_return",
    "mfe_1h",
    "mae_1h",
    "mfe_4h",
    "mae_4h",
    "max_favorable_time_4h",
    "max_adverse_time_4h",
    "outcome_status",
    "outcome_label",
    "outcome_reason",
    "evaluated_at",
    "future_data_points_15m",
    "future_data_points_30m",
    "future_data_points_1h",
    "future_data_points_4h",
    "future_price_source",
    "future_data_quality_status",
    "layer5_watch_status",
    "layer5_direction_bias",
    "v2_action_status",
    "v2_action_bias",
    "v2balanced_candidate_stage",
    "v2balanced_semantic_readiness",
    "final_entry_permission",
    "semantic_gate_shadow_decision",
    "market_relative_status_15m",
    "entry_location_phase_15m",
    "entry_location_quality_15m",
    "scenario_label",
    "scenario_disposition",
    "hard_filter_reasons",
    # Phase 9 Shadow Taxonomy
    "phase9_shadow_label",
    "phase9_shadow_reason",
    "phase9_entry_candidate_shadow",
    "phase9_wait_subtype",
    "phase9_range_subtype",
    "phase9_late_subtype",
    "phase9_risk_subtype",
    "phase9_block_subtype",
]

MEANINGFUL_MOVE = 0.015
CONTROLLED_ADVERSE = 0.0075
CHOP_MOVE = 0.010


@dataclass(frozen=True)
class FutureBucket:
    symbol: str
    timeframe: str
    bucket_start: datetime
    bucket_end: datetime
    high_price: float
    low_price: float
    close_price: float


def _clean_value(value: Any, default: str = "") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return default
    return text


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric) or numeric <= 0:
        return None
    return numeric


def _parse_timestamp(value: Any) -> datetime | None:
    text = _clean_value(value)
    if not text:
        return None
    ts = pd.to_datetime(text, utc=True, errors="coerce")
    if pd.isna(ts):
        return None
    return ts.to_pydatetime()


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def floor_timestamp(timestamp: datetime, timeframe: str) -> datetime:
    timestamp = timestamp.astimezone(UTC)
    if timeframe.endswith("m"):
        minutes = int(timeframe[:-1])
        floored_minute = timestamp.minute - (timestamp.minute % minutes)
        return timestamp.replace(minute=floored_minute, second=0, microsecond=0)
    if timeframe.endswith("h"):
        hours = int(timeframe[:-1])
        floored_hour = timestamp.hour - (timestamp.hour % hours)
        return timestamp.replace(hour=floored_hour, minute=0, second=0, microsecond=0)
    return timestamp.replace(second=0, microsecond=0)


def observation_key(row: dict[str, Any]) -> str:
    timestamp = _clean_value(row.get("timestamp"))
    return "|".join(
        [
            _clean_value(row.get("symbol")).upper(),
            _clean_value(row.get("timeframe"), TRACKING_TIMEFRAME),
            timestamp,
            _clean_value(row.get("layer5_watch_status"), "NONE"),
            _clean_value(row.get("layer5_direction_bias"), "NO_DIRECTION"),
            _clean_value(row.get("v2balanced_semantic_readiness"), "NO_SETUP"),
            _clean_value(row.get("market_relative_status_15m"), "UNKNOWN_MARKET_CONTEXT"),
            _clean_value(row.get("entry_location_phase_15m") or row.get("entry_location_label_15m"), "UNKNOWN_LOCATION"),
        ]
    )


def observation_id(row: dict[str, Any]) -> str:
    return hashlib.sha256(observation_key(row).encode("utf-8")).hexdigest()


def dedupe_observations(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    normalized = df.copy()
    normalized["observation_id"] = normalized.apply(lambda row: observation_id(row.to_dict()), axis=1)
    return normalized.drop_duplicates(subset=["observation_id"], keep="last").reset_index(drop=True)


def direction_kind(row: dict[str, Any]) -> str:
    direction = _clean_value(row.get("layer5_direction_bias"), "NO_DIRECTION")
    bias = _clean_value(row.get("v2_action_bias"))
    if direction in {"LONG_WATCH", "SHORT_SQUEEZE_WATCH"} or bias == "Bullish":
        return "LONG"
    if direction in {"SHORT_WATCH", "LONG_TRAP_WATCH"} or bias == "Bearish":
        return "SHORT"
    return "NONE"


def _bucket_close_return(price: float, bucket: FutureBucket | None) -> float | None:
    if bucket is None or price <= 0:
        return None
    return bucket.close_price / price - 1.0


def _target_bucket(future_buckets: list[FutureBucket], target: datetime) -> FutureBucket | None:
    candidates = [bucket for bucket in future_buckets if bucket.bucket_end >= target]
    return min(candidates, key=lambda bucket: bucket.bucket_end) if candidates else None


def _window_buckets(future_buckets: list[FutureBucket], start: datetime, end: datetime) -> list[FutureBucket]:
    return [bucket for bucket in future_buckets if bucket.bucket_end > start and bucket.bucket_end <= end]


def direction_aware_excursions(
    *,
    price: float,
    buckets: list[FutureBucket],
    direction: str,
) -> tuple[float | None, float | None, datetime | None, datetime | None]:
    if price <= 0 or not buckets:
        return None, None, None, None

    favorable: list[tuple[float, datetime]] = []
    adverse: list[tuple[float, datetime]] = []
    for bucket in buckets:
        if direction == "LONG":
            favorable.append((bucket.high_price / price - 1.0, bucket.bucket_end))
            adverse.append((bucket.low_price / price - 1.0, bucket.bucket_end))
        elif direction == "SHORT":
            favorable.append((price / bucket.low_price - 1.0, bucket.bucket_end))
            adverse.append((price / bucket.high_price - 1.0, bucket.bucket_end))
        else:
            high_move = abs(bucket.high_price / price - 1.0)
            low_move = abs(bucket.low_price / price - 1.0)
            favorable.append((max(high_move, low_move), bucket.bucket_end))
            adverse.append((min(bucket.close_price / price - 1.0, 0.0), bucket.bucket_end))

    max_favorable = max(favorable, key=lambda item: item[0])
    max_adverse = min(adverse, key=lambda item: item[0])
    return max_favorable[0], max_adverse[0], max_favorable[1], max_adverse[1]


def _directional_return(row: dict[str, Any], signed_return: float | None) -> float | None:
    if signed_return is None:
        return None
    direction = direction_kind(row)
    if direction == "SHORT":
        return -signed_return
    if direction == "LONG":
        return signed_return
    return abs(signed_return)


def classify_outcome(row: dict[str, Any]) -> tuple[str, str]:
    status = _clean_value(row.get("outcome_status"))
    if status in {"PENDING", "MISSING_DATA"}:
        return "UNKNOWN_OUTCOME", status.lower()

    price = _float_or_none(row.get("price_at_observation"))
    if price is None:
        return "UNKNOWN_OUTCOME", "missing_price_at_observation"

    readiness = _clean_value(row.get("v2balanced_semantic_readiness"), "NO_SETUP")
    layer5_status = _clean_value(row.get("layer5_watch_status"), "NONE")
    direction = _clean_value(row.get("layer5_direction_bias"), "NO_DIRECTION")
    v2_status = _clean_value(row.get("v2_action_status") or row.get("action_status"))
    gate_decision = _clean_value(row.get("semantic_gate_shadow_decision"))
    entry_phase = _clean_value(row.get("entry_location_phase_15m"), "UNKNOWN_LOCATION")
    mfe_4h = row.get("mfe_4h")
    mae_4h = row.get("mae_4h")
    directional_4h = _directional_return(row, row.get("after_4h_return"))
    if directional_4h is None:
        directional_4h = _directional_return(row, row.get("after_1h_return"))

    favorable = float(mfe_4h) if mfe_4h is not None and not pd.isna(mfe_4h) else directional_4h or 0.0
    adverse_abs = abs(float(mae_4h)) if mae_4h is not None and not pd.isna(mae_4h) else 0.0
    clean_move = favorable >= MEANINGFUL_MOVE and adverse_abs <= CONTROLLED_ADVERSE
    adverse_or_chop = adverse_abs >= MEANINGFUL_MOVE or favorable < CHOP_MOVE
    chop = favorable < CHOP_MOVE and adverse_abs < CHOP_MOVE
    semantic_protects = readiness in {"WAIT_SCENARIO", "WAIT_DIRECTION", "AVOID_LAYER5_RISK", "DATA_BLOCKED"}
    gate_protects = gate_decision.startswith("would_wait") or gate_decision.startswith("would_block")

    if v2_status == "Ready" and semantic_protects and gate_protects and adverse_or_chop:
        return "LEGACY_READY_PROTECTED", f"legacy_ready_{readiness.lower()}_protected"
    if v2_status == "Triggered" and semantic_protects and gate_protects and adverse_or_chop:
        return "LEGACY_TRIGGER_PROTECTED", f"legacy_trigger_{readiness.lower()}_protected"

    if readiness == "AVOID_LAYER5_RISK" or layer5_status == "AVOID_HARD_RISK":
        if clean_move:
            return "BAD_AVOID", "avoid_filtered_clean_continuation"
        if adverse_or_chop or entry_phase in {"EXHAUSTION_RISK", "DISTRIBUTION_RISK", "ACCUMULATION_RISK"}:
            return "GOOD_AVOID", "avoid_risk_validated"
        return "UNKNOWN_OUTCOME", "avoid_outcome_ambiguous"

    if readiness in {"WAIT_SCENARIO", "WAIT_DIRECTION"}:
        if clean_move:
            return "BAD_WAIT", "wait_missed_clean_move"
        if adverse_or_chop:
            return "GOOD_WAIT", "wait_protected_from_chop_or_adverse_move"
        return "UNKNOWN_OUTCOME", "wait_outcome_ambiguous"

    if layer5_status.startswith("WATCHLIST_") or direction in {"LONG_WATCH", "SHORT_WATCH", "SHORT_SQUEEZE_WATCH", "LONG_TRAP_WATCH"}:
        if clean_move:
            return "GOOD_WATCH", "watch_direction_followed_through"
        if adverse_abs >= MEANINGFUL_MOVE or chop:
            return "FALSE_WATCH", "watch_failed_to_confirm"
        return "UNKNOWN_OUTCOME", "watch_outcome_ambiguous"

    if readiness == "NO_SETUP" or layer5_status == "NONE" or direction == "NO_DIRECTION":
        if clean_move:
            return "BAD_NO_SETUP", "no_setup_missed_clean_move"
        if chop:
            return "GOOD_NO_SETUP", "no_setup_chop_confirmed"
        if favorable >= MEANINGFUL_MOVE:
            return "MISSED_MOVE", "missed_move_after_no_setup"
        return "CHOP_CONFIRMED", "no_direction_chop_confirmed"

    if clean_move and semantic_protects:
        return "MISSED_MOVE", "missed_move_after_non_ready_state"
    if chop:
        return "CHOP_CONFIRMED", "chop_confirmed"
    return "UNKNOWN_OUTCOME", "outcome_ambiguous"


def evaluate_observation(
    observation: dict[str, Any],
    symbol_buckets: list[FutureBucket],
    *,
    evaluated_at: datetime,
) -> dict[str, Any]:
    symbol = _clean_value(observation.get("symbol")).upper()
    timeframe = _clean_value(observation.get("timeframe"), TRACKING_TIMEFRAME)
    timestamp = _parse_timestamp(observation.get("timestamp"))
    if timestamp is None:
        row = _base_outcome_row(observation, None, None, evaluated_at=evaluated_at)
        row["outcome_status"] = "MISSING_DATA"
        row["outcome_label"] = "UNKNOWN_OUTCOME"
        row["outcome_reason"] = "missing_observation_timestamp"
        return row

    timestamp_floor = floor_timestamp(timestamp, timeframe)
    obs_id = observation_id(observation)
    obs_key = observation_key(observation)
    price = _float_or_none(
        observation.get("price_at_observation")
        or observation.get("price")
        or observation.get("close_price")
    )
    ordered_buckets = sorted(symbol_buckets, key=lambda bucket: bucket.bucket_end)
    if price is None:
        price_bucket = _observation_price_bucket(ordered_buckets, timestamp)
        price = price_bucket.close_price if price_bucket is not None else None

    row = _base_outcome_row(observation, obs_id, obs_key, evaluated_at=evaluated_at)
    row["timestamp"] = _iso(timestamp)
    row["timestamp_floor"] = _iso(timestamp_floor)
    row["price_at_observation"] = price

    if price is None:
        row["outcome_status"] = "MISSING_DATA"
        row["outcome_label"] = "UNKNOWN_OUTCOME"
        row["outcome_reason"] = "missing_price_at_observation"
        return row

    future_buckets = [bucket for bucket in ordered_buckets if bucket.bucket_end > timestamp]
    latest_bucket_end = max((bucket.bucket_end for bucket in ordered_buckets), default=None)
    available_horizons = 0
    pending_horizons = 0
    missing_horizons = 0
    for label, delta in HORIZONS.items():
        target = timestamp + delta
        target_bucket = _target_bucket(future_buckets, target)
        row[f"after_{label}_return"] = _bucket_close_return(price, target_bucket)
        row[f"future_data_points_{label}"] = len(_window_buckets(future_buckets, timestamp, target))
        if target_bucket is not None:
            available_horizons += 1
        elif latest_bucket_end is not None and latest_bucket_end < target:
            pending_horizons += 1
        else:
            missing_horizons += 1

    direction = direction_kind(observation)
    one_hour_buckets = _window_buckets(future_buckets, timestamp, timestamp + HORIZONS["1h"])
    four_hour_buckets = _window_buckets(future_buckets, timestamp, timestamp + HORIZONS["4h"])
    row["mfe_1h"], row["mae_1h"], _, _ = direction_aware_excursions(
        price=price,
        buckets=one_hour_buckets,
        direction=direction,
    )
    row["mfe_4h"], row["mae_4h"], favorable_time, adverse_time = direction_aware_excursions(
        price=price,
        buckets=four_hour_buckets,
        direction=direction,
    )
    row["max_favorable_time_4h"] = _iso(favorable_time)
    row["max_adverse_time_4h"] = _iso(adverse_time)
    row["future_price_source"] = "market_data_buckets_15m" if ordered_buckets else "missing"
    row["future_data_quality_status"] = "AVAILABLE" if future_buckets else "MISSING"

    if available_horizons == len(HORIZONS):
        row["outcome_status"] = "COMPLETE"
    elif available_horizons > 0:
        row["outcome_status"] = "PENDING" if pending_horizons else "PARTIAL"
    elif pending_horizons:
        row["outcome_status"] = "PENDING"
    else:
        row["outcome_status"] = "MISSING_DATA"

    row["outcome_label"], row["outcome_reason"] = classify_outcome(row)
    return row


def _base_outcome_row(
    observation: dict[str, Any],
    obs_id: str | None,
    obs_key: str | None,
    *,
    evaluated_at: datetime,
) -> dict[str, Any]:
    row = {column: None for column in OUTCOME_COLUMNS}
    row["observation_id"] = obs_id or observation_id(observation)
    row["observation_key"] = obs_key or observation_key(observation)
    row["symbol"] = _clean_value(observation.get("symbol")).upper()
    row["timeframe"] = _clean_value(observation.get("timeframe"), TRACKING_TIMEFRAME)
    row["evaluated_at"] = _iso(evaluated_at)
    row["outcome_status"] = "MISSING_DATA"
    row["outcome_label"] = "UNKNOWN_OUTCOME"
    row["outcome_reason"] = "not_evaluated"
    for column in [
        "layer5_watch_status",
        "layer5_direction_bias",
        "v2_action_status",
        "v2_action_bias",
        "v2balanced_candidate_stage",
        "v2balanced_semantic_readiness",
        "final_entry_permission",
        "semantic_gate_shadow_decision",
        "market_relative_status_15m",
        "entry_location_phase_15m",
        "entry_location_quality_15m",
        "scenario_label",
        "scenario_disposition",
        "hard_filter_reasons",
        # Phase 9 Shadow Taxonomy
        "phase9_shadow_label",
        "phase9_shadow_reason",
        "phase9_entry_candidate_shadow",
        "phase9_wait_subtype",
        "phase9_range_subtype",
        "phase9_late_subtype",
        "phase9_risk_subtype",
        "phase9_block_subtype",
    ]:
        row[column] = _clean_value(observation.get(column))
    return row


def _observation_price_bucket(buckets: list[FutureBucket], timestamp: datetime) -> FutureBucket | None:
    containing = [bucket for bucket in buckets if bucket.bucket_start <= timestamp <= bucket.bucket_end]
    if containing:
        return max(containing, key=lambda bucket: bucket.bucket_end)
    prior = [bucket for bucket in buckets if bucket.bucket_end <= timestamp]
    return max(prior, key=lambda bucket: bucket.bucket_end) if prior else None


async def load_market_buckets(observations: pd.DataFrame) -> dict[str, list[FutureBucket]]:
    if observations.empty:
        return {}
    timestamps = observations["timestamp"].apply(_parse_timestamp).dropna()
    symbols = sorted({_clean_value(value).upper() for value in observations["symbol"].dropna() if _clean_value(value)})
    if timestamps.empty or not symbols:
        return {}

    min_ts = min(timestamps) - timedelta(minutes=15)
    max_ts = max(timestamps) + HORIZONS["4h"] + timedelta(minutes=15)
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False, pool_pre_ping=True)
    session_factory = async_sessionmaker(bind=engine, expire_on_commit=False)
    buckets_by_symbol: dict[str, list[FutureBucket]] = {symbol: [] for symbol in symbols}
    try:
        async with session_factory() as session:
            result = await session.execute(
                select(MarketDataBucket)
                .where(MarketDataBucket.timeframe == TRACKING_TIMEFRAME)
                .where(MarketDataBucket.symbol.in_(symbols))
                .where(MarketDataBucket.bucket_end >= min_ts)
                .where(MarketDataBucket.bucket_start <= max_ts)
                .order_by(MarketDataBucket.symbol.asc(), MarketDataBucket.bucket_start.asc())
            )
            for bucket in result.scalars().all():
                buckets_by_symbol.setdefault(bucket.symbol, []).append(
                    FutureBucket(
                        symbol=bucket.symbol,
                        timeframe=bucket.timeframe,
                        bucket_start=bucket.bucket_start.astimezone(UTC),
                        bucket_end=bucket.bucket_end.astimezone(UTC),
                        high_price=bucket.high_price,
                        low_price=bucket.low_price,
                        close_price=bucket.close_price,
                    )
                )
    except Exception as exc:
        print(f"[WARN] Future bucket lookup failed: {exc}")
        return {}
    finally:
        await engine.dispose()
    return buckets_by_symbol


def load_observations(path: Path | None = None) -> pd.DataFrame:
    """Load observations, preferring the append-only registry when available."""
    if path is not None:
        if not path.exists():
            return pd.DataFrame()
        return pd.read_csv(path)
    # Prefer registry (append-only, survives multiple monitor runs)
    if REGISTRY_PATH.exists() and REGISTRY_PATH.stat().st_size > 0:
        return pd.read_csv(REGISTRY_PATH)
    # Fallback to per-run observations CSV
    if OBSERVATIONS_PATH.exists():
        return pd.read_csv(OBSERVATIONS_PATH)
    return pd.DataFrame()


def evaluate_observations(
    observations: pd.DataFrame,
    buckets_by_symbol: dict[str, list[FutureBucket]],
    *,
    evaluated_at: datetime | None = None,
) -> pd.DataFrame:
    evaluated_at = evaluated_at or datetime.now(UTC)
    deduped = dedupe_observations(observations)
    rows = []
    for _, obs in deduped.iterrows():
        observation = obs.to_dict()
        symbol = _clean_value(observation.get("symbol")).upper()
        rows.append(
            evaluate_observation(
                observation,
                buckets_by_symbol.get(symbol, []),
                evaluated_at=evaluated_at,
            )
        )
    return pd.DataFrame(rows, columns=OUTCOME_COLUMNS)


def _summary_series(df: pd.DataFrame, column: str, default: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series([default] * len(df), index=df.index, dtype="object")
    return df[column].fillna(default).replace("", default)


def _numeric_summary_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series([pd.NA] * len(df), index=df.index)
    return pd.to_numeric(df[column], errors="coerce")


def _write_markdown_table(handle: Any, table: pd.DataFrame | pd.Series, *, empty_note: str = "No data.") -> None:
    if table.empty:
        handle.write(empty_note)
    else:
        handle.write(table.to_markdown())
    handle.write("\n\n")


def _write_missing_column_note(handle: Any, column: str) -> None:
    handle.write(f"Column `{column}` is not available in this outcomes file.\n\n")


def _grouped_outcome_table(df: pd.DataFrame, group_column: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    labels = _summary_series(df, "outcome_label", "UNKNOWN_OUTCOME")
    groups = _summary_series(df, group_column, "UNKNOWN")
    table = pd.crosstab(groups, labels)
    if table.empty:
        return table
    table.insert(0, "n", table.sum(axis=1))
    table["sample_note"] = table["n"].apply(lambda value: "LOW_SAMPLE_WEAK_EVIDENCE" if int(value) < 5 else "")
    return table.sort_values(["n"], ascending=False)


def _case_review_table(outcomes: pd.DataFrame, labels: list[str]) -> pd.DataFrame:
    if outcomes.empty or "outcome_label" not in outcomes.columns:
        return pd.DataFrame()
    subset = outcomes[_summary_series(outcomes, "outcome_label", "UNKNOWN_OUTCOME").isin(labels)].copy()
    if subset.empty:
        return pd.DataFrame()

    subset["_mfe_4h_sort"] = _numeric_summary_series(subset, "mfe_4h").abs()
    subset["_after_4h_sort"] = _numeric_summary_series(subset, "after_4h_return").abs()
    subset = subset.sort_values(["_mfe_4h_sort", "_after_4h_sort"], ascending=False, na_position="last")
    columns = [
        "symbol",
        "timeframe",
        "timestamp",
        "layer5_direction_bias",
        "v2balanced_semantic_readiness",
        "market_relative_status_15m",
        "entry_location_phase_15m",
        "outcome_label",
        "after_1h_return",
        "after_4h_return",
        "mfe_4h",
        "mae_4h",
    ]
    available_columns = [column for column in columns if column in subset.columns]
    return subset[available_columns].head(10)


def write_summary(outcomes: pd.DataFrame, path: Path = SUMMARY_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("# Forward Shadow Outcome Summary\n\n")
        handle.write(f"**Report Generated**: {_iso(datetime.now(UTC))}\n\n")
        if outcomes.empty:
            handle.write("No forward shadow outcomes evaluated yet.\n")
            return

        handle.write(f"- **Total rows**: {len(outcomes)}\n")
        handle.write(f"- **Total observations evaluated**: {len(outcomes)}\n")
        status_counts = _summary_series(outcomes, "outcome_status", "UNKNOWN").value_counts()
        complete_count = int(status_counts.get("COMPLETE", 0))
        pending_count = int(status_counts.get("PENDING", 0))
        unknown_count = int(_summary_series(outcomes, "outcome_label", "UNKNOWN_OUTCOME").eq("UNKNOWN_OUTCOME").sum())
        completion_rate = (complete_count / len(outcomes) * 100.0) if len(outcomes) else 0.0
        handle.write(f"- **Complete**: {complete_count}\n")
        handle.write(f"- **Pending**: {pending_count}\n")
        handle.write(f"- **UNKNOWN_OUTCOME**: {unknown_count}\n")
        handle.write(f"- **Completion rate**: {completion_rate:.1f}%\n\n")

        handle.write("## Sample-Size Warnings\n")
        if complete_count < 30:
            handle.write(
                f"- COMPLETE sample is still too small for Phase 9 decisions: {complete_count}/30 minimum review target.\n"
            )
        else:
            handle.write("- COMPLETE sample has reached the minimum review target for early Phase 9 analysis.\n")
        handle.write("- Grouped rows with `LOW_SAMPLE_WEAK_EVIDENCE` have n < 5 and should not drive decisions alone.\n\n")

        completed = outcomes[_summary_series(outcomes, "outcome_status", "UNKNOWN").eq("COMPLETE")].copy()
        handle.write("## Completed Outcome Label Distribution\n")
        if completed.empty:
            handle.write("No COMPLETE outcomes yet.\n\n")
        else:
            _write_markdown_table(
                handle,
                _summary_series(completed, "outcome_label", "UNKNOWN_OUTCOME").value_counts(),
            )

        completed_groups = [
            ("Completed Outcomes by Semantic Readiness", "v2balanced_semantic_readiness"),
            ("Completed Outcomes by Entry Location Phase 15m", "entry_location_phase_15m"),
            ("Completed Outcomes by Entry Location Quality 15m", "entry_location_quality_15m"),
            ("Completed Outcomes by Layer5 Direction", "layer5_direction_bias"),
            ("Completed Outcomes by Market-Relative Status 15m", "market_relative_status_15m"),
            ("Completed Outcomes by Layer5 Watch Status", "layer5_watch_status"),
        ]
        for title, column in completed_groups:
            handle.write(f"## {title}\n")
            if column not in outcomes.columns:
                _write_missing_column_note(handle, column)
                continue
            _write_markdown_table(
                handle,
                _grouped_outcome_table(completed, column),
                empty_note="No COMPLETE outcomes yet.",
            )

        sections = [
            ("Outcome Label Distribution", _summary_series(outcomes, "outcome_label", "UNKNOWN_OUTCOME").value_counts()),
            ("Outcome by Semantic Readiness", _grouped_outcome_table(outcomes, "v2balanced_semantic_readiness")),
            ("Outcome by Layer5 Direction", _grouped_outcome_table(outcomes, "layer5_direction_bias")),
            ("Outcome by Market-Relative Status 15m", _grouped_outcome_table(outcomes, "market_relative_status_15m")),
            ("Outcome by Entry Location Phase 15m", _grouped_outcome_table(outcomes, "entry_location_phase_15m")),
        ]
        for title, table in sections:
            handle.write(f"## {title}\n")
            handle.write(table.to_markdown() if not table.empty else "No data.")
            handle.write("\n\n")

        # --- Phase 9 Shadow Taxonomy Outcome Grouping ---
        phase9_groups = [
            ("Outcome by Phase 9 Shadow Label", "phase9_shadow_label"),
            ("Outcome by Phase 9 Wait Subtype", "phase9_wait_subtype"),
            ("Outcome by Phase 9 Range Subtype", "phase9_range_subtype"),
            ("Outcome by Phase 9 Late Subtype", "phase9_late_subtype"),
            ("Outcome by Phase 9 Risk Subtype", "phase9_risk_subtype"),
            ("Outcome by Phase 9 Block Subtype", "phase9_block_subtype"),
        ]
        for title, column in phase9_groups:
            handle.write(f"## {title}\n")
            if column not in outcomes.columns:
                _write_missing_column_note(handle, column)
                continue
            non_null = _summary_series(outcomes, column, "").replace("", pd.NA).dropna()
            if non_null.empty:
                handle.write("No data with Phase 9 labels yet.\n\n")
                continue
            filtered = outcomes[_summary_series(outcomes, column, "").replace("", pd.NA).notna()].copy()
            if filtered.empty:
                handle.write("No data with Phase 9 labels yet.\n\n")
                continue
            _write_markdown_table(
                handle,
                _grouped_outcome_table(filtered, column),
                empty_note="No data with Phase 9 labels yet.",
            )

        example_cols = [
            "symbol",
            "timestamp",
            "layer5_direction_bias",
            "v2balanced_semantic_readiness",
            "market_relative_status_15m",
            "entry_location_phase_15m",
            "after_1h_return",
            "after_4h_return",
            "mfe_4h",
            "mae_4h",
            "outcome_reason",
        ]
        examples = [
            ("Top MISSED_MOVE Cases", ["MISSED_MOVE"]),
            ("Top GOOD_WAIT Examples", ["GOOD_WAIT"]),
            ("Top BAD_WAIT Examples", ["BAD_WAIT"]),
            ("Top GOOD_AVOID Examples", ["GOOD_AVOID"]),
            ("Top BAD_AVOID Examples", ["BAD_AVOID"]),
            ("Top FALSE_WATCH Cases", ["FALSE_WATCH"]),
            ("Legacy Ready Protected Examples", ["LEGACY_READY_PROTECTED", "LEGACY_TRIGGER_PROTECTED"]),
        ]
        for title, labels in examples:
            subset = outcomes[_summary_series(outcomes, "outcome_label", "UNKNOWN_OUTCOME").isin(labels)].copy()
            handle.write(f"## {title}\n")
            if subset.empty:
                handle.write("No examples yet.\n\n")
                continue
            subset["_sort_abs_mfe"] = pd.to_numeric(subset["mfe_4h"], errors="coerce").abs()
            subset = subset.sort_values("_sort_abs_mfe", ascending=False, na_position="last")
            handle.write(subset[[col for col in example_cols if col in subset.columns]].head(10).to_markdown(index=False))
            handle.write("\n\n")

        review_sections = [
            ("Review Table: MISSED_MOVE", ["MISSED_MOVE"]),
            ("Review Table: BAD_WAIT", ["BAD_WAIT"]),
            ("Review Table: BAD_AVOID", ["BAD_AVOID"]),
            ("Review Table: FALSE_WATCH", ["FALSE_WATCH"]),
        ]
        for title, labels in review_sections:
            handle.write(f"## {title}\n")
            table = _case_review_table(outcomes, labels)
            if table.empty:
                handle.write("No cases yet.\n\n")
            else:
                handle.write(table.to_markdown(index=False))
                handle.write("\n\n")


async def run_tracker() -> None:
    observations = load_observations()
    if observations.empty:
        outcomes = pd.DataFrame(columns=OUTCOME_COLUMNS)
    else:
        buckets_by_symbol = await load_market_buckets(observations)
        outcomes = evaluate_observations(observations, buckets_by_symbol)

    OUTCOMES_PATH.parent.mkdir(parents=True, exist_ok=True)
    outcomes.to_csv(OUTCOMES_PATH, index=False, encoding="utf-8")
    write_summary(outcomes, SUMMARY_PATH)
    print(f"Observations evaluated: {len(outcomes)}")
    print(f"Outcomes CSV: {OUTCOMES_PATH}")
    print(f"Outcome summary: {SUMMARY_PATH}")


if __name__ == "__main__":
    asyncio.run(run_tracker())
