import asyncio
import sys
from pathlib import Path
from datetime import datetime, UTC
from dataclasses import dataclass
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.config import get_settings
from backend.services.signal_service import SignalService, AssetState
from backend.schemas import FlowMetrics
from backend.services.timeframe_aggregator import TimeframeBucket

async def test_integration_update():
    print("Running SignalService Integration Update Test...")
    settings = get_settings()
    
    # Mock DB and Collectors
    db = MagicMock()
    hub = MagicMock()
    hub.broadcast = MagicMock(side_effect=lambda x: print(f"  [Mock Hub] Broadcasted {x.type}"))
    
    service = SignalService(settings, db, hub)
    service.symbols = ["BTCUSDT"]
    
    # Mock history and aggregate store
    tf = "15m"
    service.history["BTCUSDT"] = []
    
    # Create a mock bucket
    bucket = TimeframeBucket(
        symbol="BTCUSDT",
        timeframe=tf,
        bucket_start=datetime.now(UTC),
        bucket_end=datetime.now(UTC),
        last_timestamp=datetime.now(UTC),
        open_price=50000.0,
        high_price=51000.0,
        low_price=49000.0,
        close_price=50500.0,
        open_interest_open=1000000.0,
        open_interest_high=1050000.0,
        open_interest_low=950000.0,
        open_interest_close=1000000.0,
        spot_volume_open=0.0,
        spot_volume_close=0.0,
        spot_volume_delta=40.0,
        futures_volume_open=0.0,
        futures_volume_close=0.0,
        futures_volume_delta=60.0,
        funding_rate_sum=0.0,
        funding_rate_close=0.0,
        long_short_ratio_sum=1.0,
        long_short_ratio_close=1.0,
        taker_buy_sell_ratio_sum=1.0,
        taker_buy_sell_ratio_close=1.0,
        long_liquidations_close=0.0,
        long_liquidations_total=0.0,
        short_liquidations_close=0.0,
        short_liquidations_total=0.0
    )
    
    # Mock build_flow_metrics to return our specific test case
    metrics = FlowMetrics(
        symbol="BTCUSDT",
        foundation_version_15m="v2_option_a",
        price_change_15m=0.03,
        atr_15m=0.02,
        market_pressure_15m=0.6,
        volume_z_15m=1.2,
        oi_delta_reliable_15m=True,
        oi_delta_z_15m=0.8,
        flow_alignment_15m=0.7,
        market_pressure_status_15m="VALID"
    )
    
    service.aggregate_store.build_flow_metrics = MagicMock(return_value=metrics)
    service.aggregate_store.latest_bucket = MagicMock(return_value=bucket)
    service.aggregate_store.history_for = MagicMock(return_value=[bucket])
    
    # Mock scoring methods to prevent _sync_positioning_features from zeroing out our metrics
    service.aggregate_store._z_score = MagicMock(side_effect=lambda symbol, tf, extractor, **kwargs: getattr(metrics, f"{'volume_z' if 'volume' in str(extractor) else 'oi_delta_z'}_{tf}", 0.0))
    service.aggregate_store._ema_delta = MagicMock(return_value=0.0)
    service.aggregate_store._atr = MagicMock(return_value=0.02)
    
    # Call _update_state
    print("Calling service._update_state('BTCUSDT')...")
    await service._update_state("BTCUSDT", persist_alerts=False)
    
    # Check results in metrics
    print("\nIntegration Results for BTCUSDT (15m):")
    print(f"  regime_is_structural: {getattr(metrics, f'regime_is_structural_{tf}')}")
    print(f"  regime_is_volatile:   {getattr(metrics, f'regime_is_volatile_{tf}')}")
    print(f"  regime_warning:       {getattr(metrics, f'regime_warning_{tf}')}")
    print(f"  expansion_subtype:    {getattr(metrics, f'expansion_subtype_{tf}')}")
    print(f"  expansion_health:     {getattr(metrics, f'expansion_health_score_{tf}')}")
    print(f"  expansion_warning:    {getattr(metrics, f'expansion_warning_{tf}')}")
    print(f"  compression_type:     {getattr(metrics, f'compression_type_{tf}')}")
    
    # Check AssetState
    state = service.states_by_timeframe[tf]["BTCUSDT"]
    print("\nAssetState Snapshot Results:")
    print(f"  regime_is_structural: {state.regime_is_structural}")
    print(f"  expansion_subtype:    {state.expansion_subtype}")
    print(f"  expansion_health:     {state.expansion_health_score}")
    print(f"  compression_type:     {state.compression_type}")
    
    print("\nIntegration Validation Successful.")

if __name__ == "__main__":
    asyncio.run(test_integration_update())
