from dataclasses import dataclass, field
from datetime import datetime, UTC
from typing import Dict, Any

@dataclass
class PortfolioState:
    open_positions: Dict[str, float] = field(default_factory=dict) # symbol -> risk in R (float)
    total_risk_exposure: float = 0.0
    loss_streak: int = 0
    daily_pnl_r: float = 0.0
    current_day: str = "" # To track day resets
    correlation_map: Dict[str, str] = field(default_factory=dict) # symbol -> cluster

class PortfolioManager:
    """Global State Manager for Portfolio-level Risk Control"""
    
    def __init__(self, max_concurrent_risk: float = 3.0, max_daily_dd: float = -3.0):
        self.state = PortfolioState()
        self.MAX_CONCURRENT_RISK = max_concurrent_risk
        self.MAX_DAILY_DD = max_daily_dd

    def check_new_day(self, current_time: datetime) -> None:
        """Resets the daily PnL ledger if rolling into a new day."""
        day_str = current_time.strftime("%Y-%m-%d")
        if self.state.current_day != day_str:
            self.state.current_day = day_str
            self.state.daily_pnl_r = 0.0

    def get_global_size_multiplier(self) -> float:
        """Modulate position sizing dynamically based on consecutive loss streaks."""
        if self.state.loss_streak >= 5:
            return 0.5
        elif self.state.loss_streak >= 3:
            return 0.7
        return 1.0

    def assess_entry(self, symbol: str, current_time: datetime, intended_risk_r: float = 1.0) -> tuple[bool, str, float]:
        """
        Validates if a new trade is allowed under portfolio rules.
        Returns: (allowed, block_reason, finalized_size_multiplier)
        """
        self.check_new_day(current_time)

        # Rule 3: Daily Drawdown Guard
        if self.state.daily_pnl_r <= self.MAX_DAILY_DD:
            return False, "daily_drawdown_limit_reached", 0.0

        # Rule 1: Max Concurrent Risk
        if self.state.total_risk_exposure + intended_risk_r > self.MAX_CONCURRENT_RISK + 0.001:
            return False, "max_concurrent_risk_exceeded", 0.0

        # Rule 4: Correlation Block (Basic mock logic)
        cluster = self.state.correlation_map.get(symbol, "Unknown")
        cluster_count = sum(
            1 for active_sym in self.state.open_positions.keys()
            if self.state.correlation_map.get(active_sym, "Unknown") == cluster and cluster != "Unknown"
        )
        if cluster_count >= 2:
            return False, "correlation_cluster_limit_exceeded", 0.0

        # Rule 2: Finalize Size Multiplier
        global_multiplier = self.get_global_size_multiplier()

        return True, "", global_multiplier

    def register_entry(self, symbol: str, risk_r: float = 1.0) -> None:
        """Called when execution engine commits an entry."""
        self.state.open_positions[symbol] = risk_r
        self.state.total_risk_exposure = sum(self.state.open_positions.values())

    def register_exit(self, symbol: str, pnl_r: float, current_time: datetime) -> None:
        """Called when execution engine exits a trade."""
        self.check_new_day(current_time)

        # Update Exposure Ledger
        if symbol in self.state.open_positions:
            del self.state.open_positions[symbol]
        self.state.total_risk_exposure = sum(self.state.open_positions.values())

        # Update PnL Tracking
        self.state.daily_pnl_r += pnl_r
        
        # Loss Streak Tracking
        if pnl_r < 0:
            self.state.loss_streak += 1
        elif pnl_r > 0:
            self.state.loss_streak = 0
        # Breakeven trades (pnl_r == 0) typically do not reset the streak unless intended.
