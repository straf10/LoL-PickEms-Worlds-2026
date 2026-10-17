# Crystal Ball: champion-draft simulation (Worlds 2026)

Main run: 5000 sims, K = 15, meta shift = on, window G = 529 games, bans per game = 10.00, universe = 156 champions. Code: `crystal/draft.py`.

## (a) Top 15 by EV (no-split ranking, 50/20/10 points)

Rank = 1 + number of eligible champions strictly better (ties are not split: every tied entry gets the place's points). EV = 50 p1 + 20 p2 + 10 p3. Q2 and Q3 are restricted to champions with >= 5 picks. Presence = share of games picked or banned. WR and deaths are means over sims in which the champion has >= 5 picks. Sum of P(rank 1) per question (>= 1 because of ties): Q1 1.0474, Q2 1.2272, Q3 1.0.

### Q1 highest presence

| champion | p1 | p2 | p3 | EV | mean_presence | mean_picks | p_ge5_picks | mean_wr_given_ge5 | mean_deaths_given_ge5 | base_pick_pct | base_ban_pct |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Cassiopeia | 0.397 | 0.277 | 0.155 | 26.920 | 0.800 | 9.449 | 0.811 | 0.512 | 2.516 | 7.080 | 82.920 |
| Nocturne | 0.342 | 0.268 | 0.181 | 24.280 | 0.785 | 8.809 | 0.799 | 0.506 | 2.865 | 14.060 | 61.420 |
| Vi | 0.150 | 0.181 | 0.198 | 13.080 | 0.701 | 14.692 | 0.949 | 0.511 | 3.525 | 17.830 | 52.360 |
| Jarvan IV | 0.030 | 0.049 | 0.077 | 3.240 | 0.563 | 21.669 | 0.995 | 0.507 | 3.209 | 22.920 | 30.660 |
| Lucian | 0.023 | 0.030 | 0.052 | 2.290 | 0.530 | 21.817 | 0.994 | 0.493 | 2.654 | 21.600 | 29.340 |
| Olaf | 0.024 | 0.029 | 0.050 | 2.260 | 0.509 | 17.693 | 0.986 | 0.506 | 3.604 | 18.960 | 35.750 |
| Orianna | 0.014 | 0.030 | 0.054 | 1.820 | 0.524 | 22.235 | 0.998 | 0.501 | 2.467 | 23.110 | 35.000 |
| Syndra | 0.009 | 0.024 | 0.038 | 1.330 | 0.499 | 22.794 | 0.999 | 0.491 | 2.457 | 20.280 | 22.550 |
| Akali | 0.011 | 0.018 | 0.035 | 1.240 | 0.441 | 10.508 | 0.926 | 0.494 | 2.612 | 12.170 | 35.940 |
| Lee Sin | 0.007 | 0.022 | 0.034 | 1.120 | 0.475 | 19.992 | 0.996 | 0.513 | 3.128 | 19.340 | 24.250 |
| Nautilus | 0.008 | 0.020 | 0.026 | 1.080 | 0.433 | 16.020 | 0.986 | 0.473 | 3.490 | 14.620 | 27.450 |
| Ezreal | 0.004 | 0.008 | 0.016 | 0.530 | 0.426 | 20.980 | 0.999 | 0.492 | 2.312 | 25.380 | 24.620 |
| Caitlyn | 0.004 | 0.008 | 0.012 | 0.500 | 0.390 | 16.619 | 0.992 | 0.509 | 2.679 | 17.080 | 16.510 |
| Qiyana | 0.003 | 0.009 | 0.012 | 0.460 | 0.350 | 13.504 | 0.981 | 0.492 | 3.169 | 10.470 | 9.720 |
| Locke | 0.002 | 0.005 | 0.009 | 0.300 | 0.337 | 10.890 | 0.945 | 0.497 | 2.672 | 10.090 | 23.300 |

### Q2 highest win rate (min 5 picks)

| champion | p1 | p2 | p3 | EV | mean_presence | mean_picks | p_ge5_picks | mean_wr_given_ge5 | mean_deaths_given_ge5 | base_pick_pct | base_ban_pct |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Anivia | 0.035 | 0.031 | 0.023 | 2.590 | 0.127 | 6.883 | 0.776 | 0.536 | 2.684 | 8.020 | 7.640 |
| Annie | 0.033 | 0.025 | 0.020 | 2.340 | 0.127 | 6.636 | 0.750 | 0.520 | 2.985 | 9.150 | 8.770 |
| Taliyah | 0.029 | 0.021 | 0.020 | 2.080 | 0.118 | 7.593 | 0.830 | 0.507 | 2.550 | 7.260 | 4.060 |
| Sylas | 0.029 | 0.019 | 0.017 | 2.030 | 0.138 | 7.476 | 0.835 | 0.504 | 2.828 | 6.510 | 7.830 |
| Aurora | 0.028 | 0.021 | 0.018 | 2.010 | 0.084 | 7.060 | 0.791 | 0.510 | 2.727 | 6.320 | 1.600 |
| Cho'Gath | 0.027 | 0.020 | 0.022 | 1.970 | 0.100 | 7.447 | 0.819 | 0.504 | 3.319 | 6.700 | 1.980 |
| Twisted Fate | 0.026 | 0.020 | 0.019 | 1.870 | 0.094 | 5.070 | 0.552 | 0.518 | 2.753 | 7.450 | 8.020 |
| Aatrox | 0.027 | 0.017 | 0.014 | 1.820 | 0.059 | 4.644 | 0.483 | 0.519 | 2.823 | 5.000 | 1.230 |
| Corki | 0.024 | 0.019 | 0.014 | 1.730 | 0.082 | 6.256 | 0.703 | 0.495 | 2.467 | 7.830 | 3.490 |
| Varus | 0.023 | 0.019 | 0.018 | 1.680 | 0.158 | 10.391 | 0.935 | 0.513 | 2.879 | 11.980 | 7.830 |
| Sivir | 0.021 | 0.022 | 0.019 | 1.670 | 0.116 | 8.005 | 0.837 | 0.494 | 2.540 | 9.150 | 3.870 |
| Xayah | 0.021 | 0.019 | 0.023 | 1.660 | 0.150 | 9.612 | 0.920 | 0.507 | 2.207 | 9.910 | 4.620 |
| Shen | 0.020 | 0.022 | 0.016 | 1.620 | 0.074 | 5.338 | 0.580 | 0.506 | 3.006 | 8.400 | 8.020 |
| Skarner | 0.020 | 0.020 | 0.019 | 1.600 | 0.200 | 10.963 | 0.954 | 0.516 | 2.931 | 11.230 | 8.580 |
| Jax | 0.021 | 0.018 | 0.017 | 1.570 | 0.112 | 6.198 | 0.700 | 0.491 | 3.461 | 6.130 | 7.260 |

### Q3 highest deaths per game (min 5 picks)

| champion | p1 | p2 | p3 | EV | mean_presence | mean_picks | p_ge5_picks | mean_wr_given_ge5 | mean_deaths_given_ge5 | base_pick_pct | base_ban_pct |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Rell | 0.142 | 0.074 | 0.051 | 9.070 | 0.087 | 7.534 | 0.804 | 0.478 | 3.782 | 8.580 | 0.850 |
| Olaf | 0.054 | 0.064 | 0.067 | 4.650 | 0.509 | 17.693 | 0.986 | 0.506 | 3.604 | 18.960 | 35.750 |
| Camille | 0.057 | 0.053 | 0.042 | 4.340 | 0.192 | 11.985 | 0.972 | 0.495 | 3.448 | 13.490 | 14.620 |
| Jax | 0.061 | 0.044 | 0.039 | 4.330 | 0.112 | 6.198 | 0.700 | 0.491 | 3.461 | 6.130 | 7.260 |
| Vi | 0.052 | 0.050 | 0.048 | 4.090 | 0.701 | 14.692 | 0.949 | 0.511 | 3.525 | 17.830 | 52.360 |
| Nautilus | 0.049 | 0.052 | 0.050 | 3.980 | 0.433 | 16.020 | 0.986 | 0.473 | 3.490 | 14.620 | 27.450 |
| Cho'Gath | 0.043 | 0.038 | 0.035 | 3.280 | 0.100 | 7.447 | 0.819 | 0.504 | 3.319 | 6.700 | 1.980 |
| Renekton | 0.037 | 0.039 | 0.033 | 2.970 | 0.169 | 9.827 | 0.926 | 0.486 | 3.288 | 9.340 | 8.210 |
| Alistar | 0.024 | 0.027 | 0.029 | 2.020 | 0.155 | 11.475 | 0.963 | 0.489 | 3.204 | 12.550 | 5.000 |
| Bard | 0.022 | 0.025 | 0.033 | 1.910 | 0.331 | 16.577 | 0.994 | 0.517 | 3.301 | 18.020 | 17.080 |
| Jayce | 0.020 | 0.027 | 0.035 | 1.880 | 0.355 | 16.459 | 0.993 | 0.509 | 3.313 | 19.150 | 21.230 |
| Pantheon | 0.020 | 0.022 | 0.027 | 1.700 | 0.298 | 14.314 | 0.985 | 0.498 | 3.239 | 19.150 | 20.280 |
| Xin Zhao | 0.018 | 0.024 | 0.024 | 1.640 | 0.252 | 15.543 | 0.990 | 0.513 | 3.279 | 12.740 | 8.960 |
| Annie | 0.021 | 0.018 | 0.016 | 1.590 | 0.127 | 6.636 | 0.750 | 0.520 | 2.985 | 9.150 | 8.770 |
| Neeko | 0.020 | 0.016 | 0.018 | 1.510 | 0.087 | 4.978 | 0.525 | 0.496 | 3.050 | 5.570 | 2.920 |

## (b) Q10 unique champions picked

Mean 110.1, median 110, 10-90% range 105 to 115 (min 96, max 124, 5000 sims).

Check, Q10 median in [95, 120]: **PASS** (median 110). Historical Worlds reference: 95 unique champions in 84 games (2025) and 95 in 106 games (2024).

## (c) Calibration

IPS on the first 500 sims, up to 20 iterations, toward: marginal means pibar, bebar + common logit shift (sums to 10). Iterations used: 7. Converged to < 1.5 pp: True.

Common logit shift (bisection so targets sum to 10 per game): pick +0.021940, ban -0.004597. Marginal sums before the shift: pick 9.8131, ban 10.0335. Targets after the shift: 10.0000 and 10.0000.

- Max pick error (champions with pick rate > 3%): **0.85 pp**
- Max ban error (champions with ban rate > 3%): **1.169 pp**

Iteration history (max error, pp): 0: 8.07/64.58, 1: 6.91/13.72, 2: 3.90/7.26, 3: 2.49/4.25, 4: 1.93/2.85, 5: 1.41/1.93, 6: 1.08/1.56, 7: 0.85/1.17

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

Model: eta = logit pi'_0 = a + b*x1 + c*(x2 - x1), with x1 = logit(pi) (meta window) and x2 = logit of the late-window pick rate. Ban: eta_b = a + b*y1 + c*(y2 - y1) with y1, y2 the analogous ban logits. Per-champion sd = sd_by_bin of the window rate (pick: pi, ban: beta). Marginal means pibar = E_z[sigmoid(eta + sd*z)] by 20-node Gauss-Hermite; the calibration targets are sigmoid(logit(pibar) + d) with a common d chosen so the targets sum to 10. Per tournament, the draft log-weight shift is (eta + u) - logit(pibar), with u = sd*z1 for picks and sd_b*(rho*z1 + sqrt(1-rho^2)*z2) for bans. The common d cancels in this shift. Late window: 2026-09-23 to 2026-10-14 (is_international = false, all leagues), G_late = 618 games.

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
| Rumble | 25.19 | 27.71 | 25.73 | 26.25 | 14.81 | 15.91 | 13.23 | 15.72 |
| Ryze | 26.70 | 25.77 | 24.96 | 25.48 | 13.30 | 16.40 | 12.79 | 15.25 |
| Lulu | 19.34 | 27.54 | 23.43 | 24.33 | 12.55 | 19.31 | 13.96 | 16.49 |
| Yunara | 19.15 | 26.58 | 22.76 | 23.66 | 4.25 | 5.25 | 3.19 | 5.57 |
| K'Sante | 21.60 | 24.64 | 22.46 | 22.95 | 11.98 | 12.84 | 10.20 | 12.43 |
| Syndra | 20.28 | 24.64 | 21.98 | 22.46 | 22.55 | 29.48 | 25.39 | 27.79 |
| Lucian | 21.60 | 23.34 | 21.63 | 22.11 | 29.34 | 30.78 | 29.83 | 31.93 |
| Jarvan IV | 22.92 | 22.05 | 21.22 | 21.70 | 30.66 | 34.17 | 32.79 | 34.63 |
| Orianna | 23.11 | 21.89 | 21.18 | 21.66 | 35.00 | 25.12 | 28.60 | 30.80 |
| Milio | 20.28 | 23.34 | 21.16 | 21.63 | 0.85 | 2.83 | 0.91 | 1.76 |
| Ezreal | 25.38 | 19.14 | 20.00 | 20.46 | 24.62 | 19.47 | 19.90 | 22.49 |
| Lee Sin | 19.34 | 20.92 | 19.27 | 20.13 | 24.25 | 28.51 | 25.70 | 28.08 |
| Ambessa | 18.77 | 19.31 | 18.03 | 18.87 | 6.32 | 8.00 | 5.25 | 6.74 |
| Seraphine | 21.98 | 17.37 | 17.74 | 18.17 | 12.17 | 18.82 | 13.50 | 16.00 |
| Olaf | 18.96 | 17.85 | 17.14 | 17.96 | 35.75 | 27.71 | 30.85 | 32.86 |
| Wukong | 13.68 | 19.95 | 16.55 | 17.36 | 10.28 | 13.97 | 10.00 | 12.22 |
| Jhin | 21.60 | 15.59 | 16.38 | 16.79 | 4.06 | 9.29 | 4.66 | 7.76 |
| Viktor | 16.51 | 17.37 | 16.01 | 16.81 | 9.91 | 11.07 | 8.32 | 10.33 |
| Karma | 21.98 | 14.62 | 15.79 | 16.18 | 10.09 | 19.14 | 12.45 | 14.88 |
| Caitlyn | 17.08 | 16.56 | 15.68 | 16.46 | 16.51 | 26.09 | 19.94 | 22.56 |

### Top 20 by beta' (z = 0)

| champion | pi % | late pick % | pi' (z=0) % | pi-bar (calib) % | beta % | late ban % | beta' (z=0) % | beta-bar (calib) % |
|---|---|---|---|---|---|---|---|---|
| Cassiopeia | 7.08 | 14.46 | 10.53 | 11.15 | 82.92 | 51.94 | 73.15 | 70.64 |
| Nocturne | 14.06 | 8.32 | 9.12 | 9.68 | 61.42 | 70.19 | 72.41 | 69.95 |
| Vi | 17.83 | 15.75 | 15.38 | 16.16 | 52.36 | 51.94 | 56.11 | 55.24 |
| Jarvan IV | 22.92 | 22.05 | 21.22 | 21.70 | 30.66 | 34.17 | 32.79 | 34.63 |
| Akali | 12.17 | 9.77 | 9.66 | 10.25 | 35.94 | 28.19 | 31.29 | 33.27 |
| Olaf | 18.96 | 17.85 | 17.14 | 17.96 | 35.75 | 27.71 | 30.85 | 32.86 |
| Lucian | 21.60 | 23.34 | 21.63 | 22.11 | 29.34 | 30.78 | 29.83 | 31.93 |
| Orianna | 23.11 | 21.89 | 21.18 | 21.66 | 35.00 | 25.12 | 28.60 | 30.80 |
| Lee Sin | 19.34 | 20.92 | 19.27 | 20.13 | 24.25 | 28.51 | 25.70 | 28.08 |
| Syndra | 20.28 | 24.64 | 21.98 | 22.46 | 22.55 | 29.48 | 25.39 | 27.79 |
| Nautilus | 14.62 | 17.37 | 15.35 | 16.13 | 27.45 | 24.80 | 24.86 | 27.29 |
| Locke | 10.09 | 10.90 | 9.75 | 10.34 | 23.30 | 20.76 | 20.19 | 22.77 |
| Caitlyn | 17.08 | 16.56 | 15.68 | 16.46 | 16.51 | 26.09 | 19.94 | 22.56 |
| Ezreal | 25.38 | 19.14 | 20.00 | 20.46 | 24.62 | 19.47 | 19.90 | 22.49 |
| Qiyana | 10.47 | 14.94 | 12.31 | 13.00 | 9.72 | 34.49 | 19.35 | 21.98 |
| Jayce | 19.15 | 14.78 | 15.11 | 15.88 | 21.23 | 17.04 | 16.78 | 19.37 |
| Poppy | 5.38 | 3.96 | 3.89 | 4.16 | 25.19 | 14.30 | 16.38 | 18.96 |
| Bard | 18.02 | 16.07 | 15.66 | 16.44 | 17.08 | 15.75 | 14.15 | 16.69 |
| Lulu | 19.34 | 27.54 | 23.43 | 24.33 | 12.55 | 19.31 | 13.96 | 16.49 |
| Pantheon | 19.15 | 12.20 | 13.26 | 13.98 | 20.28 | 12.84 | 13.50 | 15.97 |

Late rates are the smoothed (count + 0.5)/(G_late + 1) values used in the model, not raw counts. Champions with no late-window appearance sit at the smoothed floor, as intended.

## Verification, spread and benchmark

### Verification: forced marginal (shift term = 0), out of sample on sims 500-999

Max abs error over targets > 3%: pick 0.886 pp, ban 1.174 pp. Pass (< 1.5 pp): True.

| champion | target pick % | sim pick % | target ban % | sim ban % |
|---|---|---|---|---|
| Cassiopeia | 11.15 | 10.26 | 70.64 | 69.47 |
| Nocturne | 9.68 | 8.97 | 69.95 | 69.32 |
| Vi | 16.16 | 15.33 | 55.24 | 55.06 |
| Jarvan IV | 21.70 | 21.33 | 34.63 | 34.55 |

### Spread: across-sim sd of the simulated ban rate vs GLMM-implied sd (marginal formulation, G = 103)

Band [0.85, 1.25]: all inside = True. Ratios range 0.95 to 1.04.

| champion | bin | sd(logit) bin | target ban-bar % | sim mean ban % | sim sd (pp) | GLMM sd (pp) | ratio | in band |
|---|---|---|---|---|---|---|---|---|
| Cassiopeia | gt20 | 0.8011 | 70.64 | 70.86 | 14.85 | 15.67 | 0.948 | yes |
| Nocturne | gt20 | 0.8011 | 69.95 | 69.91 | 15.08 | 15.84 | 0.952 | yes |
| Vi | gt20 | 0.8011 | 55.24 | 55.90 | 17.61 | 18.05 | 0.976 | yes |
| Jarvan IV | gt20 | 0.8011 | 34.63 | 35.25 | 17.53 | 16.82 | 1.042 | yes |

### Benchmark: Q1 P(lead) vs the meta-shift benchmark (no draft mechanics, G = 103)

| champion | benchmark | sim P(lead) Q1 | diff | within 0.15 |
|---|---|---|---|---|
| Nocturne | 0.310 | 0.342 | +0.032 | yes |
| Cassiopeia | 0.290 | 0.397 | +0.107 | yes |
| Vi | 0.180 | 0.150 | -0.030 | yes |
| Jarvan IV | 0.040 | 0.030 | -0.010 | yes |

Stop-rule status: none triggered.

## Slope correction

Correction: the shift is (eta + u - logit(target marginal)) / slope_c for both picks and bans, where slope_c = d logit(rate) / d log-weight measured at baseline (calibrated weights, forced marginal) with a +0.25 bump on that champion's weight, 500 sims (sims 500-999), common random numbers. Ban slopes are measured for champions with target above 10%, pick slopes for champions above 10% plus six checks. Other champions are interpolated linearly in logit(target), clamped to [1.0, max] for bans and [0.3, max] for picks. Slopes outside [0.3, 2.5] stop the run.

Measured ban slopes: 30 champions, range 1.040 to 1.971. Measured pick slopes: 44 champions, range 0.459 to 0.887. Applied ban range 1.040 to 1.971; applied pick range 0.459 to 0.887. Within stop limits: True (none).

### Ban slopes (measured)

| champion | target ban % | ban slope (measured) | ban slope (applied) |
|---|---|---|---|
| Cassiopeia | 70.64 | 1.971 | 1.971 |
| Nocturne | 69.95 | 1.881 | 1.881 |
| Vi | 55.24 | 1.656 | 1.656 |
| Jarvan IV | 34.63 | 1.360 | 1.360 |
| Akali | 33.27 | 1.267 | 1.267 |
| Olaf | 32.86 | 1.298 | 1.298 |
| Lucian | 31.93 | 1.319 | 1.319 |
| Orianna | 30.80 | 1.320 | 1.320 |
| Lee Sin | 28.08 | 1.233 | 1.233 |
| Syndra | 27.79 | 1.319 | 1.319 |
| Nautilus | 27.29 | 1.189 | 1.189 |
| Locke | 22.77 | 1.156 | 1.156 |
| Caitlyn | 22.56 | 1.178 | 1.178 |
| Ezreal | 22.49 | 1.182 | 1.182 |
| Qiyana | 21.98 | 1.091 | 1.091 |
| Jayce | 19.37 | 1.138 | 1.138 |
| Poppy | 18.96 | 1.087 | 1.087 |
| Bard | 16.69 | 1.150 | 1.150 |
| Lulu | 16.49 | 1.158 | 1.158 |
| Seraphine | 16.00 | 1.130 | 1.130 |
| Pantheon | 15.97 | 1.111 | 1.111 |
| Rumble | 15.72 | 1.171 | 1.171 |
| Ryze | 15.25 | 1.137 | 1.137 |
| Karma | 14.88 | 1.119 | 1.119 |
| Kalista | 13.44 | 1.080 | 1.080 |
| Naafiri | 12.91 | 1.101 | 1.101 |
| K'Sante | 12.43 | 1.071 | 1.071 |
| Wukong | 12.22 | 1.098 | 1.098 |
| Viktor | 10.33 | 1.054 | 1.054 |
| Xin Zhao | 10.22 | 1.040 | 1.040 |

### Pick slopes (measured)

| champion | target pick % | pick slope (measured) | pick slope (applied) |
|---|---|---|---|
| Rumble | 26.25 | 0.473 | 0.473 |
| Ryze | 25.48 | 0.460 | 0.460 |
| Lulu | 24.33 | 0.552 | 0.552 |
| Yunara | 23.66 | 0.583 | 0.583 |
| K'Sante | 22.95 | 0.526 | 0.526 |
| Syndra | 22.46 | 0.485 | 0.485 |
| Lucian | 22.11 | 0.460 | 0.460 |
| Jarvan IV | 21.70 | 0.504 | 0.504 |
| Orianna | 21.66 | 0.504 | 0.504 |
| Milio | 21.63 | 0.581 | 0.581 |
| Ezreal | 20.46 | 0.543 | 0.543 |
| Lee Sin | 20.13 | 0.555 | 0.555 |
| Ambessa | 18.87 | 0.597 | 0.597 |
| Seraphine | 18.17 | 0.642 | 0.642 |
| Olaf | 17.96 | 0.604 | 0.604 |
| Wukong | 17.36 | 0.618 | 0.618 |
| Viktor | 16.81 | 0.661 | 0.661 |
| Jhin | 16.79 | 0.600 | 0.600 |
| Caitlyn | 16.46 | 0.650 | 0.650 |
| Bard | 16.44 | 0.647 | 0.647 |
| Karma | 16.18 | 0.702 | 0.702 |
| Vi | 16.16 | 0.466 | 0.466 |
| Nautilus | 16.13 | 0.616 | 0.616 |
| Jayce | 15.88 | 0.687 | 0.687 |
| Ashe | 14.86 | 0.730 | 0.730 |
| Xin Zhao | 14.60 | 0.637 | 0.637 |
| Naafiri | 14.55 | 0.715 | 0.715 |
| Renata Glasc | 14.40 | 0.706 | 0.706 |
| Pantheon | 13.98 | 0.715 | 0.715 |
| Gnar | 13.71 | 0.709 | 0.709 |
| Kalista | 13.71 | 0.669 | 0.669 |
| Qiyana | 13.00 | 0.661 | 0.661 |
| Ahri | 12.71 | 0.759 | 0.759 |
| Rakan | 11.93 | 0.752 | 0.752 |
| Camille | 11.32 | 0.748 | 0.748 |
| Galio | 11.27 | 0.769 | 0.769 |
| Cassiopeia | 11.15 | 0.459 | 0.459 |
| Alistar | 11.04 | 0.799 | 0.799 |
| Locke | 10.34 | 0.733 | 0.733 |
| Akali | 10.25 | 0.770 | 0.770 |
| Skarner | 10.18 | 0.739 | 0.739 |
| Rell | 7.14 | 0.846 | 0.846 |
| Anivia | 6.40 | 0.887 | 0.887 |
| Leona | 5.01 | 0.864 | 0.864 |

### Spread (sim sd / GLMM sd)

| champion | GLMM sd (pp) | ratio sim/GLMM | in [0.85, 1.25] |
|---|---|---|---|
| Cassiopeia | 15.67 | 0.948 | yes |
| Nocturne | 15.84 | 0.952 | yes |
| Vi | 18.05 | 0.976 | yes |
| Jarvan IV | 16.82 | 1.042 | yes |

### Mean ban rate vs target

| champion | target ban-bar % | mean ban % | minus target (pp) | within 1.5 pp |
|---|---|---|---|---|
| Cassiopeia | 70.64 | 70.86 | +0.22 | yes |
| Nocturne | 69.95 | 69.91 | -0.03 | yes |
| Vi | 55.24 | 55.90 | +0.66 | yes |
| Jarvan IV | 34.63 | 35.25 | +0.61 | yes |

### Mean pick rate vs target (report only)

| champion | target_pick_pct | sim_mean_pick_pct | diff_pp |
|---|---|---|---|
| Cassiopeia | 11.150 | 9.160 | -1.990 |
| Nocturne | 9.680 | 8.540 | -1.140 |
| Vi | 16.160 | 14.250 | -1.910 |
| Jarvan IV | 21.700 | 21.010 | -0.690 |

Checks: spread ratio in [0.85, 1.25] for the 4 champions: True; mean ban rate within 1.5 pp of the target for the 4: True; Q1 P(rank 1) within 0.15 of the benchmark (Nocturne, Cassiopeia, Vi): True; Sum P(rank 1) >= 1: True.

## (g) Runtime

Main run: 333.33 s total (calibration 31.04 s, simulation 301.79 s). Sensitivity runs are 1,000 sims each; their timings are in their own run_*.pkl files.

## Modelling notes

- Bans per game: 9.998 in the window, rounded to 10. Window target sums (count + 0.5)/(G + 1): picks 10.1283, bans 10.1264. Calibrated target sums (marginal means + common shift): picks 10.0, bans 10.0.
- Shift bins for the ban logit use each champion's ban rate beta_c .
- Role share smoothing: s = (n_cr + 0.1) / (n_c + 0.5). Champions with no window player rows get uniform shares.
- Death pool: a starter's 2026 top-league games with the same result (all champions). If that pool is empty, use the starter role's pool across all starters with that result.
- Death factor n_c = champion's picks in the window; ratio_c = champion's window mean deaths / mean deaths of its most common window role. Champions with no window player rows get factor 1.
- mean_wr_given_ge5 and mean_deaths_given_ge5 average the per-sim rate over sims where the champion has >= 5 picks.
- The calibration error is in-sample (the same 500 sims used for IPS, with the random shift off). Calibration targets are the marginal means with one common logit shift per type so each sums to 10 per game.
- Presence uses picks + bans per sim; a champion cannot be both banned and picked in the same game.
- Shift: a, b, c, sd_by_bin and rho_pick_ban come from meta_shift_fit.json. c is required; a missing key raises.
