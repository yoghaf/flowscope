import asyncio
import logging
import pytest
from datetime import datetime, timedelta, timezone
from backend.services.signal_service import SignalService
from backend.engines.flow_engine import HistoryPoint
from sqlalchemy import text
from backend.config import get_settings
from backend.database import DatabaseManager
from collections import deque

UTC = timezone.utc

@pytest.mark.skip(reason="Environment-dependent integration test")
async def test_ingestion_batch() -> None:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    db = DatabaseManager(settings)
    await db.init()
    
    service = SignalService(settings, db)
    symbol = "BTCUSDT"
    base_now = datetime.now(UTC).replace(second=0, microsecond=0)
    
    # Generate batch for 15m (10), 1h (5), 4h (2)
    # Total lookback: 2*4h = 8h.
    # We'll simulate 500 minutes of data to cover enough 4h boundaries
    print("Generating batch simulation (500 minutes)...")
    
    for i in range(500): 
        now = base_now - timedelta(minutes=500-i)
        
        # 1. Simulate OI History
        oi_history = deque(maxlen=100)
        # Snapshots every minute for alignment
        for j in range(100):
            ts = now - timedelta(minutes=j)
            oi_history.append((ts + timedelta(seconds=2), 1000.0 + j * 5))
        
        service.collectors[0]._oi_history[symbol] = oi_history
        
        point = HistoryPoint(
            timestamp=now,
            price=60000.0 + i * 1, # Slow trend
            volume=100.0,
            open_interest=1500.0,
            funding_rate=0.0001,
            long_short_ratio=1.5,
            taker_buy_sell_ratio=1.1,
            spot_volume=40.0,
            futures_volume=60.0,
            long_liquidations=0.0,
            short_liquidations=0.0,
            exchange_count=1
        )
        
        # Ingest
        service.aggregate_store.ingest(symbol, point, service.collectors[0]._oi_history)
        
    # Manual save of all buckets in store to DB
    async with db.session_factory() as session:
        from backend.models import MarketDataBucket
        for timeframe in ["15m", "1h", "4h"]:
            if timeframe not in service.aggregate_store.buckets or symbol not in service.aggregate_store.buckets[timeframe]:
                continue
            history = service.aggregate_store.buckets[timeframe][symbol]
            for bucket in history:
                # In this simulation, we want to ensure buckets are 'complete'
                if bucket.bucket_end <= base_now:
                    bucket.last_timestamp = bucket.bucket_end
                record = bucket.to_record()
                record["foundation_version"] = "v2_option_a"
                
                # Check if exists to avoid PK conflict
                stmt = text("SELECT 1 FROM market_data_buckets WHERE symbol=:s AND timeframe=:tf AND bucket_start=:bs")
                res = await session.execute(stmt, {"s": symbol, "tf": timeframe, "bs": bucket.bucket_start})
                if not res.scalar():
                    db_bucket = MarketDataBucket(**record)
                    session.add(db_bucket)
                    print(f"Added {timeframe} bucket starting at {bucket.bucket_start}")
        
        await session.commit()
        print("Batch simulation buckets saved.")
        
        # Now simulate FlowMetrics for the report
        from backend.models import LatestAssetState
        metrics = service.aggregate_store.build_flow_metrics(symbol)
        
        # Use ORM to handle JSON serialization properly
        state = LatestAssetState(
            symbol=symbol,
            timeframe="ALL",
            snapshot=metrics.model_dump(mode="json"),
            updated_at=base_now
        )
        await session.merge(state)
        await session.commit()
        print("FlowMetrics snapshot saved via ORM.")

if __name__ == "__main__":
    asyncio.run(test_ingestion_batch())
