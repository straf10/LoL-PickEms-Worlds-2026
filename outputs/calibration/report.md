# Calibration of the team Bradley-Terry model (backtest on 12 international events)

Predictions: `model.backtest.bt_predict` via `model.backtest.evaluate` (899 games, 37 unrateable games skipped, 862 analysed). Each prediction uses only data before its event start, so the predictions are already out-of-sample.

Caveats: (1) `cross_region` uses each team's current region (`model.ratings.team_regions`, same as the model uses), not its region at the event. (2) Bo1-ish is an approximation: game 1 of its series with no other game between the same teams in that league on the same UTC day.

## 1. Reliability (favourite's predicted probability vs actual win rate)

| bin | n | pred_fav | actual_fav | gap | se |
|---|---|---|---|---|---|
| 50-55 | 179 | 0.525 | 0.547 | 0.023 | 0.037 |
| 55-60 | 160 | 0.578 | 0.550 | -0.028 | 0.039 |
| 60-65 | 96 | 0.623 | 0.500 | -0.123 | 0.049 |
| 65-70 | 85 | 0.676 | 0.565 | -0.111 | 0.051 |
| 70-75 | 95 | 0.724 | 0.758 | 0.034 | 0.046 |
| 75-80 | 100 | 0.773 | 0.760 | -0.013 | 0.042 |
| 80-85 | 81 | 0.825 | 0.877 | 0.051 | 0.042 |
| 85+ | 66 | 0.888 | 0.864 | -0.024 | 0.039 |

Overall: n=862, predicted favourite 0.667, actual 0.647, gap -2.0 pp, ECE 0.047.

## 2. Splits

| subgroup | n | pred_fav | actual_fav | gap_pp | ECE | log_loss_raw | brier_raw |
|---|---|---|---|---|---|---|---|
| all | 862 | 0.667 | 0.647 | -1.998 | 0.047 | 0.613 | 0.213 |
| Bo1-ish vs in-series: Bo1-ish | 153 | 0.709 | 0.765 | 5.525 | 0.084 | 0.491 | 0.161 |
| Bo1-ish vs in-series: in-series | 709 | 0.658 | 0.622 | -3.621 | 0.052 | 0.639 | 0.224 |
| same-region vs cross-region: same-region | 127 | 0.549 | 0.630 | 8.086 | 0.114 | 0.675 | 0.241 |
| same-region vs cross-region: cross-region | 735 | 0.688 | 0.650 | -3.740 | 0.057 | 0.602 | 0.208 |
| blue-side vs red-side favourite: blue-side fav | 511 | 0.674 | 0.673 | -0.122 | 0.057 | 0.591 | 0.204 |
| blue-side vs red-side favourite: red-side fav | 351 | 0.657 | 0.610 | -4.728 | 0.072 | 0.643 | 0.226 |

### Bo1-ish vs in-series

| group | fav_prob_bin | n | pred_fav | actual_fav | gap | se |
|---|---|---|---|---|---|---|
| Bo1-ish | 50-55 | 18 | 0.523 | 0.556 | 0.033 | 0.118 |
| Bo1-ish | 55-60 | 19 | 0.577 | 0.632 | 0.055 | 0.113 |
| Bo1-ish | 60-65 | 21 | 0.628 | 0.524 | -0.104 | 0.105 |
| Bo1-ish | 65-70 | 12 | 0.677 | 0.750 | 0.073 | 0.135 |
| Bo1-ish | 70-75 | 20 | 0.723 | 0.800 | 0.077 | 0.100 |
| Bo1-ish | 75-80 | 18 | 0.767 | 0.833 | 0.066 | 0.100 |
| Bo1-ish | 80-85 | 22 | 0.824 | 1.000 | 0.176 | 0.081 |
| Bo1-ish | 85+ | 23 | 0.889 | 0.957 | 0.067 | 0.065 |
| in-series | 50-55 | 161 | 0.525 | 0.547 | 0.022 | 0.039 |
| in-series | 55-60 | 141 | 0.578 | 0.539 | -0.039 | 0.042 |
| in-series | 60-65 | 75 | 0.622 | 0.493 | -0.129 | 0.056 |
| in-series | 65-70 | 73 | 0.676 | 0.534 | -0.142 | 0.055 |
| in-series | 70-75 | 75 | 0.725 | 0.747 | 0.022 | 0.052 |
| in-series | 75-80 | 82 | 0.775 | 0.744 | -0.031 | 0.046 |
| in-series | 80-85 | 59 | 0.826 | 0.831 | 0.005 | 0.049 |
| in-series | 85+ | 43 | 0.887 | 0.814 | -0.073 | 0.048 |

### same-region vs cross-region

| group | fav_prob_bin | n | pred_fav | actual_fav | gap | se |
|---|---|---|---|---|---|---|
| same-region | 50-55 | 68 | 0.522 | 0.632 | 0.110 | 0.061 |
| same-region | 55-60 | 54 | 0.576 | 0.667 | 0.091 | 0.067 |
| same-region | 60-65 | 5 | 0.621 | 0.200 | -0.421 | 0.217 |
| same-region | 65-70 | 0 |  |  |  |  |
| same-region | 70-75 | 0 |  |  |  |  |
| same-region | 75-80 | 0 |  |  |  |  |
| same-region | 80-85 | 0 |  |  |  |  |
| same-region | 85+ | 0 |  |  |  |  |
| cross-region | 50-55 | 111 | 0.526 | 0.495 | -0.031 | 0.047 |
| cross-region | 55-60 | 106 | 0.579 | 0.491 | -0.088 | 0.048 |
| cross-region | 60-65 | 91 | 0.623 | 0.516 | -0.107 | 0.051 |
| cross-region | 65-70 | 85 | 0.676 | 0.565 | -0.111 | 0.051 |
| cross-region | 70-75 | 95 | 0.724 | 0.758 | 0.034 | 0.046 |
| cross-region | 75-80 | 100 | 0.773 | 0.760 | -0.013 | 0.042 |
| cross-region | 80-85 | 81 | 0.825 | 0.877 | 0.051 | 0.042 |
| cross-region | 85+ | 66 | 0.888 | 0.864 | -0.024 | 0.039 |

### blue-side vs red-side favourite

| group | fav_prob_bin | n | pred_fav | actual_fav | gap | se |
|---|---|---|---|---|---|---|
| blue-side fav | 50-55 | 78 | 0.524 | 0.564 | 0.040 | 0.057 |
| blue-side fav | 55-60 | 113 | 0.578 | 0.602 | 0.024 | 0.046 |
| blue-side fav | 60-65 | 64 | 0.623 | 0.484 | -0.139 | 0.061 |
| blue-side fav | 65-70 | 56 | 0.677 | 0.571 | -0.106 | 0.062 |
| blue-side fav | 70-75 | 49 | 0.724 | 0.776 | 0.051 | 0.064 |
| blue-side fav | 75-80 | 49 | 0.774 | 0.857 | 0.083 | 0.060 |
| blue-side fav | 80-85 | 53 | 0.822 | 0.849 | 0.027 | 0.053 |
| blue-side fav | 85+ | 49 | 0.891 | 0.898 | 0.007 | 0.045 |
| red-side fav | 50-55 | 101 | 0.525 | 0.535 | 0.009 | 0.050 |
| red-side fav | 55-60 | 47 | 0.577 | 0.426 | -0.151 | 0.072 |
| red-side fav | 60-65 | 32 | 0.623 | 0.531 | -0.092 | 0.086 |
| red-side fav | 65-70 | 29 | 0.673 | 0.552 | -0.122 | 0.087 |
| red-side fav | 70-75 | 46 | 0.724 | 0.739 | 0.015 | 0.066 |
| red-side fav | 75-80 | 51 | 0.772 | 0.667 | -0.106 | 0.059 |
| red-side fav | 80-85 | 28 | 0.832 | 0.929 | 0.097 | 0.071 |
| red-side fav | 85+ | 17 | 0.880 | 0.765 | -0.115 | 0.079 |

## 3. Leave-one-event-out CV (fit on 11 events, score the held-out 12th; pooled out-of-fold scores)

| calibrator | log_loss | brier | log_loss_cross | log_loss_same | brier_cross | brier_same | d_logloss_vs_raw |
|---|---|---|---|---|---|---|---|
| raw (uncalibrated) | 0.613 | 0.213 | 0.602 | 0.675 | 0.208 | 0.241 | 0.000 |
| slope (b=0) | 0.613 | 0.213 | 0.602 | 0.676 | 0.208 | 0.242 | 0.001 |
| slope + cross-region slope | 0.614 | 0.213 | 0.602 | 0.681 | 0.208 | 0.243 | 0.001 |
| platt (a,b) | 0.613 | 0.213 | 0.603 | 0.672 | 0.208 | 0.239 | 0.001 |
| platt + cross-region slope | 0.614 | 0.213 | 0.603 | 0.678 | 0.208 | 0.242 | 0.002 |
| isotonic | 0.641 | 0.214 | 0.635 | 0.680 | 0.209 | 0.243 | 0.029 |

Per-event held-out log-loss:

| event | games | isotonic | platt (a,b) | platt + cross-region slope | raw (uncalibrated) | slope (b=0) | slope + cross-region slope |
|---|---|---|---|---|---|---|---|
| Worlds 2022 | 113 | 0.567 | 0.580 | 0.585 | 0.578 | 0.579 | 0.584 |
| MSI 2023 | 69 | 0.576 | 0.580 | 0.577 | 0.574 | 0.576 | 0.572 |
| Worlds 2023 | 109 | 0.599 | 0.603 | 0.602 | 0.605 | 0.606 | 0.603 |
| MSI 2024 | 74 | 0.936 | 0.621 | 0.621 | 0.625 | 0.623 | 0.622 |
| Worlds 2024 | 98 | 0.625 | 0.613 | 0.613 | 0.615 | 0.615 | 0.614 |
| First Stand 2025 | 35 | 0.837 | 0.794 | 0.791 | 0.789 | 0.787 | 0.785 |
| MSI 2025 | 80 | 0.675 | 0.648 | 0.648 | 0.646 | 0.645 | 0.645 |
| EWC 2025 | 33 | 0.593 | 0.605 | 0.606 | 0.614 | 0.614 | 0.612 |
| Worlds 2025 | 84 | 0.616 | 0.615 | 0.618 | 0.603 | 0.607 | 0.614 |
| First Stand 2026 | 45 | 0.640 | 0.608 | 0.606 | 0.616 | 0.616 | 0.612 |
| MSI 2026 | 71 | 0.582 | 0.605 | 0.607 | 0.611 | 0.611 | 0.612 |
| EWC 2026 | 51 | 0.559 | 0.581 | 0.589 | 0.575 | 0.578 | 0.589 |

## 4. Parameters fitted on all 12 events

| calibrator | a (same-region slope) | a_cross | b |
|---|---|---|---|
| slope | 0.931 |  | 0.000 |
| slope + cross | 1.812 | 0.920 | 0.000 |
| platt | 0.913 |  | 0.099 |
| platt + cross | 1.582 | 0.907 | 0.083 |
| isotonic | (isotonic, 35 thresholds) | | |

## 5. Recommendation

**Recommendation: no calibration needed for the team Bradley-Terry model.** Keep the identity calibrator
(`outputs/calibration/calibrator.json`) so downstream code can always call `Calibrator.load().transform(...)`.

- **Overall reliability is good.** Favourite predicted 0.667, actual 0.647 (gap -2.0 pp, ECE 0.047, 862 games).
  The 60-70% bins look over-confident (actual 0.50-0.57 vs predicted 0.62-0.68, about 2 SE each), but there is no
  consistent direction across bins. The 75-85% bins are slightly under-confident.
- **Slope fit on all 12 events:** a = 0.931 (b = 0). The model is very slightly over-confident, within noise.
- **LOEO-CV:** no calibrator beats raw. Pooled log-loss: raw 0.613, slope 0.613, Platt 0.613, isotonic 0.641
  (isotonic is worse: the MSI 2024 fold goes to 0.936). Brier is 0.213 for all but isotonic.
- **Cross-region slope:** the fit gives a_cross = 0.92 for cross-region games and 1.81 for same-region games. Out of fold
  it changes nothing for cross-region games (log-loss 0.602 vs 0.602), and it makes same-region games (n = 127) worse
  (0.675 to 0.681). The model's region gaps are not systematically mis-stated, so no separate cross-region slope is used.
- **Residual patterns, not corrected by any calibrator:** Bo1-ish games are under-predicted (+5.5 pp, n = 153; the
  Bo1 vs series difference is about 2 SE) and red-side favourites under-perform (-4.7 pp, n = 351, about 1.2 SE).
  Mean P(blue) is 0.540 vs an actual blue win rate of 0.558, a small side-bias gap.
- **Play-In implication:** calibration moves the Play-In numbers by at most about 0.005 per game. The gap to the
  bookmakers is about ratings, not calibration. CBLOL sits at the bottom of the region table (-0.74) and LCP at -0.57,
  so FURIA and MVK are rated almost equal. Bookmakers have FURIA at about 0.75 Bo5, the model at 0.49. Flag this
  before freeze.

Saved: `outputs\calibration\calibrator.json` = Calibrator(slope, a=1.000, b=0.000, n_fit=862). Refit for another model with `fit_calibrator(preds, method, cross_region_col)`.

## 6. Play-In probabilities (team model as of 2026-10-15, default Params)

| pair | cross_region | calibrator | raw_game | game | raw_bo5 | bo5 |
|---|---|---|---|---|---|---|
| FURIA vs MVK Esports | True | uncalibrated | 0.493 | 0.493 | 0.487 | 0.487 |
| FURIA vs MVK Esports | True | recommended (identity) | 0.493 | 0.493 | 0.487 | 0.487 |
| FURIA vs MVK Esports | True | fitted slope (not recommended) | 0.493 | 0.493 | 0.487 | 0.488 |
| FURIA vs MVK Esports | True | fitted slope + cross (not recommended) | 0.493 | 0.493 | 0.487 | 0.488 |
| Cloud9 vs Karmine Corp | True | uncalibrated | 0.457 | 0.457 | 0.419 | 0.419 |
| Cloud9 vs Karmine Corp | True | recommended (identity) | 0.457 | 0.457 | 0.419 | 0.419 |
| Cloud9 vs Karmine Corp | True | fitted slope (not recommended) | 0.457 | 0.460 | 0.419 | 0.425 |
| Cloud9 vs Karmine Corp | True | fitted slope + cross (not recommended) | 0.457 | 0.460 | 0.419 | 0.426 |

Bookmaker-implied Bo5 (from the brief): FURIA ~0.75, Karmine Corp ~0.64 (C9 vs KC: KC Bo5 = 1 - C9 Bo5).
