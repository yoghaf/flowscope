# V3 SuperTrend + AI Score Optimization

## Overview

Script optimasi untuk strategi V3 EMA dengan tambahan filter SuperTrend dan AI Score menggunakan Optuna.

**OPTIMIZED FEATURES:**
- ✅ rr_ratio digunakan untuk menghitung TP/SL secara dinamis
- ✅ entry_features dihitung langsung dari bucket data
- ✅ SuperTrend dicek pada timeframe sinyal (bukan hanya 15m)
- ✅ AI Score dihitung dari metrik bucket yang sebenarnya
- ✅ 50 trials untuk konvergensi lebih baik

## Parameter

### Tetap (V3 EMA Trial 24)

- `oi_z`: 0.897 - Minimum OI Delta Z-Score
- `vol_z`: 1.707 - Minimum Volume Z-Score
- `flow`: 0.874 - Minimum Flow Alignment
- `comp`: 0.441 - Maximum Compression Score
- `hist`: 67 - Minimum History Length (1h)
- `conf`: 0.806 - Minimum Clarity Confidence
- `p_break`: 0.037 - Price Break threshold (1h)
- **EMA 30/100 filter**: Aktif

### Dioptimasi (Optuna)

| Parameter | Range | Step | Keterangan |
|-----------|-------|------|------------|
| `supertrend_atr` | 7–21 | 1 | ATR period untuk SuperTrend |
| `supertrend_mult` | 1.5–4.0 | 0.1 | Multiplier untuk SuperTrend |
| `ai_threshold` | 50–80 | 1 | Threshold AI Score (0-100) |
| `rr_ratio` | 1.5–3.5 | 0.2 | Risk-Reward ratio untuk TP/SL |

## Filter Baru (Dioptimasi)

### 1. SuperTrend Filter

**TIMEFRAME-ADAPTIVE:** SuperTrend dihitung pada timeframe sinyal, bukan hardcoded 15m.

```python
# SuperTrend Calculation
ATR = Moving Average True Range (period=supertrend_atr)
Upper Band = (High + Low)/2 + supertrend_mult × ATR
Lower Band = (High + Low)/2 - supertrend_mult × ATR

Direction:
- Close > Previous SuperTrend → Bullish (1)
- Close < Previous SuperTrend → Bearish (-1)

Entry Rule:
- Long signal → SuperTrend must be Bullish (dir=1)
- Short signal → SuperTrend must be Bearish (dir=-1)
```

### 2. AI Score Filter

**BUCKET-BASED:** entry_features dihitung langsung dari MarketDataBucket.

```python
# Compute entry_features dari bucket
flow_alignment = abs(bucket.breakdown_open_interest)
structure_strength = 1.0 - min(1.0, bucket.breakdown_compression)
volume_z_score = bucket.breakdown_volume
oi_delta_z_score = bucket.breakdown_open_interest

# AI Score Formula
AI Score = Flow Alignment × 0.35 
         + Structure Strength × 0.25 
         + Volume Z-Score (normalized) × 0.20 
         + OI Delta Z-Score (normalized) × 0.20

# Normalisasi Z-Score: (-3 to 3) → (0 to 100)
normalized = (z_score + 3) / 6 × 100

Entry Rule:
- AI Score ≥ ai_threshold → PASS
- AI Score < ai_threshold → FILTERED
```

### 3. EMA 30/100 Filter

**TIMEFRAME-ADAPTIVE:** EMA dihitung pada timeframe sinyal.

```python
# Entry Rule
- Bullish: EMA30 > EMA100 → PASS
- Bearish: EMA30 < EMA100 → PASS
- Otherwise → FILTERED
```

## Exit Mechanism (rr_ratio)

**DYNAMIC TP/SL:** Target Profit dihitung dari rr_ratio.

```python
# Calculate Risk
risk = abs(entry_price - invalidation_price)

# Calculate TP based on rr_ratio
if bias == 'Bullish':
    tp_target = entry_price + rr_ratio × risk
    sl_target = invalidation_price
else:  # Bearish
    tp_target = entry_price - rr_ratio × risk
    sl_target = invalidation_price

# PnL Calculation
if max_profit >= risk × rr_ratio:
    pnl_pct = rr_ratio × 100  # TP hit (Win)
elif max_loss >= risk:
    pnl_pct = -100  # SL hit (Loss)
else:
    pnl_pct = (max_profit - max_loss) / risk × 100  # Partial
```

## Cara Menggunakan

### Install Dependencies

```powershell
cd C:\Code\flowscope
pip install -r requirements.txt
```

### Jalankan Optimasi

```powershell
# Default: 50 trials, 7 days (RECOMMENDED)
python scripts\optimize_v3_supertrend.py

# Custom settings
python scripts\optimize_v3_supertrend.py --days 14 --trials 100

# Quick test (NOT RECOMMENDED for final results)
python scripts\optimize_v3_supertrend.py --days 3 --trials 20
```

### Parameters

- `--days`: Jumlah hari data historis (default: 7)
- `--trials`: Jumlah trial Optuna (default: **50**)
- `--output`: File output JSON (default: `export/v3_supertrend_best_params.json`)

## Output

### 1. Terminal Summary

```
================================================================================
OPTIMIZATION RESULTS SUMMARY
================================================================================
Best Profit Factor: 2.3456
Total Trials: 50
Data Period: 7 days
Symbols: 28
Timestamp: 2026-05-05T12:34:56.789Z
================================================================================

BEST PARAMETERS:
Parameter                             Value
--------------------------------------------------
SuperTrend ATR Period                    14
SuperTrend Multiplier                   2.8
AI Score Threshold                       65
Risk-Reward Ratio                       2.5

V3 EMA TRIAL 24 (FIXED):
OI Delta Z-Score                        0.897
Volume Z-Score                          1.707
Flow Alignment                          0.874
Compression Score                       0.441
History Length (1h)                        67
Clarity Confidence                      0.806
Price Break (1h)                        0.037

ACTIVE FILTERS:
EMA 30/100                               True
SuperTrend                               True
AI Score                                 True
================================================================================
```

### 2. JSON File

File `export/v3_supertrend_best_params.json` berisi semua parameter terbaik.

## Alur Kerja (OPTIMIZED)

1. **Load Data**: Load historical buckets dari database (15m, 1h, 4h, 24h)
2. **Pre-compute Signals**: Jalankan replay SEKALI untuk semua simbol dengan parameter V3 Trial 24
   - Output: List of raw trade signals (dict format)
3. **Optuna Loop** (50 trials):
   - Suggest parameter baru (SuperTrend, AI, RR)
   - **Untuk setiap trade signal:**
     - Get bucket data pada timestamp sinyal
     - Compute entry_features dari bucket
     - Calculate AI Score dari features
     - Check EMA filter pada timeframe sinyal
     - Check SuperTrend filter pada timeframe sinyal
     - Check AI Score filter
     - Apply rr_ratio untuk hitung TP/SL
     - Calculate PnL berdasarkan TP/SL
   - Hitung Profit Factor dari filtered trades
   - Return objective value
4. **Save Results**: Simpan parameter terbaik ke JSON

## Keunggulan Optimasi

### Sebelum (OLD)

❌ entry_features diambil dari trade (sering None)
❌ SuperTrend hanya di 15m (tidak sesuai timeframe sinyal)
❌ rr_ratio tidak digunakan (TP/SL dari trade data)
❌ AI Score dari data yang salah
❌ Hanya 25 trials (konvergensi kurang)

### Sekarang (NEW)

✅ entry_features dihitung dari MarketDataBucket
✅ SuperTrend pada timeframe sinyal (15m/1h/4h)
✅ rr_ratio digunakan untuk TP/SL dinamis
✅ AI Score dari breakdown metrics bucket
✅ 50 trials untuk konvergensi optimal

## Catatan Penting

- **Timeframe Adaptation**: Filter (EMA, SuperTrend) menggunakan timeframe dari sinyal
- **Bucket Data**: entry_features dihitung dari `breakdown_*` fields di MarketDataBucket
- **Fallback Logic**: Jika bucket tidak ada, fallback ke 15m atau skip trade
- **PnL Calculation**: Simplified model dengan asumsi TP/SL hit berdasarkan high/low bucket
- **Pre-computation**: Trade signals di-compute SEKALI untuk efisiensi (tidak ulang replay)

## Dependencies

- `optuna>=3.5` - Optimization framework (TPE sampler)
- `pandas>=2.0` - Data manipulation
- `numpy` - Numerical calculations

## Troubleshooting

### "No symbols loaded"

Pastikan database sudah di-setup dan berisi data:

```powershell
# Check database connection
psql -U postgres -d flowscope_db -c "SELECT COUNT(*) FROM market_data_buckets;"
```

### "ModuleNotFoundError: No module named 'optuna'"

```powershell
pip install optuna
```

### Optimasi terlalu lambat

Kurangi trials (tapi hasil kurang optimal):

```powershell
python scripts\optimize_v3_supertrend.py --trials 30 --days 5
```

### Profit Factor = 0 atau inf

- Tidak ada trade yang lolos filter → Turunkan ai_threshold
- Semua trade win (no loss) → Tambah data atau trials
- Semua trade loss → Check parameter V3 atau filter terlalu ketat

## Performance Expectations

| Configuration | Runtime | Quality |
|---------------|---------|---------|
| 50 trials, 7 days | ~15-25 menit | ⭐⭐⭐⭐⭐ Optimal |
| 30 trials, 5 days | ~8-12 menit | ⭐⭐⭐⭐ Good |
| 20 trials, 3 days | ~3-5 menit | ⭐⭐⭐ Fair (quick test only) |

## Referensi

- [Optuna Documentation](https://optuna.readthedocs.io/)
- [SuperTrend Indicator](https://www.tradingview.com/support/solutions/43000502338-supertrend/)
- V3 EMA Trial 24: `export/v3_best_params.json`
- MarketDataBucket schema: `backend/models.py`
