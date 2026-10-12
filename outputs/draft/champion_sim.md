# Crystal Ball: champion-draft simulation (Worlds 2026)

Main run: 5000 sims, K = 15, meta shift = on, window G = 522 games, bans per game = 10.00, universe = 156 champions. Code: `crystal/draft.py`.

## (a) Top 15 by EV (no-split ranking, 50/20/10 points)

Rank = 1 + number of eligible champions strictly better (ties are not split: every tied entry gets the place's points). EV = 50 p1 + 20 p2 + 10 p3. Q2 and Q3 are restricted to champions with >= 5 picks. Presence = share of games picked or banned. WR and deaths are means over sims in which the champion has >= 5 picks. Sum of P(rank 1) per question (>= 1 because of ties): Q1 1.0444, Q2 1.2116, Q3 1.0.

### Q1 highest presence

| champion | p1 | p2 | p3 | EV | mean_presence | mean_picks | p_ge5_picks | mean_wr_given_ge5 | mean_deaths_given_ge5 | base_pick_pct | base_ban_pct |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Cassiopeia | 0.373 | 0.272 | 0.161 | 25.700 | 0.789 | 9.740 | 0.828 | 0.513 | 2.519 | 7.170 | 82.700 |
| Nocturne | 0.343 | 0.263 | 0.176 | 24.170 | 0.780 | 8.915 | 0.807 | 0.504 | 2.873 | 14.240 | 60.900 |
| Vi | 0.158 | 0.184 | 0.198 | 13.550 | 0.702 | 14.392 | 0.945 | 0.512 | 3.469 | 17.690 | 52.870 |
| Jarvan IV | 0.034 | 0.050 | 0.074 | 3.440 | 0.563 | 21.581 | 0.994 | 0.506 | 3.226 | 23.040 | 30.310 |
| Lucian | 0.024 | 0.032 | 0.054 | 2.390 | 0.531 | 21.572 | 0.993 | 0.495 | 2.656 | 21.510 | 29.540 |
| Olaf | 0.021 | 0.031 | 0.046 | 2.120 | 0.499 | 17.840 | 0.987 | 0.508 | 3.596 | 19.020 | 35.470 |
| Orianna | 0.015 | 0.032 | 0.055 | 1.940 | 0.525 | 22.176 | 0.998 | 0.501 | 2.412 | 23.040 | 35.090 |
| Akali | 0.012 | 0.021 | 0.035 | 1.360 | 0.442 | 10.015 | 0.913 | 0.496 | 2.664 | 11.950 | 36.420 |
| Syndra | 0.010 | 0.022 | 0.036 | 1.290 | 0.496 | 22.997 | 0.999 | 0.490 | 2.468 | 20.360 | 22.080 |
| Nautilus | 0.010 | 0.023 | 0.027 | 1.230 | 0.440 | 16.093 | 0.985 | 0.473 | 3.470 | 14.630 | 27.820 |
| Lee Sin | 0.007 | 0.021 | 0.034 | 1.130 | 0.472 | 20.122 | 0.997 | 0.512 | 3.138 | 19.410 | 24.190 |
| Ezreal | 0.005 | 0.008 | 0.017 | 0.580 | 0.430 | 20.985 | 0.999 | 0.491 | 2.306 | 25.530 | 24.950 |
| Caitlyn | 0.004 | 0.010 | 0.012 | 0.500 | 0.391 | 16.420 | 0.991 | 0.508 | 2.709 | 16.920 | 16.730 |
| Qiyana | 0.002 | 0.007 | 0.009 | 0.350 | 0.341 | 13.635 | 0.981 | 0.491 | 3.178 | 10.420 | 9.080 |
| Locke | 0.003 | 0.005 | 0.009 | 0.330 | 0.338 | 10.727 | 0.942 | 0.496 | 2.681 | 10.040 | 23.610 |

### Q2 highest win rate (min 5 picks)

| champion | p1 | p2 | p3 | EV | mean_presence | mean_picks | p_ge5_picks | mean_wr_given_ge5 | mean_deaths_given_ge5 | base_pick_pct | base_ban_pct |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Anivia | 0.039 | 0.029 | 0.021 | 2.720 | 0.130 | 6.887 | 0.776 | 0.536 | 2.641 | 7.930 | 7.740 |
| Annie | 0.035 | 0.025 | 0.018 | 2.420 | 0.124 | 6.796 | 0.764 | 0.520 | 3.004 | 9.270 | 8.700 |
| Cho'Gath | 0.030 | 0.021 | 0.018 | 2.120 | 0.101 | 7.495 | 0.824 | 0.508 | 3.327 | 6.600 | 2.010 |
| Aurora | 0.029 | 0.023 | 0.019 | 2.090 | 0.085 | 7.131 | 0.793 | 0.510 | 2.739 | 6.410 | 1.630 |
| Taliyah | 0.027 | 0.024 | 0.018 | 2.030 | 0.114 | 7.396 | 0.817 | 0.507 | 2.533 | 7.170 | 3.920 |
| Sylas | 0.028 | 0.021 | 0.018 | 1.980 | 0.140 | 7.672 | 0.849 | 0.503 | 2.840 | 6.600 | 7.930 |
| Twisted Fate | 0.024 | 0.022 | 0.020 | 1.840 | 0.092 | 4.957 | 0.536 | 0.520 | 2.780 | 7.360 | 8.130 |
| Corki | 0.025 | 0.021 | 0.014 | 1.820 | 0.080 | 5.965 | 0.668 | 0.495 | 2.487 | 7.930 | 3.540 |
| Xayah | 0.021 | 0.021 | 0.020 | 1.690 | 0.154 | 9.746 | 0.922 | 0.507 | 2.221 | 10.040 | 4.680 |
| Shen | 0.022 | 0.020 | 0.016 | 1.640 | 0.074 | 5.430 | 0.592 | 0.503 | 3.019 | 8.510 | 8.130 |
| Sivir | 0.021 | 0.020 | 0.017 | 1.620 | 0.119 | 8.357 | 0.857 | 0.493 | 2.550 | 9.270 | 3.920 |
| Skarner | 0.020 | 0.021 | 0.017 | 1.610 | 0.200 | 11.209 | 0.959 | 0.514 | 2.943 | 11.380 | 8.700 |
| Varus | 0.021 | 0.017 | 0.017 | 1.580 | 0.150 | 10.205 | 0.935 | 0.512 | 2.891 | 11.950 | 7.360 |
| Jax | 0.020 | 0.018 | 0.016 | 1.550 | 0.110 | 6.105 | 0.690 | 0.491 | 3.464 | 6.210 | 7.170 |
| Sion | 0.019 | 0.021 | 0.014 | 1.500 | 0.084 | 7.336 | 0.592 | 0.537 | 2.690 | 3.150 | 0.860 |

### Q3 highest deaths per game (min 5 picks)

| champion | p1 | p2 | p3 | EV | mean_presence | mean_picks | p_ge5_picks | mean_wr_given_ge5 | mean_deaths_given_ge5 | base_pick_pct | base_ban_pct |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Rell | 0.146 | 0.070 | 0.052 | 9.210 | 0.087 | 7.436 | 0.795 | 0.477 | 3.786 | 8.700 | 0.860 |
| Olaf | 0.056 | 0.060 | 0.060 | 4.610 | 0.499 | 17.840 | 0.987 | 0.508 | 3.596 | 19.020 | 35.470 |
| Camille | 0.058 | 0.057 | 0.050 | 4.560 | 0.193 | 11.970 | 0.971 | 0.495 | 3.459 | 13.670 | 14.630 |
| Jax | 0.063 | 0.040 | 0.041 | 4.340 | 0.110 | 6.105 | 0.690 | 0.491 | 3.464 | 6.210 | 7.170 |
| Nautilus | 0.044 | 0.052 | 0.048 | 3.730 | 0.440 | 16.093 | 0.985 | 0.473 | 3.470 | 14.630 | 27.820 |
| Vi | 0.043 | 0.044 | 0.044 | 3.450 | 0.702 | 14.392 | 0.945 | 0.512 | 3.469 | 17.690 | 52.870 |
| Cho'Gath | 0.042 | 0.042 | 0.034 | 3.290 | 0.101 | 7.495 | 0.824 | 0.508 | 3.327 | 6.600 | 2.010 |
| Renekton | 0.033 | 0.034 | 0.036 | 2.670 | 0.171 | 9.704 | 0.924 | 0.486 | 3.256 | 9.270 | 8.320 |
| Alistar | 0.025 | 0.025 | 0.031 | 2.080 | 0.156 | 11.595 | 0.962 | 0.487 | 3.199 | 12.720 | 5.070 |
| Jayce | 0.020 | 0.030 | 0.033 | 1.940 | 0.351 | 16.624 | 0.995 | 0.509 | 3.318 | 19.220 | 20.940 |
| Bard | 0.020 | 0.025 | 0.027 | 1.760 | 0.334 | 16.577 | 0.994 | 0.517 | 3.263 | 18.070 | 17.300 |
| Pantheon | 0.019 | 0.024 | 0.026 | 1.680 | 0.298 | 14.355 | 0.985 | 0.498 | 3.225 | 19.220 | 19.980 |
| Annie | 0.021 | 0.023 | 0.019 | 1.680 | 0.124 | 6.796 | 0.764 | 0.520 | 3.004 | 9.270 | 8.700 |
| Xin Zhao | 0.017 | 0.024 | 0.026 | 1.570 | 0.257 | 15.816 | 0.992 | 0.512 | 3.264 | 12.720 | 9.080 |
| Neeko | 0.021 | 0.015 | 0.018 | 1.550 | 0.083 | 4.599 | 0.468 | 0.497 | 3.092 | 5.260 | 2.960 |

## (b) Q10 unique champions picked

Mean 110.5, median 110, 10-90% range 105 to 116 (min 96, max 125, 5000 sims).

Acceptance check, Q10 median in [95, 120]: **PASS** (median 110). Historical Worlds reference: 95 unique champions in 84 games (2025) and 95 in 106 games (2024).

## (c) Calibration

IPS on the first 500 sims, up to 20 iterations, toward: marginal means pibar, bebar + common logit shift (sums to 10). Iterations used: 6. Converged to < 1.5 pp: True.

Common logit shift (bisection so targets sum to 10 per game): pick +0.019919, ban -0.004700. Marginal sums before the shift: pick 9.8302, ban 10.0343. Targets after the shift: 10.0000 and 10.0000.

- Max pick error (champions with pick rate > 3%): **1.139 pp**
- Max ban error (champions with ban rate > 3%): **1.44 pp**

Iteration history (max error, pp): 0: 8.35/63.74, 1: 6.86/13.34, 2: 3.93/7.10, 3: 2.62/4.32, 4: 1.92/2.70, 5: 1.42/1.95, 6: 1.14/1.44

## (d) Meta-shift parameters

Source: outputs/meta/meta_shift_fit.json.

```json
{
 "pick": {
  "a": -0.0237,
  "b": 1.0337,
  "c": 0.6848,
  "sd_by_bin": {
   "lt5": 0.9377,
   "5to20": 0.3302,
   "gt20": 0.1492
  }
 },
 "ban": {
  "a": 0.1445,
  "b": 1.1905,
  "c": 0.6813,
  "sd_by_bin": {
   "lt5": 1.1986,
   "5to20": 0.8065,
   "gt20": 0.8011
  }
 },
 "rho_pick_ban": 0.3846
}
```

Model: eta = logit pi'_0 = a + b*x1 + c*(x2 - x1), with x1 = logit(pi) (meta window) and x2 = logit of the late-window pick rate. Ban: eta_b = a + b*y1 + c*(y2 - y1) with y1, y2 the analogous ban logits. Per-champion sd = sd_by_bin of the window rate (pick: pi, ban: beta). Marginal means pibar = E_z[sigmoid(eta + sd*z)] by 20-node Gauss-Hermite; the calibration targets are sigmoid(logit(pibar) + d) with a common d chosen so the targets sum to 10. Per tournament, the draft log-weight shift is (eta + u) - logit(pibar), with u = sd*z1 for picks and sd_b*(rho*z1 + sqrt(1-rho^2)*z2) for bans. The common d cancels in this shift. Late window: 2026-09-23 to 2026-10-14 (is_international = false, all leagues), G_late = 586 games.

Late-window champions outside the 2026 top-league universe (cannot be drawn, ignored): Karthus, Katarina, Nunu & Willump, Rengar, Twitch, Zilean.

## (e) Sensitivity (1,000 sims each; top 5 per question by EV)

| config | Q1 | Q2 | Q3 |
|---|---|---|---|
| K=5, shift | Cassiopeia 26.75, Nocturne 23.69, Vi 13.78, Jarvan IV 3.03, Orianna 2.47 | Anivia 2.73, Taliyah 2.56, Annie 2.45, Aurora 2.42, Cho'Gath 1.96 | Rell 9.31, Olaf 4.42, Camille 4.22, Jax 3.96, Nautilus 3.86 |
| K=15, shift | Cassiopeia 26.93, Nocturne 23.56, Vi 13.84, Jarvan IV 3.13, Lucian 2.36 | Anivia 2.85, Annie 2.43, Aurora 2.23, Taliyah 2.11, Yorick 1.96 | Rell 9.73, Olaf 4.40, Camille 4.25, Jax 4.01, Nautilus 3.68 |
| K=30, shift | Cassiopeia 26.86, Nocturne 23.63, Vi 13.79, Jarvan IV 2.96, Orianna 2.54 | Anivia 2.96, Annie 2.57, Aurora 2.36, Taliyah 2.13, Corki 2.04 | Rell 9.81, Olaf 4.38, Jax 4.17, Camille 3.83, Vi 3.78 |
| no-shift | Cassiopeia 49.61, Nocturne 17.75, Vi 12.51, Orianna 0.63, Olaf 0.20 | Yorick 3.03, Anivia 2.95, Azir 2.78, Taliyah 2.53, Cho'Gath 2.52 | Rell 10.90, Jax 5.59, Olaf 5.29, Nautilus 4.43, Cho'Gath 4.06 |

## (f) Baseline sanity check (no shift)

| rank | sim champion | window champion |
|---|---|---|
| 1 | Cassiopeia (88.1) | Cassiopeia (89.8) |
| 2 | Nocturne (73.6) | Nocturne (75.1) |
| 3 | Vi (69.3) | Vi (70.5) |
| 4 | Orianna (57.5) | Orianna (58.0) |
| 5 | Olaf (54.0) | Olaf (54.4) |
| 6 | Jarvan IV (52.3) | Jarvan IV (53.3) |
| 7 | Lucian (50.5) | Lucian (51.0) |
| 8 | Ezreal (50.1) | Ezreal (50.4) |
| 9 | Akali (48.0) | Akali (48.3) |
| 10 | Lee Sin (42.4) | Lee Sin (43.5) |

Top-10 overlap: 10/10. Presence in % of games.

Mean absolute gap for champions with window presence > 5%: 0.3 pp.

## (h) Effect of the meta shift (diagnostic, 1,000 sims)

| champion | window % | no-shift % | shift % |
|---|---|---|---|
| Cassiopeia | 89.8 | 88.1 | 79.3 |
| Nocturne | 75.1 | 73.6 | 77.6 |
| Vi | 70.5 | 69.3 | 70.6 |
| Orianna | 58.0 | 57.5 | 52.8 |
| Olaf | 54.4 | 54.0 | 50.4 |
| Jarvan IV | 53.3 | 52.3 | 55.9 |
| Lucian | 51.0 | 50.5 | 53.3 |
| Ezreal | 50.4 | 50.1 | 43.4 |
| Akali | 48.3 | 48.0 | 43.7 |
| Lee Sin | 43.5 | 42.4 | 46.7 |

Champions with window presence < 1% (57 of 156): mean presence 0.43% with no shift, 0.76% with the shift.

Q10 mean: 107.6 with no shift, 110.4 with the shift. Independent per-game inclusion at the window pick rates gives about 107 for 103 games (sum over champions of 1 - (1 - pi_c)^103), so the no-shift run matches that.

The z = 0 shifted rates are in section (i).

## (i) Deterministic shift (z = 0) and marginal means: what the late-window read changes

### Top 20 by pi' (z = 0)

| champion | pi % | late pick % | pi' (z=0) % | pi-bar (calib) % | beta % | late ban % | beta' (z=0) % | beta-bar (calib) % |
|---|---|---|---|---|---|---|---|---|
| Rumble | 25.14 | 27.85 | 25.81 | 26.29 | 14.82 | 16.44 | 13.54 | 16.05 |
| Ryze | 26.67 | 25.81 | 24.98 | 25.46 | 13.29 | 16.61 | 12.90 | 15.36 |
| Lulu | 19.22 | 27.85 | 23.57 | 24.44 | 12.72 | 18.99 | 13.89 | 16.41 |
| Yunara | 19.02 | 27.00 | 22.97 | 23.83 | 4.30 | 5.54 | 3.33 | 5.79 |
| K'Sante | 21.51 | 24.96 | 22.63 | 23.09 | 11.95 | 13.03 | 10.29 | 12.53 |
| Syndra | 20.36 | 25.13 | 22.32 | 22.77 | 22.08 | 29.05 | 24.86 | 27.29 |
| Lucian | 21.51 | 23.42 | 21.64 | 22.09 | 29.54 | 31.09 | 30.15 | 32.22 |
| Jarvan IV | 23.04 | 22.23 | 21.38 | 21.83 | 30.31 | 34.67 | 32.93 | 34.76 |
| Orianna | 23.04 | 22.06 | 21.27 | 21.71 | 35.09 | 25.64 | 29.02 | 31.18 |
| Milio | 20.17 | 23.42 | 21.17 | 21.61 | 0.86 | 2.98 | 0.95 | 1.83 |
| Ezreal | 25.53 | 19.17 | 20.05 | 20.48 | 24.95 | 19.68 | 20.19 | 22.78 |
| Lee Sin | 19.41 | 21.21 | 19.48 | 20.31 | 24.19 | 28.02 | 25.35 | 27.75 |
| Ambessa | 18.83 | 19.51 | 18.18 | 18.99 | 6.21 | 7.92 | 5.17 | 6.64 |
| Seraphine | 22.08 | 17.63 | 17.96 | 18.36 | 11.76 | 19.17 | 13.44 | 15.94 |
| Olaf | 19.02 | 18.14 | 17.35 | 18.15 | 35.47 | 26.32 | 29.70 | 31.81 |
| Wukong | 13.48 | 20.02 | 16.51 | 17.28 | 10.23 | 14.40 | 10.19 | 12.43 |
| Jhin | 21.70 | 15.59 | 16.41 | 16.79 | 4.11 | 9.45 | 4.75 | 7.89 |
| Viktor | 16.35 | 17.12 | 15.80 | 16.56 | 10.04 | 11.50 | 8.61 | 10.65 |
| Bard | 18.07 | 16.10 | 15.69 | 16.45 | 17.30 | 15.93 | 14.36 | 16.91 |
| Karma | 21.89 | 14.40 | 15.60 | 15.97 | 10.23 | 18.48 | 12.21 | 14.63 |

### Top 20 by beta' (z = 0)

| champion | pi % | late pick % | pi' (z=0) % | pi-bar (calib) % | beta % | late ban % | beta' (z=0) % | beta-bar (calib) % |
|---|---|---|---|---|---|---|---|---|
| Nocturne | 14.24 | 8.60 | 9.38 | 9.93 | 60.90 | 70.44 | 72.35 | 69.89 |
| Cassiopeia | 7.17 | 15.25 | 10.99 | 11.61 | 82.70 | 50.34 | 72.12 | 69.68 |
| Vi | 17.69 | 15.76 | 15.34 | 16.09 | 52.87 | 52.56 | 56.78 | 55.83 |
| Jarvan IV | 23.04 | 22.23 | 21.38 | 21.83 | 30.31 | 34.67 | 32.93 | 34.76 |
| Akali | 11.95 | 9.11 | 9.15 | 9.69 | 36.42 | 28.71 | 31.89 | 33.81 |
| Lucian | 21.51 | 23.42 | 21.64 | 22.09 | 29.54 | 31.09 | 30.15 | 32.22 |
| Olaf | 19.02 | 18.14 | 17.35 | 18.15 | 35.47 | 26.32 | 29.70 | 31.81 |
| Orianna | 23.04 | 22.06 | 21.27 | 21.71 | 35.09 | 25.64 | 29.02 | 31.18 |
| Nautilus | 14.63 | 17.63 | 15.51 | 16.27 | 27.82 | 25.47 | 25.49 | 27.89 |
| Lee Sin | 19.41 | 21.21 | 19.48 | 20.31 | 24.19 | 28.02 | 25.35 | 27.75 |
| Syndra | 20.36 | 25.13 | 22.32 | 22.77 | 22.08 | 29.05 | 24.86 | 27.29 |
| Locke | 10.04 | 10.65 | 9.57 | 10.13 | 23.61 | 20.87 | 20.40 | 22.99 |
| Caitlyn | 16.92 | 16.27 | 15.44 | 16.19 | 16.73 | 26.49 | 20.29 | 22.91 |
| Ezreal | 25.53 | 19.17 | 20.05 | 20.48 | 24.95 | 19.68 | 20.19 | 22.78 |
| Qiyana | 10.42 | 15.08 | 12.37 | 13.03 | 9.08 | 33.82 | 18.45 | 21.08 |
| Poppy | 5.45 | 3.66 | 3.70 | 3.96 | 25.53 | 14.57 | 16.71 | 19.30 |
| Jayce | 19.22 | 14.91 | 15.22 | 15.96 | 20.94 | 16.44 | 16.25 | 18.82 |
| Bard | 18.07 | 16.10 | 15.69 | 16.45 | 17.30 | 15.93 | 14.36 | 16.91 |
| Lulu | 19.22 | 27.85 | 23.57 | 24.44 | 12.72 | 18.99 | 13.89 | 16.41 |
| Rumble | 25.14 | 27.85 | 25.81 | 26.29 | 14.82 | 16.44 | 13.54 | 16.05 |

Late rates are the smoothed (count + 0.5)/(G_late + 1) values used in the model, not raw counts. Champions with no late-window appearance sit at the smoothed floor, as intended.

## (j) Verification, spread and benchmark (round 4)

### Verification: forced marginal (shift term = 0), out of sample on sims 500-999

Max abs error over targets > 3%: pick 1.153 pp, ban 1.391 pp. Pass (< 1.5 pp): True.

| champion | target pick % | sim pick % | target ban % | sim ban % |
|---|---|---|---|---|
| Cassiopeia | 11.61 | 10.45 | 69.68 | 68.28 |
| Nocturne | 9.93 | 9.10 | 69.89 | 68.70 |
| Vi | 16.09 | 14.96 | 55.83 | 55.47 |
| Jarvan IV | 21.83 | 21.22 | 34.76 | 34.70 |

### Spread: across-sim sd of the simulated ban rate vs GLMM-implied sd (marginal formulation, G = 103)

Band [0.85, 1.25] (acceptance): all inside = True. Ratios range 0.95 to 1.04.

| champion | bin | sd(logit) bin | target ban-bar % | sim mean ban % | sim sd (pp) | GLMM sd (pp) | ratio | in band |
|---|---|---|---|---|---|---|---|---|
| Cassiopeia | gt20 | 0.8011 | 69.68 | 69.49 | 15.17 | 15.91 | 0.953 | yes |
| Nocturne | gt20 | 0.8011 | 69.89 | 69.34 | 15.31 | 15.85 | 0.966 | yes |
| Vi | gt20 | 0.8011 | 55.83 | 56.20 | 17.50 | 18.01 | 0.972 | yes |
| Jarvan IV | gt20 | 0.8011 | 34.76 | 35.35 | 17.51 | 16.84 | 1.040 | yes |

### Benchmark: Q1 P(lead) vs the meta-shift benchmark (no draft mechanics, G = 103)

| champion | benchmark | sim P(lead) Q1 | diff | within 0.15 |
|---|---|---|---|---|
| Nocturne | 0.310 | 0.343 | +0.033 | yes |
| Cassiopeia | 0.290 | 0.373 | +0.083 | yes |
| Vi | 0.180 | 0.158 | -0.022 | yes |
| Jarvan IV | 0.040 | 0.034 | -0.006 | yes |

Stop-rule status: none triggered.

## (k) Slope correction (round 7)

Correction: the shift is (eta + u - logit(target marginal)) / slope_c for both picks and bans, where slope_c = d logit(rate) / d log-weight measured at baseline (calibrated weights, forced marginal) with a +0.25 bump on that champion's weight, 500 sims (sims 500-999), common random numbers. Ban slopes are measured for champions with target above 10%, pick slopes for champions above 10% plus six checks. Other champions are interpolated linearly in logit(target), clamped to [1.0, max] for bans and [0.3, max] for picks. Slopes outside [0.3, 2.5] stop the run.

Measured ban slopes: 30 champions, range 1.029 to 1.944. Measured pick slopes: 43 champions, range 0.457 to 0.889. Applied ban range 1.029 to 1.944; applied pick range 0.457 to 0.889. Within stop limits: True (none).

### Ban slopes (measured)

| champion | target ban % | ban slope (measured) | ban slope (applied) |
|---|---|---|---|
| Nocturne | 69.89 | 1.852 | 1.852 |
| Cassiopeia | 69.68 | 1.944 | 1.944 |
| Vi | 55.83 | 1.668 | 1.668 |
| Jarvan IV | 34.76 | 1.362 | 1.362 |
| Akali | 33.81 | 1.273 | 1.273 |
| Lucian | 32.22 | 1.315 | 1.315 |
| Olaf | 31.81 | 1.268 | 1.268 |
| Orianna | 31.18 | 1.318 | 1.318 |
| Nautilus | 27.89 | 1.192 | 1.192 |
| Lee Sin | 27.75 | 1.222 | 1.222 |
| Syndra | 27.29 | 1.320 | 1.320 |
| Locke | 22.99 | 1.161 | 1.161 |
| Caitlyn | 22.91 | 1.191 | 1.191 |
| Ezreal | 22.78 | 1.183 | 1.183 |
| Qiyana | 21.08 | 1.118 | 1.118 |
| Poppy | 19.30 | 1.086 | 1.086 |
| Jayce | 18.82 | 1.119 | 1.119 |
| Bard | 16.91 | 1.138 | 1.138 |
| Lulu | 16.41 | 1.142 | 1.142 |
| Rumble | 16.05 | 1.173 | 1.173 |
| Seraphine | 15.94 | 1.133 | 1.133 |
| Pantheon | 15.77 | 1.095 | 1.095 |
| Ryze | 15.36 | 1.133 | 1.133 |
| Karma | 14.63 | 1.099 | 1.099 |
| Kalista | 13.92 | 1.095 | 1.095 |
| Naafiri | 12.95 | 1.103 | 1.103 |
| K'Sante | 12.53 | 1.078 | 1.078 |
| Wukong | 12.43 | 1.122 | 1.122 |
| Viktor | 10.65 | 1.071 | 1.071 |
| Xin Zhao | 10.45 | 1.029 | 1.029 |

### Pick slopes (measured)

| champion | target pick % | pick slope (measured) | pick slope (applied) |
|---|---|---|---|
| Rumble | 26.29 | 0.486 | 0.486 |
| Ryze | 25.46 | 0.457 | 0.457 |
| Lulu | 24.44 | 0.552 | 0.552 |
| Yunara | 23.83 | 0.567 | 0.567 |
| K'Sante | 23.09 | 0.521 | 0.521 |
| Syndra | 22.77 | 0.497 | 0.497 |
| Lucian | 22.09 | 0.477 | 0.477 |
| Jarvan IV | 21.83 | 0.494 | 0.494 |
| Orianna | 21.71 | 0.492 | 0.492 |
| Milio | 21.61 | 0.576 | 0.576 |
| Ezreal | 20.48 | 0.548 | 0.548 |
| Lee Sin | 20.31 | 0.548 | 0.548 |
| Ambessa | 18.99 | 0.592 | 0.592 |
| Seraphine | 18.36 | 0.641 | 0.641 |
| Olaf | 18.15 | 0.604 | 0.604 |
| Wukong | 17.28 | 0.624 | 0.624 |
| Jhin | 16.79 | 0.598 | 0.598 |
| Viktor | 16.56 | 0.641 | 0.641 |
| Bard | 16.45 | 0.648 | 0.648 |
| Nautilus | 16.27 | 0.630 | 0.630 |
| Caitlyn | 16.19 | 0.646 | 0.646 |
| Vi | 16.09 | 0.465 | 0.465 |
| Karma | 15.97 | 0.694 | 0.694 |
| Jayce | 15.96 | 0.685 | 0.685 |
| Ashe | 14.90 | 0.732 | 0.732 |
| Xin Zhao | 14.79 | 0.637 | 0.637 |
| Naafiri | 14.26 | 0.738 | 0.738 |
| Renata Glasc | 14.08 | 0.711 | 0.711 |
| Gnar | 14.08 | 0.696 | 0.696 |
| Pantheon | 13.96 | 0.721 | 0.721 |
| Kalista | 13.35 | 0.668 | 0.668 |
| Qiyana | 13.03 | 0.662 | 0.662 |
| Ahri | 12.88 | 0.750 | 0.750 |
| Rakan | 12.18 | 0.761 | 0.761 |
| Cassiopeia | 11.61 | 0.510 | 0.510 |
| Galio | 11.59 | 0.779 | 0.779 |
| Camille | 11.29 | 0.742 | 0.742 |
| Alistar | 11.12 | 0.763 | 0.763 |
| Skarner | 10.35 | 0.732 | 0.732 |
| Locke | 10.13 | 0.749 | 0.749 |
| Rell | 7.06 | 0.860 | 0.860 |
| Anivia | 6.36 | 0.872 | 0.872 |
| Leona | 4.85 | 0.889 | 0.889 |

### Spread before and after (sim sd / GLMM sd)

| champion | GLMM sd (pp) | ratio before (round 4) | ratio after (round 7) | in [0.85, 1.25] |
|---|---|---|---|---|
| Cassiopeia | 15.91 | 1.499 | 0.953 | yes |
| Nocturne | 15.85 | 1.456 | 0.966 | yes |
| Vi | 18.01 | 1.387 | 0.972 | yes |
| Jarvan IV | 16.84 | 1.316 | 1.040 | yes |

### Mean ban rate vs target, before and after

| champion | target ban-bar % | mean before % | mean after % | after minus target (pp) | within 1.5 pp |
|---|---|---|---|---|---|
| Cassiopeia | 69.68 | 67.84 | 69.49 | -0.18 | yes |
| Nocturne | 69.89 | 68.02 | 69.34 | -0.55 | yes |
| Vi | 55.83 | 55.67 | 56.20 | +0.37 | yes |
| Jarvan IV | 34.76 | 35.88 | 35.35 | +0.58 | yes |

### Mean pick rate vs target (report only; not an acceptance check)

| champion | target_pick_pct | sim_mean_pick_pct | diff_pp |
|---|---|---|---|
| Cassiopeia | 11.610 | 9.450 | -2.160 |
| Nocturne | 9.930 | 8.640 | -1.290 |
| Vi | 16.090 | 13.960 | -2.130 |
| Jarvan IV | 21.830 | 20.920 | -0.900 |

Acceptance (round 7): spread ratio in [0.85, 1.25] for the 4 champions: True; mean ban rate within 1.5 pp of the target for the 4: True; Q1 P(rank 1) within 0.15 of the benchmark (Nocturne, Cassiopeia, Vi): True; constraints pass (outputs/draft/tmp_check.py on the round-7 code: 0 duplicate picks, 0 role violations, 0 ban/pick overlaps, 0 fearless violations, 10 picks, 10 bans and 5 wins per game); Sum P(rank 1) >= 1: True.

## (g) Runtime

Main run: 320.48 s total (calibration 27.72 s, simulation 292.24 s). Sensitivity runs are 1,000 sims each; their timings are in their own tmp_run pickles.

## Notes and deviations from the spec

- Bans per game: 9.998 in the window, rounded to 10. Window target sums (count + 0.5)/(G + 1): picks 10.13, bans 10.1281. Calibrated target sums (marginal means + common shift): picks 10.0, bans 10.0.
- Shift bins for the ban logit use each champion's ban rate beta_c (the spec does not say which rate).
- Role share smoothing: s = (n_cr + 0.1) / (n_c + 0.5). Champions with no window player rows get uniform shares.
- Death pool: a starter's 2026 top-league games with the same result (all champions). If that pool is empty, use the starter role's pool across all starters with that result.
- Death factor n_c = champion's picks in the window; ratio_c = champion's window mean deaths / mean deaths of its most common window role. Champions with no window player rows get factor 1.
- mean_wr_given_ge5 and mean_deaths_given_ge5 average the per-sim rate over sims where the champion has >= 5 picks.
- The calibration error is in-sample (the same 500 sims used for IPS, with the random shift off). Calibration targets are the marginal means with one common logit shift per type so each sums to 10 per game.
- Presence uses picks + bans per sim; a champion cannot be both banned and picked in the same game.
- Shift: the refit contract (a, b, c, sd_by_bin, rho_pick_ban from meta_shift_fit.json). c is required; a missing key raises. The earlier logit-centre diagnostic is removed because it does not apply to this model.
