import pandas as pd

from scripts.forward_shadow_monitor import _open_utf8_writer, _write_csv_utf8


def test_forward_shadow_writes_unicode_summary_as_utf8(tmp_path) -> None:
    summary_path = tmp_path / "forward_shadow_daily_summary.md"
    text = "Mixed market / Observe -> Δ strength ✓\n"

    with _open_utf8_writer(summary_path) as handle:
        handle.write(text)

    assert summary_path.read_text(encoding="utf-8") == text


def test_forward_shadow_writes_unicode_csv_as_utf8(tmp_path) -> None:
    csv_path = tmp_path / "forward_shadow_observations.csv"
    df = pd.DataFrame(
        [
            {
                "symbol": "TESTUSDT",
                "market_relative_reason_15m": "token positive while market weak ✓",
            }
        ]
    )

    _write_csv_utf8(df, csv_path)

    assert "market weak ✓" in csv_path.read_text(encoding="utf-8")
