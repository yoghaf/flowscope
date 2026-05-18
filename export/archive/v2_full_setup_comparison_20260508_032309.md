# V2 Full Setup Lab

- Generated: `2026-05-08T03:23:09.538090+00:00`
- Database: `postgresql+asyncpg://localhost:5432/flowscope_replay_vps_20260507_123757`
- Symbols: `386`
- Days: `40`
- Full setup promotion: `Ready` non-Continuation setups become replay entries only after normal hard/post filters and entry-touch checks.

## Headline

| Strategy | Closed | Open | W/L | WR | Total R | Alloc R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| v2_balanced_continuation_only | 410 | 7 | 189/221 | 46.10% | 28.47 | 35.88 | 1.18 | -25.89 |
| v2_all_setups_triggered_only | 411 | 7 | 189/222 | 45.99% | 28.38 | 35.86 | 1.18 | -25.89 |
| v2_full_setup_ready_entry | 7622 | 118 | 2959/4663 | 38.82% | -396.13 | -118.21 | 0.88 | -412.32 |

## By Setup

### v2_balanced_continuation_only

| Setup | Closed | Open | W/L | WR | Total R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|
| Continuation | 410 | 7 | 189/221 | 46.10% | 28.47 | 1.18 | -25.89 |

### v2_all_setups_triggered_only

| Setup | Closed | Open | W/L | WR | Total R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|
| Continuation | 410 | 7 | 189/221 | 46.10% | 28.47 | 1.18 | -25.89 |
| Squeeze | 1 | 0 | 0/1 | 0.00% | -0.09 | 0.00 | -0.09 |

### v2_full_setup_ready_entry

| Setup | Closed | Open | W/L | WR | Total R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|
| Accumulation | 6810 | 96 | 2652/4158 | 38.94% | -393.52 | 0.86 | -410.99 |
| Breakout | 13 | 0 | 8/5 | 61.54% | 4.82 | 2.15 | -1.73 |
| Continuation | 290 | 4 | 130/160 | 44.83% | 14.30 | 1.13 | -16.93 |
| Squeeze | 192 | 8 | 62/130 | 32.29% | -12.67 | 0.83 | -18.89 |
| Trap | 317 | 10 | 107/210 | 33.75% | -9.07 | 0.92 | -29.75 |

## By Timeframe

### v2_balanced_continuation_only

| TF | Closed | Open | W/L | WR | Total R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|
| 15m | 132 | 0 | 49/83 | 37.12% | -5.27 | 0.90 | -18.56 |
| 1h | 63 | 0 | 26/37 | 41.27% | -0.16 | 0.99 | -9.05 |
| 24h | 18 | 7 | 9/9 | 50.00% | 3.46 | 1.65 | -3.75 |
| 4h | 197 | 0 | 105/92 | 53.30% | 30.43 | 1.44 | -11.48 |

### v2_all_setups_triggered_only

| TF | Closed | Open | W/L | WR | Total R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|
| 15m | 133 | 0 | 49/84 | 36.84% | -5.36 | 0.90 | -18.56 |
| 1h | 63 | 0 | 26/37 | 41.27% | -0.16 | 0.99 | -9.05 |
| 24h | 18 | 7 | 9/9 | 50.00% | 3.46 | 1.65 | -3.75 |
| 4h | 197 | 0 | 105/92 | 53.30% | 30.43 | 1.44 | -11.79 |

### v2_full_setup_ready_entry

| TF | Closed | Open | W/L | WR | Total R | PF R | Max DD R |
|---|---:|---:|---:|---:|---:|---:|---:|
| 15m | 5259 | 27 | 2059/3200 | 39.15% | -354.22 | 0.85 | -372.90 |
| 1h | 1540 | 38 | 593/947 | 38.51% | -17.46 | 0.97 | -55.25 |
| 24h | 53 | 16 | 20/33 | 37.74% | -2.02 | 0.89 | -11.43 |
| 4h | 770 | 37 | 287/483 | 37.27% | -22.43 | 0.92 | -41.49 |

