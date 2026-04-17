with open('backend/services/signal_service.py', 'r') as f:
    content = f.read()

target = """        if regime == "Ranging" and volatility == "Low":
            reasons.append("market_regime_ranging")
        if volatility == "Low":
            reasons.append("volatility_regime_low")
        if clarity_confidence < self.settings.entry_filter_min_clarity_confidence:
            reasons.append("clarity_below_threshold")
            
        if action.bias == "Bearish":
            if not self.settings.entry_filter_allow_shorts:
                # Dynamic context: only allow logic-defying short blocks if BTC is not Bearish
                if self._global_btc_trend() != "Bearish":
                    reasons.append("short_direction_disabled")
        elif action.bias == "Bullish":
            pass # Removed HTF OI checks for Intraday mode
            pass # Removed HTF Market Pressure checks for Intraday mode
        # Removed young coin checks for Intraday mode
        # Removed 24H ATR filter to catch 15m localized bursts
        # Removed 4H Volume drop filter because localized 15m volume matters more in intraday
        if not is_trap_setup and flow_metrics.volume_z_15m is not None and flow_metrics.volume_z_15m > self.settings.entry_filter_max_volume_z_15m:
            reasons.append("exhaustion_volume_climax")
        if not is_trap_setup and flow_metrics.oi_delta_z_15m is not None and flow_metrics.oi_delta_z_15m > self.settings.entry_filter_max_oi_delta_z_15m:
            reasons.append("exhaustion_oi_climax")
        if not is_trap_setup and flow_metrics.liq_pressure_1h > self.settings.entry_filter_max_liq_pressure_1h:
            reasons.append("exhaustion_liq_climax")
        if flow_metrics.atr_15m < self.settings.entry_filter_min_atr_15m:
            reasons.append("dead_atr_15m")
        if flow_metrics.atr_1h < self.settings.entry_filter_min_atr_1h:
            reasons.append("dead_atr_1h")
        if getattr(flow_metrics, "compression_score_15m", 0.0) > self.settings.entry_filter_max_compression_score_15m:
            reasons.append("high_compression_15m")
        if getattr(flow_metrics, "wick_ratio_24h", 1.0) < self.settings.entry_filter_min_wick_ratio_24h:
            reasons.append("tiny_wick_24h")"""

replacement = """        # --- INTRADAY HIGH-FREQUENCY MODE ---
        if clarity_confidence < 0.35:
            reasons.append("clarity_below_threshold")
        if action.bias == "Bearish" and not self.settings.entry_filter_allow_shorts and self._global_btc_trend() != "Bearish":
            reasons.append("short_direction_disabled")"""

if target in content:
    with open('backend/services/signal_service.py', 'w') as f:
        f.write(content.replace(target, replacement))
    print("Patched successfully!")
else:
    print("Target not found")
