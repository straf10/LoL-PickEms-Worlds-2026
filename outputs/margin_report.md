# Margin signal (gold diff at 15:00) for the team ratings: report

Code: `model/margin.py` (imports `BTModel`, `Params`, `team_regions`, `series_prob` from `model/ratings.py`
and `evaluate`, `bt_predict`, `EVENTS` from `model/backtest.py`; neither was modified).
Data: `data/pickems.duckdb` opened read-only. Gold column: `games.blue_golddiff15` (blue minus red, sign checked against outcomes).

## Question

Does adding the 15-minute gold difference to the Bradley-Terry team model improve out-of-sample
prediction of international games?

## Setup

- **Baseline:** `model.backtest.bt_predict` (current BT, default `Params`). ALL: log-loss 0.6125, Brier 0.2129, accuracy 0.6473, 862 rated games, 37 skipped.
- **Same games:** every comparison is an inner join of baseline and variant predictions on `(event, game_id)`, dropping games either model cannot rate. The skip sets are identical, so all 862 games are compared in every row.
- **Splits (to avoid tuning on the test set):**
  - Tuning (5 events, 2022-2024): Worlds 2022, MSI 2023, Worlds 2023, MSI 2024, Worlds 2024. 463 games.
  - Held-out (7 events, 2025-26): First Stand 2025, MSI 2025, EWC 2025, Worlds 2025, First Stand 2026, MSI 2026, EWC 2026. 399 games.
- **Selection rule:** lowest log-loss on the tuning events, per family, with zero gold weight excluded (zero gold weight is the baseline). The held-out result is reported for every candidate, not only the selected one.
- **Leakage:** training only uses `date_utc < event start`. The gold value of an event's own games is never used to predict that event.

## Variants

**A. Joint (`fit_joint`).** Same structure as `BTModel` (side, region, team, recency weights, L2 shrinkage). The objective adds `alpha/2 * sum w (g/scale - (strength_diff + side_gd))^2` over games with gold. The win probability is the logistic part only.

**B. Blend (`fit_gold_ridge`).** Fit `BTModel` unchanged. Separately fit a weighted ridge of `g/scale` on the same region + team design (own intercept, region penalty 1.0, team penalty `lam_gd`). Predict with `z = z_bt + gamma * z_gold`.

Deviation from the brief, found during tuning: with beta free, the joint model compresses the strengths. Team sd fell from 1.18 to 0.45 (alpha 0.25) and beta grew to about 1.6-8 across the checked dates. The gold term is indifferent to rescaling the strengths when beta is free, so the L2 penalty shrinks them and beta absorbs the change. This behaves like stronger shrinkage, which is already known to be worse. The final joint variant therefore fixes beta = 1, and the gold scale (`scale`, gold units per logit of strength) becomes the tuned quantity. Free-beta rows are kept in the grid for the record. `scale = 2500-3000` was the brief's starting point; the tuned optimum is lower (1500), with `scale` as the parameter.

## Grid (d log-loss vs baseline on the same games; negative = variant better)

| Variant | Tuning d_LL | Held-out d_LL (SE) | P(held-out better), bootstrap | ALL d_LL |
|---|---:|---:|---:|---:|
| joint alpha=0 (= BT, check) | 0.0000 | 0.0000 | - | 0.0000 |
| joint alpha=0.1, scale=1500 | -0.0049 | -0.0001 (0.0025) | 0.52 | -0.0027 |
| **joint alpha=0.25, scale=1500** (tune-best) | **-0.0057** | +0.0011 (0.0043) | 0.39 | -0.0025 |
| joint alpha=0.5, scale=1500 | -0.0042 | +0.0029 (0.0058) | 0.30 | -0.0009 |
| joint alpha=1.0, scale=1500 | -0.0008 | +0.0049 (0.0072) | 0.25 | +0.0018 |
| joint alpha=0.1, scale=3000 | -0.0021 | +0.0008 (0.0036) | 0.40 | -0.0008 |
| joint alpha=0.25, scale=3000 | +0.0001 | +0.0045 (0.0061) | 0.23 | +0.0021 |
| joint alpha=1.0, scale=3000 | +0.0081 | +0.0141 (0.0099) | 0.07 | +0.0108 |
| joint alpha=0.25, scale=6000 | +0.0084 | +0.0074 (0.0072) | 0.15 | +0.0079 |
| joint alpha=1.0, scale=6000 | +0.0256 | +0.0226 (0.0117) | 0.03 | +0.0242 |
| joint alpha=0.25, free beta (record) | +0.0322 | +0.0235 (0.0124) | 0.03 | +0.0282 |
| joint alpha=1.0, free beta (record) | +0.0575 | +0.0521 (0.0171) | 0.00 | +0.0550 |
| blend gamma=0 (= BT, check) | 0.0000 | 0.0000 | - | 0.0000 |
| blend lam_gd=10, gamma=0.25 | +0.0012 | +0.0005 (0.0018) | 0.40 | +0.0009 |
| blend lam_gd=30, gamma=0.5 | +0.0048 | +0.0023 (0.0035) | 0.24 | +0.0037 |
| **blend lam_gd=100, gamma=0.25** (tune-best) | +0.0007 | +0.0010 (0.0016) | 0.27 | +0.0008 |
| blend lam_gd=100, gamma=1.0 | +0.0165 | +0.0094 (0.0066) | 0.07 | +0.0132 |
| blend lam_gd=10, gamma=2.0 | +0.0680 | +0.0312 (0.0144) | 0.01 | +0.0510 |

"P(held-out better)" is the share of 2000 game-level bootstrap resamples with a negative mean difference. It is not a multiplicity-adjusted test.

Boundary check, run after the grid (not used for selection): joint alpha=0.25 at scale 1000 gives tuning +0.0031 and held-out +0.0013 (SE 0.0040). At scale 750 it gives tuning +0.0250 and held-out +0.0051. The grid edge at 1500 is therefore the best point and still does not improve the held-out set.

## Best variant per family, on all three splits (same games)

| Variant | Split | Games | LL base | LL var | dLL (SE) | Brier base -> var | Acc base -> var |
|---|---|---:|---:|---:|---:|---:|---:|
| joint alpha=0.25, scale=1500, beta=1 | (a) tuning | 463 | 0.5991 | 0.5935 | -0.0057 (0.0046) | 0.2074 -> 0.2055 | 0.646 -> 0.665 |
| | (b) held-out 2025-26 | 399 | 0.6280 | 0.6292 | +0.0011 (0.0043) | 0.2193 -> 0.2193 | 0.649 -> 0.657 |
| | (c) all | 862 | 0.6125 | 0.6100 | -0.0025 (0.0032) | 0.2129 -> 0.2119 | 0.647 -> 0.661 |
| blend lam_gd=100, gamma=0.25 | (a) tuning | 463 | 0.5991 | 0.5998 | +0.0007 (0.0024) | 0.2074 -> 0.2077 | 0.646 -> 0.644 |
| | (b) held-out 2025-26 | 399 | 0.6280 | 0.6290 | +0.0010 (0.0016) | 0.2193 -> 0.2196 | 0.649 -> 0.654 |
| | (c) all | 862 | 0.6125 | 0.6133 | +0.0008 (0.0015) | 0.2129 -> 0.2132 | 0.647 -> 0.649 |

Blend's tuning-best is not better than the baseline even on the tuning events; it is only the least-bad option.

Per event, joint alpha=0.25, scale=1500 (d log-loss): Worlds 2022 -0.020, MSI 2023 +0.012, Worlds 2023 +0.001, MSI 2024 -0.011, Worlds 2024 -0.005 | First Stand 2025 -0.017, MSI 2025 -0.003, EWC 2025 +0.003, Worlds 2025 +0.016, First Stand 2026 -0.015, MSI 2026 -0.004, EWC 2026 +0.017. The gains are not consistent across events and the held-out sign is mixed.

## Gold signal by year (international games; for the Fearless note)

| Year | Fearless | Games | corr(gold15, win) | Win prob slope per 1k gold |
|---|---|---:|---:|---:|
| 2022 | no | 207 | 0.62 | 0.087 |
| 2023 | no | 189 | 0.52 | 0.094 |
| 2024 | no | 125 | 0.58 | 0.116 |
| 2025 | yes | 232 | 0.46 | 0.124 |
| 2026 | yes | 167 | 0.49 | 0.091 |

Gold's correlation with winning drops from about 0.57 (2022-24) to about 0.47 (2025-26). That matches the expectation that it matters less under Fearless, but the drop is modest and does not explain the failure to improve.

## Play-In probabilities (fitted as of 2026-10-15, all games before that date)

| Matchup | Variant | P(game) | P(Bo5) |
|---|---|---:|---:|
| FURIA vs MVK | baseline BT (current) | 0.493 | 0.487 |
| FURIA vs MVK | joint alpha=0.25, scale=1500 | 0.488 | 0.478 |
| FURIA vs MVK | blend lam_gd=100, gamma=0.25 | 0.489 | 0.479 |
| Cloud9 vs Karmine Corp | baseline BT (current) | 0.457 | 0.419 |
| Cloud9 vs Karmine Corp | joint alpha=0.25, scale=1500 | 0.486 | 0.475 |
| Cloud9 vs Karmine Corp | blend lam_gd=100, gamma=0.25 | 0.458 | 0.422 |

Team ids: FURIA `oe:team:87e3e1e75839f75a10bbc66e894d806`, MVK Esports `oe:team:bc3824b0bbb8139d16109178faa4822`, Cloud9 `oe:team:fc8e90107dabb9a35c490b0d86adea0`, Karmine Corp `oe:team:f3aa9bbd924ce3af42ac53f8326bc7c` (the academy teams Karmine Corp Blue and MVK Esports Academy are excluded).

Sanity check against bookmakers (roadmap guideline 8): FURIA model Bo5 0.49 vs market about 0.75 is a gap of about 26 points, which needs an explanation. The gap is in the region and team priors, not the gold signal. MVK has zero international games in the 730-day window, so its rating is the LCP region effect (-0.57) plus 0. FURIA has 22 international games and rates +0.13 on top of the CBLOL region effect (-0.74). The region gap between CBLOL and LCP is small, so the model sees the two teams as close. This is the roadmap T2.2 question about LCP and Vietnamese teams, and a gold signal does not address it. Cloud9 vs KC: model Bo5 for KC is 0.58 vs market about 0.64, within the 15-point rule.

## Verdict

**Do not adopt.** No variant beats the baseline on the held-out 2025-26 events. The best joint variant improves the tuning events by 0.006 log-loss, but this does not hold out-of-sample (+0.001, SE 0.004). The blend does not improve on either split. Gold is correlated with winning (about 0.5-0.6), but the likely reason it adds nothing is that the same games' win/loss results already carry most of that information (not separately tested). At the Play-In, the joint variant moves Cloud9 vs KC from 0.457 to 0.486 per game, which is unsupported by the held-out evidence. Keep the current BT model for the picks.

Caveats: 5 tuning events (about 460 games), so the tuning signal is noisy. Only the gold scale and alpha were searched, with the BT base parameters held at their defaults. The fixed-beta choice was made after seeing the free-beta result (documented above).
