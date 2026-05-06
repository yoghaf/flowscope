"""
Binance Demo Trading Module
Connects to Binance Testnet for paper trading with real market data.
"""

from .binance_client import BinanceTestnetClient
from .demo_execution_engine import DemoExecutionEngine

__all__ = ["BinanceTestnetClient", "DemoExecutionEngine"]
