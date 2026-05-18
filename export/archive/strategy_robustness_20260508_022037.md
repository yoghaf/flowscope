# Strategy Robustness Report

- Generated: `2026-05-08T02:20:37.461388+00:00`
- Source trades: `20 files`
- Source summary: ``
- Min closed trades per robustness group: `3`

## Ranking

| Rank | Strategy | Robustness | Closed | W/L | WR | Total R | Alloc R | PF R | Max DD R | Worst Month | Worst Regime | Worst TF |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|
| 1 | qmid_p06_4h_runner_3r | 100.00 | 11 | 9/2 | 81.82% | 11.50 | 9.02 | 6.75 | -1.00 | 2026-05 11.50R | Trending 12.00R | 4h 11.50R |
| 2 | qmid_p06_4h_only | 100.00 | 11 | 9/2 | 81.82% | 9.56 | 7.98 | 5.78 | -2.00 | 2026-05 9.56R | Trending 10.06R | 4h 9.56R |
| 3 | qmid_p06_4h_runner_2r | 100.00 | 11 | 9/2 | 81.82% | 9.50 | 7.94 | 5.75 | -2.00 | 2026-05 9.50R | Trending 10.00R | 4h 9.50R |
| 4 | qmid_p06_ema | 97.83 | 28 | 17/11 | 60.71% | 7.77 | 7.93 | 1.71 | -4.50 | 2026-04 3.09R | Balanced -0.30R | 15m 1.23R |
| 5 | qmid_p06_15m_strict | 97.14 | 5 | 4/1 | 80.00% | 2.11 | 1.63 | 3.11 | -1.00 | 2026-05 1.53R | Balanced 0.08R | 15m 2.11R |
| 6 | qmid_p07 | 93.53 | 52 | 29/23 | 55.77% | 8.32 | 8.60 | 1.41 | -6.51 | 2026-04 4.14R | Balanced -0.38R | 15m -0.32R |
| 7 | qmid_p06 | 92.91 | 47 | 26/21 | 55.32% | 8.75 | 9.19 | 1.47 | -6.01 | 2026-04 3.65R | Balanced -0.88R | 15m -0.81R |
| 8 | qmid_p07_ema | 90.78 | 31 | 18/13 | 58.06% | 6.35 | 6.07 | 1.49 | -5.89 | 2026-05 2.76R | Balanced 0.20R | 15m 1.73R |
| 9 | qmid_p06_failfast | 87.65 | 47 | 23/24 | 48.94% | 6.45 | 7.55 | 1.40 | -6.87 | 2026-05 2.80R | Ranging 0.06R | 15m -0.42R |
| 10 | tf_profile | 70.11 | 34 | 18/16 | 52.94% | 3.73 | 4.72 | 1.29 | -4.19 | 2026-04 -3.14R | Balanced -1.40R | 24h -0.02R |
| 11 | qmid_p06_ema_pullback | 67.88 | 17 | 9/8 | 52.94% | 2.53 | 4.36 | 1.32 | -4.50 | 2026-05 0.51R | Balanced -3.49R | 15m -0.96R |
| 12 | guarded | 65.61 | 34 | 17/17 | 50.00% | 3.58 | 4.71 | 1.24 | -6.47 | 2026-05 -0.51R | Balanced -3.00R | 15m -1.43R |
| 13 | tf_simple | 59.70 | 72 | 34/38 | 47.22% | 3.33 | 4.09 | 1.10 | -6.95 | 2026-04 -3.57R | Balanced -3.96R | 15m 0.10R |
| 14 | qmid_p06_15m_only | 51.26 | 36 | 17/19 | 47.22% | -0.81 | 1.21 | 0.95 | -6.00 | 2026-05 -4.46R | Trending -1.50R | 15m -0.81R |
| 15 | balanced_soft | 33.93 | 57 | 25/32 | 43.86% | -4.01 | -2.13 | 0.85 | -8.13 | 2026-04 -4.53R | Balanced -5.51R | 15m -5.35R |
| 16 | context_guard | 31.43 | 68 | 29/39 | 42.65% | -5.03 | -1.36 | 0.85 | -9.09 | 2026-04 -4.53R | Balanced -6.95R | 15m -6.12R |
| 17 | quality_soft | 10.37 | 106 | 46/60 | 43.40% | -9.61 | -10.16 | 0.82 | -17.37 | 2026-04 -11.78R | Trending -5.94R | 4h -6.53R |
| 18 | ema_pullback_only | 0.00 | 61 | 21/40 | 34.43% | -15.34 | -14.98 | 0.57 | -19.28 | 2026-04 -11.98R | Trending -10.07R | 4h -8.82R |
| 19 | ema_only | 0.00 | 96 | 36/60 | 37.50% | -17.41 | -16.79 | 0.67 | -24.87 | 2026-04 -17.70R | Trending -12.65R | 4h -13.13R |
| 20 | baseline | 0.00 | 155 | 61/94 | 39.35% | -20.15 | -17.37 | 0.75 | -28.12 | 2026-04 -18.36R | Balanced -11.46R | 4h -10.63R |

## balanced_soft

### Overall

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| overall | 57 | 3 | 25/32 | 43.86% | -4.01 | -2.13 | 0.85 | -8.13 |

### By Month

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-04 | 24 | 1 | 9/15 | 37.50% | -4.53 | -5.49 | 0.61 | -8.04 |
| 2026-05 | 33 | 2 | 16/17 | 48.48% | 0.52 | 3.35 | 1.03 | -7.47 |

### By Regime

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Balanced | 27 | 0 | 10/17 | 37.04% | -5.51 | -1.97 | 0.62 | -7.63 |
| Ranging | 9 | 0 | 6/3 | 66.67% | 2.66 | 1.41 | 1.89 | -2.00 |
| Trending | 21 | 3 | 9/12 | 42.86% | -1.16 | -1.58 | 0.88 | -5.71 |

### By Volatility

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| High | 48 | 2 | 21/27 | 43.75% | -4.15 | -3.72 | 0.81 | -8.29 |
| Medium | 9 | 1 | 4/5 | 44.44% | 0.14 | 1.59 | 1.03 | -3.00 |

### By Timeframe

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 15m | 37 | 0 | 15/22 | 40.54% | -5.35 | -2.56 | 0.73 | -6.94 |
| 24h | 7 | 3 | 4/3 | 57.14% | 0.47 | 0.47 | 1.30 | -1.56 |
| 4h | 13 | 0 | 6/7 | 46.15% | 0.86 | -0.04 | 1.14 | -3.15 |

### By Setup

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Continuation | 57 | 3 | 25/32 | 43.86% | -4.01 | -2.13 | 0.85 | -8.13 |

### By Bias

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Bearish | 3 | 0 | 0/3 | 0.00% | -3.00 | -3.46 | 0.00 | -3.00 |
| Bullish | 54 | 3 | 25/29 | 46.30% | -1.01 | 1.32 | 0.96 | -6.47 |

## baseline

### Overall

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| overall | 155 | 13 | 61/94 | 39.35% | -20.15 | -17.37 | 0.75 | -28.12 |

### By Month

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-04 | 65 | 1 | 21/44 | 32.31% | -18.36 | -19.02 | 0.50 | -21.14 |
| 2026-05 | 90 | 12 | 40/50 | 44.44% | -1.79 | 1.65 | 0.96 | -7.77 |

### By Regime

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Balanced | 66 | 1 | 26/40 | 39.39% | -11.46 | -5.95 | 0.65 | -18.03 |
| Ranging | 15 | 0 | 6/9 | 40.00% | -2.08 | -2.42 | 0.73 | -4.00 |
| Trending | 74 | 12 | 29/45 | 39.19% | -6.60 | -9.00 | 0.83 | -19.51 |

### By Volatility

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| High | 110 | 4 | 46/64 | 41.82% | -10.22 | -11.99 | 0.81 | -20.96 |
| Low | 22 | 7 | 6/16 | 27.27% | -8.58 | -7.91 | 0.39 | -9.70 |
| Medium | 23 | 2 | 9/14 | 39.13% | -1.35 | 2.53 | 0.89 | -3.46 |

### By Timeframe

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 15m | 70 | 0 | 28/42 | 40.00% | -10.19 | -4.94 | 0.71 | -11.26 |
| 1h | 9 | 0 | 2/7 | 22.22% | -2.41 | -1.76 | 0.46 | -3.65 |
| 24h | 13 | 9 | 7/6 | 53.85% | 3.09 | 2.60 | 1.68 | -2.56 |
| 4h | 63 | 4 | 24/39 | 38.10% | -10.63 | -13.28 | 0.70 | -17.12 |

### By Setup

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Continuation | 155 | 13 | 61/94 | 39.35% | -20.15 | -17.37 | 0.75 | -28.12 |

### By Bias

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Bearish | 3 | 0 | 0/3 | 0.00% | -3.00 | -3.46 | 0.00 | -3.00 |
| Bullish | 152 | 13 | 61/91 | 40.13% | -17.15 | -13.91 | 0.78 | -26.12 |

## context_guard

### Overall

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| overall | 68 | 3 | 29/39 | 42.65% | -5.03 | -1.36 | 0.85 | -9.09 |

### By Month

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-04 | 24 | 1 | 9/15 | 37.50% | -4.53 | -5.49 | 0.61 | -8.04 |
| 2026-05 | 44 | 2 | 20/24 | 45.45% | -0.50 | 4.13 | 0.98 | -8.47 |

### By Regime

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Balanced | 33 | 0 | 12/21 | 36.36% | -6.95 | -2.69 | 0.62 | -9.07 |
| Ranging | 10 | 0 | 6/4 | 60.00% | 2.33 | 1.26 | 1.70 | -2.00 |
| Trending | 25 | 3 | 11/14 | 44.00% | -0.40 | 0.06 | 0.96 | -6.26 |

### By Volatility

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| High | 58 | 2 | 25/33 | 43.10% | -4.84 | -2.80 | 0.82 | -8.62 |
| Medium | 10 | 1 | 4/6 | 40.00% | -0.19 | 1.44 | 0.96 | -3.00 |

### By Timeframe

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 15m | 43 | 0 | 17/26 | 39.53% | -6.12 | -2.79 | 0.73 | -7.72 |
| 24h | 6 | 3 | 3/3 | 50.00% | -0.02 | -0.14 | 0.98 | -1.56 |
| 4h | 19 | 0 | 9/10 | 47.37% | 1.11 | 1.57 | 1.13 | -3.70 |

### By Setup

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Continuation | 68 | 3 | 29/39 | 42.65% | -5.03 | -1.36 | 0.85 | -9.09 |

### By Bias

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Bearish | 3 | 0 | 0/3 | 0.00% | -3.00 | -3.46 | 0.00 | -3.00 |
| Bullish | 65 | 3 | 29/36 | 44.62% | -2.03 | 2.10 | 0.93 | -7.47 |

## ema_only

### Overall

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| overall | 96 | 6 | 36/60 | 37.50% | -17.41 | -16.79 | 0.67 | -24.87 |

### By Month

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-04 | 45 | 1 | 13/32 | 28.89% | -17.70 | -18.53 | 0.37 | -20.34 |
| 2026-05 | 51 | 5 | 23/28 | 45.10% | 0.29 | 1.74 | 1.01 | -5.79 |

### By Regime

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Balanced | 44 | 0 | 18/26 | 40.91% | -7.20 | -4.10 | 0.68 | -10.77 |
| Ranging | 5 | 0 | 4/1 | 80.00% | 2.44 | 2.78 | 3.44 | -1.00 |
| Trending | 47 | 6 | 14/33 | 29.79% | -12.65 | -15.47 | 0.57 | -20.44 |

### By Volatility

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| High | 69 | 4 | 27/42 | 39.13% | -10.60 | -13.42 | 0.71 | -17.58 |
| Low | 16 | 2 | 5/11 | 31.25% | -6.11 | -6.48 | 0.39 | -6.67 |
| Medium | 11 | 0 | 4/7 | 36.36% | -0.69 | 3.11 | 0.88 | -2.40 |

### By Timeframe

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 15m | 44 | 0 | 19/25 | 43.18% | -5.48 | -2.10 | 0.76 | -8.41 |
| 1h | 3 | 0 | 0/3 | 0.00% | -1.19 | -1.51 | 0.05 | -1.19 |
| 24h | 8 | 4 | 5/3 | 62.50% | 2.40 | 1.79 | 2.09 | -2.19 |
| 4h | 41 | 2 | 12/29 | 29.27% | -13.13 | -14.96 | 0.51 | -16.83 |

### By Setup

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Continuation | 96 | 6 | 36/60 | 37.50% | -17.41 | -16.79 | 0.67 | -24.87 |

### By Bias

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Bullish | 96 | 6 | 36/60 | 37.50% | -17.41 | -16.79 | 0.67 | -24.87 |

## ema_pullback_only

### Overall

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| overall | 61 | 4 | 21/40 | 34.43% | -15.34 | -14.98 | 0.57 | -19.28 |

### By Month

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-04 | 30 | 1 | 8/22 | 26.67% | -11.98 | -14.57 | 0.38 | -14.88 |
| 2026-05 | 31 | 3 | 13/18 | 41.94% | -3.35 | -0.41 | 0.79 | -6.50 |

### By Regime

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Balanced | 27 | 0 | 9/18 | 33.33% | -7.71 | -5.31 | 0.53 | -9.27 |
| Ranging | 5 | 0 | 4/1 | 80.00% | 2.44 | 2.78 | 3.44 | -1.00 |
| Trending | 29 | 4 | 8/21 | 27.59% | -10.07 | -12.45 | 0.45 | -15.42 |

### By Volatility

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| High | 57 | 4 | 21/36 | 36.84% | -12.40 | -13.21 | 0.62 | -16.34 |
| Low | 1 | 0 | 0/1 | 0.00% | -1.00 | -0.81 | 0.00 | -1.00 |
| Medium | 3 | 0 | 0/3 | 0.00% | -1.94 | -0.96 | 0.03 | -1.94 |

### By Timeframe

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 15m | 31 | 0 | 12/19 | 38.71% | -6.11 | -3.58 | 0.65 | -7.52 |
| 1h | 2 | 0 | 0/2 | 0.00% | -0.94 | -1.20 | 0.06 | -1.00 |
| 24h | 4 | 2 | 3/1 | 75.00% | 0.54 | 0.30 | 1.53 | -1.00 |
| 4h | 24 | 2 | 6/18 | 25.00% | -8.82 | -10.50 | 0.45 | -11.80 |

### By Setup

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Continuation | 61 | 4 | 21/40 | 34.43% | -15.34 | -14.98 | 0.57 | -19.28 |

### By Bias

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Bullish | 61 | 4 | 21/40 | 34.43% | -15.34 | -14.98 | 0.57 | -19.28 |

## guarded

### Overall

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| overall | 34 | 0 | 17/17 | 50.00% | 3.58 | 4.71 | 1.24 | -6.47 |

### By Month

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-04 | 6 | 0 | 5/1 | 83.33% | 4.09 | 2.26 | 9.25 | -0.50 |
| 2026-05 | 28 | 0 | 12/16 | 42.86% | -0.51 | 2.45 | 0.96 | -6.47 |

### By Regime

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Balanced | 21 | 0 | 8/13 | 38.10% | -3.00 | -1.36 | 0.73 | -7.63 |
| Ranging | 5 | 0 | 4/1 | 80.00% | 3.07 | 2.60 | 4.07 | -1.00 |
| Trending | 8 | 0 | 5/3 | 62.50% | 3.52 | 3.47 | 2.17 | -3.00 |

### By Volatility

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| High | 27 | 0 | 14/13 | 51.85% | 2.97 | 2.65 | 1.27 | -4.01 |
| Medium | 7 | 0 | 3/4 | 42.86% | 0.60 | 2.06 | 1.15 | -3.00 |

### By Timeframe

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 15m | 26 | 0 | 11/15 | 42.31% | -1.43 | 0.37 | 0.89 | -6.46 |
| 4h | 8 | 0 | 6/2 | 75.00% | 5.01 | 4.35 | 3.50 | -2.00 |

### By Setup

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Continuation | 34 | 0 | 17/17 | 50.00% | 3.58 | 4.71 | 1.24 | -6.47 |

### By Bias

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Bearish | 1 | 0 | 0/1 | 0.00% | -1.00 | -1.35 | 0.00 | -1.00 |
| Bullish | 33 | 0 | 17/16 | 51.52% | 4.58 | 6.06 | 1.32 | -5.47 |

## qmid_p06

### Overall

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| overall | 47 | 2 | 26/21 | 55.32% | 8.75 | 9.19 | 1.47 | -6.01 |

### By Month

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-04 | 7 | 0 | 5/2 | 71.43% | 3.65 | 2.08 | 4.88 | -0.94 |
| 2026-05 | 40 | 2 | 21/19 | 52.50% | 5.10 | 7.11 | 1.29 | -6.01 |

### By Regime

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Balanced | 28 | 1 | 13/15 | 46.43% | -0.88 | 0.29 | 0.93 | -7.05 |
| Ranging | 7 | 0 | 4/3 | 57.14% | 1.07 | 1.25 | 1.36 | -3.00 |
| Trending | 12 | 1 | 9/3 | 75.00% | 8.56 | 7.65 | 3.85 | -2.50 |

### By Volatility

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| High | 37 | 0 | 21/16 | 56.76% | 6.99 | 6.54 | 1.52 | -3.13 |
| Low | 2 | 1 | 2/0 | 100.00% | 2.15 | 1.04 | -- | 0.00 |
| Medium | 8 | 1 | 3/5 | 37.50% | -0.40 | 1.61 | 0.92 | -3.00 |

### By Timeframe

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 15m | 36 | 0 | 17/19 | 47.22% | -0.81 | 1.21 | 0.95 | -6.00 |
| 4h | 11 | 2 | 9/2 | 81.82% | 9.56 | 7.98 | 5.78 | -2.00 |

### By Setup

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Continuation | 47 | 2 | 26/21 | 55.32% | 8.75 | 9.19 | 1.47 | -6.01 |

### By Bias

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Bearish | 1 | 0 | 0/1 | 0.00% | -1.00 | -1.35 | 0.00 | -1.00 |
| Bullish | 46 | 2 | 26/20 | 56.52% | 9.75 | 10.54 | 1.56 | -5.01 |

## qmid_p06_15m_only

### Overall

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| overall | 36 | 0 | 17/19 | 47.22% | -0.81 | 1.21 | 0.95 | -6.00 |

### By Month

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-04 | 7 | 0 | 5/2 | 71.43% | 3.65 | 2.08 | 4.88 | -0.94 |
| 2026-05 | 29 | 0 | 12/17 | 41.38% | -4.46 | -0.87 | 0.71 | -6.00 |

### By Regime

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Balanced | 26 | 0 | 12/14 | 46.15% | -0.37 | 0.93 | 0.97 | -6.05 |
| Ranging | 7 | 0 | 4/3 | 57.14% | 1.07 | 1.25 | 1.36 | -3.00 |
| Trending | 3 | 0 | 1/2 | 33.33% | -1.50 | -0.97 | 0.25 | -1.50 |

### By Volatility

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| High | 29 | 0 | 14/15 | 48.28% | -0.47 | 0.06 | 0.96 | -4.51 |
| Low | 1 | 0 | 1/0 | 100.00% | 0.59 | 0.25 | -- | 0.00 |
| Medium | 6 | 0 | 2/4 | 33.33% | -0.93 | 0.90 | 0.77 | -3.00 |

### By Timeframe

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 15m | 36 | 0 | 17/19 | 47.22% | -0.81 | 1.21 | 0.95 | -6.00 |

### By Setup

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Continuation | 36 | 0 | 17/19 | 47.22% | -0.81 | 1.21 | 0.95 | -6.00 |

### By Bias

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Bullish | 36 | 0 | 17/19 | 47.22% | -0.81 | 1.21 | 0.95 | -6.00 |

## qmid_p06_15m_strict

### Overall

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| overall | 5 | 0 | 4/1 | 80.00% | 2.11 | 1.63 | 3.11 | -1.00 |

### By Month

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-04 | 1 | 0 | 1/0 | 100.00% | 0.58 | 0.37 | -- | 0.00 |
| 2026-05 | 4 | 0 | 3/1 | 75.00% | 1.53 | 1.27 | 2.53 | -1.00 |

### By Regime

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Balanced | 3 | 0 | 2/1 | 66.67% | 0.08 | -0.58 | 1.08 | -1.00 |
| Ranging | 2 | 0 | 2/0 | 100.00% | 2.04 | 2.21 | -- | 0.00 |

### By Volatility

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| High | 5 | 0 | 4/1 | 80.00% | 2.11 | 1.63 | 3.11 | -1.00 |

### By Timeframe

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 15m | 5 | 0 | 4/1 | 80.00% | 2.11 | 1.63 | 3.11 | -1.00 |

### By Setup

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Continuation | 5 | 0 | 4/1 | 80.00% | 2.11 | 1.63 | 3.11 | -1.00 |

### By Bias

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Bullish | 5 | 0 | 4/1 | 80.00% | 2.11 | 1.63 | 3.11 | -1.00 |

## qmid_p06_4h_only

### Overall

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| overall | 11 | 2 | 9/2 | 81.82% | 9.56 | 7.98 | 5.78 | -2.00 |

### By Month

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-05 | 11 | 2 | 9/2 | 81.82% | 9.56 | 7.98 | 5.78 | -2.00 |

### By Regime

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Balanced | 2 | 1 | 1/1 | 50.00% | -0.51 | -0.64 | 0.49 | -1.00 |
| Trending | 9 | 1 | 8/1 | 88.89% | 10.06 | 8.62 | 11.06 | -1.00 |

### By Volatility

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| High | 8 | 0 | 7/1 | 87.50% | 7.46 | 6.49 | 8.46 | -1.00 |
| Low | 1 | 1 | 1/0 | 100.00% | 1.56 | 0.78 | -- | 0.00 |
| Medium | 2 | 1 | 1/1 | 50.00% | 0.54 | 0.71 | 1.53 | -1.00 |

### By Timeframe

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 4h | 11 | 2 | 9/2 | 81.82% | 9.56 | 7.98 | 5.78 | -2.00 |

### By Setup

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Continuation | 11 | 2 | 9/2 | 81.82% | 9.56 | 7.98 | 5.78 | -2.00 |

### By Bias

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Bearish | 1 | 0 | 0/1 | 0.00% | -1.00 | -1.35 | 0.00 | -1.00 |
| Bullish | 10 | 2 | 9/1 | 90.00% | 10.56 | 9.33 | 11.56 | -1.00 |

## qmid_p06_4h_runner_2r

### Overall

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| overall | 11 | 2 | 9/2 | 81.82% | 9.50 | 7.94 | 5.75 | -2.00 |

### By Month

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-05 | 11 | 2 | 9/2 | 81.82% | 9.50 | 7.94 | 5.75 | -2.00 |

### By Regime

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Balanced | 2 | 1 | 1/1 | 50.00% | -0.50 | -0.63 | 0.50 | -1.00 |
| Trending | 9 | 1 | 8/1 | 88.89% | 10.00 | 8.57 | 11.00 | -1.00 |

### By Volatility

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| High | 8 | 0 | 7/1 | 87.50% | 7.50 | 6.52 | 8.50 | -1.00 |
| Low | 1 | 1 | 1/0 | 100.00% | 1.50 | 0.75 | -- | 0.00 |
| Medium | 2 | 1 | 1/1 | 50.00% | 0.50 | 0.66 | 1.50 | -1.00 |

### By Timeframe

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 4h | 11 | 2 | 9/2 | 81.82% | 9.50 | 7.94 | 5.75 | -2.00 |

### By Setup

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Continuation | 11 | 2 | 9/2 | 81.82% | 9.50 | 7.94 | 5.75 | -2.00 |

### By Bias

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Bearish | 1 | 0 | 0/1 | 0.00% | -1.00 | -1.35 | 0.00 | -1.00 |
| Bullish | 10 | 2 | 9/1 | 90.00% | 10.50 | 9.29 | 11.50 | -1.00 |

## qmid_p06_4h_runner_3r

### Overall

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| overall | 11 | 2 | 9/2 | 81.82% | 11.50 | 9.02 | 6.75 | -1.00 |

### By Month

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-05 | 11 | 2 | 9/2 | 81.82% | 11.50 | 9.02 | 6.75 | -1.00 |

### By Regime

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Balanced | 2 | 1 | 1/1 | 50.00% | -0.50 | -0.63 | 0.50 | -1.00 |
| Trending | 9 | 1 | 8/1 | 88.89% | 12.00 | 9.65 | 13.00 | -1.00 |

### By Volatility

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| High | 8 | 0 | 7/1 | 87.50% | 10.00 | 8.69 | 11.00 | -1.00 |
| Low | 1 | 1 | 1/0 | 100.00% | 2.00 | 1.00 | -- | 0.00 |
| Medium | 2 | 1 | 1/1 | 50.00% | -0.50 | -0.68 | 0.50 | -1.00 |

### By Timeframe

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 4h | 11 | 2 | 9/2 | 81.82% | 11.50 | 9.02 | 6.75 | -1.00 |

### By Setup

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Continuation | 11 | 2 | 9/2 | 81.82% | 11.50 | 9.02 | 6.75 | -1.00 |

### By Bias

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Bearish | 1 | 0 | 0/1 | 0.00% | -1.00 | -1.35 | 0.00 | -1.00 |
| Bullish | 10 | 2 | 9/1 | 90.00% | 12.50 | 10.37 | 13.50 | -1.00 |

## qmid_p06_ema

### Overall

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| overall | 28 | 0 | 17/11 | 60.71% | 7.77 | 7.93 | 1.71 | -4.50 |

### By Month

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-04 | 4 | 0 | 4/0 | 100.00% | 3.09 | 1.86 | -- | 0.00 |
| 2026-05 | 24 | 0 | 13/11 | 54.17% | 4.68 | 6.08 | 1.43 | -4.50 |

### By Regime

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Balanced | 18 | 0 | 9/9 | 50.00% | -0.30 | 0.26 | 0.97 | -5.92 |
| Ranging | 3 | 0 | 3/0 | 100.00% | 2.53 | 2.79 | -- | 0.00 |
| Trending | 7 | 0 | 5/2 | 71.43% | 5.54 | 4.89 | 3.77 | -2.00 |

### By Volatility

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| High | 22 | 0 | 14/8 | 63.64% | 7.09 | 6.26 | 1.89 | -3.00 |
| Low | 2 | 0 | 2/0 | 100.00% | 2.15 | 1.04 | -- | 0.00 |
| Medium | 4 | 0 | 1/3 | 25.00% | -1.47 | 0.64 | 0.51 | -2.00 |

### By Timeframe

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 15m | 22 | 0 | 12/10 | 54.55% | 1.23 | 2.79 | 1.12 | -5.00 |
| 4h | 6 | 0 | 5/1 | 83.33% | 6.54 | 5.14 | 7.54 | -1.00 |

### By Setup

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Continuation | 28 | 0 | 17/11 | 60.71% | 7.77 | 7.93 | 1.71 | -4.50 |

### By Bias

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Bullish | 28 | 0 | 17/11 | 60.71% | 7.77 | 7.93 | 1.71 | -4.50 |

## qmid_p06_ema_pullback

### Overall

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| overall | 17 | 0 | 9/8 | 52.94% | 2.53 | 4.36 | 1.32 | -4.50 |

### By Month

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-04 | 2 | 0 | 2/0 | 100.00% | 2.02 | 1.22 | -- | 0.00 |
| 2026-05 | 15 | 0 | 7/8 | 46.67% | 0.51 | 3.14 | 1.06 | -4.50 |

### By Regime

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Balanced | 10 | 0 | 3/7 | 30.00% | -3.49 | -2.05 | 0.50 | -5.50 |
| Ranging | 3 | 0 | 3/0 | 100.00% | 2.53 | 2.79 | -- | 0.00 |
| Trending | 4 | 0 | 3/1 | 75.00% | 3.48 | 3.62 | 4.49 | -1.00 |

### By Volatility

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| High | 16 | 0 | 9/7 | 56.25% | 3.53 | 4.83 | 1.50 | -3.50 |
| Medium | 1 | 0 | 0/1 | 0.00% | -1.00 | -0.46 | 0.00 | -1.00 |

### By Timeframe

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 15m | 13 | 0 | 6/7 | 46.15% | -0.96 | 0.94 | 0.86 | -5.00 |
| 4h | 4 | 0 | 3/1 | 75.00% | 3.48 | 3.43 | 4.49 | -1.00 |

### By Setup

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Continuation | 17 | 0 | 9/8 | 52.94% | 2.53 | 4.36 | 1.32 | -4.50 |

### By Bias

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Bullish | 17 | 0 | 9/8 | 52.94% | 2.53 | 4.36 | 1.32 | -4.50 |

## qmid_p06_failfast

### Overall

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| overall | 47 | 2 | 23/24 | 48.94% | 6.45 | 7.55 | 1.40 | -6.87 |

### By Month

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-04 | 7 | 0 | 5/2 | 71.43% | 3.65 | 2.08 | 4.88 | -0.94 |
| 2026-05 | 40 | 2 | 18/22 | 45.00% | 2.80 | 5.47 | 1.18 | -6.87 |

### By Regime

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Balanced | 28 | 1 | 13/15 | 46.43% | 1.16 | 1.99 | 1.11 | -5.36 |
| Ranging | 7 | 0 | 3/4 | 42.86% | 0.06 | -0.27 | 1.02 | -2.51 |
| Trending | 12 | 1 | 7/5 | 58.33% | 5.23 | 5.83 | 2.60 | -2.50 |

### By Volatility

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| High | 37 | 0 | 19/18 | 51.35% | 6.14 | 5.64 | 1.54 | -3.87 |
| Low | 2 | 1 | 1/1 | 50.00% | 0.52 | 0.22 | 7.98 | -0.07 |
| Medium | 8 | 1 | 3/5 | 37.50% | -0.21 | 1.70 | 0.96 | -3.00 |

### By Timeframe

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 15m | 36 | 0 | 16/20 | 44.44% | -0.42 | 0.58 | 0.97 | -6.07 |
| 4h | 11 | 2 | 7/4 | 63.64% | 6.87 | 6.97 | 5.20 | -1.36 |

### By Setup

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Continuation | 47 | 2 | 23/24 | 48.94% | 6.45 | 7.55 | 1.40 | -6.87 |

### By Bias

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Bearish | 1 | 0 | 0/1 | 0.00% | -1.00 | -1.35 | 0.00 | -1.00 |
| Bullish | 46 | 2 | 23/23 | 50.00% | 7.45 | 8.90 | 1.49 | -5.87 |

## qmid_p07

### Overall

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| overall | 52 | 3 | 29/23 | 55.77% | 8.32 | 8.60 | 1.41 | -6.51 |

### By Month

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-04 | 8 | 0 | 6/2 | 75.00% | 4.14 | 2.67 | 5.41 | -0.94 |
| 2026-05 | 44 | 3 | 23/21 | 52.27% | 4.17 | 5.93 | 1.21 | -6.51 |

### By Regime

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Balanced | 29 | 1 | 14/15 | 48.28% | -0.38 | 0.89 | 0.97 | -7.05 |
| Ranging | 7 | 0 | 4/3 | 57.14% | 1.07 | 1.25 | 1.36 | -3.00 |
| Trending | 16 | 2 | 11/5 | 68.75% | 7.63 | 6.46 | 2.55 | -3.93 |

### By Volatility

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| High | 40 | 1 | 24/16 | 60.00% | 8.48 | 8.41 | 1.63 | -3.13 |
| Low | 3 | 1 | 2/1 | 66.67% | 1.15 | -0.18 | 2.15 | -1.00 |
| Medium | 9 | 1 | 3/6 | 33.33% | -1.31 | 0.37 | 0.78 | -3.38 |

### By Timeframe

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 15m | 37 | 0 | 18/19 | 48.65% | -0.32 | 1.80 | 0.98 | -6.00 |
| 4h | 15 | 3 | 11/4 | 73.33% | 8.63 | 6.80 | 3.20 | -3.00 |

### By Setup

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Continuation | 52 | 3 | 29/23 | 55.77% | 8.32 | 8.60 | 1.41 | -6.51 |

### By Bias

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Bearish | 1 | 0 | 0/1 | 0.00% | -1.00 | -1.35 | 0.00 | -1.00 |
| Bullish | 51 | 3 | 29/22 | 56.86% | 9.32 | 9.95 | 1.48 | -5.51 |

## qmid_p07_ema

### Overall

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| overall | 31 | 1 | 18/13 | 58.06% | 6.35 | 6.07 | 1.49 | -5.89 |

### By Month

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-04 | 5 | 0 | 5/0 | 100.00% | 3.59 | 2.45 | -- | 0.00 |
| 2026-05 | 26 | 1 | 13/13 | 50.00% | 2.76 | 3.62 | 1.21 | -5.89 |

### By Regime

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Balanced | 19 | 0 | 10/9 | 52.63% | 0.20 | 0.85 | 1.02 | -5.92 |
| Ranging | 3 | 0 | 3/0 | 100.00% | 2.53 | 2.79 | -- | 0.00 |
| Trending | 9 | 1 | 5/4 | 55.56% | 3.62 | 2.43 | 1.92 | -3.92 |

### By Volatility

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| High | 23 | 1 | 15/8 | 65.22% | 7.58 | 6.85 | 1.95 | -3.00 |
| Low | 3 | 0 | 2/1 | 66.67% | 1.15 | -0.18 | 2.15 | -1.00 |
| Medium | 5 | 0 | 1/4 | 20.00% | -2.38 | -0.60 | 0.39 | -2.38 |

### By Timeframe

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 15m | 23 | 0 | 13/10 | 56.52% | 1.73 | 3.39 | 1.17 | -5.00 |
| 4h | 8 | 1 | 5/3 | 62.50% | 4.62 | 2.69 | 2.58 | -2.92 |

### By Setup

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Continuation | 31 | 1 | 18/13 | 58.06% | 6.35 | 6.07 | 1.49 | -5.89 |

### By Bias

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Bullish | 31 | 1 | 18/13 | 58.06% | 6.35 | 6.07 | 1.49 | -5.89 |

## quality_soft

### Overall

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| overall | 106 | 6 | 46/60 | 43.40% | -9.61 | -10.16 | 0.82 | -17.37 |

### By Month

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-04 | 51 | 1 | 18/33 | 35.29% | -11.78 | -13.46 | 0.57 | -14.81 |
| 2026-05 | 55 | 5 | 28/27 | 50.91% | 2.17 | 3.30 | 1.09 | -6.89 |

### By Regime

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Balanced | 43 | 0 | 20/23 | 46.51% | -2.93 | 0.21 | 0.85 | -9.64 |
| Ranging | 13 | 0 | 6/7 | 46.15% | -0.75 | -1.01 | 0.88 | -3.00 |
| Trending | 50 | 6 | 20/30 | 40.00% | -5.94 | -9.36 | 0.77 | -15.51 |

### By Volatility

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| High | 87 | 4 | 38/49 | 43.68% | -7.98 | -11.31 | 0.81 | -17.05 |
| Medium | 19 | 2 | 8/11 | 42.11% | -1.64 | 1.15 | 0.85 | -2.46 |

### By Timeframe

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 15m | 58 | 0 | 25/33 | 43.10% | -6.10 | -2.09 | 0.79 | -7.16 |
| 24h | 12 | 3 | 7/5 | 58.33% | 3.02 | 2.41 | 1.85 | -2.56 |
| 4h | 36 | 3 | 14/22 | 38.89% | -6.53 | -10.48 | 0.68 | -12.62 |

### By Setup

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Continuation | 106 | 6 | 46/60 | 43.40% | -9.61 | -10.16 | 0.82 | -17.37 |

### By Bias

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Bearish | 3 | 0 | 0/3 | 0.00% | -3.00 | -3.46 | 0.00 | -3.00 |
| Bullish | 103 | 6 | 46/57 | 44.66% | -6.61 | -6.70 | 0.87 | -15.37 |

## tf_profile

### Overall

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| overall | 34 | 3 | 18/16 | 52.94% | 3.73 | 4.72 | 1.29 | -4.19 |

### By Month

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-04 | 10 | 1 | 3/7 | 30.00% | -3.14 | -3.61 | 0.33 | -3.14 |
| 2026-05 | 24 | 2 | 15/9 | 62.50% | 6.87 | 8.33 | 1.85 | -3.00 |

### By Regime

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Balanced | 9 | 0 | 4/5 | 44.44% | -1.40 | -0.77 | 0.69 | -4.50 |
| Ranging | 3 | 0 | 3/0 | 100.00% | 2.53 | 2.79 | -- | 0.00 |
| Trending | 22 | 3 | 11/11 | 50.00% | 2.60 | 2.71 | 1.31 | -5.26 |

### By Volatility

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| High | 31 | 2 | 16/15 | 51.61% | 1.66 | 2.02 | 1.14 | -4.19 |
| Medium | 3 | 1 | 2/1 | 66.67% | 2.07 | 2.70 | 3.07 | -1.00 |

### By Timeframe

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 15m | 9 | 0 | 6/3 | 66.67% | 2.64 | 3.30 | 2.05 | -1.50 |
| 24h | 6 | 3 | 3/3 | 50.00% | -0.02 | -0.14 | 0.98 | -1.56 |
| 4h | 19 | 0 | 9/10 | 47.37% | 1.11 | 1.57 | 1.13 | -3.70 |

### By Setup

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Continuation | 34 | 3 | 18/16 | 52.94% | 3.73 | 4.72 | 1.29 | -4.19 |

### By Bias

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Bearish | 1 | 0 | 0/1 | 0.00% | -1.00 | -1.35 | 0.00 | -1.00 |
| Bullish | 33 | 3 | 18/15 | 54.55% | 4.73 | 6.07 | 1.40 | -4.19 |

## tf_simple

### Overall

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| overall | 72 | 4 | 34/38 | 47.22% | 3.33 | 4.09 | 1.10 | -6.95 |

### By Month

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 2026-04 | 19 | 1 | 6/13 | 31.58% | -3.57 | -5.98 | 0.63 | -3.63 |
| 2026-05 | 53 | 3 | 28/25 | 52.83% | 6.90 | 10.07 | 1.31 | -6.95 |

### By Regime

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Balanced | 28 | 0 | 11/17 | 39.29% | -3.96 | -3.11 | 0.73 | -10.14 |
| Ranging | 7 | 0 | 4/3 | 57.14% | 1.07 | 1.25 | 1.36 | -3.00 |
| Trending | 37 | 4 | 19/18 | 51.35% | 6.23 | 5.95 | 1.42 | -8.19 |

### By Volatility

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| High | 61 | 2 | 29/32 | 47.54% | 2.66 | 1.26 | 1.10 | -6.02 |
| Medium | 11 | 2 | 5/6 | 45.45% | 0.68 | 2.83 | 1.11 | -2.00 |

### By Timeframe

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 15m | 32 | 0 | 15/17 | 46.88% | 0.10 | 2.15 | 1.01 | -5.01 |
| 24h | 11 | 3 | 6/5 | 54.55% | 2.53 | 1.79 | 1.71 | -2.56 |
| 4h | 29 | 1 | 13/16 | 44.83% | 0.70 | 0.15 | 1.05 | -6.13 |

### By Setup

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Continuation | 72 | 4 | 34/38 | 47.22% | 3.33 | 4.09 | 1.10 | -6.95 |

### By Bias

| Segment | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Bearish | 1 | 0 | 0/1 | 0.00% | -1.00 | -1.35 | 0.00 | -1.00 |
| Bullish | 71 | 4 | 34/37 | 47.89% | 4.33 | 5.44 | 1.14 | -5.95 |
