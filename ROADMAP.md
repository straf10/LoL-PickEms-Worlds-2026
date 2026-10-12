# Worlds 2026 Pick'Em Model — Roadmap

**Created:** 2026-10-11 · **Hard deadline:** Play-In Pick'Em **and** Crystal Ball both lock ≈ **Oct 15** (3d22h from Oct 11; confirm the exact time in the app) · **Internal freeze:** **Oct 14, 20:00**

## 0. Context

| Stage | Dates | Format | Pick'Em relevance |
|---|---|---|---|
| Play-In | Oct 15–18 (LA) | 4 teams, double elimination, all Bo5, 1 team advances | **MVP — locks Oct 15** |
| Swiss | Oct 23–26, Oct 28–31 | 16 teams, 5 rounds, Bo1 (Bo3 when advancing/eliminating), 3W advance / 3L out, no rematches | Separate Pick'Em later. Needed **now** as a simulation for the Crystal Ball |
| Knockout | Nov 3–14 | 8 teams, single elim, Bo5 | Same as Swiss |
| Crystal Ball | Whole event | 18 questions | **MVP — locks Oct 15** |

**Play-In bracket** (all picks are made up front, before any match is played):

```
UB1  FURIA (CBLOL) vs MVK (LCP, Vietnam) ─┐
                                          ├─ UBF ──────────────┐
UB2  Cloud9 (LCS)  vs Karmine Corp (LEC) ─┘                    ├─ GF → Swiss
LB1  L(UB1) vs L(UB2) ── LBF: L(UBF) vs W(LB1) ────────────────┘
```

**Scoring:** 5 pts for each correct pre-final winner, 10 for the final, 30 in total. ⚠ This needs confirming: there are 5 pre-final matches, so 5×5+10 = 35, not 30. The optimizer reads the scoring from `config/worlds2026.yaml`.

**What the double deadline means for scope:**
- Most Crystal Ball questions (Faker 84 kills, Peyz vs Gumayusi, regions in Knockouts, LCS in Knockouts, HLE vs T1, Finals MVP role, any stat totals) depend on **how many games each team plays across the whole event**.
- So the MVP must include a **rough full-tournament simulation** (Play-In → Swiss → Knockout) for all 19 teams, not just the 4 Play-In teams.
- That simulation can be crude. It only needs to give expected games played and placement distributions.

**Rules that shape the model:**
- **Fearless Draft** in every Bo3/Bo5, which means every Play-In game. Champion-pool depth matters more than one comfort pick, and Fearless increases the number of unique champions picked (question 10).
- All 4 Play-In teams come from **different regions**. The main modelling problem is **cross-region strength**.

---

## 1. General guidelines (apply to every task)

1. **Deadline beats completeness.** Every task has a time box. When it runs out, take the exit clause and move on. **Freeze on Oct 14, 20:00**, then submit both the Play-In picks and the Crystal Ball.
2. **Always have an answer.** From Checkpoint 1 onwards, `outputs/picks.md` must always contain a complete Play-In bracket **and** an answer for all 18 Crystal Ball questions, even if some are crude. Each later task only improves answers.
3. **Cache everything raw.** Every API response or scrape goes to `data/raw/<source>/<date>/` once. Never re-scrape what is already cached. Respect rate limits: at most 1 request/sec, with a descriptive User-Agent.
4. **One canonical name per entity.** All team, player and champion names go through `data/aliases.csv`. Ratings are tracked per player so roster changes don't reset strength.
5. **No leakage.** A backtest for event X may only use games played **before** X started.
6. **Calibration over accuracy.** Judge models on log-loss and Brier score against a baseline.
7. **Reproducible runs.** Fix seeds, keep config in `config/worlds2026.yaml`, and stamp outputs with the data snapshot date and the patch version.
8. **Human sanity check.** Every final answer gets a one-line rationale. Compare Play-In odds with betting markets. A gap of more than 15 percentage points needs an explanation.
9. **Keep it simple until it beats the baseline.**
10. **Spend effort where the points are.**
    - Play-In: 30 pts across 6 matches.
    - Crystal Ball: rank questions by how much the model can actually add over a fan's gut call, and put effort there first.
    - Questions that are mostly noise (e.g. 18 "team that wins the shortest game") get a base-rate answer and nothing more.

---

## 2. Project layout

```
LOL_PICKEMS/
  ROADMAP.md
  config/worlds2026.yaml      # format, teams, scoring, lock times, crystal-ball questions
  data/raw/                   # cached source responses (never edited)
  data/aliases.csv
  data/pickems.duckdb         # clean tables
  ingest/                     # leaguepedia.py, patches.py
  model/                      # ratings.py, series.py, meta.py, player_stats.py
  sim/                        # playin.py, swiss.py, knockout.py, tournament.py
  crystal/                    # one estimator per question type
  picks/                      # optimizer.py, report.py
  notebooks/                  # backtests
  outputs/                    # picks.md, probability tables
```
Stack: Python 3.11, pandas, numpy, scikit-learn (already installed). Add `mwclient` and `duckdb`.

---

## 3. MVP plan (Oct 11 → Oct 14 freeze)

**MVP definition of done:**
1. Play-In: the **expected-points-maximising bracket** (one pick for each of the 6 matches), with probabilities.
2. Crystal Ball: an answer for each of the 18 questions, with a probability or confidence and a one-line rationale.
3. Both are produced by `python -m picks.report` into `outputs/picks.md`.

### Day 1 — Oct 11/12: data foundation

#### T1.1 Config (time box: 30m) — ✅ mostly done
- **Done:** Play-In teams, bracket, scoring and lock dates are in `config/worlds2026.yaml`.
- **Remaining:**
  - Resolve the 30-vs-35 scoring question.
  - Fill in the 15 direct qualifiers and their Swiss seeding/pools (this happens in T1.3).

#### T1.2 Ingest pro game data from Leaguepedia (time box: 4h)
- **Goal:** game-level and player-game-level tables for:
  - **2026:** LCK, LPL, LEC, LCS, LCP, CBLOL, First Stand, MSI, EWC.
  - **2024–2025:** Worlds, MSI, First Stand, EWC.
- **Fields:**
  - Games: date, event, patch, teams, side, winner, duration, picks and bans in order.
  - Players: champion, role, K/D/A, CS, damage, team kills (for kill participation).
- **Done when:** the `games` and `player_games` tables load and the row counts per league look sensible.
- **Exit clause:** if the Cargo API is blocked or rate-limited for more than 1h, switch to Oracle's Elixir CSVs, then to gol.gg as a last resort.

#### T1.3 Rosters and aliases (time box: 1.5h)
- **Goal:**
  - The 19 Worlds rosters, with each player's past teams.
  - `aliases.csv`.
  - Swiss seeding and draw-pool rules taken from the official announcement.
- **Done when:** fewer than 1% of 2026 rows are unmapped and every Worlds player has 2026 games.
- **Exit clause:** if the Swiss seeding rules can't be found, use a random draw that avoids same-region opening matches and record that assumption.

#### T1.4 Base rates from Worlds 2024–2025 (time box: 1.5h)
- **Goal:** historical answers to the Crystal Ball questions at past Worlds:
  - Unique champions picked (especially 2025, the first Fearless Worlds).
  - Share of games shorter than 32 minutes.
  - Count of 15+ kill games and 450+ CS games.
  - Finals MVP roles.
  - Top presence, win-rate and death-rate champions.
  - KDA, damage and kill-participation leaders (including their roles and how far their teams went).
  - Number of regions in the Knockouts.
- **Done when:** a base-rate table exists, giving a first answer to every Crystal Ball question.

**🏁 Checkpoint 1 (end of Day 1):**
- Data loaded.
- `outputs/picks.md` v1: Play-In picked by region seeding, Crystal Ball answered from base rates plus fan priors.
- **From here on, a complete submission always exists.**

### Day 2 — Oct 12/13: strength model and simulation

#### T2.1 Team ratings (time box: 2.5h)
- Elo or Glicko-2 that follows players across roster changes.
- Recent games weigh more (half-life of about 8–10 weeks).
- International games get a higher K-factor.

#### T2.2 Region strength offsets (time box: 2.5h) — *most important for the Play-In*
- **Goal:** offsets for LCK, LPL, LEC, LCS, LCP and CBLOL, estimated from cross-region games (First Stand, MSI and EWC 2026, Worlds 2025), shrunk toward a historical prior.
- **Particular care:** LCP is a merged league, so check whether Vietnamese teams' international results differ from those of the rest of LCP. If they do, consider giving them their own offset.
- **Exit clause:** if a region has fewer than about 10 cross-region games, use the prior and mark it **low confidence**.

#### T2.3 Series probabilities and backtest (time box: 2h)
- Bo1, Bo3 and Bo5 formulas, e.g. `P(Bo5) = p³·(1 + 3(1−p) + 6(1−p)²)`.
- Backtest on Worlds 2024/25 and MSI 2026, comparing log-loss and Brier score against two baselines: 50/50 and "pick the higher seed".
- **Exit clause:** if the model doesn't beat the seed baseline, remove features one at a time. If it still doesn't, use plain Elo with the region prior and mark the results low confidence.

#### T2.4 Full tournament simulator (time box: 3h)
- **Play-In:** the exact double-elimination bracket.
- **Swiss:** pair by record, no rematches, Bo1 or Bo3 depending on the stakes.
- **Knockout:** a random Bo5 bracket among the 8 survivors.
- **≥50k runs, recording for each team:** probability of each stage outcome and number of **games** played (not just series). For Bo3/Bo5 series, simulate each game so game counts are correct.
- **Done when:** in every run, exactly 1 Play-In qualifier, 8 Knockout teams and 1 champion; and the probabilities for the 4 Play-In teams match closed-form calculations.
- **Exit clause:** if the Swiss no-rematch pairing gets stuck, re-draw the round. Expected games played is what matters, not exact pairings.

**🏁 Checkpoint 2 (end of Day 2):**
- P(win) for every Play-In matchup, plus the backtest numbers.
- Tournament outcome table for all 19 teams.
- `picks.md` v2: Play-In bracket from the model, and questions 15, 16 and 17 answered from the simulation.

### Day 3 — Oct 13/14: patch, players, Crystal Ball, optimizer

#### T3.1 Patch and meta (time box: 2.5h)
1. Identify the Worlds patch and the 1–2 patches before it. Parse the champion and item changes into `champion_changes` (buff / nerf / adjust, magnitude 1–3).
2. Champion **meta score:** recent pro presence, recent patches weighted more, plus the patch direction. This feeds questions 1–3, 9 and 10.
3. Team **meta fit** and **pool depth** (distinct champions with at least 3 games and a win rate of 50% or higher): a capped adjustment of at most ±3 percentage points on game win probability.
- **Exit clause:** if patch notes can't be parsed cleanly in 1h, encode the changes by hand for the top ~25 meta champions.

#### T3.2 Player and champion stat estimators (time box: 3h)
- **Player rates (questions 4–8):**
  - 2026 KDA, damage per game, kill participation and kills per game.
  - Shrink toward role averages, weighted by games played.
  - Adjust for opponent strength: Worlds opponents are tougher than domestic ones.
- **Totals (questions 7–8):** per-game rate × the simulated game-count distribution from T2.4.
  - **Q8:** P(Faker reaches 84+ kills) = P(sum over Faker's simulated games of his kills ≥ 84).
- **Leaders (questions 4–6):** simulate per-game stats for each player in each run, and apply any minimum-games rule. Note: players knocked out early can lead "average" stats on small samples, so check the `*` and minimum-games rules.
- **Champion questions (2–3):** meta score × class/role death rates, with a minimum-games filter.
- **Tail events (questions 11–13, 18):**
  - Per-game probability of a 15+ kill game, a 450+ CS game, or a game under 32 minutes, from 2025–26 international games.
  - Scaled by the expected number of games in the event.
  - Game length adjusted for patch tempo if the data allows.
- **Question 14 (Finals MVP role):** historical role distribution, adjusted for the likely finalists' star players.
- **Exit clause:** any question not done within the time box keeps its T1.4 base-rate answer.

#### T3.3 Optimizer and report (time box: 1.5h)
- **Play-In:** enumerate all 2⁶ = 64 ways to fill the bracket. Score each against the simulated outcomes and pick the one with the highest **expected points**. Because the final is worth double, the result may not be the same as "pick the favourite in every match".
- **Crystal Ball:** for each question, the answer with the highest probability.
- **Report:** `outputs/picks.md` with picks, probabilities, confidence and a one-line rationale each.

**🏁 Checkpoint 3 / FREEZE (Oct 14, 20:00):**
1. Sanity review (guideline 8): compare with betting odds and check the latest roster news.
2. Submit the Play-In bracket and the Crystal Ball.
3. No model changes after this.

### Day 4 — Oct 15 onward
- Log the Play-In results.
- Post-mortem on calibration.
- Start Phase 2.

---

## 4. After the MVP

- **Phase 2 — Swiss Pick'Em (before Oct 23):** reuse T2.4 with the real Play-In winner and the actual Swiss draw. Update ratings with Play-In results. Add the Swiss scoring to the config and run the optimizer.
- **Phase 3 — Knockout Pick'Em (before Nov 3):** a Bo5 bracket on updated ratings, re-run before each round if picks are made per round.
- **Ongoing:** track Crystal Ball answers against the live tournament. The answers can't be changed, but tracking helps calibrate the 2027 model.

---

## 5. Open questions / risks

| Risk | Mitigation |
|---|---|
| Scoring ambiguity (30 vs 35 pts) | Optimizer is config-driven; confirm with the user |
| Exact lock time | Confirm in the app; internal freeze is 1 day early |
| Swiss seeding rules unknown | T1.3 looks them up; fallback is a random draw avoiding same-region openers |
| Crystal Ball minimum-games rule (`*`) | Look up the official definition; assume a minimum of 5 games if not found |
| Small cross-region sample (LCP-Vietnam, CBLOL) | Shrink toward a prior; low-confidence flag |
| Late roster changes or substitutes | Player-based ratings; manual roster check on Oct 14 |
| Data source blocked | Leaguepedia → Oracle's Elixir → gol.gg |
| Patch hotfix before Worlds | Freeze patch analysis on Oct 14 and record the version used |
