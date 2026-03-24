from __future__ import annotations

from datetime import UTC, datetime

from backend.database import DatabaseManager
from backend.schemas import ConditionPerformance, PerformanceResponse, RegimePerformance, SetupPerformance


class PerformanceEngine:
    def __init__(self, database: DatabaseManager) -> None:
        self.database = database

    async def compute(self) -> PerformanceResponse | None:
        if not self.database.enabled:
            return None

        trades = await self.database.list_trade_signals()
        closed = [trade for trade in trades if trade.result in ("win", "loss")]
        if not closed:
            return PerformanceResponse(
                generated_at=datetime.now(UTC),
                total_trades=0,
                winrate=0.0,
                expectancy=0.0,
                best_setup=None,
                worst_setup=None,
                setups=[],
            )

        total = len(closed)
        wins = [trade for trade in closed if trade.result == "win"]
        losses = [trade for trade in closed if trade.result == "loss"]
        winrate = len(wins) / total if total else 0.0
        avg_win = sum(trade.pnl_pct for trade in wins) / len(wins) if wins else 0.0
        avg_loss = abs(sum(trade.pnl_pct for trade in losses) / len(losses)) if losses else 0.0
        expectancy = (winrate * avg_win) - ((1 - winrate) * avg_loss)

        grouped: dict[str, list] = {}
        for trade in closed:
            grouped.setdefault(trade.setup_type, []).append(trade)

        setups: list[SetupPerformance] = []
        for setup_type, trades_for_type in grouped.items():
            wins_t = [trade for trade in trades_for_type if trade.result == "win"]
            losses_t = [trade for trade in trades_for_type if trade.result == "loss"]
            total_t = len(trades_for_type)
            winrate_t = len(wins_t) / total_t if total_t else 0.0
            avg_win_t = sum(trade.pnl_pct for trade in wins_t) / len(wins_t) if wins_t else 0.0
            avg_loss_t = abs(sum(trade.pnl_pct for trade in losses_t) / len(losses_t)) if losses_t else 0.0
            expectancy_t = (winrate_t * avg_win_t) - ((1 - winrate_t) * avg_loss_t)
            rr_ratio = avg_win_t / avg_loss_t if avg_loss_t else 0.0
            setups.append(
                SetupPerformance(
                    setup_type=setup_type,
                    state=None,
                    trades=total_t,
                    winrate=round(winrate_t, 4),
                    avg_win=round(avg_win_t, 4),
                    avg_loss=round(avg_loss_t, 4),
                    rr_ratio=round(rr_ratio, 4),
                    expectancy=round(expectancy_t, 4),
                    validated=total_t >= 20 and expectancy_t > 0,
                )
            )

        best_setup = max(setups, key=lambda item: item.expectancy, default=None)
        worst_setup = min(setups, key=lambda item: item.expectancy, default=None)

        regime_grouped: dict[str, list] = {}
        for trade in closed:
            regime_grouped.setdefault(trade.market_regime or "Balanced", []).append(trade)

        regimes: list[RegimePerformance] = []
        for regime, trades_for_regime in regime_grouped.items():
            wins_r = [trade for trade in trades_for_regime if trade.result == "win"]
            losses_r = [trade for trade in trades_for_regime if trade.result == "loss"]
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
