# Meta shift: binomial logit-normal fit (top-league pre-window + late any-league read)

Model, separately for pick and ban: event_count ~ Binomial(G_ev, sigmoid(a + b*x1 + c*(x2 - x1) + u)), u ~ Normal(0, sd^2) with sd chosen by the pre-rate bin of x1. x1 is the logit of the smoothed top-league 60-day pre-window rate; x2 is the logit of the smoothed late 21-day rate across all non-international leagues. Each event's universe is every champion picked or banned in any non-international game of that calendar year or in the event, so zero-count champions are kept. Event counts are not smoothed. u is integrated with 20-node Gauss-Hermite quadrature and the likelihood is maximized with L-BFGS-B from two starts (they agree on a, b, c and the log-likelihood). Standard errors come from the inverse of a central finite-difference Hessian of the negative log-likelihood (step 1e-3). The sd values are the event-specific shift; binomial event noise is excluded because the draft sim regenerates it.

Recommended variant: **fearless**. Fearless = 2025-26 events (5 events). Pooled = all 11 events.

## Fit table

| Fit | a (SE) | b (SE) | c (SE) | sd lt5 | sd 5to20 | sd gt20 | n | loglik |
|---|---|---|---|---|---|---|---|---|
| pick fearless (rec) | -0.0237 (0.0596) | 1.0337 (0.0283) | 0.6848 (0.0687) | 0.9377 | 0.3302 | 0.1492 | 862 | -1345.30 |
| ban fearless (rec) | 0.1445 (0.0944) | 1.1905 (0.0355) | 0.6813 (0.0682) | 1.1986 | 0.8065 | 0.8011 | 862 | -1258.51 |
| pick pooled | -0.0735 (0.0568) | 1.0345 (0.0215) | 0.4917 (0.0363) | 1.3865 | 0.6989 | 0.7617 | 1850 | -3483.64 |
| ban pooled | 0.0323 (0.0553) | 1.2044 (0.0237) | 0.6264 (0.0277) | 1.6325 | 1.1588 | 1.0630 | 1850 | -3134.70 |

## What c says

- pick: the late-read coefficient is c = 0.6848 (SE 0.0687, z = 9.97). The top-league pre-window coefficient is b - c = 0.3488. So the late read carries c / b = 0.66 of the total slope on the two reads combined (only meaningful when 0 <= c / b <= 1).
- ban: the late-read coefficient is c = 0.6813 (SE 0.0682, z = 10.00). The top-league pre-window coefficient is b - c = 0.5092. So the late read carries c / b = 0.57 of the total slope on the two reads combined (only meaningful when 0 <= c / b <= 1).
A c near zero means the late any-league read adds little beyond the top-league pre-window. A c near b means the late read substitutes for the pre-window. Patches right before an event are often played only in minor leagues, so the late read can be noisy or unrepresentative for some champions.

## Sanity check: unique picked champions per event

| Event | G_pre | G_ev | G_late | Universe | Unique picked (actual) | Unique picked (expected, rec. pick model) | actual - expected |
|---|---|---|---|---|---|---|---|
| WLDs 2022 | 563 | 127 | 354 | 162 | 109 | 108.4 | +0.6 |
| WLDs 2023 | 230 | 113 | 259 | 163 | 89 | 101.5 | -12.5 |
| WLDs 2024 | 490 | 106 | 337 | 169 | 95 | 110.8 | -15.8 |
| WLDs 2025 | 605 | 84 | 556 | 172 | 95 | 106.9 | -11.9 |
| MSI 2022 | 559 | 80 | 190 | 162 | 98 | 86.7 | +11.3 |
| MSI 2023 | 771 | 76 | 308 | 163 | 79 | 86.9 | -7.9 |
| MSI 2024 | 645 | 78 | 360 | 169 | 86 | 89.4 | -3.4 |
| MSI 2025 | 909 | 80 | 459 | 172 | 107 | 107.5 | -0.5 |
| MSI 2026 | 689 | 71 | 337 | 173 | 101 | 105.5 | -4.5 |
| FST 2025 | 654 | 35 | 704 | 172 | 84 | 87.3 | -3.3 |
| FST 2026 | 846 | 45 | 615 | 173 | 95 | 92.5 | +2.5 |

Expected = sum over the universe of 1 - E_u[(1 - p)^G_ev], integrated over u with the recommended pick model. The model is fitted on these same events, so this is an in-sample check. Actual unique picked counts range from 79 to 109 (median 95) across the 11 events.

## Fit notes

- Pick and ban rho (posterior-mean u, same champion and event, recommended variant): **0.3846**.
- Recommendation rule: fearless unless its c SE is above 0.3 while the pooled c SE is below 0.3 for pick or ban; then pooled. Recommended here: **fearless**.
- Previous smoothed-OLS fit (v1, with bootstrap-adjusted sd): kept under smoothed_fit_v1 in the JSON and not used. It smoothed the event side as 0.5/(G_ev+1), against 0.5/(G_pre+1) on the pre side, which put a higher floor on event rates, and it dropped champions at zero in both windows. The draft sim showed that this pulls rare champions up too far.

## Leader check

| Event | Presence leader (pre rank) | Pre presence leader (event rank) | Most picked (pre pick rank) |
|---|---|---|---|
| WLDs 2022 | Aatrox (pre rank 25) | Kalista (event rank 9) | Sylas (pre pick rank 9) |
| WLDs 2023 | Orianna (pre rank 54) | Xayah (event rank 2) | Kai'Sa (pre pick rank 2) |
| WLDs 2024 | Yone (pre rank 28) | Rumble (event rank 13) | Rell (pre pick rank 2) |
| WLDs 2025 | Yunara (pre rank 2) | Azir (event rank 2) | Xin Zhao (pre pick rank 3) |
| MSI 2022 | Ahri (pre rank 2) | Zeri (event rank 58) | Gwen (pre pick rank 28) |
| MSI 2023 | Vi (pre rank 2) | Annie (event rank 3) | Aphelios (pre pick rank 6) |
| MSI 2024 | Kalista (pre rank 1) | Kalista (event rank 1) | K'Sante (pre pick rank 3) |
| MSI 2025 | Varus (pre rank 2) | Vi (event rank 5) | Rell (pre pick rank 6) |
| MSI 2026 | Vi (pre rank 13) | Varus (event rank 7) | Jarvan IV (pre pick rank 4) |
| FST 2025 | Kalista (pre rank 2) | Skarner (event rank 2) | Ezreal (pre pick rank 6) |
| FST 2026 | Orianna (pre rank 2) | Varus (event rank 4) | Yunara (pre pick rank 2) |

Notes: MSI 2022: 2 champions tied for the event presence lead (alphabetical tie-break). MSI 2024: 2 champions tied for the event presence lead (alphabetical tie-break). FST 2026: 2 champions tied for the event presence lead (alphabetical tie-break).

Ranks are among all champions seen in either top-league window, with ties sharing the higher rank.

## Events

| Event | Start (UTC) | G_pre | G_ev | G_late | Top-league pre-window leagues |
|---|---|---|---|---|---|
| WLDs 2022 | 2022-09-29 | 563 | 127 | 354 | CBLOL, LCK, LCS, LEC, LJL, LPL, PCS, VCS |
| WLDs 2023 | 2023-10-09 | 230 | 113 | 259 | CBLOL, LCK, LCS, LEC, LJL, PCS, VCS |
| WLDs 2024 | 2024-09-25 | 490 | 106 | 337 | CBLOL, LCK, LCS, LEC, LJL, LPL, PCS, VCS |
| WLDs 2025 | 2025-10-14 | 605 | 84 | 556 | LCK, LCP, LEC, LJL, LPL, LTA, LTA N, LTA S, PCS |
| MSI 2022 | 2022-05-10 | 559 | 80 | 190 | CBLOL, LCK, LCS, LEC, LJL, LPL, PCS, VCS |
| MSI 2023 | 2023-05-02 | 771 | 76 | 308 | CBLOL, LCK, LCS, LEC, LJL, LPL, PCS, VCS |
| MSI 2024 | 2024-05-01 | 645 | 78 | 360 | CBLOL, LCK, LCS, LEC, LJL, LPL, PCS, VCS |
| MSI 2025 | 2025-06-27 | 909 | 80 | 459 | LCK, LCP, LEC, LJL, LPL, LTA N, LTA S, PCS, VCS |
| MSI 2026 | 2026-06-28 | 689 | 71 | 337 | CBLOL, LCK, LCP, LCS, LEC, LJL, LPL, PCS, VCS |
| FST 2025 | 2025-03-10 | 654 | 35 | 704 | LCK, LCP, LEC, LJL, LPL, LTA, LTA N, LTA S, PCS, VCS |
| FST 2026 | 2026-03-16 | 846 | 45 | 615 | CBLOL, LCK, LCP, LCS, LEC, LJL, LPL, VCS |

## Data notes

The database has no LCS rows dated 2025, so LCS is absent from every 2025 pre-window and LTA, LTA N and LTA S appear instead. WLDs 2023 has no LPL in its pre-window because LPL's last 2023 game (2023-08-05) falls before it. data_complete = False for all LPL 2022-25 games, 126 LPL 2026 games and all MSI 2024 games; their pick and ban columns are populated, so they are used as-is (data_complete is not a method filter). Blank champion slots are dropped.

