# Q7 stress test: Peyz vs Gumayusi total kills (Worlds 2026)

Run: `python -m crystal.q7_check 40000 11` (40,000 sims per variant; second seed 12 for stability).
Code: `crystal/q7_check.py` (reuses `sim.tournament.run`, `crystal.estimate.player_pools` and `matrix_sampler`).

## Bottom line

**Peyz, P = 0.66** (combined variant, 40k sims). The current 0.67 (file says 0.673) is close. Most of the lead is real: Peyz takes a bigger share of his team's kills (0.34 vs 0.26). The biggest downward adjustment is recency: Gumayusi's 2026 share at HLE is below his T1-era share, and Peyz's 2026 share is above his earlier share. Opponent-strength adjustments are within noise and point in both directions depending on the definition.

## Inputs (2026 top-league pool, as used by the model)

| | Peyz (T1) | Gumayusi (HLE) |
|---|---|---|
| 2026 games | 142 | 123 |
| Kills per game (sd) | 5.83 (4.02) | 4.31 (2.82) |
| Kills in wins / losses | 7.34 / 3.44 | 5.19 / 2.98 |
| vs Worlds-2026 field (games) | 5.93 (92) | 4.16 (79) |
| vs LCK top-4 (games) | 5.34 (67) | 3.97 (58) |
| International games 2026 | 7.12 (33) | 4.50 (24) |
| Team kills per game | 16.9 | 16.6 |
| Kill share of team kills, 2026 | 0.344 | 0.260 |
| Kill share, 2024-25 (prior) | 0.315 | 0.303 |
| Between-half-year sd of share (tau) | 0.022 | 0.025 |
| Weight on 2026 share in recency shrink | 0.71 | 0.80 |
| Team kill env factor (field) | 0.975 | 0.968 |
| Bot share factor (field) | 1.039 | 1.009 |
| Recency factor (posterior / 2026 share) | 0.975 | 1.033 |

Context: 2025-26 pooled (all teams) Peyz 5.19 kills/game (n=287), Gumayusi 4.72 (n=244). Peyz's 2025 JDG games were 4.3-4.8 per game. The 2026 gap is not a MSI/EWC artifact: LCK-only 2026 is Peyz 5.44 (n=109) vs Gumayusi 4.26 (n=99).

Small-sample rule: the field and LCK-top-4 subsets have 58-92 games each (above 15), so no subset was dropped. Every group factor is still shrunk toward 1 by n/(n+30). The fearless factor uses all 2025-26 top-league games.

## P(Peyz > Gumayusi) by variant (40k sims, seed 11)

| Variant | P(Peyz) | P(Gumayusi) | P(tie) |
|---|---|---|---|
| a) current method (replica) | 0.672 | 0.319 | 0.009 |
| b1) team kill environment vs field only | 0.676 | 0.314 | 0.010 |
| b2) bot kill share vs field only | 0.689 | 0.303 | 0.008 |
| b3) game-3+ factor only (Fearless) | 0.673 | 0.318 | 0.009 |
| b4) recency shrink + parameter uncertainty only | 0.639 | 0.352 | 0.009 |
| c) opponent (b1+b2) | 0.695 | 0.297 | 0.008 |
| c2) opponent with LCK top-4 definition | 0.668 | 0.322 | 0.009 |
| **d) all combined (b1-b4)** | **0.662** | **0.330** | **0.009** |

Combined at seed 12: 0.659. Every variant at seed 12 is within 0.007 of seed 11.

## Findings on the five checks

1. **Opponent strength.** Peyz's kills drop vs LCK top-4 (5.34 vs 5.83) and Gumayusi's drop by the same proportion (3.97 vs 4.31). The field-based version (Worlds teams) raises Peyz's lead to 0.695, while the LCK top-4 version leaves it at 0.668. The field sample is 79-92 games per player, so the difference between players is within noise. Not adopted on its own; it is in the combined run.
2. **Team kill share.** T1 and HLE have nearly the same team kills per game (16.9 vs 16.6). The edge comes from Peyz's share (0.34 vs 0.26). Gumayusi's share fell from 0.30-0.33 at T1 (2025) to 0.26 at HLE (2026). Peyz's share rose from 0.30-0.31 at JDG to 0.32-0.38 at T1. Both moves look like team-context effects rather than noise.
3. **Fearless.** Kills in game 3+ of a series are 3% below games 1-2 across all players (ratio 0.970), and the drop is similar in domestic series that are not Fearless. Player-level samples are too small: Peyz international game 3+ is 8.45 (n=11), Gumayusi 5.24 (n=33). Peyz domestic game 3+ is 1.0 kills lower (n=78), but his international game 3+ goes the other way. Using the pooled 0.97 factor changes P by +0.001. No player-specific Fearless penalty is adopted.
4. **Games played.** T1 and HLE play equal numbers of games in the sim (13.7 vs 13.8 mean). P(T1 more games) 0.46, P(HLE more) 0.48, P(equal) 0.06, correlation -0.07. Games are symmetric, so they do not bias P. Caveat: P(team plays 24+ games) is about 0.3% in the sim, while T1 played 24 games at Worlds 2025 as champion. The tail may be thin, but it affects variance, not direction.
5. **Ties.** P(exact tie) is about 0.9% (current method). The current code counts neither player on a tie. The config does not state a tie rule for Q7. In adjusted variants, factors make kills non-integer, so totals are rounded to whole kills before comparing, keeping ties consistent across variants.

Other notes: the current method gives HLE a slightly higher per-game win rate in the sim (0.623 vs 0.617 for T1). Peyz's kills depend strongly on winning (7.3 per win vs 3.4 per loss), so this small edge slightly favours Gumayusi.

## Verification

| # | Check | Result | Status |
|---|---|---|---|
| 1 | Baseline reproduces 0.68 +/- 0.02 | Replica (a) gives 0.672; `crystal.estimate.estimate()` at the same n and seed gives 0.671. | **PASS** |
| 2 | Inputs printed, sample sizes shown, small samples shrunk | Printed above; subsets 58-92 games; shrink n/(n+30) applied to all group factors | **PASS** |
| 3 | Seed stability, combined variant, two seeds within 0.01 | Seeds 11 and 12: 0.6616 and 0.6594, difference 0.002 | **PASS** |
| 4 | Plausibility: simulated total = mean games x kills/game used | Peyz: 78.6 simulated vs 78.5 expected (ratio 1.0005); Gumayusi: 60.1 vs 60.2 (ratio 0.999) | **PASS** |

No single adjustment moves P by more than 0.05 (largest: recency, -0.033), so no closed-form double check was required.

## Caveats

- Recency is the main judgement call. The between-half-year spread is estimated from only 5 half-years per player. Halving the 2026 weight would roughly halve the -0.03 recency effect (the shift is linear in the weight).
- The opponent adjustment depends on the definition of "strong" (see finding 1).
- Parameter uncertainty is drawn only for the share (recency variant). Kill bootstraps otherwise come from the 2026 pool as the current model does.
- Only 2026 TOP-league games are used, as in the current method. The 2025-26 pooled gap (0.47) is much smaller than the 2026 gap (1.52), so a longer window would lower P materially. The recency variant covers part of this.

## Files

- `crystal/q7_check.py` (new)
- `outputs/q7/q7_report.md` (this file)
- `outputs/q7/q7_inputs.csv`, `outputs/q7/q7_variants.csv`, `outputs/q7/q7_seed_stability.csv`

No existing files were edited.
