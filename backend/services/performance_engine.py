from __future__ import annotations

import csv
import html
import json
from datetime import datetime, timezone
UTC = timezone.utc
from io import StringIO

from backend.database import DatabaseManager
from backend.schemas import (
    ConditionPerformance,
    PerformanceResponse,
    PerformanceTradeRow,
    PerformanceTradeTableResponse,
    RegimePerformance,
    SetupPerformance,
)


class PerformanceEngine:
    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    def _active_since(self) -> datetime | None:
        settings = getattr(self.database, "settings", None)
        value = getattr(settings, "trade_signals_active_since", None)
        return value if isinstance(value, datetime) else None

    def _active_tag(self) -> str | None:
        settings = getattr(self.database, "settings", None)
        value = getattr(settings, "trade_signals_active_tag", None)
        return value if isinstance(value, str) and value.strip() else None

    def _trade_in_scope(self, trade: object, *, scope: str) -> bool:
        if scope != "active":
            return True
        active_tag = self._active_tag()
        if active_tag is not None:
            return getattr(trade, "engine_tag", None) == active_tag
        active_since = self._active_since()
        if active_since is None:
            return True
        created_at = getattr(trade, "created_at", None)
        return isinstance(created_at, datetime) and created_at >= active_since

    @staticmethod
    def _round(value: float | None, digits: int = 4) -> float | None:
        if value is None:
            return None
        return round(value, digits)

    @staticmethod
    def _safe_div(numerator: float, denominator: float) -> float | None:
        if abs(denominator) <= 1e-12:
            return None
        return numerator / denominator

    @staticmethod
    def _display(value: float | int | str | None, digits: int | None = None) -> str:
        if value is None:
            return "--"
        if isinstance(value, float) and digits is not None:
            return f"{value:.{digits}f}"
        return str(value)
from __future__ import annotations

import csv
import html
import json
from datetime import datetime, timezone
UTC = timezone.utc
from io import StringIO

from backend.database import DatabaseManager
from backend.schemas import (
    ConditionPerformance,
    PerformanceResponse,
    PerformanceTradeRow,
    PerformanceTradeTableResponse,
    RegimePerformance,
    SetupPerformance,
)


class PerformanceEngine:
    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    def _active_since(self) -> datetime | None:
        settings = getattr(self.database, "settings", None)
        value = getattr(settings, "trade_signals_active_since", None)
        return value if isinstance(value, datetime) else None

    def _active_tag(self) -> str | None:
        settings = getattr(self.database, "settings", None)
        value = getattr(settings, "trade_signals_active_tag", None)
        return value if isinstance(value, str) and value.strip() else None

    def _trade_in_scope(self, trade: object, *, scope: str) -> bool:
        if scope != "active":
            return True
        active_tag = self._active_tag()
        if active_tag is not None:
            return getattr(trade, "engine_tag", None) == active_tag
        active_since = self._active_since()
        if active_since is None:
            return True
        created_at = getattr(trade, "created_at", None)
        return isinstance(created_at, datetime) and created_at >= active_since

    @staticmethod
    def _round(value: float | None, digits: int = 4) -> float | None:
        if value is None:
            return None
        return round(value, digits)

    @staticmethod
    def _safe_div(numerator: float, denominator: float) -> float | None:
        if abs(denominator) <= 1e-12:
            return None
        return numerator / denominator

    @staticmethod
    def _display(value: float | int | str | None, digits: int | None = None) -> str:
        if value is None:
            return "--"
        if isinstance(value, float) and digits is not None:
            return f"{value:.{digits}f}"
        return str(value)

    async def _filtered_trades(
        self,
        *,
        symbol: str = "ALL",
        timeframe: str = "ALL",
        setup_type: str | None = None,
        scope: str = "active",
        strategy: str = "v2_balanced",
    ) -> list:
        trades = await self.database.list_trade_signals()
        filtered = []
        for trade in trades:
            if not self._trade_in_scope(trade, scope=scope):
                continue
            if symbol != "ALL" and trade.symbol != symbol:
                continue
            if timeframe != "ALL" and trade.timeframe != timeframe:
                continue
            if setup_type and trade.setup_type != setup_type:
                continue
            if strategy and strategy != "ALL" and strategy != "all":
                features = trade.entry_features if isinstance(trade.entry_features, dict) else {}
                if features.get("strategy_version", "v1") != strategy:
                    continue
            filtered.append(trade)
        filtered.sort(key=lambda trade: trade.created_at, reverse=True)
        return filtered

    async def _trade_report_rows(
        self,
        *,
        symbol: str = "ALL",
        timeframe: str = "ALL",
        setup_type: str | None = None,
        scope: str = "active",
        strategy: str = "v2_balanced",
        capital_per_trade: float = 100.0,
    ) -> list[dict[str, object]]:
        filtered = await self._filtered_trades(
            symbol=symbol,
            timeframe=timeframe,
            setup_type=setup_type,
            scope=scope,
            strategy=strategy,
        )

        rows: list[dict[str, object]] = []
        for trade in filtered:
            entry_features = getattr(trade, "entry_features", None)
            if not isinstance(entry_features, dict):
                entry_features = {}
            fill_count = max(getattr(trade, "fill_count", 1) or 1, 1)
            base_capital = capital_per_trade * fill_count
            allocation_multiplier = 1.0
            try:
                allocation_multiplier = float(entry_features.get("position_size_multiplier", 1.0) or 1.0)
            except (TypeError, ValueError):
                allocation_multiplier = 1.0
            allocation_multiplier = max(0.1, allocation_multiplier)
            effective_capital = base_capital * allocation_multiplier
            entry = trade.entry_price
            invalidation = trade.invalidation_price
            target_1 = trade.target_price_1 or trade.target_price
            target_2 = trade.target_price_2 or target_1

            risk_per_unit = abs(entry - invalidation) if entry is not None and invalidation is not None else None
            reward_tp1 = abs(target_1 - entry) if entry is not None and target_1 is not None else None
            reward_tp2 = abs(target_2 - entry) if entry is not None and target_2 is not None else None
            rr_tp1 = self._safe_div(reward_tp1, risk_per_unit) if reward_tp1 is not None and risk_per_unit is not None else None
            rr_tp2 = self._safe_div(reward_tp2, risk_per_unit) if reward_tp2 is not None and risk_per_unit is not None else None

            quantity = (effective_capital / entry) if entry and entry > 0 else None
            risk_amount_usd = quantity * risk_per_unit if quantity is not None and risk_per_unit is not None else None
            tp1_reward_usd = quantity * reward_tp1 if quantity is not None and reward_tp1 is not None else None
            tp2_reward_usd = quantity * reward_tp2 if quantity is not None and reward_tp2 is not None else None
            risk_pct_of_capital = self._safe_div(risk_amount_usd * 100, effective_capital) if risk_amount_usd is not None else None

            realized_pnl_usd = effective_capital * (trade.pnl_pct / 100)
            max_profit_usd = effective_capital * (trade.max_profit_pct / 100)
            max_drawdown_usd = effective_capital * (trade.max_drawdown_pct / 100)
            realized_r_multiple = self._safe_div(realized_pnl_usd, risk_amount_usd) if risk_amount_usd is not None else None
            allocated_r_multiple = realized_r_multiple * allocation_multiplier if realized_r_multiple is not None else None

            row = {
                "trade_id": trade.id,
                "symbol": trade.symbol,
                "timeframe": trade.timeframe,
                "setup_type": trade.setup_type,
                "state": trade.state,
                "bias": trade.bias,
                "status": trade.status,
                "result": trade.result,
                "market_regime": trade.market_regime,
                "volatility_regime": trade.volatility_regime,
                "confidence_pct": self._round(trade.confidence * 100, 2),
                "quality_score": trade.quality_score,
                "risk_level": trade.risk_level,
                "signal_timestamp": trade.timestamp.isoformat(),
                "created_at": trade.created_at.isoformat(),
                "entry_touched_at": trade.entry_touched_at.isoformat() if trade.entry_touched_at else None,
                "fill_count": fill_count,
                "last_scale_in_at": trade.last_scale_in_at.isoformat() if trade.last_scale_in_at else None,
                "closed_at": trade.closed_at.isoformat() if trade.closed_at else None,
                "close_reason": trade.close_reason,
                "updated_at": trade.updated_at.isoformat(),
                "entry_price": self._round(entry, 6),
                "invalidation_price": self._round(invalidation, 6),
                "target_price_1": self._round(target_1, 6),
                "target_price_2": self._round(target_2, 6),
                "risk_per_unit": self._round(risk_per_unit, 6),
                "reward_tp1_per_unit": self._round(reward_tp1, 6),
                "reward_tp2_per_unit": self._round(reward_tp2, 6),
                "planned_rr_tp1": self._round(rr_tp1, 4),
                "planned_rr_tp2": self._round(rr_tp2, 4),
                "base_capital_per_trade": self._round(base_capital, 2),
                "capital_per_trade": self._round(effective_capital, 2),
                "estimated_quantity": self._round(quantity, 8),
                "risk_amount_usd": self._round(risk_amount_usd, 2),
                "tp1_reward_usd": self._round(tp1_reward_usd, 2),
                "tp2_reward_usd": self._round(tp2_reward_usd, 2),
                "risk_pct_of_capital": self._round(risk_pct_of_capital, 4),
                "pnl_pct": self._round(trade.pnl_pct, 4),
                "realized_pnl_usd": self._round(realized_pnl_usd, 2),
                "realized_r_multiple": self._round(realized_r_multiple, 4),
                "allocated_r_multiple": self._round(allocated_r_multiple, 4),
                "max_profit_pct": self._round(trade.max_profit_pct, 4),
                "max_profit_usd": self._round(max_profit_usd, 2),
                "max_drawdown_pct": self._round(trade.max_drawdown_pct, 4),
                "max_drawdown_usd": self._round(max_drawdown_usd, 2),
                "engine_tag": getattr(trade, "engine_tag", None),
                "strategy_version": entry_features.get("strategy_version", "unknown") if entry_features else "unknown",
                "position_size_multiplier": self._round(allocation_multiplier, 4),
            }
            if entry_features:
                for key, value in entry_features.items():
                    if isinstance(value, (int, float, bool, str)):
                        row[f"feat_{key}"] = value
            rows.append(row)
        return rows

    async def export_trade_report_csv(
        self,
        *,
        symbol: str = "ALL",
        timeframe: str = "ALL",
        setup_type: str | None = None,
        scope: str = "active",
        strategy: str = "v2_balanced",
        capital_per_trade: float = 100.0,
    ) -> str:
        rows = await self._trade_report_rows(
            symbol=symbol,
            timeframe=timeframe,
            setup_type=setup_type,
            scope=scope,
            strategy=strategy,
            capital_per_trade=capital_per_trade,
        )

        base_fields = [
            "trade_id",
            "symbol",
            "timeframe",
            "setup_type",
            "state",
            "bias",
            "status",
            "result",
            "market_regime",
            "volatility_regime",
            "confidence_pct",
            "quality_score",
            "risk_level",
            "signal_timestamp",
            "created_at",
            "entry_touched_at",
            "fill_count",
            "last_scale_in_at",
            "closed_at",
            "close_reason",
            "updated_at",
            "entry_price",
            "invalidation_price",
            "target_price_1",
            "target_price_2",
            "risk_per_unit",
            "reward_tp1_per_unit",
            "reward_tp2_per_unit",
            "planned_rr_tp1",
            "planned_rr_tp2",
            "base_capital_per_trade",
            "capital_per_trade",
            "estimated_quantity",
            "risk_amount_usd",
            "tp1_reward_usd",
            "tp2_reward_usd",
            "risk_pct_of_capital",
            "pnl_pct",
            "realized_pnl_usd",
            "realized_r_multiple",
            "allocated_r_multiple",
            "max_profit_pct",
            "max_profit_usd",
            "max_drawdown_pct",
            "max_drawdown_usd",
            return PerformanceResponse(
                generated_at=datetime.now(UTC),
                total_trades=0,
                winrate=0.0,
                expectancy=0.0,
                best_setup=None,
                worst_setup=None,
                setups=[],
            )

        if not closed:
            setups = [
                SetupPerformance(
                    setup_type=setup_type,
                    state=None,
                    trades=len(trades_for_type),
                    open_trades=len(trades_for_type),
                    closed_trades=0,
                    wins=0,
                    losses=0,
                    breakevens=0,
                    winrate=0.0,
                    avg_win=0.0,
                    avg_loss=0.0,
                    rr_ratio=0.0,
                    expectancy=0.0,
                    validated=False,
                )
                for setup_type, trades_for_type in grouped_all.items()
            ]
            return PerformanceResponse(
                generated_at=datetime.now(UTC),
                total_trades=0,
                winrate=0.0,
                expectancy=0.0,
                best_setup=None,
                worst_setup=None,
                setups=sorted(setups, key=lambda item: item.trades, reverse=True),
            )

        total = len(closed)
        wins = [trade for trade in closed if trade.result == "win"]
        losses = [trade for trade in closed if trade.result == "loss"]
        winrate = len(wins) / total if total else 0.0
        avg_win = sum(trade.pnl_pct for trade in wins) / len(wins) if wins else 0.0
        avg_loss = abs(sum(trade.pnl_pct for trade in losses) / len(losses)) if losses else 0.0
        expectancy = (winrate * avg_win) - ((1 - winrate) * avg_loss)

        setups: list[SetupPerformance] = []
        for setup_type, trades_for_type in grouped_all.items():
            closed_t = [trade for trade in trades_for_type if trade.result in ("win", "loss")]
            open_t = [trade for trade in trades_for_type if trade.result == "open"]
            wins_t = [trade for trade in closed_t if trade.result == "win"]
            losses_t = [trade for trade in closed_t if trade.result == "loss"]
            breakevens_t = [trade for trade in trades_for_type if trade.result == "breakeven"]
            total_t = len(closed_t)
            winrate_t = len(wins_t) / total_t if total_t else 0.0
            avg_win_t = sum(trade.pnl_pct for trade in wins_t) / len(wins_t) if wins_t else 0.0
            avg_loss_t = abs(sum(trade.pnl_pct for trade in losses_t) / len(losses_t)) if losses_t else 0.0
            expectancy_t = (winrate_t * avg_win_t) - ((1 - winrate_t) * avg_loss_t)
            rr_ratio = avg_win_t / avg_loss_t if avg_loss_t else 0.0
            setups.append(
                SetupPerformance(
                    setup_type=setup_type,
                    state=None,
                    trades=len(trades_for_type),
                    open_trades=len(open_t),
                    closed_trades=total_t,
                    wins=len(wins_t),
                    losses=len(losses_t),
                    breakevens=len(breakevens_t),
                    winrate=round(winrate_t, 4),
                    avg_win=round(avg_win_t, 4),
                    avg_loss=round(avg_loss_t, 4),
                    rr_ratio=round(rr_ratio, 4),
                    expectancy=round(expectancy_t, 4),
                    validated=total_t >= 20 and expectancy_t > 0,
                )
            )

        setups_with_results = [item for item in setups if item.closed_trades > 0]
        ranked_setups = sorted(setups_with_results, key=lambda item: item.expectancy, reverse=True)
        best_setup = ranked_setups[0] if ranked_setups else None
        worst_setup = next(
            (
                item
                for item in reversed(ranked_setups)
                if best_setup is None or item.setup_type != best_setup.setup_type
            ),
            None,
        )

        regime_grouped: dict[str, list] = {}
        for trade in closed:
            regime_grouped.setdefault(trade.market_regime or "Balanced", []).append(trade)

        regimes: list[RegimePerformance] = []
        for regime, trades_for_regime in regime_grouped.items():
            wins_r = [trade for trade in trades_for_regime if trade.result == "win"]
            losses_r = [trade for trade in trades_for_regime if trade.result == "loss"]
            breakevens_r = [trade for trade in trades_for_regime if trade.result == "breakeven"]
            total_r = len(trades_for_regime)
            winrate_r = len(wins_r) / total_r if total_r else 0.0
            avg_win_r = sum(trade.pnl_pct for trade in wins_r) / len(wins_r) if wins_r else 0.0
            avg_loss_r = abs(sum(trade.pnl_pct for trade in losses_r) / len(losses_r)) if losses_r else 0.0
            expectancy_r = (winrate_r * avg_win_r) - ((1 - winrate_r) * avg_loss_r)
            rr_ratio_r = avg_win_r / avg_loss_r if avg_loss_r else 0.0
            regimes.append(
                RegimePerformance(
                    regime=regime,
                    trades=total_r,
                    wins=len(wins_r),
                    losses=len(losses_r),
                    breakevens=len(breakevens_r),
                    winrate=round(winrate_r, 4),
                    avg_win=round(avg_win_r, 4),
                    avg_loss=round(avg_loss_r, 4),
                    rr_ratio=round(rr_ratio_r, 4),
                    expectancy=round(expectancy_r, 4),
                    validated=total_r >= 20 and expectancy_r > 0,
                )
            )

        condition_grouped: dict[tuple[str, str, str], list] = {}
        for trade in closed:
            regime = trade.market_regime or "Balanced"
            volatility = trade.volatility_regime or "Medium"
            key = (trade.setup_type, regime, volatility)
            condition_grouped.setdefault(key, []).append(trade)

        conditions: list[ConditionPerformance] = []
        for (setup_type, regime, volatility), trades_for_condition in condition_grouped.items():
            wins_c = [trade for trade in trades_for_condition if trade.result == "win"]
            losses_c = [trade for trade in trades_for_condition if trade.result == "loss"]
            breakevens_c = [trade for trade in trades_for_condition if trade.result == "breakeven"]
            total_c = len(trades_for_condition)
            winrate_c = len(wins_c) / total_c if total_c else 0.0
            avg_win_c = sum(trade.pnl_pct for trade in wins_c) / len(wins_c) if wins_c else 0.0
            avg_loss_c = abs(sum(trade.pnl_pct for trade in losses_c) / len(losses_c)) if losses_c else 0.0
            expectancy_c = (winrate_c * avg_win_c) - ((1 - winrate_c) * avg_loss_c)
            rr_ratio_c = avg_win_c / avg_loss_c if avg_loss_c else 0.0
            conditions.append(
                ConditionPerformance(
                    setup_type=setup_type,
                    regime=regime,
                    volatility=volatility,
                    trades=total_c,
                    wins=len(wins_c),
                    losses=len(losses_c),
                    breakevens=len(breakevens_c),
                    winrate=round(winrate_c, 4),
                    avg_win=round(avg_win_c, 4),
                    avg_loss=round(avg_loss_c, 4),
                    rr_ratio=round(rr_ratio_c, 4),
                    expectancy=round(expectancy_c, 4),
                    validated=total_c >= 20 and expectancy_c > 0,
                )
            )

        return PerformanceResponse(
            generated_at=datetime.now(UTC),
            total_trades=total,
            winrate=round(winrate, 4),
            expectancy=round(expectancy, 4),
            best_setup=best_setup.setup_type if best_setup else None,
            worst_setup=worst_setup.setup_type if worst_setup else None,
            setups=sorted(setups, key=lambda item: item.expectancy, reverse=True),
            regimes=sorted(regimes, key=lambda item: item.expectancy, reverse=True),
            conditions=sorted(conditions, key=lambda item: item.expectancy, reverse=True),
        )
