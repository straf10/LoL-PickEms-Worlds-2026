# Spread diagnosis: across-tournament sd of the ban rate vs the GLMM sd

Scratch diagnostic `outputs/draft/tmp_spread_diag.py`. Same calibration as the main run (500 sims, marginal targets, common shift). Experiments use 1,000 sims unless stated. Ratios are sim sd / GLMM sd (marginal formulation, G = 103). sd values are in percentage points.

## Reproduction check (experiment A at the round-4 setting)

| champion | round-4 ratio (5,000) | rerun ratio (5,000) | diff | A ratio (1,000) | A vs round-4 within 0.1 |
|---|---|---|---|---|---|
| Cassiopeia | 1.4991 | 1.4991 | +0.0000 | 1.425 | yes |
| Nocturne | 1.4556 | 1.4556 | +0.0000 | 1.548 | yes |
| Vi | 1.3872 | 1.3872 | +0.0000 | 1.373 | yes |
| Jarvan IV | 1.3157 | 1.3157 | +0.0000 | 1.280 | yes |

5,000-sim rerun identical to the round-4 deliverable: True.

## Experiments

A: baseline. B: random shift only on the target (others 0). C: fearless off (shift on). D: no shift (draft noise floor). E: slope amplification (+0.25 log-weight on the target's ban weight at baseline; slope / p(1-p)). F: ban-side shift only. G: pick-side shift only.

| champion | GLMM sd (pp) | A ratio | B ratio (target only) | C ratio (fearless off) | D sd (pp, no shift) | binomial floor (pp) | D / floor | E amplification | F ratio (ban shift only) | G ratio (pick shift only) | H sd (pp, no shift, fearless off) | H / floor |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Cassiopeia | 15.91 | 1.425 | 1.410 | 1.297 | 6.46 | 4.57 | 1.412 | 1.691 | 1.453 | 0.410 | 4.41 | 0.964 |
| Nocturne | 15.85 | 1.548 | 1.528 | 1.462 | 6.33 | 4.57 | 1.387 | 1.669 | 1.573 | 0.403 | 4.56 | 0.998 |
| Vi | 18.01 | 1.373 | 1.356 | 1.269 | 6.83 | 4.90 | 1.393 | 1.604 | 1.397 | 0.387 | 4.77 | 0.973 |
| Jarvan IV | 16.84 | 1.280 | 1.283 | 1.248 | 5.94 | 4.69 | 1.265 | 1.438 | 1.287 | 0.353 | 4.72 | 1.007 |

## Variance decomposition (tournament part)

| champion | GLMM tournament sd (pp) = sqrt(GLMM^2 - floor^2) | sim tournament sd (pp) = sqrt(A^2 - D^2) | ratio | E slope amplification |
|---|---|---|---|---|
| Cassiopeia | 15.23 | 21.73 | 1.427 | 1.691 |
| Nocturne | 15.18 | 23.71 | 1.562 | 1.669 |
| Vi | 17.33 | 23.78 | 1.372 | 1.604 |
| Jarvan IV | 16.18 | 20.74 | 1.282 | 1.438 |

Mean ban rates, no shift, fearless off (pp): Cassiopeia 71.58, Nocturne 69.98, Vi 60.33, Jarvan IV 39.89.

Baseline no-shift mean ban rates (pp): Cassiopeia 68.60, Nocturne 68.77, Vi 55.24, Jarvan IV 34.77. E slope (dp per unit log-weight): Cassiopeia 0.3643, Nocturne 0.3584, Vi 0.3967, Jarvan IV 0.3262. Calibrated shift-run means (A, pp): Cassiopeia 68.67, Nocturne 67.46, Vi 56.16, Jarvan IV 34.91.

## Extra experiment H

H: no shift, fearless off. Its sd divided by the binomial floor is 0.96 to 1.01 for all four champions, so the sim adds no noise beyond the binomial floor once locks are removed (sims are independent, no leakage).

## Findings

Reproduction: the 5,000-sim rerun reproduces the round-4 ratios exactly. The 1,000-sim experiment A is within 0.1 of the round-4 ratios for all four champions (largest gap +0.092, Nocturne), so the stop rule does not trigger.

- **Fearless locks are the largest source of the no-shift excess (experiment D).** With no shift at all, the across-sim sd of the ban rate is 1.27 to 1.41 times the binomial floor. With fearless off (H) it is 0.96 to 1.01 times the floor. Mechanism: a champion banned in game 1 was not picked in game 1, so it stays available in game 2; a champion picked in game 1 is locked for the rest of the series. Ban outcomes within a series are therefore positively correlated, and the per-tournament ban rate scatters more than the GLMM's independent-game binomial term allows. This is the real fearless rule, implemented as specified. Turning fearless off (C) lowers the ratio by 0.13 (Cassiopeia), 0.09 (Nocturne), 0.10 (Vi) and 0.03 (Jarvan IV).
- **The draft amplifies a champion's own ban-weight shift (experiment E).** At baseline, the logit of a champion's ban rate moves 1.44 to 1.69 per unit of its own log-weight, against 1.0 in the GLMM. The tournament part of the sim variance is 1.28 to 1.56 times the GLMM's tournament part (decomposition table), so this is the main driver of the excess. The mechanism is not derived analytically here: with a fixed budget of 10 bans drawn without replacement, a high-rate champion's own weight changes the draw more than an independent-logit model implies. Saturation at larger shifts is why the tournament ratio sits below E.
- **Competition for ban slots is not the cause (experiment B).** When only the target champion carries a shift, its ratio is within 0.02 of the full-shift ratio (1.28 to 1.53 against 1.28 to 1.55). Other champions' shifts barely feed back.
- **The pick-side shift does not drive the ban spread (experiments F and G).** Pick-only shift gives 0.35 to 0.41 of the GLMM sd. Ban-only shift reproduces the full result (F 1.29 to 1.57 against A 1.28 to 1.55).
- **Residual with fearless off.** Experiment C is still 1.25 to 1.46, so the draft amplification remains after the lock effect is removed.

**Bug verdict: no implementation bug found in the spread path.** Checked:
- No double counting. The random shift enters only through the draft weights (`_shift_draws`, crystal/draft.py lines 451 to 467; applied in `_simulate` at line 312). Calibration (`_calibrate`) runs with the random shift off, so the random part is not counted again.
- No cross-sim leakage. With no shift and fearless off the sd equals the binomial floor (H).
- The lock is applied to the correct series: lock mask per (sim, series) at lines 283, 300 and 348. Fearless is therefore a real correlation source, not a fault.
- Design note, not a bug: the spec's shift term (eta + u) - logit(pibar) is also non-zero at u = 0, so the baseline weights are not the state the calibration was fitted to. Verification tests the forced-marginal state, not the average across tournaments.
- Real modelling mismatch to decide on: the average across tournaments does not hit the marginal target. In the round-4 5,000-sim run, mean ban rates are Cassiopeia 67.84% against target 69.68% (-1.8 pp), Nocturne 68.02% against 69.89% (-1.9 pp), Vi 55.67% against 55.83% (-0.2 pp) and Jarvan IV 35.89% against 34.76% (+1.1 pp). The marginal target assumes the draft's inclusion equals sigmoid(logit), which the draft does not satisfy (see the E amplification above).

## Files

- Deliverables `outputs/draft/champion_sim.md`, `outputs/draft/champion_sim.csv` and `crystal/draft.py` were not modified; their SHA-256 hashes match the pre-diagnosis values (checked before and after).
- Diagnostic code: `outputs/draft/tmp_spread_diag.py` (imports `crystal.draft`, adds shift masks and a fearless switch on a copy of the game arrays; no change to `draft.py`).
