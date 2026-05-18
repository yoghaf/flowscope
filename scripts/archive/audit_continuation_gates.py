from __future__ import annotations

import asyncio
import csv
import logging
import sys
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqlalchemy import select

from backend.config import get_settings, TIMEFRAME_PROFILES
from backend.database import DatabaseManager
from backend.models import MarketDataBucket
from backend.services.signal_service import SignalService, AssetState
from backend.services.realtime import RealtimeHub
from backend.services.timeframe_aggregator import TimeframeBucket, TIMEFRAME_ORDER, TIMEFRAME_DELTAS

# Logging setup
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger("ContinuationAudit")

@dataclass
class AuditResult:
    mode: str
    total_candidates: int = 0
    allowed_count: int = 0
    blocked_by: Counter = field(default_factory=Counter)
    semantic_states: Counter = field(default_factory=Counter)
    hypothetical_allowed: int = 0
    unlocked_by_scenario: Counter = field(default_factory=Counter)
    unlocked_by_semantic: Counter = field(default_factory=Counter)
    risky_unlocked: Counter = field(default_factory=Counter)

@dataclass
class AuditCandidate:
    symbol: str
    timestamp: datetime
    foundation_version: str
    setup_type: str
    bias: str
    scenario_label: str
    scenario_disposition: str
    oi_alignment: str
    oi_reliable: bool
    oi_build_type: str
    effort_result_state: str
    absorption_candidate: bool
    climax_candidate: bool
    crowding_status: str
    reasons: list[str]
    efficient_build_quality: str | None = None
    efficient_build_quality_reason: str | None = None
    final_entry_permission: bool = False
    
    # Modes results
    mode_a_allowed: bool = False
    mode_a_reasons: list[str] = field(default_factory=list)
    mode_c_unlocked: bool = False
    mode_c_risks: list[str] = field(default_factory=list)

SEMANTIC_GATES = {
    "semantic_absorption_block",
    "semantic_climax_continuation_block",
    "semantic_crowded_late_continuation_block"
}

async def run_audit():
    print(f"Script started at {datetime.now().isoformat()}", flush=True)
    settings = get_settings()
    db = DatabaseManager(settings)
    hub = RealtimeHub()
    service = SignalService(settings, db, hub)
    
    csv_out = REPO_ROOT / "continuation_audit_full_v3.csv"
    print(f"Input mode: Existing market data buckets in DB", flush=True)
    print(f"Output CSV path: {csv_out}", flush=True)
    
    mode_a = AuditResult("STRICT")
    mode_b = AuditResult("LEGACY_DIAGNOSTIC")
    mode_c = AuditResult("SHADOW_RELAXED")
    
    candidates = []
    
    async with db.session_factory() as session:
        # Get symbols with buckets
        symbols_res = await session.execute(select(MarketDataBucket.symbol).distinct())
        symbols = [r[0] for r in symbols_res.fetchall()]
        total_symbols = len(symbols)
        print(f"Total symbols found: {total_symbols}", flush=True)
        
        for idx, symbol in enumerate(symbols):
            if (idx + 1) % 10 == 0 or idx == 0:
                print(f"[progress] processing symbol {idx+1}/{total_symbols}: {symbol}", flush=True)
                
            res = await session.execute(
                select(MarketDataBucket)
                .where(MarketDataBucket.symbol == symbol)
                .order_by(MarketDataBucket.bucket_start.asc())
            )
            buckets = res.scalars().all()
            
            service.aggregate_store.buckets = {tf: defaultdict(deque) for tf in TIMEFRAME_ORDER}
            profile = TIMEFRAME_PROFILES["15m"]
            
            for b_idx, b_model in enumerate(buckets):
                bucket = TimeframeBucket.from_record(b_model)
                service.aggregate_store.buckets[bucket.timeframe][symbol].append(bucket)
                
                if bucket.timeframe != "15m" or b_idx < 30:
                    continue
                    
                flow_metrics = service.aggregate_store.build_flow_metrics(symbol)
                state_assessment = service.state_engine.evaluate(
                    bucket=bucket, metrics=flow_metrics, timeframe="15m", 
                    history=list(service.aggregate_store.buckets["15m"][symbol])
                )
                
                # We simulate signal detection logic here
                interpretation = service.market_interpreter.evaluate(
                    bucket=bucket, metrics=flow_metrics, timeframe="15m",
                    history=list(service.aggregate_store.buckets["15m"][symbol]),
                    positioning=service.positioning_engine.evaluate(
                        bucket=bucket, metrics=flow_metrics, timeframe="15m",
                        history=list(service.aggregate_store.buckets["15m"][symbol]),
                        state=state_assessment
                    ),
                    state_assessment=state_assessment
                )
                
                action = service.execution_engine.build_action(symbol, "15m", bucket, interpretation)
                
                if not action or action.setup_type != "Continuation":
                    continue
                    
                # Identified a Continuation Candidate
                phase = service.phase_engine.detect(flow_metrics)
                scenario = service.context_bridge.assess(
                    flow_metrics=flow_metrics, timeframe="15m", state=state_assessment, 
                    action=action, market_interpretation=interpretation, phase=phase
                )
                
                # Quality Logic
                quality, q_reason, q_score = service._calculate_efficient_build_quality(
                    scenario_label=scenario.label, flow_metrics=flow_metrics, timeframe="15m"
                )
                setattr(flow_metrics, "efficient_build_quality_15m", quality)
                setattr(flow_metrics, "efficient_build_quality_reason_15m", q_reason)
                
                # Production Block Reasons
                prod_reasons = service._entry_hard_filter_reasons(
                    action=action, flow_metrics=flow_metrics, timeframe="15m",
                    clarity_confidence=interpretation.clarity_confidence,
                    market_interpretation=interpretation, scenario_label=scenario.label,
                    scenario_score=scenario.score, scenario_disposition=scenario.disposition,
                    state_name=state_assessment.state
                )
                
                foundation_version = getattr(flow_metrics, "foundation_version_15m", "unknown")
                oi_alignment = getattr(b_model, "oi_alignment_status", "MISSING")
                oi_reliable = getattr(flow_metrics, "oi_delta_reliable_15m", False)
                oi_build = getattr(flow_metrics, "oi_build_type_15m", "unknown")
                
                cand = AuditCandidate(
                    symbol=symbol, timestamp=bucket.last_timestamp,
                    foundation_version=foundation_version, setup_type="Continuation",
                    bias=action.bias, scenario_label=scenario.label,
                    scenario_disposition=scenario.disposition, oi_alignment=oi_alignment,
                    oi_reliable=oi_reliable, oi_build_type=oi_build,
                    effort_result_state=getattr(flow_metrics, "effort_result_state_15m", "Neutral"),
                    absorption_candidate=getattr(flow_metrics, "absorption_candidate_15m", False),
                    climax_candidate=getattr(flow_metrics, "climax_candidate_15m", False),
                    crowding_status=getattr(flow_metrics, "crowding_status_15m", "neutral"),
                    efficient_build_quality=quality,
                    efficient_build_quality_reason=q_reason,
                    final_entry_permission=not bool(prod_reasons),
                    reasons=prod_reasons
                )
                
                # Mode A Logic
                mode_a.total_candidates += 1
                mode_a_reasons = []
                if foundation_version != "v2_option_a": mode_a_reasons.append("foundation_version_not_trusted")
                if oi_alignment != "ALIGNED": mode_a_reasons.append("oi_delta_unreliable")
                if scenario.disposition != "allow": mode_a_reasons.append(scenario.label + "_blocked")
                for r in prod_reasons:
                    if r in SEMANTIC_GATES: mode_a_reasons.append(r)
                mode_a_reasons = list(set(mode_a_reasons))
                cand.mode_a_reasons = mode_a_reasons
                if not mode_a_reasons: mode_a.allowed_count += 1
                else:
                    for r in mode_a_reasons: mode_a.blocked_by[r] += 1
                
                # Mode C Logic
                mode_c.total_candidates += 1
                mode_c_risks = []
                for r in prod_reasons:
                    if r in SEMANTIC_GATES: mode_c_risks.append(r)
                if scenario.disposition != "allow": mode_c_risks.append(scenario.label + "_blocked")
                
                cand.mode_c_risks = mode_c_risks
                if not mode_c_risks:
                    mode_c.allowed_count += 1
                    cand.mode_c_unlocked = True
                
                candidates.append(cand)
                if len(candidates) % 100 == 0:
                    print(f"[progress] processed {len(candidates)} continuation candidates", flush=True)

    print(f"\nWriting output to {csv_out.name}...", flush=True)
    with open(csv_out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "symbol", "timestamp", "foundation", "scenario", "oi_align", "oi_build", 
            "mode_a_allowed", "mode_a_reasons", "mode_c_unlocked", "mode_c_risks",
            "eb_quality", "eb_reason", "final_permission"
        ])
        for c in candidates:
            writer.writerow([
                c.symbol, c.timestamp.isoformat(), c.foundation_version, c.scenario_label,
                c.oi_alignment, c.oi_build_type, str(c.mode_a_allowed),
                "|".join(c.mode_a_reasons), str(c.mode_c_unlocked), "|".join(c.mode_c_risks),
                c.efficient_build_quality, c.efficient_build_quality_reason,
                str(c.final_entry_permission)
            ])
    
    print(f"{csv_out.name} written.", flush=True)
    print(f"Total rows: {len(candidates)}", flush=True)
    print(f"eb_quality column included: True", flush=True)
    print(f"eb_reason column included: True", flush=True)
    
    print("\n" + "="*50, flush=True)
    print("FINAL AUDIT SUMMARY", flush=True)
    print("="*50, flush=True)
    print(f"Total Continuation Candidates: {len(candidates)}", flush=True)
    print(f"Shadow Relaxed Unlocked (Mode C): {mode_c.allowed_count}", flush=True)
    
    eb_count = sum(1 for c in candidates if c.scenario_label == "efficient_build")
    print(f"Efficient Build Scenarios: {eb_count}", flush=True)
    
    q_counts = Counter(c.efficient_build_quality for c in candidates if c.scenario_label == "efficient_build")
    print("\nEfficient Build Quality Breakdown:", flush=True)
    for q, count in q_counts.items():
        print(f"  {q:<16}: {count}", flush=True)
    
    final_allowed = sum(1 for c in candidates if c.final_entry_permission)
    print(f"\nFINAL ALLOWED (Production Hard Gates): {final_allowed}", flush=True)
    print("="*50, flush=True)

if __name__ == "__main__":
    asyncio.run(run_audit())
