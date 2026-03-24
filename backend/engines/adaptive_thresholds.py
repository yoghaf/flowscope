from __future__ import annotations

import math
from dataclasses import dataclass


EPSILON = 1e-12


@dataclass(slots=True)
class AdaptiveThresholds:
    oi_abs: float
    volume: float
    price_move: float
    compression: float
    crowd: float


def percentile(values: list[float], q: float, default: float) -> float:
    cleaned = sorted(value for value in values if math.isfinite(value))
    if not cleaned:
        return default
    if len(cleaned) == 1:
        return cleaned[0]

    bounded_q = max(0.0, min(q, 1.0))
    position = (len(cleaned) - 1) * bounded_q
    lower_index = int(math.floor(position))
    upper_index = int(math.ceil(position))
    if lower_index == upper_index:
        return cleaned[lower_index]

    lower_value = cleaned[lower_index]
    upper_value = cleaned[upper_index]
    fraction = position - lower_index
    return lower_value + (upper_value - lower_value) * fraction


def build_adaptive_thresholds(
    feature_rows: list[dict[str, float]],
    profile: dict[str, float | int],
) -> AdaptiveThresholds:
    default_oi = max(float(profile["oi_z"]) * 0.5, 0.3)
    default_volume = max(float(profile["volume_z"]) * 0.55, 0.35)
    default_price = max(float(profile["price_flat"]) * 0.8, EPSILON)
    default_compression = max(float(profile.get("compression_min", 0.5)) * 0.9, 0.35)

    oi_samples = [abs(row["oi_delta_z"]) for row in feature_rows if abs(row["oi_delta_z"]) > EPSILON]
    volume_samples = [row["volume_z"] for row in feature_rows if row["volume_z"] > EPSILON]
    price_samples = [abs(row["price_change"]) for row in feature_rows if abs(row["price_change"]) > EPSILON]
    compression_samples = [row["compression"] for row in feature_rows if row["compression"] > EPSILON]
    crowd_samples = [
        max(
            abs(row["funding_trend"]) / max(float(profile["funding_trend"]), EPSILON),
            abs(row["ls_delta"]) / max(float(profile["ls_delta"]), EPSILON),
        )
        for row in feature_rows
    ]

    return AdaptiveThresholds(
        oi_abs=max(percentile(oi_samples, 0.60, default_oi), 0.2),
        volume=max(percentile(volume_samples, 0.70, default_volume), 0.2),
        price_move=max(percentile(price_samples, 0.65, default_price), EPSILON),
        compression=max(percentile(compression_samples, 0.60, default_compression), 0.25),
        crowd=max(percentile(crowd_samples, 0.65, 1.0), 0.5),
    )
