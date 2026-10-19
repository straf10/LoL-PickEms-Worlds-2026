# Presence-leader calibration backtest

Question: is the fitted model overconfident about which champion leads presence at an event? For each of the 11 events, the model simulates 5,000 draws of pick and ban counts for every champion in the event's universe, and takes the presence leader (pick + ban games, capped at G_ev) in each draw, with ties split. P(lead) is the share of draws in which the champion leads. We compare the model's favourite (highest P(lead)) and the probability it gave to the actual leader(s) with what happened.

Parameters: the recommended fearless fit (pick a=-0.0237, b=1.0337, c=0.6848; ban a=0.1445, b=1.1905, c=0.6813). The in-sample table uses these. The LOEO table refits the same model on the other 10 events for each held-out event. Correlation of u_pick and u_ban: rho = 0.3846, as in the fit JSON. That value is a posterior-mean correlation and is attenuated, so the latent correlation is probably higher; the simulation therefore understates the coupling.

## In-sample (recommended fearless fit)

| Event | Actual leader(s) | P(actual leader) | Model favourite | P(favourite) | Favourite hit |
|---|---|---|---|---|---|
| WLDs 2022 | Aatrox | 0.0155 | Wukong | 0.2236 | N |
| WLDs 2023 | Orianna | 0.0024 | Rell | 0.2118 | N |
| WLDs 2024 | Yone | 0.0295 | Rumble | 0.1685 | N |
| WLDs 2025 | Yunara | 0.0302 | Azir | 0.2155 | N |
| MSI 2022 | Ahri / Lucian | 0.3761 | Ahri | 0.3670 | Y |
| MSI 2023 | Vi | 0.1806 | Vi | 0.1806 | Y |
| MSI 2024 | Kalista / Senna | 0.1995 | Kalista | 0.1974 | Y |
| MSI 2025 | Varus | 0.1443 | Vi | 0.2305 | N |
| MSI 2026 | Vi | 0.0044 | Orianna | 0.3014 | N |
| FST 2025 | Kalista | 0.1555 | Skarner | 0.4365 | N |
| FST 2026 | Orianna / Ryze | 0.3277 | Orianna | 0.3043 | Y |

Calibration: sum of P(favourite) over 11 events = 2.84; actual favourite hits = 4; mean log-loss of the actual leader = 2.8987.

Reference: a uniform guess over each event's universe (about 160-175 champions) has mean log-loss 5.1247. The favourites' P ranged 0.17-0.44.

## Scaling every sd by s (in-sample)

| sd scale s | Expected favourite hits | Actual favourite hits | Mean log-loss |  |
|---|---|---|---|---|
| 1.0 | 2.84 | 4 | 2.8987 |  |
| 1.25 | 2.25 | 3 | 2.7894 |  |
| 1.5 | 1.75 | 3 | 2.7582 | <- s_best |
| 2.0 | 1.02 | 3 | 2.9844 |  |
| 2.5 | 0.63 | 3 | 3.2705 |  |
| 3.0 | 0.43 | 3 | 3.5328 |  |

s_best (in-sample, minimum mean log-loss) = **1.5**.

## Leave-one-event-out (same model refit on the other 10 events)

LOEO refits took 26.9 s in total (within the ~10 minute budget).

Optimizer caveat: in 3 of 22 held-out fits (pick and ban, 11 events each), the two L-BFGS-B starts ended at different points on a flat ridge (nll gap of 4-5 units; the parameters differ by up to about 0.09 in a, b and c). The lower-nll point is used. A Nelder-Mead polish did not close the gap, so these fits are less precise than the in-sample fit, which both starts agree on. Per-fit spreads are in the JSON (loeo.start_checks).

| Event | Actual leader(s) | P(actual leader) | Model favourite | P(favourite) | Favourite hit |
|---|---|---|---|---|---|
| WLDs 2022 | Aatrox | 0.0156 | Wukong | 0.1583 | N |
| WLDs 2023 | Orianna | 0.0045 | Rell | 0.1402 | N |
| WLDs 2024 | Yone | 0.0217 | Rumble | 0.1171 | N |
| WLDs 2025 | Yunara | 0.0299 | Azir | 0.0954 | N |
| MSI 2022 | Ahri / Lucian | 0.2469 | Ahri | 0.2367 | Y |
| MSI 2023 | Vi | 0.1298 | Vi | 0.1298 | Y |
| MSI 2024 | Kalista / Senna | 0.1385 | Nautilus | 0.1464 | N |
| MSI 2025 | Varus | 0.1060 | Vi | 0.1201 | N |
| MSI 2026 | Vi | 0.0190 | Orianna | 0.1620 | N |
| FST 2025 | Kalista | 0.0902 | Skarner | 0.1899 | N |
| FST 2026 | Orianna / Ryze | 0.2052 | Orianna | 0.1636 | Y |

Calibration: sum of P(favourite) over 11 events = 1.66; actual favourite hits = 3; mean log-loss of the actual leader = 2.9565.

## Scaling every sd by s (LOEO)

| sd scale s | Expected favourite hits | Actual favourite hits | Mean log-loss |  |
|---|---|---|---|---|
| 1.0 | 1.66 | 3 | 2.9565 | <- s_best |
| 1.25 | 1.15 | 3 | 2.9811 |  |
| 1.5 | 0.82 | 4 | 3.1343 |  |
| 2.0 | 0.47 | 4 | 3.4643 |  |
| 2.5 | 0.31 | 4 | 3.7425 |  |
| 3.0 | 0.23 | 4 | 3.9528 |  |

s_best (LOEO) = **1.0**.

## Notes

- The actual presence leader counts games where the champion was picked or banned (per-game union). The database has 2 games (of 53,499) in which a champion appears both as a pick and as a ban; summing pick and ban counts would double count those, so the union is used.
- The model's presence is min(pick + ban, G_ev) / G_ev, as briefed.
- Log-loss uses max(P, 0.0001); 0.0001 is half a draw, the lowest probability the simulation can resolve.
- Monte Carlo error on each P(lead) is at most about 0.007 (5,000 draws). Random numbers are seeded per event and reused across s, so the s comparison uses common random numbers.
- In-sample: the fearless fit used only the 2025-26 events. The 2022-24 events are out-of-era for these parameters, so the LOEO table is the fairer test for them.

