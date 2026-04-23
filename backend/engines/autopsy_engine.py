from __future__ import annotations
import math

class AutopsyEngine:
    """Analyzes entry and exit features to generate an autopsy rationale."""
    
    @classmethod
    def generate_rationale(
        cls,
        result: str,
        close_reason: str,
        entry_features: dict,
        exit_features: dict,
        tp1_hit: bool,
        bias: str,
    ) -> str:
        if not entry_features or not exit_features:
            return "Insufficient data to generate autopsy report."

        # Extract features
        def safe_float(d: dict, key: str) -> float:
            try:
                return float(d.get(key, 0.0) or 0.0)
            except (ValueError, TypeError):
                return 0.0

        en_oi_delta = safe_float(entry_features, "oi_delta_1h")
        ex_oi_delta = safe_float(exit_features, "oi_delta_1h")
        en_vol_z = safe_float(entry_features, "volume_z_1h")
        ex_vol_z = safe_float(exit_features, "volume_z_1h")
        en_funding = safe_float(entry_features, "funding_level_1h")
        
        ex_oi_delta = safe_float(exit_features, "open_interest_close") - safe_float(exit_features, "open_interest_open")
        ex_vol_delta = safe_float(exit_features, "volume_delta")
        ex_funding = safe_float(exit_features, "funding_rate_close")

        reasons = []

        # Analyze Funding
        if bias == "Bullish" and ex_funding < 0 and en_funding > 0:
            reasons.append("Funding rate flipped negative, showing retail sentiment shifted bearish.")
        elif bias == "Bearish" and ex_funding > 0 and en_funding < 0:
            reasons.append("Funding rate flipped positive, showing retail sentiment shifted bullish.")

        # Analyze OI
        if bias == "Bullish" and ex_oi_delta < 0:
            reasons.append("Open Interest dropped, indicating longs closing or losing momentum.")
        elif bias == "Bearish" and ex_oi_delta < 0:
            reasons.append("Open Interest dropped, showing short covering reducing downward pressure.")

        # Result context
        rationale = f"Trade closed as {result.upper()} due to {close_reason}. "
        
        if result == "win":
            rationale += "The trade played out favorably. "
        elif result == "loss":
            rationale += "The setup was invalidated. "
        
        if tp1_hit and result != "win":
            rationale += "The trade successfully reached TP1 but reversed before hitting further targets, getting stopped out by the trailing stop. "
        
        if reasons:
            rationale += "Key observations: " + " ".join(reasons)
        else:
            rationale += "Market conditions remained relatively stable during the trade."

        return rationale
