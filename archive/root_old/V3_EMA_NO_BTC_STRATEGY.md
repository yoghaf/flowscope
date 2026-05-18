# V3 EMA No BTC Strategy Variant

## Overview

Varian strategi `v3_ema_no_btc` adalah modifikasi dari `v3_adaptive` (Trial 24) yang **melepaskan ketergantungan dari tren Bitcoin**.

## Perubahan Utama

### 1. Parameter Baru di `backend/config.py`

```python
entry_filter_use_global_btc_trend: bool = True  # Default: True (gunakan BTC)
```

Untuk aktivasi varian no-BTC, set:

```bash
FLOWSCOPE_STRATEGY_VERSION=v3_ema_no_btc
FLOWSCOPE_ENTRY_FILTER_USE_GLOBAL_BTC_TREND=False
```

### 2. Modifikasi di `backend/services/signal_service.py`

#### A. `_higher_timeframe_context()` (baris ~4351)

- Untuk token selain BTCUSDT dengan `v3_ema_no_btc`: gunakan **HTF token sendiri**
- Tidak ada fallback ke tren BTC
- BTCUSDT tetap menggunakan logika lama (HTF sendiri)

#### B. `_entry_hard_filter_reasons()` (baris ~5556)

- Deteksi `v3_ema_no_btc` dan nonaktifkan:
  - ❌ `short_direction_disabled` (filter arah Short berdasarkan BTC)
  - ❌ `exhaustion_volume_climax`
  - ❌ `exhaustion_oi_climax`
  - ❌ `exhaustion_liq_climax`
  - ❌ `overcrowded_short_positioning`
  - ❌ `funding_extreme_short_premium`

#### C. `_continuation_filter_reasons()` (baris ~5704)

- Deteksi `v3_ema_no_btc` sebagai bagian dari V3
- Tetap apply relaksasi Short V3:
  - ✅ `continuation_flow_alignment_below_threshold` (threshold 20% lebih rendah)
  - ✅ `continuation_higher_timeframe_not_aligned` (skip untuk Short)

### 3. Logika Higher Timeframe Trend

**V3 Adaptive (lama):**

```
Token ≠ BTC → HTF Token → (jika Neutral) → HTF BTC
BTC → HTF BTC
```

**V3 EMA No BTC (baru):**

```
Semua Token → HTF Token sendiri (NO fallback ke BTC)
BTC → HTF BTC sendiri
```

## Perbandingan Filter

| Filter                                      | v2_balanced | v3_adaptive         | v3_ema_no_btc       |
| ------------------------------------------- | ----------- | ------------------- | ------------------- |
| `clarity_below_threshold`                   | ✅ Active   | ❌ Disabled (Short) | ❌ Disabled (Short) |
| `short_direction_disabled`                  | ✅ Active   | ❌ Disabled         | ❌ Disabled         |
| `exhaustion_*_climax`                       | ✅ Active   | ❌ Disabled         | ❌ Disabled         |
| `overcrowded_short_positioning`             | ✅ Active   | ❌ Disabled         | ❌ Disabled         |
| `funding_extreme_short_premium`             | ✅ Active   | ❌ Disabled         | ❌ Disabled         |
| `continuation_flow_alignment`               | 0.70        | 0.70 (Short: 0.56)  | 0.70 (Short: 0.56)  |
| `continuation_higher_timeframe_not_aligned` | ✅ Active   | ❌ Disabled (Short) | ❌ Disabled (Short) |
| **BTC Dependency**                          | ✅ Yes      | ✅ Yes              | ❌ **NO**           |

## Cara Menggunakan

### Backtest

```bash
# v2_balanced
FLOWSCOPE_STRATEGY_VERSION=v2_balanced python scripts/replay_full_strategy.py

# v3_adaptive (Trial 24 + EMA)
FLOWSCOPE_STRATEGY_VERSION=v3_adaptive python scripts/replay_full_strategy.py

# v3_ema_no_btc (Trial 24 + EMA + No BTC)
FLOWSCOPE_STRATEGY_VERSION=v3_ema_no_btc FLOWSCOPE_ENTRY_FILTER_USE_GLOBAL_BTC_TREND=False python scripts/replay_full_strategy.py
```

### Comparison Script

```bash
python scripts/compare_v2_v3_v3nobtc.py
```

Output:

- `export/v2_v3_v3nobtc_comparison.json` - Summary statistics
- `export/v2_v3_v3nobtc_trades_detail.csv` - Detail trades

## Hipotesis

**v3_ema_no_btc akan menghasilkan:**

1. ✅ **Lebih banyak sinyal Short** - tidak terhambat oleh BTC Bearish
2. ✅ **Lebih diversifikasi** - setiap token dinilai independen
3. ⚠️ **Potensi drawdown lebih tinggi** - jika BTC sedang crash, altcoins tetap entry Short
4. ⚠️ **Korelasi tetap ada** - market crypto masih correlated, tapi tidak eksplisit di filter

## Files Modified

1. `backend/config.py` - Added `entry_filter_use_global_btc_trend`
2. `backend/services/signal_service.py`:
   - `_higher_timeframe_context()` - No BTC fallback for no-BTC variant
   - `_entry_hard_filter_reasons()` - Disable BTC-based filters
   - `_continuation_filter_reasons()` - Support no-BTC variant
3. `scripts/compare_v2_v3_v3nobtc.py` - New comparison script
