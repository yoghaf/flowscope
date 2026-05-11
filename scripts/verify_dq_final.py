import asyncio, json
from collections import Counter
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

url = "postgresql+asyncpg://postgres:Yoga12345@localhost:5432/flowscope_db"

async def main():
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        res = await conn.execute(text("""
            SELECT symbol, updated_at, snapshot
            FROM latest_asset_states
            WHERE timeframe='15m'
            ORDER BY updated_at DESC
        """))
        rows = res.fetchall()

    v2 = 0
    funding_age_missing = 0
    liq_age_missing = 0
    funding_sources = Counter()
    liq_sources = Counter()
    
    # Track ages per source
    funding_ages_by_src = {}
    liq_ages_by_src = {}

    for symbol, ts, snap in rows:
        if isinstance(snap, str):
            snap = json.loads(snap)
        fm = snap.get("flow_metrics") or {}

        if fm.get("foundation_version_15m") != "v2_option_a":
            continue

        v2 += 1

        fa = fm.get("funding_age_seconds_15m")
        la = fm.get("liquidation_age_seconds_15m")
        fs = fm.get("funding_source_15m")
        ls = fm.get("liquidation_source_15m")

        funding_sources[str(fs)] += 1
        liq_sources[str(ls)] += 1
        
        if fs in ("missing", "MISSING_TIMESTAMP"):
            if v2 < 10:
                print(f"DEBUG {symbol}: fs={fs}, fa={fa}, upd={fm.get('funding_age_seconds_15m')}")

        if isinstance(fa, (int, float)):
            if fs not in funding_ages_by_src: funding_ages_by_src[fs] = []
            funding_ages_by_src[fs].append(fa)
        else:
            funding_age_missing += 1

        if isinstance(la, (int, float)):
            if ls not in liq_ages_by_src: liq_ages_by_src[ls] = []
            liq_ages_by_src[ls].append(la)
        else:
            liq_age_missing += 1

    print("v2 states:", v2)
    print("funding_age missing:", funding_age_missing, "/", v2)
    print("liquidation_age missing:", liq_age_missing, "/", v2)

    print("\nfunding sources breakdown:")
    for src, count in sorted(funding_sources.items()):
        ages = funding_ages_by_src.get(src, [])
        avg = sum(ages)/len(ages) if ages else 0
        mx = max(ages) if ages else 0
        print(f"  {src:25}: {count:3} | avg={avg:8.4f}s | max={mx:8.4f}s")

    print("\nliquidation sources breakdown:")
    for src, count in sorted(liq_sources.items()):
        ages = liq_ages_by_src.get(src, [])
        avg = sum(ages)/len(ages) if ages else 0
        mx = max(ages) if ages else 0
        print(f"  {src:25}: {count:3} | avg={avg:8.4f}s | max={mx:8.4f}s")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
