from __future__ import annotations

import logging
from datetime import datetime, timezone
UTC = timezone.utc

from backend.config import Settings
from backend.database import DatabaseManager
from backend.engines.autopsy_engine import AutopsyEngine
from backend.services.timeframe_aggregator import TIMEFRAME_DELTAS, floor_timestamp

logger = logging.getLogger(__name__)
BREAKEVEN_EPSILON = 1e-9


class TradeEvaluator:
    def __init__(self, settings: Settings, database: DatabaseManager, signal_service: object) -> None:
        self.settings = settings
        self.database = database
        self.signal_service = signal_service

    async def evaluate(self) -> None:
        if not self.database.enabled:
            return

        open_trades = await self.database.load_open_trade_signals()
        if not open_trades:
            return

        now = datetime.now(UTC)
        catchup_queued = 0
        for trade in open_trades:
          try:
            trade_timeframe = self._normalize_timeframe(getattr(trade, "timeframe", None))
            history_logs = list(getattr(trade, "history_logs", None) or [])
            # A trade is "fresh" if it has never been evaluated before (no history logs).
            # This includes trades where entry was touched at creation time (entry_touched_at
            # is set immediately when entry price equals current price). We must still filter
            # stale buckets for these trades because the current candle's high/low contains
            # price data from before the trade existed.
            is_fresh_trade = not history_logs
            if history_logs:
                evaluation_anchor = datetime.fromisoformat(history_logs[-1]["timestamp"])
            else:
                evaluation_anchor = getattr(trade, "last_scale_in_at", None) or trade.entry_touched_at or trade.timestamp
                
            evaluation_buckets = await self._load_evaluation_buckets(
                trade=trade,
                anchor=evaluation_anchor,
                trade_created_at=trade.timestamp if is_fresh_trade else None,
            )

            price = (
                evaluation_buckets[-1].close_price
                if evaluation_buckets
                else await self.signal_service.get_latest_price(trade.symbol, trade_timeframe)
            )
            if price is None or trade.entry_price is None:
                continue

            bias = trade.bias
            direction = 1 if bias == "Bullish" else -1 if bias == "Bearish" else 1

            status = trade.status
            result = "open"
            entry_touched_at = trade.entry_touched_at
            tp1_hit = trade.tp1_hit
            trailing_stop_price = trade.trailing_stop_price
            pnl_pct = trade.pnl_pct
            max_profit_pct = trade.max_profit_pct
            max_drawdown_pct = trade.max_drawdown_pct
            closed_at = None
            close_reason = None
            exit_price = None

            entry_features = dict(getattr(trade, "entry_features", None) or {})
            tp1_pnl_pct = self._feature_float(entry_features.get("tp1_pnl_pct"))
            strategy_version = entry_features.get("strategy_version", "v1")
            entry_flow_alignment = getattr(trade, "entry_flow_alignment", None)
            setup_type = getattr(trade, "setup_type", None)

            payload: dict[str, object] = {"updated_at": now}
            timeframe_delta = TIMEFRAME_DELTAS.get(trade_timeframe, TIMEFRAME_DELTAS["1h"])
            timeout_window = timeframe_delta * max(self.settings.entry_touch_timeout_buckets, 1)
            risk_pct = (
                abs(trade.entry_price - trade.invalidation_price) / trade.entry_price * 100
                if trade.entry_price is not None
                and trade.invalidation_price is not None
                and trade.entry_price > BREAKEVEN_EPSILON
                else None
            )

            # Dynamic interval logic based on timeframe
            tf = trade_timeframe
            if tf == "15m":
                req_interval = 300  # 5 mins
            elif tf == "1h":
                req_interval = 900  # 15 mins
            elif tf == "4h":
                req_interval = 1800 # 30 mins
            elif tf in ("24h", "1d"):
                req_interval = 3600 # 1 hour
            else:
                req_interval = 300

            for bucket in evaluation_buckets:
                high_price = bucket.high_price
                low_price = bucket.low_price
                price = bucket.close_price
                entry_crossed_this_bucket = high_price >= trade.entry_price if direction > 0 else low_price <= trade.entry_price
                trade_is_active = entry_touched_at is not None or entry_crossed_this_bucket

                if entry_crossed_this_bucket and status != "Triggered":
                    status = "Triggered"
                if entry_crossed_this_bucket and entry_touched_at is None:
                    entry_touched_at = bucket.last_timestamp

                if not trade_is_active:
                    if entry_touched_at is None and bucket.last_timestamp - trade.timestamp >= timeout_window:
                        result = "timeout"
                        closed_at = bucket.last_timestamp
                        close_reason = "Entry Never Touched"
                        break
                    continue

                pnl_pct = ((price - trade.entry_price) / trade.entry_price) * direction * 100
                max_profit_pct = max(max_profit_pct, pnl_pct)
                max_drawdown_pct = min(max_drawdown_pct, pnl_pct)
                
                bucket_time = bucket.last_timestamp
                should_log = False
                if not history_logs:
                    should_log = True
                else:
                    last_log_time = datetime.fromisoformat(history_logs[-1]["timestamp"])
                    if (bucket_time - last_log_time).total_seconds() >= req_interval:
                        should_log = True
                
                if should_log:
                    history_logs.append({
                        "timestamp": bucket_time.isoformat(),
                        "price": price,
                        "pnl_pct": round(pnl_pct, 4),
                        "volume": bucket.spot_volume_delta + bucket.futures_volume_delta,
                        "oi": bucket.open_interest_close,
                        "funding": bucket.funding_rate_close,
                        "long_short_ratio": getattr(bucket, "long_short_ratio_close", None),
                        "taker_ratio": getattr(bucket, "taker_buy_sell_ratio_close", None),
                        "event": "update",
                    })

                entry_features = self._merge_trade_analytics_features(
                    entry_features=entry_features,
                    pnl_pct=pnl_pct,
                    max_profit_pct=max_profit_pct,
                    max_drawdown_pct=max_drawdown_pct,
                    risk_pct=risk_pct,
                )

                tp1_just_hit = False
                if trade.target_price_1 is not None and not tp1_hit:
                    if direction > 0 and high_price >= trade.target_price_1:
                        tp1_hit = True
                        tp1_just_hit = True
                        tp1_pnl_pct = ((trade.target_price_1 - trade.entry_price) / trade.entry_price) * direction * 100
                        trailing_stop_price = trade.entry_price
                        entry_features["tp1_pnl_pct"] = round(tp1_pnl_pct, 6)
                        history_logs.append({
                            "timestamp": bucket.last_timestamp.isoformat(),
                            "price": trade.target_price_1,
                            "pnl_pct": round(tp1_pnl_pct, 4),
                            "event": "tp1_hit",
                            "reason": "Take Profit 1"
                        })
                    if direction < 0 and low_price <= trade.target_price_1:
                        tp1_hit = True
                        tp1_just_hit = True
                        tp1_pnl_pct = ((trade.target_price_1 - trade.entry_price) / trade.entry_price) * direction * 100
                        trailing_stop_price = trade.entry_price
                        entry_features["tp1_pnl_pct"] = round(tp1_pnl_pct, 6)
                        history_logs.append({
                            "timestamp": bucket.last_timestamp.isoformat(),
                            "price": trade.target_price_1,
                            "pnl_pct": round(tp1_pnl_pct, 4),
                            "event": "tp1_hit",
                            "reason": "Take Profit 1"
                        })

                exit_price = None
                hit_target_2 = False
                hit_invalidation = False
                if trade.target_price_2 is not None:
                    hit_target_2 = high_price >= trade.target_price_2 if direction > 0 else low_price <= trade.target_price_2
                
                # If TP1 is hit, the trailing stop replaces the invalidation price.
                # But if TP1 was just hit in this candle, we don't activate the trailing stop yet
                # because we don't know the intra-candle path (it might have hit low before high).
                active_stop_price = trailing_stop_price if (tp1_hit and trailing_stop_price is not None and not tp1_just_hit) else trade.invalidation_price
                
                hit_stop = False
                if active_stop_price is not None:
                    hit_stop = low_price <= active_stop_price if direction > 0 else high_price >= active_stop_price

                if hit_target_2:
                    exit_price = trade.target_price_2
                    result = "win"
                    close_reason = "Target 2"
                elif hit_stop:
                    exit_price = active_stop_price
                    if tp1_hit and trailing_stop_price is not None and active_stop_price == trailing_stop_price:
                        result = "win"
                        close_reason = (
                            "Continuation Trail Stop"
                            if setup_type == "Continuation" and abs(trailing_stop_price - trade.entry_price) > BREAKEVEN_EPSILON
                            else "Breakeven SL"
                        )
                    else:
                        result = "loss"
                        close_reason = "Invalidation"

                if exit_price is None and entry_touched_at is not None and strategy_version != "v2_balanced":
                    elapsed_since_entry = bucket.last_timestamp - entry_touched_at
                    fail_fast_window = timeframe_delta * max(self.settings.fail_fast_max_candles, 1)
                    if elapsed_since_entry >= fail_fast_window:
                        mfe_r = (max_profit_pct / risk_pct) if risk_pct and risk_pct > BREAKEVEN_EPSILON else None
                        price_failed_to_follow = mfe_r is not None and mfe_r < self.settings.fail_fast_min_mfe_r
                        current_flow_alignment = self._current_flow_alignment(symbol=trade.symbol, timeframe=trade_timeframe)
                        flow_dropped = (
                            entry_flow_alignment is not None
                            and current_flow_alignment is not None
                            and current_flow_alignment <= entry_flow_alignment - self.settings.fail_fast_flow_drop
                        )
                        if (price_failed_to_follow or flow_dropped) and pnl_pct < 0:
                            exit_price = price
                            result = "loss"
                            close_reason = "Fail-Fast Exit"

                # Stale trade exit: close at market after 6 candles without TP1 (V1 ONLY)
                if exit_price is None and not tp1_hit and entry_touched_at is not None and strategy_version != "v2_balanced":
                    stale_window = timeframe_delta * 6
                    elapsed_since_entry = bucket.last_timestamp - entry_touched_at
                    if elapsed_since_entry >= stale_window and pnl_pct < 0:
                        exit_price = price
                        result = "loss"
                        close_reason = "Stale Exit"

                if exit_price is None and tp1_hit and setup_type == "Continuation":
                    trailing_stop_price = self._continuation_trailing_stop(
                        trade=trade,
                        bucket=bucket,
                        direction=direction,
                        current_price=price,
                        existing_stop=trailing_stop_price,
                        entry_features=entry_features,
                    )

                if exit_price is not None:
                    close_pnl_pct = ((exit_price - trade.entry_price) / trade.entry_price) * direction * 100
                    # Blend 50% TP1 + 50% close for split-position model
                    if tp1_hit and tp1_pnl_pct is not None:
                        pnl_pct = 0.5 * tp1_pnl_pct + 0.5 * close_pnl_pct
                    else:
                        pnl_pct = close_pnl_pct
                    closed_at = bucket.last_timestamp
                    break

            # ---------------------------------------------------------
            # REAL-TIME EVALUATION (If still open after bucket history)
            # ---------------------------------------------------------
            if result == "open" and trade.entry_price and trade.entry_price > 0:
                rt_price = await self.signal_service.get_latest_price(trade.symbol, trade_timeframe)

                # Real-time entry touch detection (before candle close)
                rt_entry_just_touched = False
                if rt_price is not None and status != "Triggered" and entry_touched_at is None:
                    entry_crossed_rt = rt_price >= trade.entry_price if direction > 0 else rt_price <= trade.entry_price
                    if entry_crossed_rt:
                        status = "Triggered"
                        entry_touched_at = now
                        rt_entry_just_touched = True
                        history_logs.append({
                            "timestamp": now.isoformat(),
                            "price": rt_price,
                            "pnl_pct": 0.0,
                            "event": "entry_touch",
                            "reason": "Entry touched (realtime)",
                        })
                        logger.info(
                            "RT entry touch trade_id=%s symbol=%s rt_price=%.6f entry=%.6f",
                            trade.id, trade.symbol, rt_price, trade.entry_price,
                        )

                # CRITICAL: When entry is first touched in real-time, do NOT evaluate
                # TP/SL in the same cycle. We don't know the intra-tick path — the price
                # snapshot might already be past TP1 but the actual market path may not
                # have crossed entry → TP1 sequentially. Wait for the next evaluation
                # cycle when we have proper price movement data.
                if rt_price is not None and status == "Triggered" and not rt_entry_just_touched:
                    rt_pnl_pct = ((rt_price - trade.entry_price) / trade.entry_price) * direction * 100
                    pnl_pct = rt_pnl_pct
                    max_profit_pct = max(max_profit_pct, rt_pnl_pct)
                    max_drawdown_pct = min(max_drawdown_pct, rt_pnl_pct)

                    # --- TP1 real-time check (critical: detect TP1 hit between candles) ---
                    rt_tp1_just_hit = False
                    if trade.target_price_1 is not None and not tp1_hit:
                        rt_hit_tp1 = rt_price >= trade.target_price_1 if direction > 0 else rt_price <= trade.target_price_1
                        if rt_hit_tp1:
                            tp1_hit = True
                            rt_tp1_just_hit = True
                            tp1_pnl_pct = ((trade.target_price_1 - trade.entry_price) / trade.entry_price) * direction * 100
                            trailing_stop_price = trade.entry_price
                            entry_features["tp1_pnl_pct"] = round(tp1_pnl_pct, 6)
                            history_logs.append({
                                "timestamp": now.isoformat(),
                                "price": trade.target_price_1,
                                "pnl_pct": round(tp1_pnl_pct, 4),
                                "event": "tp1_hit",
                                "reason": "Take Profit 1 (realtime)",
                            })
                            logger.info(
                                "RT TP1 hit trade_id=%s symbol=%s rt_price=%.6f tp1=%.6f",
                                trade.id, trade.symbol, rt_price, trade.target_price_1,
                            )

                    # --- Real-time trailing stop update (after TP1 hit) ---
                    if tp1_hit and not rt_tp1_just_hit and setup_type == "Continuation":
                        # Build a lightweight pseudo-bucket for trailing stop calc
                        class _RtBucket:
                            pass
                        rt_bucket = _RtBucket()
                        rt_bucket.high_price = rt_price
                        rt_bucket.low_price = rt_price
                        rt_bucket.close_price = rt_price
                        trailing_stop_price = self._continuation_trailing_stop(
                            trade=trade,
                            bucket=rt_bucket,
                            direction=direction,
                            current_price=rt_price,
                            existing_stop=trailing_stop_price,
                            entry_features=entry_features,
                        )

                    # --- TP2 / SL / SL-BE real-time check ---
                    rt_hit_target_2 = rt_price >= trade.target_price_2 if trade.target_price_2 and direction > 0 else (rt_price <= trade.target_price_2 if trade.target_price_2 else False)
                    # If TP1 just hit this cycle, don't activate trailing stop yet (same logic as bucket)
                    rt_active_stop = trailing_stop_price if (tp1_hit and trailing_stop_price is not None and not rt_tp1_just_hit) else trade.invalidation_price
                    rt_hit_stop = False
                    if rt_active_stop is not None:
                        rt_hit_stop = rt_price <= rt_active_stop if direction > 0 else rt_price >= rt_active_stop

                    if rt_hit_target_2:
                        exit_price = trade.target_price_2
                        result = "win"
                        close_reason = "Target 2"
                    elif rt_hit_stop:
                        exit_price = rt_active_stop
                        result = "win" if tp1_hit else "loss"
                        if tp1_hit:
                            close_reason = "Continuation Trail Stop" if setup_type == "Continuation" and abs(trailing_stop_price - trade.entry_price) > BREAKEVEN_EPSILON else "Breakeven SL"
                        else:
                            close_reason = "Invalidation"
                        
                    if exit_price is not None:
                        close_pnl_pct = ((exit_price - trade.entry_price) / trade.entry_price) * direction * 100
                        if tp1_hit and entry_features.get("tp1_pnl_pct") is not None:
                            pnl_pct = 0.5 * float(entry_features["tp1_pnl_pct"]) + 0.5 * close_pnl_pct
                        else:
                            pnl_pct = close_pnl_pct
                        closed_at = now
                        price = exit_price

            payload["status"] = status
            payload["entry_touched_at"] = entry_touched_at
            payload["tp1_hit"] = tp1_hit
            payload["trailing_stop_price"] = trailing_stop_price
            payload["result"] = result
            payload["pnl_pct"] = pnl_pct
            payload["max_profit_pct"] = max_profit_pct
            payload["max_drawdown_pct"] = max_drawdown_pct
            payload["closed_at"] = closed_at
            payload["close_reason"] = close_reason
            payload["entry_features"] = self._merge_trade_analytics_features(
                entry_features=entry_features,
                pnl_pct=pnl_pct,
                max_profit_pct=max_profit_pct,
                max_drawdown_pct=max_drawdown_pct,
                risk_pct=risk_pct,
            )

            if result in ("win", "loss"):
                import dataclasses
                # Use last available bucket for exit features, or empty dict if none
                payload["exit_features"] = {
                    k: v
                    for k, v in dataclasses.asdict(evaluation_buckets[-1]).items()
                    if k not in ("symbol", "timeframe", "bucket_start", "bucket_end", "last_timestamp")
                } if evaluation_buckets else {"realtime_exit": True}
                
                payload["autopsy_rationale"] = AutopsyEngine.generate_rationale(
                    result=result,
                    close_reason=close_reason or "Unknown",
                    entry_features=entry_features,
                    exit_features=payload["exit_features"],
                    tp1_hit=tp1_hit,
                    bias=trade.bias,
                )
                
            if result != "open":
                history_logs.append({
                    "timestamp": closed_at.isoformat() if closed_at else now.isoformat(),
                    "price": exit_price if exit_price is not None else price,
                    "pnl_pct": round(pnl_pct, 4),
                    "event": "close",
                    "reason": close_reason or "Unknown",
                })

            payload["history_logs"] = history_logs
            await self.database.update_trade_signal(trade.id, payload)
            for key, value in payload.items():
                setattr(trade, key, value)
            if result in {"win", "loss", "breakeven"} and hasattr(self.signal_service, "record_continuation_feedback_trade"):
                self.signal_service.record_continuation_feedback_trade(trade)

            updated_result = result
            updated_entry_touched_at = entry_touched_at
            if (
                updated_result == "open"
                and updated_entry_touched_at is not None
                and getattr(trade, "entry_notification_sent_at", None) is None
                and hasattr(self.signal_service, "catch_up_trade_entry_notification")
            ):
                trade.result = "open"
                trade.entry_touched_at = updated_entry_touched_at
                queued = await self.signal_service.catch_up_trade_entry_notification(trade)
                if queued:
                    catchup_queued += 1
          except Exception:
            logger.exception("Trade evaluator failed for trade_id=%s symbol=%s", getattr(trade, "id", "?"), getattr(trade, "symbol", "?"))

        logger.info("Trade evaluator scanned open_trades=%d catchup_queued=%d", len(open_trades), catchup_queued)

    def _current_flow_alignment(self, *, symbol: str, timeframe: str) -> float | None:
        timeframe = self._normalize_timeframe(timeframe)
        states_by_timeframe = getattr(self.signal_service, "states_by_timeframe", None)
        if not isinstance(states_by_timeframe, dict):
            return None
        state = states_by_timeframe.get(timeframe, {}).get(symbol)
        if state is None or not getattr(state, "market_interpretation", None):
            return None
        value = state.market_interpretation.get("flow_alignment")
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _current_metric(self, *, symbol: str, timeframe: str, metric_name: str) -> float | None:
        timeframe = self._normalize_timeframe(timeframe)
        states_by_timeframe = getattr(self.signal_service, "states_by_timeframe", None)
        if not isinstance(states_by_timeframe, dict):
            return None
        state = states_by_timeframe.get(timeframe, {}).get(symbol)
        if state is None or not getattr(state, "metrics_raw", None):
            return None
        value = state.metrics_raw.get(f"{metric_name}_{timeframe}")
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _feature_float(value: object) -> float | None:
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    def _continuation_trailing_stop(
        self,
        *,
        trade: object,
        bucket: object,
        direction: int,
        current_price: float,
        existing_stop: float | None,
        entry_features: dict[str, object],
    ) -> float | None:
        trade_timeframe = self._normalize_timeframe(getattr(trade, "timeframe", None))
        atr_fraction = self._current_metric(symbol=trade.symbol, timeframe=trade_timeframe, metric_name="atr")
        if atr_fraction is None or atr_fraction <= BREAKEVEN_EPSILON:
            atr_fraction = self._feature_float(entry_features.get(f"atr_{trade_timeframe}")) or 0.0
        buffer_multiplier = self._continuation_trailing_buffer_multiplier(entry_features=entry_features)
        buffer = atr_fraction * current_price * buffer_multiplier
        if buffer <= BREAKEVEN_EPSILON and trade.invalidation_price is not None:
            buffer = abs(trade.entry_price - trade.invalidation_price) * 0.35
        if buffer <= BREAKEVEN_EPSILON:
            return existing_stop

        recent_low = self._current_metric(symbol=trade.symbol, timeframe=trade_timeframe, metric_name="recent_low") or bucket.low_price
        recent_high = self._current_metric(symbol=trade.symbol, timeframe=trade_timeframe, metric_name="recent_high") or bucket.high_price
        candidate = recent_low - buffer if direction > 0 else recent_high + buffer
        anchor = existing_stop if existing_stop is not None else trade.entry_price
        if direction > 0:
            return round(max(candidate, trade.entry_price, anchor), 10)
        return round(min(candidate, trade.entry_price, anchor), 10)

    def _continuation_trailing_buffer_multiplier(self, *, entry_features: dict[str, object]) -> float:
        multiplier = self.settings.continuation_trailing_atr_buffer
        volatility_regime = str(entry_features.get("decision_volatility_regime") or "")
        if volatility_regime == "High":
            multiplier *= self.settings.continuation_trailing_high_vol_multiplier
        elif volatility_regime == "Low":
            multiplier *= self.settings.continuation_trailing_low_vol_multiplier

        structure_strength = self._feature_float(entry_features.get("structure_strength")) or 0.5
        multiplier *= 0.9 + (structure_strength * 0.25)

        elite_boost_active = bool(entry_features.get("continuation_elite_boost_active"))
        if elite_boost_active and bool(entry_features.get("continuation_history_ready")):
            multiplier *= self.settings.continuation_elite_trailing_boost_multiplier

        mfe_r = self._feature_float(entry_features.get("mfe_r")) or 0.0
        if mfe_r >= self.settings.continuation_trailing_profit_lock_mfe_r:
            multiplier *= self.settings.continuation_trailing_profit_lock_multiplier

        historical_bucket_mfe_r = self._feature_float(entry_features.get("continuation_bucket_avg_mfe_r")) or 0.0
        if historical_bucket_mfe_r >= self.settings.continuation_trailing_mfe_loosen_r:
            multiplier *= self.settings.continuation_trailing_mfe_loosen_multiplier
        elif historical_bucket_mfe_r > BREAKEVEN_EPSILON and historical_bucket_mfe_r <= self.settings.continuation_trailing_mfe_tighten_r:
            multiplier *= self.settings.continuation_trailing_mfe_tighten_multiplier

        entry_efficiency = self._feature_float(entry_features.get("entry_efficiency"))
        if entry_efficiency is not None and entry_efficiency < self.settings.continuation_feedback_penalty_efficiency:
            multiplier *= 0.95

        return max(0.35, round(multiplier, 4))

    def _merge_trade_analytics_features(
        self,
        *,
        entry_features: dict[str, object],
        pnl_pct: float | None,
        max_profit_pct: float,
        max_drawdown_pct: float,
        risk_pct: float | None,
    ) -> dict[str, object]:
        features = dict(entry_features)
        mae_pct = abs(min(max_drawdown_pct, 0.0))
        mfe_pct = max(max_profit_pct, 0.0)
        features["mae_pct"] = round(mae_pct, 6)
        features["mfe_pct"] = round(mfe_pct, 6)

        if risk_pct is not None and risk_pct > BREAKEVEN_EPSILON:
            features["mae_r"] = round(mae_pct / risk_pct, 4)
            features["mfe_r"] = round(mfe_pct / risk_pct, 4)
            features["realized_r"] = round((pnl_pct or 0.0) / risk_pct, 4)

        efficiency_denominator = mfe_pct + mae_pct
        if efficiency_denominator > BREAKEVEN_EPSILON:
            features["entry_efficiency"] = round(mfe_pct / efficiency_denominator, 4)

        return features

    async def _load_evaluation_buckets(self, *, trade: object, anchor: datetime, trade_created_at: datetime | None = None) -> list[object]:
        buckets_by_start: dict[datetime, object] = {}
        timeframe = self._normalize_timeframe(getattr(trade, "timeframe", None))
        query_since = floor_timestamp(anchor, timeframe) if timeframe in TIMEFRAME_DELTAS else anchor

        if hasattr(self.database, "load_market_buckets"):
            db_buckets = await self.database.load_market_buckets([trade.symbol], query_since, [timeframe])
            for bucket in db_buckets:
                buckets_by_start[bucket.bucket_start] = bucket

        aggregate_store = getattr(self.signal_service, "aggregate_store", None)
        if aggregate_store is not None:
            if hasattr(aggregate_store, "history_for"):
                for bucket in aggregate_store.history_for(trade.symbol, timeframe, closed_only=False):
                    if bucket.last_timestamp >= anchor:
                        buckets_by_start[bucket.bucket_start] = bucket
            latest_bucket = aggregate_store.latest_bucket(trade.symbol, timeframe, closed_only=False)
            if latest_bucket is not None and latest_bucket.last_timestamp >= anchor:
                buckets_by_start[latest_bucket.bucket_start] = latest_bucket

        sorted_buckets = [buckets_by_start[key] for key in sorted(buckets_by_start)]

        # CRITICAL: For fresh trades (no history yet, entry not touched), exclude
        # buckets whose candle opened BEFORE the trade was created. These buckets
        # contain high/low prices from before the signal existed, which would
        # cause false TP1/SL hits (e.g. a 24h candle whose high was set hours
        # before the signal, but the candle is still open).
        # Only allow buckets that started AFTER the trade was created.
        if trade_created_at is not None:
            sorted_buckets = [
                b for b in sorted_buckets
                if b.bucket_start >= trade_created_at
            ]

        return sorted_buckets

    @staticmethod
    def _normalize_timeframe(value: object) -> str:
        return str(value or "").strip().lower()
