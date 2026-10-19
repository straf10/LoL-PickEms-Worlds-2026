# Worlds 2026 Swiss Stage picks (due before 2026-10-23)

**Format (user, 2026-10-19):** pick 8 teams to advance. Three of them are bonus picks, one each for a 3-0, 3-1 and 3-2 record; a bonus pick pays extra only if that team advances with exactly that record. Round 1 is Bo1; decisive matches are Bo3. Same-region matches are allowed from Round 2.

**Draw (Round 1):** GEN–IG, TL–CFO, AL–KC, G2–DK, HLE–TES, LOS–T1, TSW–LYON, BLG–MKOI. KC won the Play-In.

## Picks (model + market blend, v2 — 2026-10-19)

| Slot | Team | P(that record) | P(advance) |
|---|---|---|---|
| 3-0 bonus | GEN | 0.36 | 0.91 |
| 3-1 bonus | HLE | 0.34 | 0.86 |
| 3-2 bonus | DK | 0.27 | 0.72 |
| advance | T1 | | 0.87 |
| advance | BLG | | 0.80 |
| advance | AL | | 0.67 |
| advance | IG | | 0.50 |
| advance | G2 | | 0.49 |

Same picks for bonus sizes 0.5x–4x a correct qualifier. Expected correct qualifiers ≈ 5.8 of 8.

**Change from the model-only picks:** TES out, G2 in; 3-2 bonus TES → DK. Both books rate TES much lower than the model (0.36 vs 0.57) and G2 higher (0.56 vs 0.43).

Close calls: 8th slot G2 0.487 vs TES 0.463 (next is KC 0.35); 3-2 bonus DK 0.267 vs AL 0.255.

## Method

`python -m sim.swiss_market [n]`: each book's "reach top 8" price is de-margined (power method, sums to 8), the two books are logit-averaged, then logit-averaged 50/50 with the model and re-scaled to sum to 8. One logit strength offset per team is fitted so the simulated P(advance) matches that target (within 0.01), and the stage is re-simulated 100k times for the record split. Book odds are in the script.

## Full table

| Team | Book 1 | Book 2 | Model | Blended P(advance) | 3-0 | 3-1 | 3-2 |
|---|---|---|---|---|---|---|---|
| GEN | 0.88 | 0.91 | 0.92 | 0.91 | 0.36 | 0.35 | 0.20 |
| T1 | 0.85 | 0.84 | 0.88 | 0.87 | 0.34 | 0.33 | 0.21 |
| HLE | 0.85 | 0.83 | 0.86 | 0.86 | 0.28 | 0.34 | 0.24 |
| BLG | 0.80 | 0.83 | 0.80 | 0.80 | 0.25 | 0.31 | 0.24 |
| DK | 0.55 | 0.66 | 0.80 | 0.72 | 0.17 | 0.28 | 0.27 |
| AL | 0.64 | 0.68 | 0.67 | 0.67 | 0.16 | 0.26 | 0.26 |
| IG | 0.42 | 0.51 | 0.53 | 0.50 | 0.07 | 0.19 | 0.25 |
| G2 | 0.52 | 0.59 | 0.43 | 0.49 | 0.07 | 0.18 | 0.24 |
| TES | 0.39 | 0.34 | 0.57 | 0.46 | 0.06 | 0.17 | 0.23 |
| KC | 0.35 | 0.23 | 0.40 | 0.35 | 0.04 | 0.12 | 0.18 |
| LYON | 0.38 | 0.40 | 0.26 | 0.31 | 0.05 | 0.11 | 0.15 |
| TL | 0.39 | 0.33 | 0.26 | 0.31 | 0.05 | 0.11 | 0.15 |
| MKOI | 0.33 | 0.28 | 0.26 | 0.28 | 0.03 | 0.10 | 0.15 |
| TSW | 0.30 | 0.29 | 0.18 | 0.24 | 0.03 | 0.08 | 0.12 |
| CFO | 0.17 | 0.19 | 0.10 | 0.14 | 0.02 | 0.05 | 0.07 |
| LOS | 0.17 | 0.08 | 0.07 | 0.09 | 0.01 | 0.03 | 0.05 |

Model-only run (200k sims, no market): `python -m sim.swiss_draw`, gave GEN 3-0, HLE 3-1, TES 3-2 + T1, DK, BLG, AL, IG.
