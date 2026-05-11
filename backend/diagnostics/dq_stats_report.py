
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from collections import Counter
from backend.services.signal_service import SignalService
from backend.config import get_settings

UTC = timezone.utc

async def generate_dq_report():
    print("=== FlowScope Data Quality Metrics Report ===")
    settings = get_settings()
    service = SignalService(settings=settings, database=None)
    
    if not service.symbols:
        print("No symbols configured.")
        return

    symbols = service.symbols
    total_symbols = len(symbols)
    
    stale_oi_count = 0
    default_taker_count = 0
    default_ls_count = 0
    coalesced_count = 0
    
    ages = {
        "price": [],
        "volume": [],
        "oi": [],
        "funding": [],
        "ratio": [],
        "liq": []
    }
    
    scores = []
    statuses = Counter()
    
    now = datetime.now(UTC)
    
    for symbol in symbols:
        state = service.state.get(symbol)
        if not state:
            continue
            
        # Stats from AssetState
        if "open_interest" in state.stale_fields: stale_oi_count += 1
        if state.taker_ratio_is_default: default_taker_count += 1
        if state.long_short_ratio_is_default: default_ls_count += 1
        if state.data_was_coalesced: coalesced_count += 1
        
        if state.price_age_seconds is not None: ages["price"].append(state.price_age_seconds)
        if state.futures_volume_age_seconds is not None: ages["volume"].append(state.futures_volume_age_seconds)
        if state.open_interest_age_seconds is not None: ages["oi"].append(state.open_interest_age_seconds)
        if state.funding_age_seconds is not None: ages["funding"].append(state.funding_age_seconds)
        if state.taker_ratio_age_seconds is not None: ages["ratio"].append(state.taker_ratio_age_seconds)
        if state.liquidation_age_seconds is not None: ages["liq"].append(state.liquidation_age_seconds)
        
        scores.append(state.data_quality_score)
        statuses[state.data_quality_status] += 1

    if not scores:
        print("No live state found for any symbol.")
        return

    print(f"\nSample Size: {len(scores)} symbols")
    print("-" * 40)
    print(f"STALE OI:        {stale_oi_count/len(scores)*100:6.1f}% ({stale_oi_count})")
    print(f"DEFAULT TAKER:   {default_taker_count/len(scores)*100:6.1f}% ({default_taker_count})")
    print(f"DEFAULT L/S:     {default_ls_count/len(scores)*100:6.1f}% ({default_ls_count})")
    print(f"COALESCED DATA:  {coalesced_count/len(scores)*100:6.1f}% ({coalesced_count})")
    print("-" * 40)
    
    print("Average / Max Age (seconds):")
    for field, vals in ages.items():
        avg = sum(vals)/len(vals) if vals else 0
        mx = max(vals) if vals else 0
        print(f"  {field.upper():10}: {avg:6.1f}s avg, {mx:6.1f}s max")
    
    print("-" * 40)
    avg_score = sum(scores)/len(scores)
    print(f"AVERAGE DQ SCORE: {avg_score:.2f}")
    print("STATUS DISTRIBUTION:")
    for status, count in statuses.items():
        print(f"  {status:15}: {count:4} ({count/len(scores)*100:5.1f}%)")

if __name__ == "__main__":
    asyncio.run(generate_dq_report())
