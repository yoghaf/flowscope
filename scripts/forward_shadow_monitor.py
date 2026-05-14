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

ACTIVE_STATE_WINDOW_MINUTES = 10

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
    active_states_scanned = 0
    stale_states_ignored = 0

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

                active_cutoff = datetime.now(UTC) - timedelta(minutes=ACTIVE_STATE_WINDOW_MINUTES)
                foundation_expr = LatestAssetState.snapshot["flow_metrics"]["foundation_version_15m"].as_string()

                base_stmt = select(LatestAssetState).where(
                    LatestAssetState.timeframe == "15m",
                    foundation_expr == "v2_option_a",
                )
                base_count_res = await session.execute(
                    select(func.count()).select_from(base_stmt.subquery())
                )
                eligible_state_count = base_count_res.scalar() or 0

                stmt = base_stmt.where(LatestAssetState.updated_at > active_cutoff)
                res = await session.execute(stmt)
                snapshots = res.scalars().all()
                active_states_scanned = len(snapshots)
                stale_states_ignored = max(eligible_state_count - active_states_scanned, 0)
                
                for snap in snapshots:
                    data = snap.snapshot
                    if data.get("timeframe") != "15m": continue

                    fm = data.get("flow_metrics", {})
                    found_ver = fm.get(f"foundation_version_{snap.timeframe}", "unknown")
                    if found_ver != "v2_option_a": continue
                    
                    # Filter for Continuation
                    setup = data.get("setup_type")
                    if setup != "Continuation": continue
                    
                    # Extract fields
                    mi = data.get("market_interpretation", {})
                    ef = mi.get("entry_filters", {})
                    scenario_obj = data.get("scenario", {})
                    
                    # Robust extraction for scenario
                    scenario_label = data.get("scenario_label") or scenario_obj.get("label")
                    scenario_disposition = data.get("scenario_disposition") or scenario_obj.get("disposition")
                    scenario_reasons_raw = data.get("scenario_reasons") or scenario_obj.get("reasons", [])
                    
                    risk_notes = mi.get("risk_notes", [])
                    warnings = mi.get("warnings", [])
                    ef_reasons = data.get("hard_filter_reasons") or ef.get("reasons", [])
                    
                    # Efficient Build Quality & Reasons
                    ebq = data.get("efficient_build_quality") or fm.get(f"efficient_build_quality_{snap.timeframe}", "UNKNOWN")
                    ebqr = data.get("efficient_build_quality_reason") or fm.get(f"efficient_build_quality_reason_{snap.timeframe}")
                    
                    final_ep = data.get("final_entry_permission") or ("ALLOW" if ef.get("passed", True) else "BLOCK")
                    
                    candidates.append({
                        "timestamp": data.get("timestamp"),
                        "symbol": snap.symbol,
                        "timeframe": snap.timeframe,
                        "foundation_version": found_ver,
                        "data_quality_status": fm.get(f"data_quality_status_{snap.timeframe}"),
                        "oi_delta_reliable": fm.get(f"oi_delta_reliable_{snap.timeframe}", False),
                        "zscore_baseline_status": fm.get(f"zscore_baseline_status_{snap.timeframe}", "NORMAL"),
                        "scenario_label": scenario_label,
                        "scenario_disposition": scenario_disposition,
                        "setup_type": setup,
                        "efficient_build_quality": ebq,
                        "efficient_build_quality_reason": ebqr,
                        "scenario_reasons": "|".join(scenario_reasons_raw) if isinstance(scenario_reasons_raw, list) else str(scenario_reasons_raw),
                        "mode_c_risks": "|".join(risk_notes) if isinstance(risk_notes, list) else str(risk_notes),
                        "mode_a_reasons": "|".join(warnings) if isinstance(warnings, list) else str(warnings),
                        "block_reasons": "|".join(ef_reasons) if isinstance(ef_reasons, list) else str(ef_reasons),
                        "hard_filter_reasons": "|".join(ef_reasons) if isinstance(ef_reasons, list) else str(ef_reasons),
                        "crowding_status": fm.get(f"crowding_status_{snap.timeframe}"),
                        "crowding_side": fm.get(f"crowding_side_{snap.timeframe}"),
                        "taker_price_divergence": fm.get(f"taker_price_divergence_{snap.timeframe}", False),
                        "absorption_candidate": fm.get(f"absorption_candidate_{snap.timeframe}", False),
                        "climax_candidate": fm.get(f"climax_candidate_{snap.timeframe}", False),
                        "regime_warning": data.get("regime_warning") or fm.get(f"regime_warning_{snap.timeframe}"),
                        "expansion_subtype": data.get("expansion_subtype") or fm.get(f"expansion_subtype_{snap.timeframe}"),
                        "compression_type": data.get("compression_type") or fm.get(f"compression_type_{snap.timeframe}"),
                        "final_entry_permission": final_ep,
                        "final_structural_permission": data.get("final_structural_permission", "NOT_APPLICABLE"),
                        "structural_block_reason": data.get("structural_block_reason"),
                        "structural_warning_reason": data.get("structural_warning_reason"),
                        "structural_confidence_multiplier": data.get("structural_confidence_multiplier", 1.0),
                        "bucket_is_closed": data.get("bucket_is_closed", False),
                        "bucket_completion_pct": data.get("bucket_completion_pct", 0.0),
                        "volume_z_reliable": fm.get(f"volume_z_reliable_{snap.timeframe}", True),
                        "oi_delta_z_reliable": fm.get(f"oi_delta_z_reliable_{snap.timeframe}", True)
                    })
    except Exception as e:
        print(f"\n[ERROR] Database error: {e}")

    # 3. Export CSV (Always)
    df_cols = [
        "timestamp", "symbol", "timeframe", "foundation_version", "data_quality_status", "oi_delta_reliable", 
        "zscore_baseline_status", "scenario_label", "scenario_disposition", "setup_type", 
        "efficient_build_quality", "efficient_build_quality_reason", "scenario_reasons",
        "mode_c_risks", "mode_a_reasons", "block_reasons", "hard_filter_reasons",
        "crowding_status", "crowding_side", "taker_price_divergence", "absorption_candidate",
        "climax_candidate", "regime_warning", "expansion_subtype", "compression_type",
        "final_entry_permission", "final_structural_permission", 
        "structural_block_reason", "structural_warning_reason", "structural_confidence_multiplier", 
        "bucket_is_closed", "bucket_completion_pct", "volume_z_reliable", "oi_delta_z_reliable"
    ]
    
    if candidates:
        df = pd.DataFrame(candidates)
        if csv_path.exists():
            try:
                existing_df = pd.read_csv(csv_path)
                # Align columns
                for col in df_cols:
                    if col not in existing_df.columns:
                        existing_df[col] = None
                df = pd.concat([existing_df, df]).drop_duplicates(subset=["symbol", "timestamp"], keep="last")
            except:
                pass
    else:
        if csv_path.exists():
            try:
                df = pd.read_csv(csv_path)
                # Align columns
                for col in df_cols:
                    if col not in df.columns:
                        df[col] = None
            except:
                df = pd.DataFrame(columns=df_cols)
        else:
            df = pd.DataFrame(columns=df_cols)
    
    # Sort columns to match df_cols
    df = df[df_cols]
    df.to_csv(csv_path, index=False)
    
    current_count = len(candidates)
    total_logged = len(df)
    
    print(f"Current Run Observations: {current_count}")
    print(f"Total Logged Observations: {total_logged}")
    print(f"Active States Scanned: {active_states_scanned}")
    print(f"Stale States Ignored: {stale_states_ignored}")
    print(f"Output CSV Path:      {csv_path.absolute()}")

    # 4. Generate Summary (Always)
    with open(summary_path, "w") as f:
        f.write("# Forward Shadow Daily Summary\n\n")
        f.write(f"**Report Generated**: {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')} UTC\n\n")
        
        f.write("> [!IMPORTANT]\n")
        f.write("> **Monitor Scope Notice**:\n")
        f.write("> - This monitor reads `latest_asset_states` only (the current live state of the market).\n")
        f.write("> - It is NOT a historical replay engine and does not represent a backtest.\n")
        f.write("> - Zero current observations simply means no symbols are currently in a Continuation setup; it does NOT mean the pipeline is failing.\n\n")

        f.write("## 0. Pipeline Status & Metadata\n")
        f.write(f"- **v2 Buckets in DB**: {v2_count}\n")
        f.write(f"- **v2 Symbols Tracked**: {v2_symbols}\n")
        f.write(f"- **Latest Data Timestamp**: {latest_v2 if latest_v2 else 'None'}\n")
        f.write(f"- **Active State Window**: {ACTIVE_STATE_WINDOW_MINUTES} minutes\n")
        f.write(f"- **Active States Scanned**: {active_states_scanned}\n")
        f.write(f"- **Stale States Ignored**: {stale_states_ignored}\n")
        f.write(f"- **Current Run Observations**: {current_count}\n")
        f.write(f"- **Total Logged Observations**: {total_logged}\n\n")

        if total_logged == 0:
            f.write("> [!NOTE]\n")
            f.write("> No forward v2 continuation observations collected yet.\n\n")
        else:
            total_candidates = total_logged
            quality_counts = df["efficient_build_quality"].value_counts()
            quality_reason_counts = df["efficient_build_quality_reason"].value_counts()
            scenario_counts = df["scenario_label"].value_counts()
            disposition_counts = df["scenario_disposition"].value_counts()
            
            baseline_allow = len(df[df["final_entry_permission"] == "ALLOW"])
            baseline_block = len(df[df["final_entry_permission"] == "BLOCK"])
            
            # Conflict Matrix
            allow_struct_allow = len(df[(df["final_entry_permission"] == "ALLOW") & (df["final_structural_permission"] == "STRUCTURAL_ALLOW")])
            allow_struct_block = len(df[(df["final_entry_permission"] == "ALLOW") & (df["final_structural_permission"] == "STRUCTURAL_BLOCK")])
            allow_struct_watch = len(df[(df["final_entry_permission"] == "ALLOW") & (df["final_structural_permission"] == "STRUCTURAL_WATCHLIST")])
            allow_struct_pen   = len(df[(df["final_entry_permission"] == "ALLOW") & (df["final_structural_permission"] == "STRUCTURAL_PENALTY")])
            
            top_block_reasons = df[df["final_structural_permission"] == "STRUCTURAL_BLOCK"]["structural_block_reason"].value_counts()
            top_hard_filters = df[df["final_entry_permission"] == "BLOCK"]["hard_filter_reasons"].fillna("").astype(str).str.split("|").explode().value_counts()
            
            foundation_counts = df["foundation_version"].value_counts()
            oi_reliable_counts = df["oi_delta_reliable"].value_counts()
            zscore_counts = df["zscore_baseline_status"].value_counts()
            crowding_counts = df["crowding_status"].value_counts()
            regime_warn_counts = df["regime_warning"].value_counts()
            expansion_counts = df["expansion_subtype"].value_counts()
            compression_counts = df["compression_type"].value_counts()

            f.write("## 1. Candidate Volume & Disposition\n")
            f.write(f"- **Total Continuation Candidates**: {total_candidates}\n")
            f.write(f"- **Baseline ALLOW**: {baseline_allow}\n")
            f.write(f"- **Baseline BLOCK**: {baseline_block}\n\n")
            
            f.write("## 2. Efficient Build Quality Distribution\n")
            f.write(quality_counts.to_markdown() + "\n\n")
            
            f.write("## 3. WAIT Reason Breakdown (Quality)\n")
            f.write(quality_reason_counts.to_markdown() if not quality_reason_counts.empty else "No reasons logged yet.")
            f.write("\n\n")
            
            f.write("## 4. Scenario Label Distribution\n")
            f.write(scenario_counts.to_markdown() + "\n\n")
            
            f.write("## 5. Scenario Disposition Breakdown\n")
            f.write(disposition_counts.to_markdown() + "\n\n")
            
            f.write("## 6. Structural Shadow Conflict Matrix\n")
            f.write("| Combination | Count | Description |\n")
            f.write("| :--- | :--- | :--- |\n")
            f.write(f"| Baseline ALLOW + STRUCTURAL_ALLOW | {allow_struct_allow} | High Confidence Signals |\n")
            f.write(f"| Baseline ALLOW + STRUCTURAL_BLOCK | {allow_struct_block} | **Filtered by V3 (The Delta)** |\n")
            f.write(f"| Baseline ALLOW + STRUCTURAL_WATCHLIST | {allow_struct_watch} | Confidence Friction |\n")
            f.write(f"| Baseline ALLOW + STRUCTURAL_PENALTY | {allow_struct_pen} | Confidence Friction |\n\n")
            
            f.write("## 7. Top Baseline Block Reasons (Hard Filters)\n")
            f.write(top_hard_filters.to_markdown() if not top_hard_filters.empty else "No hard blocks yet.")
            f.write("\n\n")
            
            f.write("## 8. Top Structural Block Reasons\n")
            f.write(top_block_reasons.to_markdown() if not top_block_reasons.empty else "No structural blocks yet.")
            f.write("\n\n")
            
            f.write("## 9. Data Integrity Metrics\n")
            f.write(f"- **Foundation Versions**: {foundation_counts.to_dict()}\n")
            f.write(f"- **OI Reliability**: {oi_reliable_counts.to_dict()}\n")
            f.write(f"- **Z-Score Status**: {zscore_counts.to_dict()}\n\n")
            
            f.write("## 10. Crowding & Sentiment Status\n")
            f.write(crowding_counts.to_markdown() + "\n\n")
            
            f.write("## 11. Regime & Expansion Diagnostics\n")
            f.write("### Expansion Subtypes\n")
            f.write(expansion_counts.to_markdown() + "\n\n")
            f.write("### Regime Warnings\n")
            f.write(regime_warn_counts.to_markdown() if not regime_warn_counts.empty else "No regime warnings.")
            f.write("\n\n")
            
            f.write("## 12. Compression Status\n")
            f.write(compression_counts.to_markdown() + "\n")


    print(f"Summary generated at: {summary_path.absolute()}")
    
    # Verify file existence before claiming success
    if csv_path.exists() and summary_path.exists():
        print("\n[SUCCESS] All monitor artifacts written to disk.")
    else:
        print("\n[WARNING] One or more artifacts failed to persist.")

if __name__ == "__main__":
    asyncio.run(run_forward_monitor())
