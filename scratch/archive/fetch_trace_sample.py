
import asyncio
import json
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from backend.models import TradeSignal

DATABASE_URL = "postgresql+asyncpg://postgres:Yoga12345@localhost:5432/flowscope_db"

async def get_latest_signal():
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Get the latest closed trade or signal to have complete data
        result = await session.execute(
            select(TradeSignal).order_by(desc(TradeSignal.timestamp)).limit(1)
        )
        signal = result.scalar_one_or_none()
        
        if signal:
            data = {
                "id": signal.id,
                "symbol": signal.symbol,
                "timeframe": signal.timeframe,
                "timestamp": signal.timestamp.isoformat(),
                "state": signal.state,
                "bias": signal.bias,
                "setup_type": signal.setup_type,
                "confidence": signal.confidence,
                "entry_price": signal.entry_price,
            }
            # Extract specific metrics for the trace
            features = signal.entry_features or {}
            mi = features.get("market_interpretation", {})
            data["trace_metrics"] = {
                "price": signal.entry_price,
                "volume_zscore": features.get("volume_z_4h"),
                "oi_delta_z": features.get("oi_delta_z_4h"),
                "regime": features.get("market_regime"),
                "setup_type": signal.setup_type,
                "confidence": signal.confidence,
                "trap_risk": mi.get("trap_risk") or features.get("trap_risk"),
                "conflict_score": mi.get("conflict_score") or features.get("conflict_score"),
                "flow_alignment": mi.get("flow_alignment") or features.get("flow_alignment"),
                "structure_strength": mi.get("structure_strength") or features.get("structure_strength"),
                "clarity_confidence": mi.get("clarity_confidence") or features.get("clarity_confidence")
            }
            print(json.dumps(data, indent=2))
        else:
            print("No signals found.")
    
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(get_latest_signal())
