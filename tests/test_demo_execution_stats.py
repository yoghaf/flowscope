from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from backend.services.binance_demo.demo_execution_engine import DemoExecutionEngine


def make_engine() -> DemoExecutionEngine:
    engine = DemoExecutionEngine(
        client=SimpleNamespace(),
        database=SimpleNamespace(enabled=False),
        settings=SimpleNamespace(default_symbols=[]),
    )
    engine.started_at = datetime(2026, 5, 7, 1, 0, tzinfo=timezone.utc)
    return engine


def test_demo_stats_wait_for_final_close_after_partial_tp() -> None:
    engine = make_engine()
    engine._start_position_qty = {"BNBUSDT": 100.0}

    stats = engine._summarize_position_cycles(
        fills=[
            {
                "id": 1,
                "symbol": "BNBUSDT",
                "side": "SELL",
                "qty": 50,
                "realizedPnl": 10,
                "time": 1_770_000_000_000,
            },
        ],
        open_positions=1,
    )

    assert stats["total_trades"] == 0
    assert stats["partial_closes"] == 1
    assert stats["winning_trades"] == 0
    assert stats["winrate"] == 0.0


def test_demo_stats_combines_partial_tp_and_final_close_into_one_trade() -> None:
    engine = make_engine()
    engine._start_position_qty = {"BNBUSDT": 100.0}

    stats = engine._summarize_position_cycles(
        fills=[
            {
                "id": 1,
                "symbol": "BNBUSDT",
                "side": "SELL",
                "qty": 50,
                "realizedPnl": 10,
                "time": 1_770_000_000_000,
            },
            {
                "id": 2,
                "symbol": "BNBUSDT",
                "side": "SELL",
                "qty": 50,
                "realizedPnl": -2,
                "time": 1_770_000_010_000,
            },
        ],
        open_positions=0,
    )

    assert stats["total_trades"] == 1
    assert stats["partial_closes"] == 1
    assert stats["winning_trades"] == 1
    assert stats["losing_trades"] == 0
    assert stats["realized_pnl"] == 8
    assert stats["winrate"] == 100.0


def test_demo_stats_counts_complete_round_trip_loss() -> None:
    engine = make_engine()

    stats = engine._summarize_position_cycles(
        fills=[
            {
                "id": 1,
                "symbol": "ETCUSDT",
                "side": "BUY",
                "qty": 10,
                "realizedPnl": 0,
                "time": 1_770_000_000_000,
            },
            {
                "id": 2,
                "symbol": "ETCUSDT",
                "side": "SELL",
                "qty": 10,
                "realizedPnl": -5,
                "time": 1_770_000_010_000,
            },
        ],
        open_positions=0,
    )

    assert stats["total_trades"] == 1
    assert stats["winning_trades"] == 0
    assert stats["losing_trades"] == 1
    assert stats["winrate"] == 0.0


class FakeDemoClient:
    def __init__(self, *, current_price: float = 100.0, balance: float = 1000.0) -> None:
        self.orders: list[dict[str, object]] = []
        self.cancelled_orders: list[tuple[str, int]] = []
        self.current_price = current_price
        self.balance = balance

    async def get_full_state(self) -> dict[str, object]:
        return {
            "account": {
                "available_balance": self.balance,
                "wallet_balance": self.balance,
                "total_unrealized_pnl": 0.0,
                "margin_balance": self.balance,
            },
            "positions": [],
        }

    async def get_current_price(self, symbol: str) -> float:
        return self.current_price

    async def place_order(self, **kwargs: object) -> dict[str, object]:
        self.orders.append(dict(kwargs))
        order_type = kwargs["order_type"]
        return {
            "order_id": len(self.orders),
            "symbol": kwargs["symbol"],
            "side": kwargs["side"],
            "type": order_type,
            "quantity": kwargs["quantity"],
            "price": kwargs.get("price") or 0.0,
            "avg_price": self.current_price if order_type == "MARKET" else 0.0,
            "status": "FILLED" if order_type == "MARKET" else "NEW",
        }

    async def get_open_orders(self, symbol: str | None = None) -> list[dict[str, object]]:
        return [
            {
                "orderId": index + 1,
                "symbol": order["symbol"],
                "type": order["order_type"],
                "status": "NEW",
            }
            for index, order in enumerate(self.orders)
            if order["order_type"] == "LIMIT"
        ]

    async def _round_quantity(self, symbol: str, quantity: float) -> float:
        return round(quantity, 3)

    async def cancel_order(self, symbol: str, order_id: int) -> dict[str, object]:
        self.cancelled_orders.append((symbol, order_id))
        return {"success": True, "order_id": order_id, "status": "CANCELED"}


def test_demo_execute_signal_uses_fixed_risk_and_places_protection() -> None:
    client = FakeDemoClient()
    engine = DemoExecutionEngine(
        client=client,
        database=SimpleNamespace(enabled=False),
        settings=SimpleNamespace(default_symbols=[]),
    )
    engine.running = True
    engine.session_id = "demo_test"

    import asyncio

    result = asyncio.run(
        engine.execute_signal(
            symbol="BNBUSDT",
            signal_type="Continuation",
            bias="Bullish",
            setup_type="Continuation",
            confidence=0.8,
            entry_price=100.0,
            stop_loss=95.0,
            take_profit_1=105.0,
            take_profit_2=110.0,
            risk_usdt=10.0,
            max_entry_drift_pct=15.0,
            max_market_tp1_progress_pct=30.0,
            max_pullback_tp1_progress_pct=60.0,
            tp1_close_pct=50.0,
        )
    )

    assert result["success"] is True
    assert result["quantity"] == 2.0
    assert result["protected"] is True
    assert len(client.orders) == 4
    assert client.orders[0]["order_type"] == "MARKET"
    assert client.orders[0]["quantity"] == 2.0
    assert client.orders[1]["order_type"] == "STOP_MARKET"
    assert client.orders[1]["quantity"] == 2.0
    assert client.orders[1]["reduce_only"] is True
    assert client.orders[2]["order_type"] == "TAKE_PROFIT_MARKET"
    assert client.orders[2]["quantity"] == 1.0
    assert client.orders[3]["order_type"] == "TAKE_PROFIT_MARKET"
    assert client.orders[3]["quantity"] == 1.0


def test_demo_execute_signal_places_pullback_limit_when_market_drift_too_far() -> None:
    client = FakeDemoClient(current_price=100.1, balance=5000.0)
    engine = DemoExecutionEngine(
        client=client,
        database=SimpleNamespace(enabled=False),
        settings=SimpleNamespace(default_symbols=[]),
    )
    engine.running = True
    engine.session_id = "demo_test"

    import asyncio

    result = asyncio.run(
        engine.execute_signal(
            symbol="BNBUSDT",
            signal_type="Continuation",
            bias="Bullish",
            setup_type="Continuation",
            confidence=0.8,
            entry_price=100.0,
            stop_loss=99.5,
            take_profit_1=100.4,
            take_profit_2=100.8,
            risk_usdt=10.0,
            max_entry_drift_pct=15.0,
            max_market_tp1_progress_pct=30.0,
            max_pullback_tp1_progress_pct=60.0,
            tp1_close_pct=50.0,
        )
    )

    assert result["success"] is True
    assert result["pending"] is True
    assert result["quantity"] == 20.0
    assert len(client.orders) == 1
    assert client.orders[0]["order_type"] == "LIMIT"
    assert client.orders[0]["price"] == 100.0
    assert engine._pending_entries["BNBUSDT"]["order_id"] == 1


def test_demo_execute_signal_rejects_when_pullback_tp1_progress_too_far() -> None:
    client = FakeDemoClient(current_price=100.28, balance=5000.0)
    engine = DemoExecutionEngine(
        client=client,
        database=SimpleNamespace(enabled=False),
        settings=SimpleNamespace(default_symbols=[]),
    )
    engine.running = True
    engine.session_id = "demo_test"

    import asyncio

    result = asyncio.run(
        engine.execute_signal(
            symbol="BNBUSDT",
            signal_type="Continuation",
            bias="Bullish",
            setup_type="Continuation",
            confidence=0.8,
            entry_price=100.0,
            stop_loss=99.5,
            take_profit_1=100.4,
            take_profit_2=100.8,
            risk_usdt=10.0,
            max_entry_drift_pct=15.0,
            max_market_tp1_progress_pct=30.0,
            max_pullback_tp1_progress_pct=60.0,
            tp1_close_pct=50.0,
        )
    )

    assert result["success"] is False
    assert "TP1 progress" in result["error"]
    assert client.orders == []


def test_demo_pending_pullback_limit_cancels_when_tp1_progress_expires() -> None:
    client = FakeDemoClient(current_price=100.28, balance=5000.0)
    engine = DemoExecutionEngine(
        client=client,
        database=SimpleNamespace(enabled=False),
        settings=SimpleNamespace(default_symbols=[]),
    )
    engine._pending_entries["BNBUSDT"] = {
        "symbol": "BNBUSDT",
        "order_id": 7,
        "bias": "Bullish",
        "entry_price": 100.0,
        "stop_loss": 99.5,
        "take_profit_1": 100.4,
        "max_pullback_tp1_progress_pct": 60.0,
    }

    import asyncio

    asyncio.run(engine._reconcile_pending_entries([]))

    assert engine._pending_entries == {}
    assert client.cancelled_orders == [("BNBUSDT", 7)]
