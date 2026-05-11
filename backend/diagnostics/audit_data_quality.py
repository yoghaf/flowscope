
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from backend.services.signal_service import SignalService
from backend.config import get_settings

UTC = timezone.utc

async def audit_data_quality():
    print("=== FlowScope Data Quality Audit ===")
    settings = get_settings()
    service = SignalService(settings=settings, database=None)
    collector = BinanceCollector(settings=settings)
    
    # Check if we have any data
    if not service.symbols:
        print("No symbols configured.")
        return

    print(f"Auditing {len(service.symbols)} symbols...")
    
    # We'll trigger an update to see the DQ scores
    for symbol in service.symbols[:5]:
        print(f"\nSymbol: {symbol}")
        # Try to get latest snapshot
        snapshots = service.get_latest_snapshots([symbol])
        if not snapshots:
            print("  No snapshots available.")
            continue
            
        for snap in snapshots:
            print(f"  Timeframe: {snap.timeframe}")
            print(f"  DQ Score: {snap.data_quality_score:.2f} ({snap.data_quality_status})")
            print(f"  Stale Fields: {snap.stale_fields}")
            print(f"  Missing Fields: {snap.missing_fields}")
            print(f"  Fallback Fields: {snap.fallback_fields}")
            print(f"  Sources:")
            print(f"    Price: {snap.price_source} ({snap.price_age_seconds:.1f}s age)")
            print(f"    Volume: {snap.volume_source} ({snap.futures_volume_age_seconds:.1f}s age)")
            print(f"    OI: {snap.open_interest_source} ({snap.open_interest_age_seconds:.1f}s age)")
            print(f"  Bucket Status: {'Closed' if snap.bucket_is_closed else 'Open'} ({snap.bucket_completion_pct*100:.1f}%)")
            if snap.liquidation_is_reset_suspected:
                print("  WARNING: Liquidation reset suspected!")
            if snap.data_was_coalesced:
                print("  NOTICE: Data was coalesced (carried forward).")

if __name__ == "__main__":
    asyncio.run(audit_data_quality())
