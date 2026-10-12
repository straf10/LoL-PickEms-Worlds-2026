# Worlds 2026 Pick'Em model

Probability model for the Worlds 2026 Pick'Em: Play-In bracket picks and the 18 Crystal Ball questions.
The answers themselves live in `outputs/picks.md`; this file describes how they are produced.

## Deadlines

- Play-In Pick'Em and Crystal Ball lock about **2026-10-15** (confirm the exact time in the app).
- Internal freeze: **2026-10-14 20:00**.
- Swiss picks due before **2026-10-23**; Knockout picks before **2026-11-03**.
- Scoring rules are in `config/worlds2026.yaml`.

## Data

| Input | Where | How it gets there |
|---|---|---|
| Oracle's Elixir match CSVs, 2022-2026 | `data/raw/oe/` (git-ignored) | Downloaded by hand; the S3 links are dead |
| Game and player tables (`data/pickems.duckdb`, git-ignored) | built | `python -m ingest.oracles` |
| Team, roster and alias tables | `data/worlds2026_teams.csv`, `data/rosters_2026.csv`, `data/aliases.csv` | `python -m ingest.rosters_from_db` |
| Patch changes | `data/champion_changes.csv` (hand-curated from Riot notes) | edited by hand |
| Bookmaker odds | `model/predict.py` (`MARKET_BO5`) | supplied by the user |

## Rerun order after a data refresh

```
python -m ingest.oracles
python -m ingest.rosters_from_db
python -m crystal.meta_shift
python -m crystal.draft --main
python -m crystal.estimate 20000
python -m crystal.q10_correct
python -m crystal.q7_check 40000 11
python -m crystal.q11_check
python -m crystal.base_rates
python -m crystal.meta
python -m crystal.meta_leader_backtest
```

Then update `outputs/picks.md` by hand. Timings on this machine: draft about 6 min, Q7 about 2.5 min,
estimate about 40 s, Q11 about 45 s, leader backtest about 1 min.

Run every step from the project root with `python -m`. Paths are resolved from `common/paths.py`,
so the working directory does not matter.

## Code layout

```
common/          paths.py (ROOT, DB_PATH, OUTPUTS), mathutil.py (logit, sigmoid), report.py (markdown tables)
config/          worlds2026.yaml: format, teams, scoring, lock times
ingest/          oracles.py (CSV -> DuckDB), rosters_from_db.py (teams, rosters, aliases)
model/           ratings.py (team Bradley-Terry), player_ratings.py (player Bradley-Terry),
                 backtest.py (shared harness), calibration.py, predict.py (game probabilities)
sim/             playin.py (Play-In bracket and optimiser), tournament.py (full Monte Carlo)
crystal/         estimate.py (Crystal Ball estimates), draft.py (champion draft sim),
                 meta.py (patch and meta report), meta_shift.py (meta shift model),
                 meta_leader_backtest.py, base_rates.py, q7_check.py, q10_correct.py, q11_check.py
outputs/         reports and tables. picks.md is the answer sheet.
```

## Method in brief

- **Game probabilities:** 50/50 logit blend of a team Bradley-Terry model (region plus team effects) and a
  player Bradley-Terry model. Where a bookmaker price differs from the model by more than 15 points, the
  game probability is the logit-average of model and market.
- **Uncertainty:** each simulation draws team strengths from the models' Laplace covariance, so the reported
  probabilities include rating uncertainty.
- **Tournament:** Play-In (double elimination), Swiss (5 rounds), Knockout, simulated game by game.
- **Champion questions (Q1-Q3, Q10):** draft simulation with per-tournament meta shift, calibrated against
  past international events.
- **Player and stat questions:** bootstrap of each starter's 2026 games, conditioned on the simulated result.

## Known limits

- Oracle's Elixir CSVs are the only game source. The earlier Leaguepedia ingest was removed; it is in
  git history (commit `37e4aec`).
- `picks.md` is maintained by hand. Its numbers come from the runs above, not from a script.
- The draft's K-sensitivity runs (K = 5, 15, 30, no-shift) are git-ignored caches
  (`outputs/draft/run_*_s1000.pkl`). On a fresh clone, rebuild them with
  `python -m crystal.draft --sims 1000 --k K [--no-shift]`; `champion_sim.md` reads them for its sensitivity section.
