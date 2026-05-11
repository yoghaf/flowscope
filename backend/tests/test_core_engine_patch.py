import pytest
from datetime import datetime, timezone
import math

from backend.schemas import EntryTriggerType
from backend.engines.execution_engine import TradeGeometryValidator
from backend.services.trade_evaluator import is_entry_triggered

def test_trade_geometry_validator_long():
    # SL < Entry < TP1 < TP2
    is_valid, reason = TradeGeometryValidator.validate(side=1, entry=100.0, sl=90.0, tp1=110.0, tp2=120.0)
    assert is_valid is True
    
    # Invalid: SL > Entry
    is_valid, reason = TradeGeometryValidator.validate(side=1, entry=100.0, sl=105.0, tp1=110.0, tp2=120.0)
    assert is_valid is False
    assert reason == "ENTRY_REJECTED_GEOMETRY_LONG_INVALID"

def test_trade_geometry_validator_short():
    # TP2 < TP1 < Entry < SL
    is_valid, reason = TradeGeometryValidator.validate(side=-1, entry=100.0, sl=110.0, tp1=90.0, tp2=80.0)
    assert is_valid is True
    
    # Invalid: TP1 > Entry
    is_valid, reason = TradeGeometryValidator.validate(side=-1, entry=100.0, sl=110.0, tp1=105.0, tp2=80.0)
    assert is_valid is False
    assert reason == "ENTRY_REJECTED_GEOMETRY_SHORT_INVALID"

def test_trade_geometry_validator_nan_inf():
    is_valid, reason = TradeGeometryValidator.validate(side=1, entry=100.0, sl=math.nan, tp1=110.0, tp2=120.0)
    assert is_valid is False
    assert reason == "ENTRY_REJECTED_GEOMETRY_INVALID_VALUES"

def test_is_entry_triggered_market():
    triggered, reason = is_entry_triggered(side=1, trigger_type="MARKET_TRIGGER", high_price=105.0, low_price=95.0, entry_price=100.0)
    assert triggered is False
    assert reason == "ENTRY_REJECTED_INVALID_MARKET_TRIGGER_STATE"

def test_is_entry_triggered_long_breakout():
    # BREAKOUT_STOP: trigger when high_price >= entry_price
    triggered, reason = is_entry_triggered(side=1, trigger_type="BREAKOUT_STOP", high_price=99.0, low_price=95.0, entry_price=100.0)
    assert triggered is False
    
    triggered, reason = is_entry_triggered(side=1, trigger_type="BREAKOUT_STOP", high_price=101.0, low_price=95.0, entry_price=100.0)
    assert triggered is True
    assert reason == "ENTRY_TRIGGERED_BREAKOUT_STOP"

def test_is_entry_triggered_short_pullback():
    # PULLBACK_LIMIT: trigger when high_price >= entry_price
    triggered, reason = is_entry_triggered(side=-1, trigger_type="PULLBACK_LIMIT", high_price=99.0, low_price=95.0, entry_price=100.0)
    assert triggered is False
    
    triggered, reason = is_entry_triggered(side=-1, trigger_type="PULLBACK_LIMIT", high_price=101.0, low_price=95.0, entry_price=100.0)
    assert triggered is True
    assert reason == "ENTRY_TRIGGERED_PULLBACK_LIMIT"
