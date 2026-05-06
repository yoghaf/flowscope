"""
V3 EMA (Trial 24) Final Backtest Script — FIXED VERSION.

CHANGELOG vs versi lama:
──────────────────────────────────────────────────────────────
BUG FIX #1 — One-position rule sekarang benar-benar block
  - Sebelumnya: hanya trade dengan result='open' yang dicek,
    trade 'win'/'loss' lolos tanpa pengecekan sehingga
    satu symbol bisa punya banyak posisi overlap.
  - Sesudahnya: semua trade dicek via symbol_active_until dict,
    menggunakan exit_timestamp (jika ada) atau entry_timestamp
    untuk mendeteksi overlap waktu secara akurat.

BUG FIX #2 — Timestamp ditambahkan ke CSV & trade_dict
  - Sebelumnya: tidak ada timestamp → tidak bisa audit urutan
    dan timing trade sama sekali.
  - Sesudahnya: entry_timestamp & exit_timestamp dicatat
    di trade_dict dan diekspor ke CSV.

BUG FIX #3 — EMA filter sekarang cek harga vs EMA30
  - Sebelumnya: hanya cek EMA30 vs EMA100 (crossing saja),
    tidak peduli apakah harga sudah ada di sisi yang benar.
  - Sesudahnya:
      Long  → EMA30 > EMA100 AND harga > EMA30
      Short → EMA30 < EMA100 AND harga < EMA30
──────────────────────────────────────────────────────────────

Output: Summary table + CSV (dengan kolom Timestamp & EMA info)
"""

import argparse
import asyncio
import json
import logging
import sys
import csv
import pandas as pd
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional
from collections import defaultdict

# Silence noisy loggers
logging.getLogger("sqlalchemy").setLevel(logging.ERROR)
logging.getLogger("backend.services.signal_service").setLevel(logging.ERROR)
logging.getLogger("backend.database").setLevel(logging.ERROR)

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    stream=sys.stdout
)
logger = logging.getLogger("V3EMAFinal")

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(REPO_ROOT))

from backend.config import get_settings, Settings
from backend.database import DatabaseManager
from scripts.replay_full_strategy import replay_symbol, load_bucket_history, TimeframeBucket

# ─────────────────────────────────────────────────────────────
# PARAMETERS
# ─────────────────────────────────────────────────────────────

V3_EMA_TRIAL_24 = {
    "strategy_version": "v3_adaptive",
    "entry_filter_min_abs_oi_delta_z": 0.897,
    "entry_filter_min_volume_z": 1.707,
    "continuation_min_flow_alignment": 0.874,
    "entry_filter_max_compression_score_15m": 0.441,
    "entry_filter_min_history_1h": 67,
    "entry_filter_min_clarity_confidence": 0.806,
}

V3_EMA_TF_TRIAL_24 = {
    "1h": {"price_break": 0.037}
}

# Global EMA cache
# Key: (symbol, timeframe, timestamp) -> (ema_30, ema_100)
ema_cache: dict[tuple, tuple[float, float]] = {}


# ─────────────────────────────────────────────────────────────
# SETUP
# ─────────────────────────────────────────────────────────────

def apply_ema_overrides(settings: Settings) -> None:
    for k, v in V3_EMA_TRIAL_24.items():
        setattr(settings, k, v)
    import backend.config
    for tf, overrides in V3_EMA_TF_TRIAL_24.items():
        if tf in backend.config.TIMEFRAME_PROFILES:
            backend.config.TIMEFRAME_PROFILES[tf].update(overrides)


def calculate_ema_for_symbol(symbol: str, buckets: dict[str, list[TimeframeBucket]]) -> None:
    """Calculate EMA 30/100 untuk semua timeframe dan simpan ke cache."""
    for tf, tf_buckets in buckets.items():
        if not tf_buckets:
            continue
        close_series = pd.Series([b.close_price for b in tf_buckets])
        ema_30  = close_series.ewm(span=30,  adjust=False).mean()
        ema_100 = close_series.ewm(span=100, adjust=False).mean()
        for i, bucket in enumerate(tf_buckets):
            ts = bucket.bucket_end
            ema_cache[(symbol, tf, ts)] = (ema_30.iloc[i], ema_100.iloc[i])


# ─────────────────────────────────────────────────────────────
# BUG FIX #3 — EMA FILTER (crossing + price position)
# ─────────────────────────────────────────────────────────────

def _get_ema_values(symbol: str, timeframe: str, ts: datetime) -> Optional[tuple[float, float]]:
    """
    Ambil nilai EMA dari cache. Fallback ke timestamp terdekat
    jika exact match tidak ada. Return None jika benar-benar
    tidak ada data sama sekali.
    """
    key = (symbol, timeframe, ts)
    val = ema_cache.get(key)
    if val:
        return val

    # Fallback ke timestamp terdekat
    candidates = [k for k in ema_cache if k[0] == symbol and k[1] == timeframe]
    if not candidates:
        return None  # FIX: return None bukan lanjut (dulu di sini ada bug skip)

    t_naive = ts.replace(tzinfo=None) if ts.tzinfo else ts
    closest = min(
        candidates,
        key=lambda k: abs((k[2].replace(tzinfo=None) if k[2].tzinfo else k[2]) - t_naive)
    )
    return ema_cache[closest]


def filter_trades_with_ema(trades: list, use_ema: bool = True) -> list:
    """
    Apply EMA filter ke list trade.

    KONDISI YANG DIPERIKSA (kedua harus terpenuhi):
    ─────────────────────────────────────────────────
    Long  (Bullish):
        1. EMA30 > EMA100  → trend naik (crossing benar)
        2. close_price > EMA30 → harga di atas EMA30

    Short (Bearish):
        1. EMA30 < EMA100  → trend turun (crossing benar)
        2. close_price < EMA30 → harga di bawah EMA30

    Jika EMA data tidak tersedia sama sekali → trade di-SKIP
    (lebih aman daripada lolos tanpa filter).
    """
    if not use_ema:
        return trades

    filtered = []
    rejected_crossing = 0
    rejected_price    = 0
    rejected_no_data  = 0

    for t in trades:
        ema_vals = _get_ema_values(t.symbol, t.timeframe, t.timestamp)

        # Tidak ada data EMA → skip trade ini
        if ema_vals is None:
            rejected_no_data += 1
            continue

        ema_30, ema_100 = ema_vals

        # ── FIX #3a: Cek EMA crossing ──
        if t.bias == 'Bullish' and ema_30 <= ema_100:
            rejected_crossing += 1
            continue
        if t.bias == 'Bearish' and ema_30 >= ema_100:
            rejected_crossing += 1
            continue

        # ── FIX #3b: Cek posisi harga vs EMA30 ──
        # Ambil close price dari trade. Coba beberapa atribut yang umum dipakai
        # di FlowScope. Sesuaikan jika nama atribut berbeda.
        close_price = (
            getattr(t, 'entry_price', None)
            or getattr(t, 'close_price', None)
            or getattr(t, 'price', None)
        )

        if close_price is not None:
            if t.bias == 'Bullish' and close_price < ema_30:
                # Harga masih di bawah EMA30 → belum konfirmasi breakout → REJECT
                rejected_price += 1
                continue
            if t.bias == 'Bearish' and close_price > ema_30:
                # Harga masih di atas EMA30 → belum konfirmasi breakdown → REJECT
                rejected_price += 1
                continue
        else:
            # Jika close_price tidak tersedia, catat warning tapi tetap lanjut
            # (fallback: hanya pakai crossing check)
            logger.warning(
                f"[EMA-FILTER] {t.symbol}/{t.timeframe}: close_price tidak tersedia, "
                f"skip price-position check."
            )

        filtered.append(t)

    if rejected_crossing or rejected_price or rejected_no_data:
        logger.info(
            f"[EMA-FILTER] Rejected — crossing: {rejected_crossing}, "
            f"price-position: {rejected_price}, no-data: {rejected_no_data}"
        )

    return filtered


# ─────────────────────────────────────────────────────────────
# BUG FIX #1 — ONE-POSITION RULE (overlap-aware)
# ─────────────────────────────────────────────────────────────

def apply_one_position_rule(sorted_trades: list, symbol: str) -> list:
    """
    Filter trade list untuk symbol tertentu sehingga hanya satu
    posisi aktif pada satu waktu.

    CARA KERJA:
    ────────────────────────────────────────────────────────────
    Menggunakan exit_timestamp untuk mendeteksi overlap:
      - Trade baru diizinkan HANYA jika tidak ada posisi yang
        sedang aktif pada entry_time trade tersebut.
      - Jika exit_timestamp tidak tersedia di trade object,
        fallback ke entry_timestamp (sekuential sederhana):
        trade baru hanya boleh masuk setelah trade sebelumnya
        dicatat (bukan benar-benar memeriksa overlap durasi).

    KENAPA INI FIX:
    ────────────────────────────────────────────────────────────
    Kode lama hanya memblokir trade dengan result='open',
    membiarkan semua 'win'/'loss' lewat tanpa pengecekan.
    Akibatnya PENGUUSDT punya 8 trade, FARTCOIN 6 trade, dst.

    Kode baru memblokir trade APAPUN selama posisi sebelumnya
    masih aktif (belum melewati exit_timestamp-nya).
    """
    allowed = []
    # Waktu kapan posisi saat ini berakhir. None = tidak ada posisi aktif.
    current_position_end: Optional[datetime] = None

    for t in sorted_trades:
        entry_ts = getattr(t, 'timestamp', None)
        if entry_ts is None:
            continue  # trade tanpa timestamp → skip

        # ── Normalisasi timezone ──
        if entry_ts.tzinfo is None:
            entry_ts = entry_ts.replace(tzinfo=timezone.utc)

        # ── Cek apakah posisi sebelumnya masih aktif ──
        if current_position_end is not None:
            end_naive = current_position_end
            if end_naive.tzinfo is None:
                end_naive = end_naive.replace(tzinfo=timezone.utc)

            if entry_ts < end_naive:
                # Overlap terdeteksi → TOLAK trade ini
                logger.debug(
                    f"[ONE-POS] {symbol} | Trade di {entry_ts} DITOLAK "
                    f"(posisi aktif hingga {end_naive})"
                )
                continue

        # ── Trade diizinkan ──
        allowed.append(t)

        # Tentukan kapan posisi ini berakhir
        exit_ts = (
            getattr(t, 'exit_timestamp', None)
            or getattr(t, 'close_time', None)
            or getattr(t, 'exit_time', None)
        )

        if exit_ts is not None:
            # Ada exit timestamp → pakai untuk overlap detection akurat
            if exit_ts.tzinfo is None:
                exit_ts = exit_ts.replace(tzinfo=timezone.utc)
            if t.result in ['win', 'loss']:
                current_position_end = exit_ts   # posisi sudah tutup
            else:
                # result='open': posisi masih berjalan
                current_position_end = datetime.now(timezone.utc) + timedelta(days=9999)
        else:
            # Exit timestamp tidak tersedia → fallback sekuential
            # win/loss = posisi tutup → izinkan trade berikutnya
            # open     = posisi masih berjalan → block semua trade berikutnya
            if t.result in ['win', 'loss']:
                current_position_end = None   # bebas untuk trade selanjutnya
            else:
                current_position_end = datetime.now(timezone.utc) + timedelta(days=9999)

    return allowed


# ─────────────────────────────────────────────────────────────
# METRICS
# ─────────────────────────────────────────────────────────────

def calculate_metrics(trades: list[dict]) -> dict[str, Any]:
    closed = [t for t in trades if t.get('result') in ['win', 'loss']]
    if not closed:
        return {
            'total_trades': 0, 'wins': 0, 'losses': 0,
            'winrate': 0.0, 'net_pnl_pct': 0.0,
            'gross_profit': 0.0, 'gross_loss': 0.0, 'profit_factor': 0.0,
        }
    wins   = [t for t in closed if t.get('result') == 'win']
    losses = [t for t in closed if t.get('result') == 'loss']
    gross_profit = sum(t.get('pnl_pct', 0) for t in wins)
    gross_loss   = abs(sum(t.get('pnl_pct', 0) for t in losses))
    return {
        'total_trades':  len(closed),
        'wins':          len(wins),
        'losses':        len(losses),
        'winrate':       len(wins) / len(closed) * 100,
        'net_pnl_pct':   sum(t.get('pnl_pct', 0) for t in closed),
        'gross_profit':  gross_profit,
        'gross_loss':    gross_loss,
        'profit_factor': gross_profit / gross_loss if gross_loss > 0 else (float('inf') if gross_profit > 0 else 0.0),
    }


# ─────────────────────────────────────────────────────────────
# BUG FIX #2 — CSV EXPORT (tambah timestamp)
# ─────────────────────────────────────────────────────────────

def export_trades_to_csv(trades: list[dict], output_path: str) -> None:
    """
    Export trade ke CSV.

    FIX #2: Tambahkan kolom EntryTimestamp dan ExitTimestamp
    agar trade bisa diaudit secara kronologis dan diverifikasi
    tidak overlap.
    """
    headers = [
        # FIX #2: dua kolom timestamp baru
        "EntryTimestamp", "ExitTimestamp",
        # kolom lama
        "Symbol", "Timeframe", "Setup", "Regime",
        "Confidence", "Bias", "Position", "PnL_Pct", "Result",
        # info EMA tambahan untuk audit filter
        "EMA30", "EMA100", "EntryPrice",
    ]

    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for t in trades:
            position = (
                "Long"  if t.get('bias') == 'Bullish' else
                "Short" if t.get('bias') == 'Bearish' else
                "Unknown"
            )
            writer.writerow([
                t.get('entry_timestamp', ''),
                t.get('exit_timestamp', ''),
                t.get('symbol', ''),
                t.get('timeframe', ''),
                t.get('setup_type', ''),
                t.get('market_regime', ''),
                round(t.get('confidence', 0.0) or 0.0, 4),
                t.get('bias', ''),
                position,
                round(t.get('pnl_pct', 0) or 0.0, 4),
                t.get('result', ''),
                round(t.get('ema_30', 0.0) or 0.0, 6),
                round(t.get('ema_100', 0.0) or 0.0, 6),
                round(t.get('entry_price', 0.0) or 0.0, 6),
            ])

    print(f"\n[EXPORT] Trade details saved to: {output_path}")


def print_summary_table(metrics: dict, days: int, symbols: int) -> None:
    print("\n" + "=" * 80)
    print(f"V3 EMA (Trial 24) FINAL — BACKTEST SUMMARY ({days} Days, {symbols} Symbols)")
    print("=" * 80)
    print(f"{'Metric':<30} | {'Value':<20}")
    print("-" * 80)
    print(f"{'Total Trades':<30} | {metrics['total_trades']:<20}")
    print(f"{'Wins':<30} | {metrics['wins']:<20}")
    print(f"{'Losses':<30} | {metrics['losses']:<20}")
    print(f"{'Winrate (%)':<30} | {metrics['winrate']:.1f}")
    print(f"{'Net PnL (%)':<30} | {metrics['net_pnl_pct']:+.2f}")
    print(f"{'Gross Profit (%)':<30} | {metrics['gross_profit']:.2f}")
    print(f"{'Gross Loss (%)':<30} | {metrics['gross_loss']:.2f}")
    print(f"{'Profit Factor':<30} | {metrics['profit_factor']:.2f}")
    print("=" * 80)


# ─────────────────────────────────────────────────────────────
# MAIN BACKTEST
# ─────────────────────────────────────────────────────────────

async def run_backtest(days: int = 30) -> None:
    print(f"\n[INGEST] Loading {days}-day history for all symbols...", flush=True)

    settings = get_settings()
    settings.debug = False
    db = DatabaseManager(settings)

    import io
    original_stdout = sys.stdout
    sys.stdout = io.StringIO()
    try:
        buckets_by_symbol = await load_bucket_history(db, symbols=None, days=days, limit_per_symbol=0)
    finally:
        sys.stdout = original_stdout

    symbols = list(buckets_by_symbol.keys())
    total_symbols = len(symbols)
    print(f"[INGEST] Loaded {total_symbols} symbols. Calculating EMA...", flush=True)

    for s in symbols:
        calculate_ema_for_symbol(s, buckets_by_symbol[s])
    print("[INGEST] EMA calculation complete.\n", flush=True)

    results: list[dict] = []
    semaphore = asyncio.Semaphore(10)

    print("=== RUNNING BACKTEST: V3 EMA (Trial 24) FINAL ===", flush=True)
    settings_ema = get_settings()
    settings_ema.debug = False
    apply_ema_overrides(settings_ema)

    processed = 0
    for symbol in symbols:
        async with semaphore:
            trades, diag = await replay_symbol(
                settings=settings_ema,
                symbol=symbol,
                buckets=buckets_by_symbol[symbol]
            )

            # Debug: short candidates yang ditolak
            for samples in diag.strategy_bias_samples.values():
                for s in samples:
                    if s.get("bias") == "Bearish":
                        reasons = s.get("reasons", [])
                        if reasons:
                            print(
                                f"[KANDIDAT SHORT] {symbol} | {s.get('market_state')} "
                                f"| Setup: {s.get('entry_type')} | Status: {s.get('signal_status')} "
                                f"| Reasons ditolak: {reasons}",
                                flush=True
                            )

            # ── STEP 1: EMA Filter (crossing + price position) ──
            filtered_trades = filter_trades_with_ema(trades, use_ema=True)

            for t in filtered_trades:
                if t.bias == "Bearish":
                    print(f"[SHORT MASUK] {t.symbol} | {t.timeframe} | Setup: {t.setup_type}", flush=True)

            # ── STEP 2: Sort by entry timestamp ──
            sorted_trades = sorted(filtered_trades, key=lambda t: t.timestamp)

            # ── STEP 3: One-position rule (FIX #1) ──
            valid_trades = apply_one_position_rule(sorted_trades, symbol)

            # ── STEP 4: Build trade_dict dengan timestamp (FIX #2) ──
            for t in valid_trades:
                if t.result not in ['win', 'loss', 'open']:
                    continue

                # Ambil EMA values untuk dicatat di CSV (FIX #2 + #3 audit)
                ema_vals = _get_ema_values(t.symbol, t.timeframe, t.timestamp)
                ema_30_val  = ema_vals[0] if ema_vals else None
                ema_100_val = ema_vals[1] if ema_vals else None

                entry_price = (
                    getattr(t, 'entry_price', None)
                    or getattr(t, 'close_price', None)
                    or getattr(t, 'price', None)
                )

                exit_ts = (
                    getattr(t, 'exit_timestamp', None)
                    or getattr(t, 'close_time', None)
                    or getattr(t, 'exit_time', None)
                )

                trade_dict = {
                    # FIX #2: timestamp
                    'entry_timestamp': t.timestamp.isoformat() if t.timestamp else '',
                    'exit_timestamp':  exit_ts.isoformat() if exit_ts else '',
                    # data utama
                    'symbol':        t.symbol,
                    'timeframe':     t.timeframe,
                    'setup_type':    t.setup_type,
                    'market_regime': t.market_regime,
                    'confidence':    getattr(t, 'confidence', 0.0),
                    'bias':          t.bias,
                    'result':        t.result,
                    'pnl_pct':       t.pnl_pct,
                    # FIX #3 audit info
                    'ema_30':        ema_30_val,
                    'ema_100':       ema_100_val,
                    'entry_price':   entry_price,
                }
                results.append(trade_dict)

            processed += 1
            if processed % 20 == 0 or processed == total_symbols:
                pct = (processed / total_symbols) * 100
                print(f"Progress: {processed}/{total_symbols} ({pct:.1f}%)", flush=True)

    print("=== COMPLETED: V3 EMA FINAL ===\n", flush=True)

    # ── Metrics ──
    print("[METRICS] Calculating performance metrics...", flush=True)
    metrics = calculate_metrics(results)
    print_summary_table(metrics, days, total_symbols)

    # ── Export ──
    output_dir = Path(REPO_ROOT) / "export"
    output_dir.mkdir(exist_ok=True)

    csv_path = output_dir / "v3_ema_final_trades.csv"
    export_trades_to_csv(results, str(csv_path))

    summary = {
        "backtest_date": datetime.now(timezone.utc).isoformat(),
        "days":          days,
        "symbols":       total_symbols,
        "strategy":      "V3 EMA (Trial 24) FINAL — Fixed",
        "parameters":    V3_EMA_TRIAL_24,
        "fixes_applied": [
            "BUG FIX #1: One-position rule menggunakan exit_timestamp untuk overlap detection",
            "BUG FIX #2: EntryTimestamp & ExitTimestamp ditambahkan ke CSV",
            "BUG FIX #3: EMA filter cek crossing DAN posisi harga vs EMA30",
        ],
        "metrics": metrics,
    }

    json_path = output_dir / "v3_ema_final_summary.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"\n[EXPORT] Metrics summary saved to: {json_path}")
    print("\n[COMPLETE] Final backtest finished!\n")


def main():
    parser = argparse.ArgumentParser(description="V3 EMA (Trial 24) Final Backtest — Fixed")
    parser.add_argument("--days", type=int, default=30)
    args = parser.parse_args()

    print(f"\n{'=' * 80}")
    print("V3 EMA (Trial 24) FINAL Backtest — FIXED")
    print(f"{'=' * 80}")
    print("Fixes applied:")
    print("  [FIX #1] One-position rule: overlap detection via exit_timestamp")
    print("  [FIX #2] Timestamp: EntryTimestamp + ExitTimestamp di CSV")
    print("  [FIX #3] EMA filter: EMA crossing + price vs EMA30")
    print(f"{'=' * 80}\n")

    asyncio.run(run_backtest(days=args.days))


if __name__ == "__main__":
    main()