# Q11 check: games under vs over 32:00 at Worlds 2026

Code: `crystal/q11_check.py` (run: `python -m crystal.q11_check`). Tables: `outputs/q11/gap_by_year.csv`, `backtest.csv`, `variants.csv`, log in `q11_run.log`.

## Bottom line

**Recommendation: After, P ≈ 0.62** (not 0.88). The 0.88 treats the Worlds target share as exactly 0.44. Once the target's own uncertainty (about 8 points) is added, the lean toward "After" is weak. The best single method gives 0.71, the second-best backtest method gives 0.53, and the backtest-weighted average of all methods gives 0.47. Treat this as close to a coin flip with a slight After lean.

## 1. Worlds gap by year (share of games under 32:00, %)

Domestic = LCK, LPL, LEC, LCS, LCP, CBLOL. Intl = MSI, FST, EWC of the same year. Pre-Worlds window = the 6 weeks before the first Worlds game (2026: from 15 Oct, the lock date). Gap = Worlds minus comparison (negative = Worlds games longer).

| Year | Worlds (n) | Intl same year (n) | Gap vs intl | Domestic 6 wk (n) | Gap vs dom 6 wk | Domestic full year | Gap vs dom year |
|---|---|---|---|---|---|---|---|
| 2022 | 59.8 (127) | 63.8 (80) | -3.9 | 44.9 (156) | +15.0 | 51.1 | +8.7 |
| 2023 | 62.0 (113) | 64.5 (76) | -2.5 | 72.7 (22) | -10.8 | 57.4 | +4.5 |
| 2024 | 48.1 (106) | 65.0 (97) | -16.8 | 55.8 (165) | -7.6 | 52.9 | -4.8 |
| 2025 | 48.8 (84) | 58.8 (148) | -10.0 | 59.8 (209) | -11.0 | 54.3 | -5.5 |
| 2026 (pre-Worlds) | n/a | 52.7 (167) | | 57.0 (223) | | 50.4 | |

- The Worlds-vs-intl gap is negative in all four years (mean -8.3, sd about 6.4). That sign consistency is the main reason to prefer the intl-based projection.
- The domestic gap changes sign, and 2023's 6-week window has only 22 games.
- The 2026 domestic majors have only played patch 16.16-16.17. The Worlds patch (16.20) has not been played by any major league yet.

## 2. Out-of-sample backtest (Worlds 2023-25)

Each method uses only data before that year's Worlds. Error = predicted minus actual, in points.

| Method | 2023 | 2024 | 2025 | RMSE |
|---|---|---|---|---|
| Last Worlds | -2.1 | +13.8 | -0.7 | 8.1 |
| Mean of prior Worlds | -2.1 | +12.8 | +7.8 | 8.7 |
| **Same-year intl + prior intl gap (chosen)** | -1.4 | +13.6 | +2.2 | **8.0** |
| Same-year intl, no gap | +2.5 | +16.8 | +10.0 | 11.4 |
| 6-week domestic + prior gap | +25.8 | +9.7 | +9.9 | 16.9 |
| 6-week domestic, no gap | +10.8 | +7.6 | +11.0 | 9.9 |
| 8-week domestic + prior gap | +9.3 | +17.1 | +11.5 | 13.1 |

Target sd used = 8.0 points (the chosen method's RMSE). With only three test years this estimate is itself rough. The 2024 error (about +14) is the main driver. The domestic-based methods are worse, so the recent-domestic tempo does not beat same-year internationals as a predictor here.

## 3. 2026 projections (Worlds under-share)

| Projection | Mean | sd (backtest RMSE) |
|---|---|---|
| Intl 2026 + mean gap (chosen) | 44.4 | 8.0 |
| Last Worlds (2025) | 48.8 | 8.1 |
| Intl 2026, no gap | 52.7 | 11.4 |
| Mean of Worlds 2022-25 | 54.7 | 8.7 |
| 6-week domestic + gap | 53.3 | 16.9 |
| 6-week domestic, no gap | 57.0 | 9.9 |

The current 0.44 matches the chosen intl-based mean. The real gap is that it has no spread. The methods disagree by about 10 points, which is larger than the 6-point gap to 0.50.

Patch check: a league-adjusted regression on 2026 games gives patch 16.18 about +0.1 points and 16.20 about +2.0 points versus 16.17 (only 78 games on 16.20). The raw "16.20 is very fast" figure comes from league mix (LAS, EM), so patch tempo does not move the target much.

## 4. P(After) by variant

Per-sim target: each simulation draws its own share from Normal(mean, sd) and is shifted to hit it. Same simulation as `crystal/estimate.py` (seed 11 / seed 12, 20,000 sims, about 103 games per sim).

| Variant | Mean | sd | P(After) s11 / s12 | P(Before) | P(tie) | Normal approx |
|---|---|---|---|---|---|---|
| (a) Current: fixed 0.44 | 0.440 | 0 | 0.879 / 0.881 | 0.10 | 0.02 | 0.890 |
| (b) Fixed 0.44 + target sd | 0.440 | 0.080 | 0.734 / 0.732 | 0.25 | 0.02 | 0.739 |
| **(c) Rebuilt: intl + gap, with sd** | 0.444 | 0.080 | 0.711 / 0.718 | 0.27 | 0.02 | 0.725 |
| s1 Intl 2026, no gap | 0.527 | 0.114 | 0.405 / 0.408 | 0.58 | 0.02 | 0.414 |
| s2 Recent domestic 6 wk + gap | 0.533 | 0.169 | 0.421 / 0.418 | 0.57 | 0.01 | 0.425 |
| s3 Mean of Worlds 2022-25 | 0.547 | 0.087 | 0.316 / 0.314 | 0.67 | 0.02 | 0.320 |
| s4 Last Worlds (2025) | 0.488 | 0.081 | 0.534 / 0.539 | 0.44 | 0.02 | 0.550 |
| s5 Recent domestic 6 wk, no gap | 0.570 | 0.099 | 0.257 / 0.257 | 0.73 | 0.01 | 0.265 |
| Average of projections (inverse MSE) | | | 0.468 / 0.471 | | | |

The "average" row weights each projection by 1/RMSE², using (c) and s1-s5. Recommendation = equal weight of (c) and s4 (0.71 and 0.53, averaged in each seed, about 0.62).

## 5. Verification

| # | Check | Result |
|---|---|---|
| 1 | Baseline (a): P(After) 0.88 ± 0.02, share 0.44 | **PASS**: 0.879 (seed 11), 0.881 (seed 12); share 0.440 |
| 2 | Base rates: Worlds 2024 48.1%, 2025 48.8% (±0.5) | **PASS**: 48.11% (51/106), 48.81% (41/84) |
| 3 | Normal approx for (c) within 0.03 of simulation | **PASS**: 0.711 vs 0.725 (diff 0.014); 0.718 vs 0.725 (diff 0.007) |
| 4 | Seeds 11 and 12 agree within 0.01 on every variant | **PASS**: largest gap 0.007 (variant c), 0.005 (s4), all others 0.003 or less |

Boundary and tie rules:
- **32:00 counts as "after" in the code.** Under means duration < 1920 s, so exactly 32:00 is not under. This matches `base_rates.py` (`>= 32:00` is the "over" group). In the database, 58 games are exactly 1920 s and none are Worlds games. The simulation uses continuous durations, so it essentially never hits exactly 32:00.
- **Ties (exactly half the games under) are counted as neither** in P(After). They are about 1.5-2% of sims (e.g. 1.7% in (c)). If Crystal Ball resolves ties in favour of one side, that side's probability goes up by that amount.

## Caveats

- Backtest has three test years. The RMSE values are noisy, and the Worlds regime changed between 2022-23 (about 60% under) and 2024-25 (about 48%).
- The normal target distribution is an assumption. A two-regime distribution would widen the tails.
- The simulation keeps the mismatch and winner-speed terms from `estimate.py`. Only the constant shift is replaced by a per-sim target.
