# Live April Trade Autopsy

- Window: `2026-04-01T00:00:00+00:00` to `2026-05-01T00:00:00+00:00`
- Database: `postgresql+asyncpg://localhost:5432/flowscope_db`
- Closed trades: `64`

## Headline

| Scope | Closed | W/L | WR | Total R | Alloc R | PF R |
|---|---:|---:|---:|---:|---:|---:|
| All | 64 | 28/36 | 43.75% | -12.03 | -15.76 | 0.67 |

## By Setup

| Value | Closed | W/L | WR | Total R | Alloc R | PF R |
|---|---:|---:|---:|---:|---:|---:|
| Continuation | 64 | 28/36 | 43.75% | -12.03 | -15.76 | 0.67 |

## By Bias

| Value | Closed | W/L | WR | Total R | Alloc R | PF R |
|---|---:|---:|---:|---:|---:|---:|
| Bullish | 62 | 28/34 | 45.16% | -10.03 | -13.65 | 0.70 |
| Bearish | 2 | 0/2 | 0.00% | -2.00 | -2.11 | 0.00 |

## By Timeframe

| Value | Closed | W/L | WR | Total R | Alloc R | PF R |
|---|---:|---:|---:|---:|---:|---:|
| 4h | 20 | 6/14 | 30.00% | -8.90 | -9.52 | 0.36 |
| 24h | 6 | 2/4 | 33.33% | -1.56 | -2.64 | 0.61 |
| 1h | 5 | 2/3 | 40.00% | -1.45 | -1.76 | 0.52 |
| 15m | 33 | 18/15 | 54.55% | -0.13 | -1.83 | 0.99 |

## By State

| Value | Closed | W/L | WR | Total R | Alloc R | PF R |
|---|---:|---:|---:|---:|---:|---:|
| Long Build-up | 60 | 27/33 | 45.00% | -9.68 | -13.00 | 0.71 |
| Expansion | 3 | 1/2 | 33.33% | -1.35 | -1.56 | 0.32 |
| Pre-Squeeze | 1 | 0/1 | 0.00% | -1.00 | -1.19 | 0.00 |

## By Entry Type

| Value | Closed | W/L | WR | Total R | Alloc R | PF R |
|---|---:|---:|---:|---:|---:|---:|
| Continuation Pullback | 64 | 28/36 | 43.75% | -12.03 | -15.76 | 0.67 |

## By Market Regime

| Value | Closed | W/L | WR | Total R | Alloc R | PF R |
|---|---:|---:|---:|---:|---:|---:|
| Trending | 28 | 6/22 | 21.43% | -15.42 | -18.10 | 0.30 |
| Ranging | 8 | 3/5 | 37.50% | -3.04 | -3.73 | 0.39 |
| Balanced | 28 | 19/9 | 67.86% | 6.43 | 6.07 | 1.71 |

## By Volatility

| Value | Closed | W/L | WR | Total R | Alloc R | PF R |
|---|---:|---:|---:|---:|---:|---:|
| High | 49 | 20/29 | 40.82% | -12.35 | -16.73 | 0.57 |
| Low | 7 | 3/4 | 42.86% | -1.59 | -1.75 | 0.60 |
| Medium | 8 | 5/3 | 62.50% | 1.91 | 2.72 | 1.64 |

## By Close Reason

| Value | Closed | W/L | WR | Total R | Alloc R | PF R |
|---|---:|---:|---:|---:|---:|---:|
| Invalidation | 36 | 0/36 | 0.00% | -36.00 | -36.38 | 0.00 |
| Partial TP1 | 2 | 2/0 | 100.00% | 1.44 | 0.81 | -- |
| Breakeven SL | 11 | 11/0 | 100.00% | 5.62 | 5.74 | -- |
| Continuation Trail Stop | 9 | 9/0 | 100.00% | 7.90 | 6.67 | -- |
| Target 2 | 6 | 6/0 | 100.00% | 9.01 | 7.41 | -- |

## By Engine Tag

| Value | Closed | W/L | WR | Total R | Alloc R | PF R |
|---|---:|---:|---:|---:|---:|---:|
| v2_balanced | 64 | 28/36 | 43.75% | -12.03 | -15.76 | 0.67 |

## Worst Trades

| ID | Symbol | TF | Setup | Bias | State | Result | R | Close Reason | Entry Type |
|---:|---|---|---|---|---|---|---:|---|---|
| 1 | APEUSDT | 4h | Continuation | Bullish | Long Build-up | loss | -1.00 | Invalidation | Continuation Pullback |
| 2 | 1000SHIBUSDT | 15m | Continuation | Bullish | Long Build-up | loss | -1.00 | Invalidation | Continuation Pullback |
| 5 | HYPEUSDT | 1h | Continuation | Bullish | Long Build-up | loss | -1.00 | Invalidation | Continuation Pullback |
| 6 | RAVEUSDT | 15m | Continuation | Bullish | Long Build-up | loss | -1.00 | Invalidation | Continuation Pullback |
| 10 | PIPPINUSDT | 4h | Continuation | Bullish | Expansion | loss | -1.00 | Invalidation | Continuation Pullback |
| 14 | GALAUSDT | 4h | Continuation | Bullish | Long Build-up | loss | -1.00 | Invalidation | Continuation Pullback |
| 16 | KATUSDT | 15m | Continuation | Bullish | Long Build-up | loss | -1.00 | Invalidation | Continuation Pullback |
| 18 | QUSDT | 15m | Continuation | Bullish | Long Build-up | loss | -1.00 | Invalidation | Continuation Pullback |
| 19 | ADAUSDT | 15m | Continuation | Bearish | Pre-Squeeze | loss | -1.00 | Invalidation | Continuation Pullback |
| 9 | TRUMPUSDT | 24h | Continuation | Bullish | Long Build-up | loss | -1.00 | Invalidation | Continuation Pullback |
| 20 | MOVRUSDT | 15m | Continuation | Bullish | Long Build-up | loss | -1.00 | Invalidation | Continuation Pullback |
| 21 | ENJUSDT | 15m | Continuation | Bullish | Long Build-up | loss | -1.00 | Invalidation | Continuation Pullback |
| 26 | ENSOUSDT | 15m | Continuation | Bullish | Long Build-up | loss | -1.00 | Invalidation | Continuation Pullback |
| 30 | SOONUSDT | 15m | Continuation | Bullish | Long Build-up | loss | -1.00 | Invalidation | Continuation Pullback |
| 34 | ORCAUSDT | 15m | Continuation | Bullish | Long Build-up | loss | -1.00 | Invalidation | Continuation Pullback |
| 36 | INJUSDT | 15m | Continuation | Bullish | Long Build-up | loss | -1.00 | Invalidation | Continuation Pullback |
| 33 | XLMUSDT | 1h | Continuation | Bullish | Long Build-up | loss | -1.00 | Invalidation | Continuation Pullback |
| 40 | HIGHUSDT | 15m | Continuation | Bullish | Long Build-up | loss | -1.00 | Invalidation | Continuation Pullback |
| 41 | SONICUSDT | 15m | Continuation | Bearish | Long Build-up | loss | -1.00 | Invalidation | Continuation Pullback |
| 37 | CHZUSDT | 4h | Continuation | Bullish | Long Build-up | loss | -1.00 | Invalidation | Continuation Pullback |
| 51 | GENIUSUSDT | 15m | Continuation | Bullish | Long Build-up | loss | -1.00 | Invalidation | Continuation Pullback |
| 44 | FARTCOINUSDT | 4h | Continuation | Bullish | Long Build-up | loss | -1.00 | Invalidation | Continuation Pullback |
| 47 | 1000PEPEUSDT | 4h | Continuation | Bullish | Long Build-up | loss | -1.00 | Invalidation | Continuation Pullback |
| 48 | AAVEUSDT | 4h | Continuation | Bullish | Long Build-up | loss | -1.00 | Invalidation | Continuation Pullback |
| 49 | SPKUSDT | 4h | Continuation | Bullish | Long Build-up | loss | -1.00 | Invalidation | Continuation Pullback |

## Best Trades

| ID | Symbol | TF | Setup | Bias | State | Result | R | Close Reason | Entry Type |
|---:|---|---|---|---|---|---|---:|---|---|
| 67 | AXSUSDT | 15m | Continuation | Bullish | Long Build-up | win | 1.54 | Target 2 | Continuation Pullback |
| 4 | MASKUSDT | 24h | Continuation | Bullish | Long Build-up | win | 1.50 | Target 2 | Continuation Pullback |
| 71 | DOGEUSDT | 4h | Continuation | Bullish | Long Build-up | win | 1.50 | Target 2 | Continuation Pullback |
| 8 | GALAUSDT | 4h | Continuation | Bullish | Long Build-up | win | 1.49 | Target 2 | Continuation Pullback |
| 61 | PRLUSDT | 15m | Continuation | Bullish | Long Build-up | win | 1.49 | Target 2 | Continuation Pullback |
| 53 | APEUSDT | 15m | Continuation | Bullish | Long Build-up | win | 1.49 | Target 2 | Continuation Pullback |
| 42 | VVVUSDT | 15m | Continuation | Bullish | Long Build-up | win | 1.29 | Continuation Trail Stop | Continuation Pullback |
| 52 | AXSUSDT | 15m | Continuation | Bullish | Long Build-up | win | 1.10 | Continuation Trail Stop | Continuation Pullback |
| 70 | TACUSDT | 15m | Continuation | Bullish | Long Build-up | win | 0.98 | Continuation Trail Stop | Continuation Pullback |
| 11 | INJUSDT | 24h | Continuation | Bullish | Long Build-up | win | 0.95 | Partial TP1 | Continuation Pullback |
| 13 | ENAUSDT | 15m | Continuation | Bullish | Long Build-up | win | 0.91 | Continuation Trail Stop | Continuation Pullback |
| 45 | VIRTUALUSDT | 1h | Continuation | Bullish | Long Build-up | win | 0.90 | Continuation Trail Stop | Continuation Pullback |
| 38 | AXSUSDT | 15m | Continuation | Bullish | Long Build-up | win | 0.84 | Continuation Trail Stop | Continuation Pullback |
| 35 | SEIUSDT | 15m | Continuation | Bullish | Long Build-up | win | 0.69 | Continuation Trail Stop | Continuation Pullback |
| 15 | 币安人生USDT | 1h | Continuation | Bullish | Expansion | win | 0.65 | Continuation Trail Stop | Continuation Pullback |

## Loss Close Reasons

- `Invalidation`: 36
