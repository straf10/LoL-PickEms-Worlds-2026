# Q10 (unique champions picked at Worlds 2026): draft sim vs closed form, and the bias correction

Code: `crystal/q10_correct.py` (run `python -m crystal.q10_correct`). Outputs: `outputs/q10/q10_buckets.csv`, `outputs/q10/q10_backtest.csv`.

## 1. Draft sim vs closed form for Worlds 2026

| Quantity | Value |
|---|---|
| Closed form, expected unique champions (G = sim game count, averaged over the 5,000 sims; mean G 103.2) | **111.3** |
| Closed form, same with G fixed at the mean | 111.3 |
| Draft sim, shifted (5,000 sims, mean / median / sd) | 110.5 / 110 / 4.0 |
| Gap (draft minus closed form) | **-0.8** |

The gap is well inside the 3-point threshold, so the backtested bias can be applied to the draft sim. Using the draft's own window (start 2026-10-14) instead of the Play-In start (2026-10-15) moves the closed form to 111.1. The closed form uses the meta-shift windows: domestic leagues for the 60 days before the event, and all non-international games for the 21 days before it. Pre-window G = 528, late-window G = 563, universe 173 champions.

## 2. Backtesting the draft sim

Not done. `crystal/draft.py` is built only for 2026: it reads `data/rosters_2026.csv`, the 2026 Worlds bracket sim (`outputs/draft/sim_games_5k.csv.gz`) and 2026 base-rate windows. A past-event run would need a 2025 roster file and a 2025 bracket sim, so this exceeded the time box. The bridge is step 1 (gap -0.8).

## 3. The correction

Residual = actual unique picked minus closed-form expected, for the pick model (fearless fit, as in the sanity table).

| Event | Expected | Actual | Residual |
|---|---|---|---|
| WLDs 2022 | 108.4 | 109 | +0.6 |
| WLDs 2023 | 101.5 | 89 | -12.5 |
| WLDs 2024 | 110.8 | 95 | -15.8 |
| WLDs 2025 | 106.9 | 95 | -11.9 |
| MSI 2022-2026 | | | +11.3, -7.9, -3.4, -0.5, -4.5 (mean -1.0) |
| FST 2025, 2026 | | | -3.3, +2.5 (mean -0.4) |

**Primary choice: Worlds 2022-25.** Reasons: the target is a Worlds (same format and game count, G about 103). All four Worlds events are used, including 2022, because excluding it would mean choosing the set by its result. Mean residual -9.9.

**Spread.** Sample sd of the four Worlds residuals is 7.2 (n = 4, standard error of the mean 3.6). The sd used is built in two parts:
- Model-error sd of 6.3. This is the 11-event residual variance minus the binomial spread the closed form already predicts (about 4.5 per event). The draft sim has its own per-sim spread of about 4, which is the realized part, so it is not added again.
- Mean uncertainty of 3.6, from the four events.
- Extra noise sd = sqrt(6.3² + 3.6²) = **7.3**. Combined with the draft sim's own spread of 4.0, the total corrected sd is about 8.3.

**Primary correction: -9.9 ± 7.3** (applied as a shift plus per-sim normal noise, seed 11, 200 noise draws per sim).

## 4. Bucket probabilities under each variant

| Variant | Shift mean | Extra sd | a) 0-99 | b) 100-104 | c) 105-109 | d) 110-114 | e) 115-119 | f) 120+ |
|---|---|---|---|---|---|---|---|---|
| **Primary: Worlds 2022-25** | -9.9 | 7.3 | **0.447** | 0.234 | 0.177 | 0.095 | 0.036 | 0.012 |
| Worlds 2023-25 | -13.4 | 6.4 | 0.624 | 0.211 | 0.113 | 0.041 | 0.010 | 0.002 |
| All 11 events | -4.1 | 6.7 | 0.191 | 0.215 | 0.250 | 0.194 | 0.103 | 0.047 |
| Worlds 2022-25, sd without the realized-noise removal (8.0) | -9.9 | 8.0 | 0.451 | 0.217 | 0.171 | 0.100 | 0.043 | 0.018 |
| Previous manual -10 ± 7 (check) | -10.0 | 7.0 | 0.451 | 0.240 | 0.177 | 0.091 | 0.032 | 0.009 |
| No correction (raw draft) | 0 | 0 | 0.004 | 0.063 | 0.337 | 0.436 | 0.148 | 0.012 |

The answer is sensitive to which events set the bias: a) ranges from 0.19 to 0.62 depending on the event set. The draft sim itself is well pinned down; the uncertainty is in the bias.

## 5. Verification

| # | Check | Result |
|---|---|---|
| 1 | Reproduce the current answer with -10 ± 7 (a ≈ 0.45 ± 0.03, b ≈ 0.22, c ≈ 0.17) | **Partial.** a = 0.451 (pass). b = 0.240 and c = 0.177 are 0.02 and 0.01 above the stated values. The inputs are not the cause: the round-4 draft run gives b = 0.242, and the one-draw-per-sim version with seed 11 gives b = 0.228 (Monte Carlo noise of about ±0.006). The old values match a normal with total sd of about 9, which is what you get if the draft's own spread of 4 is counted twice (sqrt(7² + 2·4²) ≈ 8.9). I could not find a record of how the old numbers were computed. |
| 2 | Backtest reproduction (±1.5 of the report table) | **Pass.** WLDs 2022 108.42 (report 108.4); 2023 101.49 (101.5); 2024 110.76 (110.8); 2025 106.93 (106.9); MSI 2025 107.53 (107.5). All 11 events match to ±0.05. |
| 3 | Buckets sum to 1 for every variant | **Pass** (all sums are 1.000). |
| 4 | Seed stability (two seeds within 0.01 per bucket) | **Pass.** Seeds 11 and 12 differ by at most 0.0008 on any bucket. MC vs analytic normal-CDF average differs by at most 0.0007. |

Rerun check: `python -m crystal.q10_correct --rerun-draft` reruns the draft sim (about 5 minutes) and should reproduce the saved run exactly. **Pass.** The rerun (log in `outputs/q10/rerun_log.txt`) gives the same per-sim values as the saved run (max difference 0). The first attempt crashed with a Python GIL error inside NumPy's Gumbel draw; the second attempt completed. The crash did not recur and was not investigated further.

## 6. Recommendation

**a) 0-99 at P ≈ 0.45** (primary 0.447; the same answer as before, but with a corrected bias model). The number depends on the Worlds-only bias choice: with Worlds 2023-25 it rises to 0.62, and with all events it falls to 0.19.

## 7. Rerun after the Oct 14 refresh

`python -m crystal.q10_correct` checks whether the saved draft run (`outputs/draft/tmp_run_k15_shift_s5000.pkl`) is newer than `data/pickems.duckdb`. If it is not, it reruns the draft sim (about 5 minutes) and caches it in `outputs/q10/draft_q10_s5000.pkl`. The closed-form check and the backtest are recomputed from the DB each time.
