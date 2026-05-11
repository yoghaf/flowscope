import asyncio
import sys
import pandas as pd
from pathlib import Path
from datetime import datetime, UTC, timedelta
from collections import Counter, defaultdict

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.config import get_settings
from backend.database import DatabaseManager
from backend.models import LatestAssetState, MarketDataBucket
from sqlalchemy import select, func

async def run_forward_monitor():
    settings = get_settings()
    db_manager = DatabaseManager(settings)
    
    # 1. Ensure artifacts directory exists
    artifacts_dir = REPO_ROOT / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    
    csv_path = artifacts_dir / "forward_shadow_observations.csv"
    summary_path = artifacts_dir / "forward_shadow_daily_summary.md"

    print("="*60)
    print("FLOWSCOPE FORWARD SHADOW MONITOR STARTUP")
    print("="*60)

    candidates = []
    v2_count = 0
    v2_symbols = 0
    latest_v2 = None

    try:
        async with db_manager.session_factory() as session:
            # Startup Debug
            print("Connecting to database...")
            
            # Check v2_option_a buckets
            v2_stmt = select(func.count()).select_from(MarketDataBucket).where(MarketDataBucket.foundation_version == "v2_option_a")
            v2_count_res = await session.execute(v2_stmt)
            v2_count = v2_count_res.scalar() or 0
            
            latest_v2_stmt = select(func.max(MarketDataBucket.last_timestamp)).where(MarketDataBucket.foundation_version == "v2_option_a")
            latest_v2_res = await session.execute(latest_v2_stmt)
            latest_v2 = latest_v2_res.scalar()
            
            v2_symbols_stmt = select(func.count(func.distinct(MarketDataBucket.symbol))).where(MarketDataBucket.foundation_version == "v2_option_a")
            v2_symbols_res = await session.execute(v2_symbols_stmt)
            v2_symbols = v2_symbols_res.scalar() or 0
            
            print(f"DB Status: Connected")
            print(f"v2_option_a Buckets: {v2_count}")
            print(f"v2_option_a Symbols: {v2_symbols}")
            print(f"Latest v2_option_a:  {latest_v2}")
            
            if v2_count > 0:
                # 2. Collect Continuation Candidates from Latest States
                print("\nPolling latest asset states for Continuation candidates...")
                
                stmt = select(LatestAssetState)
                res = await session.execute(stmt)
                snapshots = res.scalars().all()
                
                for snap in snapshots:
                    data = snap.snapshot
                    if data.get("timeframe") != "15m": continue
                    
                    # Filter for Continuation
                    setup = data.get("setup_type")
                    if setup != "Continuation": continue
                    
                    # Check foundation version from latest bucket for this symbol
                    bucket_stmt = select(MarketDataBucket.foundation_version).where(
                        MarketDataBucket.symbol == snap.symbol,
                        MarketDataBucket.timeframe == snap.timeframe
                    ).order_by(MarketDataBucket.bucket_start.desc()).limit(1)
                    b_res = await session.execute(bucket_stmt)
                    found_ver = b_res.scalar() or "unknown"
                    
                    if found_ver != "v2_option_a": continue
                    
                    # Extract fields
                    fm = data.get("flow_metrics", {})
                    mi = data.get("market_interpretation", {})
                    ef = mi.get("entry_filters", {})
                    
                    candidates.append({
                        "timestamp": data.get("timestamp"),
                        "symbol": snap.symbol,
                        "timeframe": snap.timeframe,
                        "foundation_version": found_ver,
                        "oi_delta_reliable": fm.get(f"oi_delta_z_reliable_{snap.timeframe}", False),
                        "zscore_baseline_status": fm.get(f"zscore_baseline_status_{snap.timeframe}", "NORMAL"),
                        "scenario_label": data.get("scenario_label"),
                        "scenario_disposition": data.get("scenario_disposition"),
                        "setup_type": setup,
                        "efficient_build_quality": fm.get(f"efficient_build_quality_{snap.timeframe}", "UNKNOWN"),
                        "final_entry_permission": "ALLOW" if ef.get("passed") else "BLOCK",
                        "final_structural_permission": data.get("final_structural_permission", "NOT_APPLICABLE"),
                        "structural_block_reason": data.get("structural_block_reason"),
                        "structural_warning_reason": data.get("structural_warning_reason"),
                        "structural_confidence_multiplier": data.get("structural_confidence_multiplier", 1.0),
                        "regime_is_structural": data.get("regime_is_structural", False),
                        "regime_is_volatile": data.get("regime_is_volatile", False),
                        "regime_warning": data.get("regime_warning"),
                        "expansion_subtype": data.get("expansion_subtype", "unknown_expansion"),
                        "compression_type": data.get("compression_type", "no_compression"),
                        "trap_absorption_risk": data.get("trap_absorption_risk", 0.0),
                        "taker_price_divergence": fm.get(f"taker_price_divergence_{snap.timeframe}", False)
                    })
    except Exception as e:
        print(f"\n[ERROR] Database error: {e}")

    # 3. Export CSV (Always)
    df_cols = [
        "timestamp", "symbol", "timeframe", "foundation_version", "oi_delta_reliable", 
        "zscore_baseline_status", "scenario_label", "scenario_disposition", "setup_type", 
        "efficient_build_quality", "final_entry_permission", "final_structural_permission", 
        "structural_block_reason", "structural_warning_reason", "structural_confidence_multiplier", 
        "regime_is_structural", "regime_is_volatile", "regime_warning", "expansion_subtype", 
        "compression_type", "trap_absorption_risk", "taker_price_divergence"
    ]
    
    if candidates:
        df = pd.DataFrame(candidates)
        if csv_path.exists():
            try:
                existing_df = pd.read_csv(csv_path)
                df = pd.concat([existing_df, df]).drop_duplicates(subset=["symbol", "timestamp"], keep="last")
            except:
                pass
    else:
        if csv_path.exists():
            df = pd.read_csv(csv_path)
        else:
            df = pd.DataFrame(columns=df_cols)
    
    df.to_csv(csv_path, index=False)
    print(f"Observations Processed: {len(candidates)}")
    print(f"Total Logged in CSV:  {len(df)}")
    print(f"Output CSV Path:      {csv_path.absolute()}")

    # 4. Generate Summary (Always)
    with open(summary_path, "w") as f:
        f.write("# Forward Shadow Daily Summary\n\n")
        f.write(f"**Report Generated**: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n")
        
        if len(df) == 0:
            f.write("> [!NOTE]\n")
            f.write("> No forward v2 continuation observations collected yet.\n\n")
            f.write(f"- **v2 Buckets in DB**: {v2_count}\n")
            f.write(f"- **Latest Data Timestamp**: {latest_v2 if latest_v2 else 'None'}\n")
        else:
            total_candidates = len(df)
            quality_counts = df["efficient_build_quality"].value_counts()
            baseline_allow = len(df[df["final_entry_permission"] == "ALLOW"])
            
            # Conflict Matrix
            allow_struct_allow = len(df[(df["final_entry_permission"] == "ALLOW") & (df["final_structural_permission"] == "STRUCTURAL_ALLOW")])
            allow_struct_block = len(df[(df["final_entry_permission"] == "ALLOW") & (df["final_structural_permission"] == "STRUCTURAL_BLOCK")])
            allow_struct_watch = len(df[(df["final_entry_permission"] == "ALLOW") & (df["final_structural_permission"] == "STRUCTURAL_WATCHLIST")])
            allow_struct_pen   = len(df[(df["final_entry_permission"] == "ALLOW") & (df["final_structural_permission"] == "STRUCTURAL_PENALTY")])
            
            top_block_reasons = df[df["final_structural_permission"] == "STRUCTURAL_BLOCK"]["structural_block_reason"].value_counts()
            top_warn_reasons = df["structural_warning_reason"].value_counts()
            foundation_counts = df["foundation_version"].value_counts()
            oi_reliable_counts = df["oi_delta_reliable"].value_counts()
            zscore_counts = df["zscore_baseline_status"].value_counts()

            f.write("## Volume Metrics\n")
            f.write(f"- **Total Continuation Candidates**: {total_candidates}\n")
            f.write(f"- **Baseline Allowed Count**: {baseline_allow}\n\n")
            
            f.write("## Structural Shadow Conflict Matrix\n")
            f.write("| Combination | Count | Description |\n")
            f.write("| :--- | :--- | :--- |\n")
            f.write(f"| Baseline ALLOW + STRUCTURAL_ALLOW | {allow_struct_allow} | High Confidence Signals |\n")
            f.write(f"| Baseline ALLOW + STRUCTURAL_BLOCK | {allow_struct_block} | **Filtered by V3 (The Delta)** |\n")
            f.write(f"| Baseline ALLOW + STRUCTURAL_WATCHLIST | {allow_struct_watch} | Confidence Friction |\n")
            f.write(f"| Baseline ALLOW + STRUCTURAL_PENALTY | {allow_struct_pen} | Confidence Friction |\n\n")
            
            f.write("## Quality & Reason Breakdown\n")
            f.write("### Efficient Build Quality\n")
            f.write(quality_counts.to_markdown() + "\n\n")
            
            f.write("### Top Structural Block Reasons\n")
            f.write(top_block_reasons.to_markdown() if not top_block_reasons.empty else "No structural blocks yet.")
            f.write("\n\n")
            
            f.write("### Top Structural Warnings\n")
            f.write(top_warn_reasons.to_markdown() if not top_warn_reasons.empty else "No structural warnings yet.")
            f.write("\n\n")
            
            f.write("## Data Integrity Breakdown\n")
            f.write(f"- **Foundation Versions**: {foundation_counts.to_dict()}\n")
            f.write(f"- **OI Reliability**: {oi_reliable_counts.to_dict()}\n")
            f.write(f"- **Z-Score Status**: {zscore_counts.to_dict()}\n")

    print(f"Summary generated at: {summary_path.absolute()}")
    
    # Verify file existence before claiming success
    if csv_path.exists() and summary_path.exists():
        print("\n[SUCCESS] All monitor artifacts written to disk.")
    else:
        print("\n[WARNING] One or more artifacts failed to persist.")

if __name__ == "__main__":
    asyncio.run(run_forward_monitor())
