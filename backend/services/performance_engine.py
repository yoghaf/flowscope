from __future__ import annotations

import csv
import html
import json
from collections import defaultdict
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
        regime: str = "ALL",
        result: str = "ALL",
        month: str | None = None,
        search: str | None = None,
        scope: str = "active",
        strategy: str = "v2_balanced",
    ) -> list:
        trades = await self.database.list_trade_signals()
        filtered = []
        search_term = search.strip().lower() if search else ""
        month_filter = month.strip() if month else ""
        for trade in trades:
            if not self._trade_in_scope(trade, scope=scope):
                continue
            if symbol != "ALL" and trade.symbol != symbol:
                continue
            if timeframe != "ALL" and trade.timeframe != timeframe:
                continue
            if setup_type and setup_type not in {"ALL", "all"} and trade.setup_type != setup_type:
                continue
            if regime not in {"ALL", "all"} and trade.market_regime != regime:
                continue
            if result not in {"ALL", "all"}:
                if result == "closed":
                    if trade.result == "open":
                        continue
                elif trade.result != result:
                    continue
            if month_filter:
                created_at = getattr(trade, "created_at", None)
                if not isinstance(created_at, datetime) or created_at.strftime("%Y-%m") != month_filter:
                    continue
            if search_term:
                searchable = " ".join(
                    str(value or "")
                    for value in (
                        getattr(trade, "symbol", ""),
                        getattr(trade, "setup_type", ""),
                        getattr(trade, "market_regime", ""),
                        getattr(trade, "state", ""),
                        getattr(trade, "bias", ""),
                        getattr(trade, "close_reason", ""),
                    )
                ).lower()
                if search_term not in searchable:
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
        regime: str = "ALL",
        result: str = "ALL",
        month: str | None = None,
        search: str | None = None,
        scope: str = "active",
        strategy: str = "v2_balanced",
        simulation_mode: str = "fixed_risk",
        starting_capital: float = 1000.0,
        capital_per_trade: float = 100.0,
        risk_per_trade: float | None = 10.0,
        risk_pct_per_trade: float = 1.0,
        fee_pct: float = 0.0,
        use_position_multiplier: bool = True,
    ) -> list[dict[str, object]]:
        filtered = await self._filtered_trades(
            symbol=symbol,
            timeframe=timeframe,
            setup_type=setup_type,
            regime=regime,
            result=result,
            month=month,
            search=search,
            scope=scope,
            strategy=strategy,
        )

        rows: list[dict[str, object]] = []
        equity = max(starting_capital, 0.0)
        closed_results = {"win", "loss", "breakeven", "timeout"}
        for trade in sorted(filtered, key=lambda item: item.created_at):
            entry_features = getattr(trade, "entry_features", None)
            if not isinstance(entry_features, dict):
                entry_features = {}
            fill_count = max(getattr(trade, "fill_count", 1) or 1, 1)
            allocation_multiplier = 1.0
            try:
                allocation_multiplier = float(entry_features.get("position_size_multiplier", 1.0) or 1.0)
            except (TypeError, ValueError):
                allocation_multiplier = 1.0
            allocation_multiplier = max(0.1, allocation_multiplier)
            entry = trade.entry_price
            invalidation = trade.invalidation_price
            target_1 = trade.target_price_1 or trade.target_price
            target_2 = trade.target_price_2 or target_1

            risk_per_unit = abs(entry - invalidation) if entry is not None and invalidation is not None else None
            reward_tp1 = abs(target_1 - entry) if entry is not None and target_1 is not None else None
            reward_tp2 = abs(target_2 - entry) if entry is not None and target_2 is not None else None
            rr_tp1 = self._safe_div(reward_tp1, risk_per_unit) if reward_tp1 is not None and risk_per_unit is not None else None
            rr_tp2 = self._safe_div(reward_tp2, risk_per_unit) if reward_tp2 is not None and risk_per_unit is not None else None

            position_multiplier = allocation_multiplier if use_position_multiplier else 1.0
            risk_fraction = (
                abs((entry - invalidation) / entry)
                if entry is not None and invalidation is not None and entry > 0
                else None
            )

            if simulation_mode == "fixed_size":
                base_capital = capital_per_trade * fill_count
                effective_capital = base_capital * position_multiplier
                risk_amount_usd = effective_capital * risk_fraction if risk_fraction is not None else None
            elif simulation_mode == "equity_risk_pct":
                risk_budget = equity * max(risk_pct_per_trade, 0.0) / 100
                risk_amount_usd = risk_budget * position_multiplier
                effective_capital = (
                    risk_amount_usd / risk_fraction
                    if risk_fraction is not None and risk_fraction > 0
                    else capital_per_trade * position_multiplier
                )
                base_capital = effective_capital
            else:
                base_risk = risk_per_trade if risk_per_trade is not None and risk_per_trade > 0 else 10.0
                risk_amount_usd = base_risk * position_multiplier
                effective_capital = (
                    risk_amount_usd / risk_fraction
                    if risk_fraction is not None and risk_fraction > 0
                    else capital_per_trade * position_multiplier
                )
                base_capital = effective_capital

            quantity = (effective_capital / entry) if entry and entry > 0 else None

            tp1_reward_usd = quantity * reward_tp1 if quantity is not None and reward_tp1 is not None else None
            tp2_reward_usd = quantity * reward_tp2 if quantity is not None and reward_tp2 is not None else None
            risk_pct_of_capital = self._safe_div(risk_amount_usd * 100, effective_capital) if risk_amount_usd is not None and effective_capital else None

            pnl_pct = float(trade.pnl_pct or 0.0)
            max_profit_pct = float(trade.max_profit_pct or 0.0)
            max_drawdown_pct = float(trade.max_drawdown_pct or 0.0)
            is_closed = trade.result in closed_results
            gross_pnl_usd = effective_capital * (pnl_pct / 100) if effective_capital else 0.0
            fee_usd = effective_capital * (fee_pct / 100) * 2 if effective_capital and is_closed else 0.0
            realized_pnl_usd = gross_pnl_usd - fee_usd
            max_profit_usd = effective_capital * (max_profit_pct / 100) if effective_capital else 0.0
            max_drawdown_usd = effective_capital * (max_drawdown_pct / 100) if effective_capital else 0.0
            realized_r_multiple = self._safe_div(realized_pnl_usd, risk_amount_usd) if risk_amount_usd is not None else None
            allocated_r_multiple = realized_r_multiple
            if is_closed:
                equity += realized_pnl_usd

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
                "simulation_mode": simulation_mode,
                "starting_capital": self._round(starting_capital, 2),
                "base_capital_per_trade": self._round(base_capital, 2),
                "capital_per_trade": self._round(effective_capital, 2),
                "estimated_quantity": self._round(quantity, 8),
                "risk_amount_usd": self._round(risk_amount_usd, 2),
                "fee_usd": self._round(fee_usd, 2),
                "tp1_reward_usd": self._round(tp1_reward_usd, 2),
                "tp2_reward_usd": self._round(tp2_reward_usd, 2),
                "risk_pct_of_capital": self._round(risk_pct_of_capital, 4),
                "pnl_pct": self._round(pnl_pct, 4),
                "realized_pnl_usd": self._round(realized_pnl_usd, 2),
                "realized_r_multiple": self._round(realized_r_multiple, 4),
                "allocated_r_multiple": self._round(allocated_r_multiple, 4),
                "max_profit_pct": self._round(max_profit_pct, 4),
                "max_profit_usd": self._round(max_profit_usd, 2),
                "max_drawdown_pct": self._round(max_drawdown_pct, 4),
                "max_drawdown_usd": self._round(max_drawdown_usd, 2),
                "equity_after_trade": self._round(equity, 2),
                "engine_tag": getattr(trade, "engine_tag", None),
                "strategy_version": entry_features.get("strategy_version", "unknown") if entry_features else "unknown",
                "position_size_multiplier": self._round(allocation_multiplier, 4),
            }
            if entry_features:
                for key, value in entry_features.items():
                    if isinstance(value, (int, float, bool, str)):
                        row[f"feat_{key}"] = value
            rows.append(row)
        rows.sort(key=lambda row: str(row.get("created_at", "")), reverse=True)
        return rows

    @staticmethod
    def _row_float(row: dict[str, object], key: str, default: float = 0.0) -> float:
        value = row.get(key)
        if isinstance(value, (int, float)):
            return float(value)
        try:
            return float(value) if value is not None else default
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _is_closed_row(row: dict[str, object]) -> bool:
        return row.get("result") != "open"

    def _build_breakdown(self, rows: list[dict[str, object]], key: str) -> list[dict[str, object]]:
        grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in rows:
            group_key = str(row.get(key) or "Unknown")
            grouped[group_key].append(row)

        items: list[dict[str, object]] = []
        for group_key, group_rows in grouped.items():
            closed_rows = [row for row in group_rows if self._is_closed_row(row)]
            wins = sum(1 for row in closed_rows if row.get("result") == "win")
            losses = sum(1 for row in closed_rows if row.get("result") == "loss")
            breakevens = sum(1 for row in closed_rows if row.get("result") == "breakeven")
            timeouts = sum(1 for row in closed_rows if row.get("result") == "timeout")
            pnl_values = [self._row_float(row, "realized_pnl_usd") for row in closed_rows]
            r_values = [
                self._row_float(row, "realized_r_multiple")
                for row in closed_rows
                if row.get("realized_r_multiple") is not None
            ]
            gross_profit = sum(value for value in pnl_values if value > 0)
            gross_loss = sum(value for value in pnl_values if value < 0)
            decisive = wins + losses
            closed_count = len(closed_rows)
            items.append(
                {
                    "key": group_key,
                    "total_trades": len(group_rows),
                    "closed_trades": closed_count,
                    "open_trades": len(group_rows) - closed_count,
                    "wins": wins,
                    "losses": losses,
                    "breakevens": breakevens,
                    "timeouts": timeouts,
                    "winrate": round((wins / decisive * 100) if decisive else 0.0, 2),
                    "net_pnl_usd": round(sum(pnl_values), 2),
                    "expectancy_usd": round(sum(pnl_values) / closed_count, 2) if closed_count else 0.0,
                    "profit_factor": round(gross_profit / abs(gross_loss), 4) if gross_loss < 0 else None,
                    "avg_r_multiple": round(sum(r_values) / len(r_values), 4) if r_values else None,
                }
            )

        return sorted(items, key=lambda item: (float(item["net_pnl_usd"]), int(item["closed_trades"])), reverse=True)

    def _build_report_summary(self, rows: list[dict[str, object]], *, starting_capital: float) -> dict[str, object]:
        closed_rows = [row for row in rows if self._is_closed_row(row)]
        open_rows = [row for row in rows if row.get("result") == "open"]
        wins = sum(1 for row in closed_rows if row.get("result") == "win")
        losses = sum(1 for row in closed_rows if row.get("result") == "loss")
        breakevens = sum(1 for row in closed_rows if row.get("result") == "breakeven")
        timeouts = sum(1 for row in closed_rows if row.get("result") == "timeout")
        decisive = wins + losses
        pnl_values = [self._row_float(row, "realized_pnl_usd") for row in closed_rows]
        r_values = [
            self._row_float(row, "realized_r_multiple")
            for row in closed_rows
            if row.get("realized_r_multiple") is not None
        ]
        gross_profit = sum(value for value in pnl_values if value > 0)
        gross_loss = sum(value for value in pnl_values if value < 0)
        net_pnl = sum(pnl_values)

        equity = starting_capital
        peak = starting_capital
        max_drawdown_usd = 0.0
        max_drawdown_pct = 0.0
        chronological = sorted(rows, key=lambda row: str(row.get("created_at", "")))
        first_timestamp = chronological[0].get("created_at") if chronological else datetime.now(UTC).isoformat()
        equity_curve: list[dict[str, object]] = [
            {
                "timestamp": str(first_timestamp),
                "equity": self._round(starting_capital, 2),
                "pnl_usd": 0.0,
                "symbol": "START",
                "result": "start",
            }
        ]
        for row in chronological:
            if not self._is_closed_row(row):
                continue
            pnl_usd = self._row_float(row, "realized_pnl_usd")
            equity += pnl_usd
            peak = max(peak, equity)
            drawdown_usd = min(0.0, equity - peak)
            drawdown_pct = (drawdown_usd / peak * 100) if peak > 0 else 0.0
            max_drawdown_usd = min(max_drawdown_usd, drawdown_usd)
            max_drawdown_pct = min(max_drawdown_pct, drawdown_pct)
            equity_curve.append(
                {
                    "timestamp": str(row.get("closed_at") or row.get("updated_at") or row.get("created_at")),
                    "equity": self._round(equity, 2),
                    "pnl_usd": self._round(pnl_usd, 2),
                    "symbol": str(row.get("symbol") or ""),
                    "result": str(row.get("result") or ""),
                }
            )

        close_reason_rows: list[dict[str, object]] = []
        for row in closed_rows:
            cloned = dict(row)
            cloned["close_reason_group"] = row.get("close_reason") or row.get("result") or "Unknown"
            close_reason_rows.append(cloned)

        closed_count = len(closed_rows)
        return {
            "closed_trades": closed_count,
            "open_trades": len(open_rows),
            "wins": wins,
            "losses": losses,
            "breakevens": breakevens,
            "timeouts": timeouts,
            "winrate": round((wins / decisive * 100) if decisive else 0.0, 2),
            "net_pnl_usd": round(net_pnl, 2),
            "roi_pct": round((net_pnl / starting_capital * 100) if starting_capital > 0 else 0.0, 2),
            "expectancy_usd": round(net_pnl / closed_count, 2) if closed_count else 0.0,
            "profit_factor": round(gross_profit / abs(gross_loss), 4) if gross_loss < 0 else None,
            "max_drawdown_usd": round(max_drawdown_usd, 2),
            "max_drawdown_pct": round(max_drawdown_pct, 2),
            "avg_win_usd": round(gross_profit / wins, 2) if wins else 0.0,
            "avg_loss_usd": round(gross_loss / losses, 2) if losses else 0.0,
            "avg_r_multiple": round(sum(r_values) / len(r_values), 4) if r_values else None,
            "equity_curve": equity_curve,
            "by_timeframe": self._build_breakdown(rows, "timeframe"),
            "by_regime": self._build_breakdown(rows, "market_regime"),
            "by_setup": self._build_breakdown(rows, "setup_type"),
            "by_close_reason": self._build_breakdown(close_reason_rows, "close_reason_group"),
        }

    async def export_trade_report_csv(
        self,
        *,
        symbol: str = "ALL",
        timeframe: str = "ALL",
        setup_type: str | None = None,
        regime: str = "ALL",
        result: str = "ALL",
        month: str | None = None,
        search: str | None = None,
        scope: str = "active",
        strategy: str = "v2_balanced",
        simulation_mode: str = "fixed_risk",
        starting_capital: float = 1000.0,
        capital_per_trade: float = 100.0,
        risk_per_trade: float | None = 10.0,
        risk_pct_per_trade: float = 1.0,
        fee_pct: float = 0.0,
        use_position_multiplier: bool = True,
    ) -> str:
        rows = await self._trade_report_rows(
            symbol=symbol,
            timeframe=timeframe,
            setup_type=setup_type,
            regime=regime,
            result=result,
            month=month,
            search=search,
            scope=scope,
            strategy=strategy,
            simulation_mode=simulation_mode,
            starting_capital=starting_capital,
            capital_per_trade=capital_per_trade,
            risk_per_trade=risk_per_trade,
            risk_pct_per_trade=risk_pct_per_trade,
            fee_pct=fee_pct,
            use_position_multiplier=use_position_multiplier,
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
            "simulation_mode",
            "starting_capital",
            "base_capital_per_trade",
            "capital_per_trade",
            "estimated_quantity",
            "risk_amount_usd",
            "fee_usd",
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
            "equity_after_trade",
        ]
        all_keys = set()
        for row in rows:
            all_keys.update(row.keys())
        feature_fields = sorted([k for k in all_keys if k.startswith("feat_")])
        fieldnames = base_fields + feature_fields

        buffer = StringIO()
        writer = csv.DictWriter(
            buffer,
            fieldnames=fieldnames,
            extrasaction='ignore'
        )
        writer.writeheader()
        writer.writerows(rows)

        return buffer.getvalue()

    async def get_trade_report_table(
        self,
        *,
        symbol: str = "ALL",
        timeframe: str = "ALL",
        setup_type: str | None = None,
        regime: str = "ALL",
        result: str = "ALL",
        month: str | None = None,
        search: str | None = None,
        scope: str = "active",
        strategy: str = "v2_balanced",
        simulation_mode: str = "fixed_risk",
        starting_capital: float = 1000.0,
        capital_per_trade: float = 100.0,
        risk_per_trade: float | None = 10.0,
        risk_pct_per_trade: float = 1.0,
        fee_pct: float = 0.0,
        use_position_multiplier: bool = True,
    ) -> PerformanceTradeTableResponse:
        rows = await self._trade_report_rows(
            symbol=symbol,
            timeframe=timeframe,
            setup_type=setup_type,
            regime=regime,
            result=result,
            month=month,
            search=search,
            scope=scope,
            strategy=strategy,
            simulation_mode=simulation_mode,
            starting_capital=starting_capital,
            capital_per_trade=capital_per_trade,
            risk_per_trade=risk_per_trade,
            risk_pct_per_trade=risk_pct_per_trade,
            fee_pct=fee_pct,
            use_position_multiplier=use_position_multiplier,
        )
        summary = self._build_report_summary(rows, starting_capital=starting_capital)
        return PerformanceTradeTableResponse(
            generated_at=datetime.now(UTC),
            symbol=symbol,
            timeframe=timeframe,
            setup_type=setup_type,
            regime=regime,
            result_filter=result,
            month=month,
            search=search,
            scope=scope,
            active_tag=self._active_tag() if scope == "active" else None,
            active_since=self._active_since().isoformat() if scope == "active" and self._active_since() is not None else None,
            strategy=strategy,
            simulation_mode=simulation_mode,
            starting_capital=starting_capital,
            capital_per_trade=capital_per_trade,
            risk_per_trade=risk_per_trade,
            risk_pct_per_trade=risk_pct_per_trade,
            fee_pct=fee_pct,
            use_position_multiplier=use_position_multiplier,
            total_rows=len(rows),
            **summary,
            rows=[PerformanceTradeRow.model_validate(row) for row in rows],
        )

    async def export_trade_report_html(
        self,
        *,
        symbol: str = "ALL",
        timeframe: str = "ALL",
        setup_type: str | None = None,
        regime: str = "ALL",
        result: str = "ALL",
        month: str | None = None,
        search: str | None = None,
        scope: str = "active",
        strategy: str = "v2_balanced",
        simulation_mode: str = "fixed_risk",
        starting_capital: float = 1000.0,
        capital_per_trade: float = 100.0,
        risk_per_trade: float | None = 10.0,
        risk_pct_per_trade: float = 1.0,
        fee_pct: float = 0.0,
        use_position_multiplier: bool = True,
    ) -> str:
        rows = await self._trade_report_rows(
            symbol=symbol,
            timeframe=timeframe,
            setup_type=setup_type,
            regime=regime,
            result=result,
            month=month,
            search=search,
            scope=scope,
            strategy=strategy,
            simulation_mode=simulation_mode,
            starting_capital=starting_capital,
            capital_per_trade=capital_per_trade,
            risk_per_trade=risk_per_trade,
            risk_pct_per_trade=risk_pct_per_trade,
            fee_pct=fee_pct,
            use_position_multiplier=use_position_multiplier,
        )
        summary = self._build_report_summary(rows, starting_capital=starting_capital)

        summary_cards = [
            ("Rows", str(len(rows))),
            ("Closed", str(summary["closed_trades"])),
            ("Open", str(summary["open_trades"])),
            ("Wins / Losses", f"{summary['wins']} / {summary['losses']}"),
            ("Breakevens", str(summary["breakevens"])),
            ("Winrate", f"{summary['winrate']:.2f}%"),
            ("Net PnL", f"${summary['net_pnl_usd']:,.2f}"),
            ("ROI", f"{summary['roi_pct']:.2f}%"),
        ]

        visible_columns = [
            "symbol",
            "timeframe",
            "setup_type",
            "state",
            "bias",
            "status",
            "result",
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
            "planned_rr_tp1",
            "planned_rr_tp2",
            "confidence_pct",
            "quality_score",
            "risk_level",
            "market_regime",
            "volatility_regime",
            "capital_per_trade",
            "estimated_quantity",
            "risk_amount_usd",
            "fee_usd",
            "realized_pnl_usd",
            "realized_r_multiple",
            "pnl_pct",
        ]
        filterable_columns = [
            "symbol",
            "timeframe",
            "setup_type",
            "state",
            "bias",
            "status",
            "result",
        ]

        header_map = {
            "symbol": "Symbol",
            "timeframe": "TF",
            "setup_type": "Setup",
            "state": "State",
            "bias": "Bias",
            "status": "Status",
            "result": "Result",
            "signal_timestamp": "Signal Time",
            "created_at": "Recorded",
            "entry_touched_at": "Entry Touched",
            "fill_count": "Fills",
            "last_scale_in_at": "Last Add",
            "closed_at": "Closed At",
            "close_reason": "Close Reason",
            "updated_at": "Updated At",
            "entry_price": "Entry",
            "invalidation_price": "Stop",
            "target_price_1": "TP1",
            "target_price_2": "TP2",
            "planned_rr_tp1": "RR TP1",
            "planned_rr_tp2": "RR TP2",
            "confidence_pct": "Conf %",
            "quality_score": "Quality",
            "risk_level": "Risk",
            "market_regime": "Regime",
            "volatility_regime": "Vol",
            "capital_per_trade": "Notional",
            "estimated_quantity": "Qty",
            "risk_amount_usd": "Risk $",
            "fee_usd": "Fee",
            "realized_pnl_usd": "Realized $",
            "realized_r_multiple": "R-Multiple",
            "pnl_pct": "PnL %",
        }
        filter_options = {
            column: sorted(
                {
                    str(row[column]).strip()
                    for row in rows
                    if row.get(column) is not None and str(row[column]).strip()
                }
            )
            for column in filterable_columns
        }

        table_rows = []
        for row in rows:
            cells = []
            for column in visible_columns:
                value = row[column]
                if isinstance(value, float):
                    if column in {"estimated_quantity"}:
                        rendered = self._display(value, 6)
                    elif column in {"pnl_pct"}:
                        rendered = f"{value:.2f}%"
                    elif column in {"planned_rr_tp1", "planned_rr_tp2", "realized_r_multiple"}:
                        rendered = self._display(value, 2)
                    else:
                        rendered = self._display(value, 4)
                else:
                    rendered = self._display(value)
                cells.append(f"<td>{html.escape(rendered)}</td>")
            row_attrs = " ".join(
                f'data-{column}="{html.escape(str(row.get(column, "")).strip().lower())}"'
                for column in filterable_columns
            )
            table_rows.append(f"<tr {row_attrs}>" + "".join(cells) + "</tr>")

        summary_html = "".join(
            f"""
            <div class="card">
              <div class="label">{html.escape(label)}</div>
              <div class="value">{html.escape(value)}</div>
            </div>
            """
            for label, value in summary_cards
        )
        filters_html = "".join(
            f"""
            <label class="filter-item">
              <span>{html.escape(header_map[column])}</span>
              <select id="filter-{html.escape(column)}" data-column="{html.escape(column)}">
                <option value="">All</option>
                {"".join(
                    f'<option value="{html.escape(option.lower())}">{html.escape(option)}</option>'
                    for option in filter_options[column]
                )}
              </select>
            </label>
            """
            for column in filterable_columns
        )
        table_header_html = "".join(f"<th>{html.escape(header_map[column])}</th>" for column in visible_columns)
        table_body_html = "".join(table_rows)
        empty_row_html = f'<tr id="no-rows"><td colspan="{len(visible_columns)}" class="empty">No trades match the active filters.</td></tr>'
        initial_visible_count = len(rows)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>FlowScope Performance Report</title>
  <style>
    body {{
      font-family: Arial, sans-serif;
      background: #0b1020;
      color: #e5e7eb;
      margin: 0;
      padding: 24px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 28px;
    }}
    p {{
      margin: 0;
      color: #94a3b8;
    }}
    .meta {{
      margin-top: 8px;
      font-size: 14px;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      gap: 12px;
      margin: 24px 0;
    }}
    .card {{
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 14px;
      background: #111827;
      padding: 14px 16px;
    }}
    .label {{
      color: #94a3b8;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 6px;
    }}
    .value {{
      font-size: 22px;
      font-weight: 700;
      color: #f8fafc;
    }}
    .table-wrap {{
      overflow-x: auto;
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 16px;
      background: #111827;
    }}
    .filters {{
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 16px;
      background: #111827;
      padding: 16px;
      margin: 0 0 18px;
    }}
    .filters-head {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 14px;
      flex-wrap: wrap;
    }}
    .filters-title {{
      font-size: 16px;
      font-weight: 700;
      color: #f8fafc;
    }}
    .filters-meta {{
      font-size: 13px;
      color: #94a3b8;
    }}
    .filter-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 12px;
    }}
    .filter-item {{
      display: flex;
      flex-direction: column;
      gap: 6px;
      font-size: 12px;
      color: #94a3b8;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}
    .filter-item select {{
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 10px;
      background: #0f172a;
      color: #f8fafc;
      padding: 10px 12px;
      font-size: 13px;
      outline: none;
    }}
    .filter-actions {{
      display: flex;
      justify-content: flex-end;
      margin-top: 14px;
    }}
    .filter-reset {{
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 10px;
      background: rgba(255,255,255,0.04);
      color: #e5e7eb;
      padding: 10px 14px;
      font-size: 13px;
      cursor: pointer;
    }}
    .filter-reset:hover {{
      background: rgba(255,255,255,0.08);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 1500px;
    }}
    th, td {{
      padding: 12px 14px;
      border-bottom: 1px solid rgba(255,255,255,0.06);
      text-align: left;
      white-space: nowrap;
      font-size: 13px;
    }}
    th {{
      position: sticky;
      top: 0;
      background: #172036;
      color: #cbd5e1;
      text-transform: uppercase;
      font-size: 11px;
      letter-spacing: 0.06em;
    }}
    tr:nth-child(even) td {{
      background: rgba(255,255,255,0.015);
    }}
    .empty {{
      text-align: center;
      color: #94a3b8;
      padding: 24px;
    }}
  </style>
</head>
<body>
  <h1>FlowScope Performance Report</h1>
  <p>Readable trade table with RR, modal per trade, quantity, and realized dollar performance.</p>
  <p class="meta">Generated at: {html.escape(datetime.now(UTC).isoformat())} | Symbol: {html.escape(symbol)} | Timeframe: {html.escape(timeframe)} | Setup: {html.escape(setup_type or "ALL")} | Regime: {html.escape(regime)} | Result: {html.escape(result)} | Month: {html.escape(month or "ALL")} | Scope: {html.escape(scope)} | Strategy: {html.escape(strategy)} | Simulation: {html.escape(simulation_mode)}</p>
  <div class="summary">{summary_html}</div>
  <div class="filters">
    <div class="filters-head">
      <div class="filters-title">Table Filters</div>
      <div id="filter-summary" class="filters-meta">{initial_visible_count} / {initial_visible_count} rows visible</div>
    </div>
    <div class="filter-grid">
      {filters_html}
    </div>
    <div class="filter-actions">
      <button id="reset-filters" class="filter-reset" type="button">Reset Filters</button>
    </div>
  </div>
  <div class="table-wrap">
    <table>
      <thead>
        <tr>{table_header_html}</tr>
      </thead>
      <tbody>{table_body_html}{empty_row_html}</tbody>
    </table>
  </div>
  <script>
    const filterColumns = {json.dumps(filterable_columns)};
    const tableRows = Array.from(document.querySelectorAll("tbody tr[data-symbol]"));
    const noRows = document.getElementById("no-rows");
    const summary = document.getElementById("filter-summary");

    function applyFilters() {{
      let visible = 0;
      for (const row of tableRows) {{
        let show = true;
        for (const column of filterColumns) {{
          const control = document.getElementById(`filter-${{column}}`);
          const selected = control ? control.value : "";
          if (selected && row.dataset[column] !== selected) {{
            show = false;
            break;
          }}
        }}
        row.style.display = show ? "" : "none";
        if (show) {{
          visible += 1;
        }}
      }}

      if (noRows) {{
        noRows.style.display = visible === 0 ? "" : "none";
      }}
      if (summary) {{
        summary.textContent = `${{visible}} / ${{tableRows.length}} rows visible`;
      }}
    }}

    for (const column of filterColumns) {{
      const control = document.getElementById(`filter-${{column}}`);
      if (control) {{
        control.addEventListener("change", applyFilters);
      }}
    }}

    const resetButton = document.getElementById("reset-filters");
    if (resetButton) {{
      resetButton.addEventListener("click", () => {{
        for (const column of filterColumns) {{
          const control = document.getElementById(`filter-${{column}}`);
          if (control) {{
            control.value = "";
          }}
        }}
        applyFilters();
      }});
    }}

    applyFilters();
  </script>
</body>
</html>"""

    async def compute(self, *, scope: str = "active", strategy: str = "v2_balanced") -> PerformanceResponse | None:
        if not self.database.enabled:
            return None

        trades = await self._filtered_trades(scope=scope, strategy=strategy)
        grouped_all: dict[str, list] = {}
        for trade in trades:
            grouped_all.setdefault(trade.setup_type, []).append(trade)

        closed = [trade for trade in trades if trade.result in ("win", "loss")]
        if not trades:
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
