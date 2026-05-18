# Quick Start: V3 SuperTrend Optimization

## Install Dependencies

```powershell
cd C:\Code\flowscope
pip install -r requirements.txt
```

## Run Optimization

### Default Settings (50 trials, 7 days) ⭐ RECOMMENDED

```powershell
python scripts\optimize_v3_supertrend.py
```

### Custom Settings

```powershell
# More data, more trials (production)
python scripts\optimize_v3_supertrend.py --days 14 --trials 100

# Quick test (NOT for final results)
python scripts\optimize_v3_supertrend.py --days 3 --trials 20
```

## Output

1. **Terminal**: Summary table dengan best parameters
2. **File**: `export/v3_supertrend_best_params.json`

## Parameters

### Optimized (Optuna)

| Parameter | Range | Step | Default |
|-----------|-------|------|---------|
| SuperTrend ATR | 7–21 | 1 | - |
| SuperTrend Multiplier | 1.5–4.0 | 0.1 | - |
| AI Score Threshold | 50–80 | 1 | - |
| Risk-Reward Ratio | 1.5–3.5 | 0.2 | - |

### Fixed (V3 EMA Trial 24)

- OI Delta Z: 0.897
- Volume Z: 1.707
- Flow Alignment: 0.874
- Compression: 0.441
- History (1h): 67
- Confidence: 0.806
- Price Break: 0.037
- EMA 30/100: ✅ Active

## Filters (TIMEFRAME-ADAPTIVE)

### SuperTrend

```python
# Calculated on SIGNAL'S timeframe (not hardcoded 15m)
Entry only if signal direction matches SuperTrend:
Bullish → SuperTrend = 1
Bearish → SuperTrend = -1
```

### AI Score

```python
# Computed from MarketDataBucket breakdown fields
AI Score = 0.35×Flow + 0.25×Structure + 0.20×Volume + 0.20×OI
Entry only if AI Score ≥ threshold (0-100 scale)
```

### EMA 30/100

```python
# Calculated on SIGNAL'S timeframe
Bullish → EMA30 > EMA100
Bearish → EMA30 < EMA100
```

### RR Ratio (Dynamic TP/SL)

```python
# Used to calculate Take Profit level
TP = Entry ± (RR × Risk)
SL = Invalidation Price
```

## Expected Runtime

| Configuration | Runtime | Quality |
|---------------|---------|---------|
| **50 trials, 7 days** | ~15-25 min | ⭐⭐⭐⭐⭐ **Optimal** |
| 30 trials, 5 days | ~8-12 min | ⭐⭐⭐⭐ Good |
| 20 trials, 3 days | ~3-5 min | ⭐⭐⭐ Quick test |

## Troubleshooting

### No symbols loaded

```powershell
# Check database
psql -U postgres -d flowscope_db -c "SELECT COUNT(*) FROM market_data_buckets;"
```

### Missing optuna

```powershell
pip install optuna
```

### Slow optimization

Reduce trials (not recommended for final results):

```powershell
python scripts\optimize_v3_supertrend.py --trials 30 --days 5
```

### Profit Factor = 0 or inf

- No trades pass filters → Lower `ai_threshold`
- All trades win → Increase data or trials
- All trades lose → Check V3 parameters or filters too strict

## Next Steps

After optimization:

1. Review best parameters in `export/v3_supertrend_best_params.json`
2. Backtest dengan parameter baru
3. Compare dengan baseline V3 EMA
4. Validate out-of-sample performance

## Key Improvements (NEW vs OLD)

| Feature | OLD | NEW |
|---------|-----|-----|
| entry_features source | From trade (often None) | From MarketDataBucket ✅ |
| SuperTrend timeframe | Hardcoded 15m | Signal's timeframe ✅ |
| rr_ratio usage | Not used | Dynamic TP/SL ✅ |
| AI Score calculation | From trade data | From bucket metrics ✅ |
| Default trials | 25 | 50 ✅ |
