from __future__ import annotations

import argparse
import asyncio
from collections import defaultdict
from collections.abc import Iterable

from sqlalchemy import select

from backend.config import get_settings
from backend.database import DatabaseManager
from backend.models import MarketDataBucket
from backend.services.realtime import RealtimeHub
from backend.services.signal_service import SignalService
from backend.services.timeframe_aggregator import TIMEFRAME_ORDER, TimeframeBucket


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay Pre-Breakdown detection from stored market_data_buckets.")
    parser.add_argument("--symbol", required=True, help="Symbol, for example XRPUSDT")
    parser.add_argument("--timeframe", default="15m", choices=["15m", "1h", "4h"], help="Replay anchor timeframe")
    parser.add_argument("--limit", type=int, default=300, help="Maximum anchor buckets to replay")
    return parser.parse_args()


def _distribution_risk_label(market_interpretation: dict[str, object] | None) -> str:
    warnings = market_interpretation.get("warnings", []) if isinstance(market_interpretation, dict) else []
    for warning in warnings:
        if isinstance(warning, str) and warning.startswith("Distribution Risk:"):
            return warning.split(":", 1)[1].strip()
    return "LOW"


def _execution_trigger(execution: object) -> str:
    if execution is None:
        return "--"
    entry = getattr(execution, "entry_min", None)
    return f"{entry:.6f}" if isinstance(entry, (int, float)) else "--"


async def load_buckets(database: DatabaseManager, symbol: str) -> dict[str, list[TimeframeBucket]]:
    timeframes = ["15m", "1h", "4h"]
    async with database.session_factory() as session:
        result = await session.scalars(
            select(MarketDataBucket)
            .where(MarketDataBucket.symbol == symbol)
            .where(MarketDataBucket.timeframe.in_(timeframes))
            .order_by(MarketDataBucket.bucket_start.asc())
        )
        rows = list(result)

    grouped: dict[str, list[TimeframeBucket]] = defaultdict(list)
    for row in rows:
        grouped[row.timeframe].append(TimeframeBucket.from_record(row))
    return grouped


async def replay(symbol: str, timeframe: str, limit: int) -> int:
    settings = get_settings()
    database = DatabaseManager(settings)
    service = SignalService(settings, database, RealtimeHub())
    service.database.enabled = False

    grouped = await load_buckets(database, symbol)
    anchor = grouped.get(timeframe, [])
    if not anchor:
        print(f"No stored buckets found for {symbol} {timeframe}.")
        await database.close()
        return 1

    anchor = anchor[-limit:] if limit > 0 else anchor
    indices = {tf: 0 for tf in ["15m", "1h", "4h"]}
    first_pre_breakdown = None
    first_triggered_short = None
    pre_breakdown_count = 0

    try:
        for index, anchor_bucket in enumerate(anchor):
            anchor_timestamp = anchor_bucket.last_timestamp

            for tf in ["15m", "1h", "4h"]:
                while indices[tf] < len(grouped.get(tf, [])) and grouped[tf][indices[tf]].last_timestamp <= anchor_timestamp:
                    bucket = grouped[tf][indices[tf]]
                    service.aggregate_store.buckets[tf][symbol].append(bucket)
                    indices[tf] += 1

            await service._update_state(symbol, persist_alerts=False)
            state = service.states_by_timeframe.get(timeframe, {}).get(symbol)
            if state is None or state.market_interpretation is None:
                continue

            market_interpretation = state.market_interpretation
            state_label = market_interpretation.get("state", state.market_state)
            distribution_risk = _distribution_risk_label(market_interpretation)
            trigger = _execution_trigger(state.execution)
            price = state.price

            if "Pre-Breakdown" in state_label:
                pre_breakdown_count += 1
                if first_pre_breakdown is None:
                    first_pre_breakdown = state.timestamp
                print(
                    f"t={index:03d} | {state.timestamp.isoformat()} | {state_label} | "
                    f"risk={distribution_risk} | trigger={trigger} | price={price:.6f}"
                )

            if state.action_status == "Triggered" and state.action_bias == "Bearish":
                if first_triggered_short is None:
                    first_triggered_short = state.timestamp
                print(
                    f"t={index:03d} | {state.timestamp.isoformat()} | SHORT_TRIGGERED | "
                    f"risk={distribution_risk} | trigger={trigger} | price={price:.6f}"
                )

        total = len(anchor)
        density = (pre_breakdown_count / total) if total else 0.0
        print("")
        print(f"Replay summary for {symbol} {timeframe}")
        print(f"- anchor buckets: {total}")
        print(f"- pre_breakdown_count: {pre_breakdown_count}")
        print(f"- pre_breakdown_density: {density:.2%}")
        print(f"- first_pre_breakdown: {first_pre_breakdown.isoformat() if first_pre_breakdown else 'None'}")
        print(f"- first_triggered_short: {first_triggered_short.isoformat() if first_triggered_short else 'None'}")

        if first_pre_breakdown and first_triggered_short:
            if first_pre_breakdown < first_triggered_short:
                print("- validation: PASS (Pre-Breakdown appeared before bearish trigger)")
            elif first_pre_breakdown == first_triggered_short:
                print("- validation: BORDERLINE (Pre-Breakdown and trigger appeared on the same bucket)")
            else:
                print("- validation: FAIL (Pre-Breakdown appeared after bearish trigger)")
        elif first_pre_breakdown and not first_triggered_short:
            print("- validation: PARTIAL (Pre-Breakdown detected but no bearish trigger occurred in replay window)")
        elif not first_pre_breakdown and first_triggered_short:
            print("- validation: FAIL (Bearish trigger occurred without prior Pre-Breakdown)")
        else:
            print("- validation: NO SIGNAL (No Pre-Breakdown or bearish trigger in replay window)")

        return 0
    finally:
        await database.close()


async def main() -> int:
    args = parse_args()
    return await replay(args.symbol.upper(), args.timeframe, args.limit)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
