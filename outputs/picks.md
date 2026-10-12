# Worlds 2026 Pick'Em — current picks

**Version:** v4.5 · 2026-10-12 · data: Oracle's Elixir 2022 → 2026-10-11 · Worlds patch 26.20 (OE 16.20)
**Model:** 50/50 blend of team and player Bradley-Terry ratings (backtest log-loss 0.613 vs 0.693 coin on 862 international games 2022–26; calibration verified, no correction needed); FURIA–MVK blended 50/50 with bookmaker odds (gap > 15 pts). 20,000 full-tournament simulations with rating uncertainty: each simulation draws plausible team strengths from the models' Laplace covariance (`python -m crystal.estimate`; `--fixed` for point estimates).
**Freeze:** Oct 14, 20:00 · **Lock:** ≈ Oct 15

## Play-In bracket — expected 19.8 / 35 pts

| Slot | Pick | P(correct) | Pts |
|---|---|---|---|
| UB1 FURIA vs MVK | **FURIA** | 0.62 | 5 |
| UB2 C9 vs KC | **KC** | 0.68 | 5 |
| UB Final | **KC** | 0.57 | 5 |
| LB R1 | **C9** | 0.51 | 5 |
| LB Final | **C9** | 0.37 | 5 |
| Grand Final | **KC** | 0.64 | 10 |

P(advance to Swiss): KC 0.64 · C9 0.23 · FURIA 0.08 · MVK 0.05. Best alternative: LB Final = FURIA (−0.6 EV).
Odds check: FURIA Bo5 model 0.50 / market 0.75 → used 0.63. KC Bo5 model 0.71 / market 0.64 (within tolerance).

## Crystal Ball

Scoring: ranked questions (Q1–Q6, Q18) pay 50 / 20 / 10 for finishing 1st / 2nd / 3rd, and ties aren't split. Q7–Q9 pay 100; the rest pay 50. Ranked answers are chosen by **expected points (EV)** = 50·P(1st) + 20·P(2nd) + 10·P(3rd).

| # | Question | Answer | P(1st/2nd/3rd) · EV | Basis |
|---|---|---|---|---|
| 1 | Highest presence champion | **Cassiopeia** ⚖ | .37/.27/.16 · **25.7** (Nocturne 24.2, Vi 13.6) | Draft sim: two-way race, with Vi third. Cassiopeia's late-patch drop (ban 83%→50% in minor leagues) is offset by her very high top-league rate. Her 16.20 nerf is barely in the data, so Nocturne is an equally good pick |
| 2 | Highest win-rate champion* | **Anivia** | .04/.03/.02 · **2.7** (lottery; Leona 1.4) | Leaders have ~5–8 picks (Mundo 5–0 in 2025, Gragas 4–1 in 2024). Anivia: ~7 expected picks, 78% chance to reach 5, played by strong teams |
| 3 | Highest avg deaths champion* | **Rell** | .15/.07/.05 · **9.2** (Olaf 4.6, Camille 4.6) | Clear favourite: engage support with ~7 picks |
| 4 | Highest avg KDA pro | **Zeka** | .14/.10/.07 · **9.9** (Knight 8.4, Chovy 7.8) | Wide open |
| 5 | Highest avg damage pro | **Peyz** | .19/.13/.10 · **13.1** (Caliste 7.4, Doggo 5.2) | Viper led in 2024 and 2025, but his 2026 output is lower |
| 6 | Highest avg kill participation | **CoreJJ** | .07/.05/.05 · **5.2** (Vulcan 4.6, Zhuo 4.5) | Flat field of supports and junglers. No minimum games (confirmed), so players from teams knocked out in the Play-In can place too |
| 7 | Peyz vs Gumayusi kills | **Peyz** | 0.66 | Peyz takes 34% of T1's kills vs Gumayusi's 26% at HLE; team kills and games played are equal. Stress test (`outputs/q7/q7_report.md`): opponent strength and Fearless don't matter; shrinking Gumayusi's share toward his T1-era level costs 0.03 |
| 8 | Faker reaches 700 (needs 84) | **No** | 0.96 | Mean 47 kills, p90 73 |
| 9 | Teemo picked | **No** | ~0.98 | 0 top-level picks in 2026, no buffs |
| 10 | Unique champions picked | **a) 0–99** | 0.45 (b 0.23, c 0.18) | Draft sim 110.5 matches the meta-shift closed form (111.3), so that model's Worlds bias carries over: −9.9 ± 7.3 (Worlds 2022–25). Now in code: `python -m crystal.q10_correct`. Sensitive to event set: Worlds 2023–25 only → a) 0.62; all 11 internationals → c) 0.25 best. Past Worlds: 109, 89, 95, 95 |
| 11 | Games before/after 32:00 | **After** | ~0.65 (was 0.88) | Projected 44% under (2026 internationals 52.7%, and Worlds has had a lower under-share than same-year internationals in all 4 years 2022–25), but this projection missed by 8 pts on average in backtests → 0.71; "same as last Worlds" (48.8%) → 0.53. Methods that ignore the Worlds gap or 2026's slower tempo lean Before. `outputs/q11/q11_report.md`. Use this, not `crystal_sim.md`'s 0.88 |
| 12 | Any pro 15+ kills in a game | **Yes** | 0.84 | |
| 13 | Any pro 450+ CS in a game | **Yes** | ~0.99 | |
| 14 | Finals MVP role | **Bot** | 0.39 (Mid 0.28) | Sim of champion team's final performance, 50/50 with history |
| 15 | Regions in Knockouts | **3** | 0.45 (4: 0.44) — close | |
| 16 | LCS team reaches Knockouts | **No** ⚖ | 0.49 — coin flip (was 0.505 without uncertainty) | LYON 0.27, TL 0.26, C9 0.06 |
| 17 | HLE vs T1 higher | **HLE** ⚖ | 0.46 vs 0.43 (same stage 0.10) — near coin flip | History favours T1 (above HLE in 2024, 2025) |
| 18 | Team that wins shortest game | **Gen.G** | .16/.14/.12 · **11.8** (HLE 10.5, DK 7.2) | Strongest team, most lopsided games. Each team is ranked by its own shortest win (confirmed) |

⚖ = model can't separate the options; a judgement call is fine.

## Tournament outlook (20k sims, with rating uncertainty)
Champion: GEN 0.36 · HLE 0.19 · T1 0.17 · DK 0.11 · BLG 0.08 · AL 0.04 · TES 0.02 · IG 0.02. P(Knockouts): GEN .93, HLE .87, T1 .86, DK .80, BLG .78, AL .67, TES .60, IG .56, G2 .45.

**Champion questions (Q1–Q3, Q10)** come from a draft simulation (`python -m crystal.draft --main`): bans, picks and Fearless locks for every simulated game, drawn from each player's champion pool and the meta. The meta is shifted in each simulated tournament by a model fitted on 11 past international events (`python -m crystal.meta_shift`), which predicts event pick and ban rates from top-league rates and the last three weeks of all leagues. Backtested on those events, its leader probabilities are calibrated (favourites won 4 times against 2.8 expected). Details: `outputs/draft/champion_sim.md`, `outputs/meta/meta_shift_report.md`, `outputs/meta/leader_backtest.md`.

## Changelog
- v4.5 (Oct 12): Q11 stress test (`crystal/q11_check.py`). The 0.88 treated the 44% target as exact; with the target's backtested uncertainty (±8 pts), P(After) ≈ 0.65. Answer unchanged (After). Ties (~2%) count for neither side.
- v4.4 (Oct 12): stress tests of Q7 and Q10, answers unchanged. Q7: Peyz 0.68→0.66 (recency shrink on kill share; opponent strength, Fearless and games played checked, all immaterial; `crystal/q7_check.py`). Q10: the −10 correction was measured on the meta-shift closed form. The draft sim agrees with it on Worlds 2026 (−0.8 gap), so the correction stands (−9.9 ± 7.3). It is now automated in `crystal/q10_correct.py`; a) 0.45.
- v4.3 (Oct 12): Q10 is a bucket question (0–99 / 100–104 / 105–109 / 110–114 / 115–119 / 120+). The draft sim's distribution, shifted by the model's Worlds track record (−10 ± 7), puts a) 0–99 at ~0.45. Answer: a).
- v4.2 (Oct 12): Q6 has no minimum games (user-confirmed), so the sim was rerun and Q6 goes back from Vulcan to CoreJJ (EV 5.2 vs 4.6). Q4 and Q5 also have no minimum (confirmed) and were rerun; their answers are unchanged (Zeka 9.9, Peyz 13.1).
- v4.1 (Oct 12): real scoring (50/20/10 for ranked questions, no tie splitting; 100 for Q7–Q9), with answers chosen by expected points. The draft sim's random meta shift is now corrected so its spread matches the backtested model (it was 1.3–1.5× too wide). Changed: Q6 CoreJJ→Vulcan (EV 5.4 vs 5.1, marginal). Q1–Q5 and Q18 confirmed by EV.
- v4 (Oct 12): champion draft simulation with the fitted meta shift. Changed: Q1 Vi→Cassiopeia (coin flip with Nocturne; Vi third), Q2 Leona→Anivia (P 0.017→0.031), Q10 ~95→~100. Q3 Rell confirmed (0.15).
- v3.1 (Oct 12): scoring confirmed at 35 pts (5 × 5 pre-final + 10 final); Q2 and Q3 minimum of 5 games confirmed by user (answers unchanged: Leona, Rell; both clear the filter); Play-In and Crystal Ball lock at the same time.
- v3 (Oct 12): rating uncertainty in the simulation. Probabilities move slightly toward 50/50 (KC to advance 0.70→0.64; long shots up). Only change: Q16 Yes→No (0.505→0.49, a coin flip either way). Play-In bracket unchanged.
- v2 (Oct 12): blended team+player model, market blend for FURIA–MVK, full simulation. Changed: Q1 Cassiopeia→Vi, Q2 Galio→Leona, Q3 Nautilus→Rell, Q4 Chovy→Zeka, Q5 Viper→Peyz, Q6 Elyoya→CoreJJ, Q7 Gumayusi→Peyz, Q11 Before→After, Q14 Mid→Bot, Q16 No→Yes, Q17 T1→HLE. Play-In unchanged.
- v1 (Oct 11): first complete sheet.
