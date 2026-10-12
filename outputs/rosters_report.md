# Worlds 2026 rosters, aliases and Swiss rules (T1.3b)

Snapshot: 2026-10-11. Source: `data/pickems.duckdb` (Oracle's Elixir, built by `ingest/oracles.py`), read-only. No network calls. Rebuild the tables with `python -m ingest.rosters_from_db`. Status: **complete for the 19 teams, the 95 starters and the three Crystal Ball players.** Open items are in section 5.

## 1. Corrections to the earlier partial report

- **CBLOL1 is LØS, not LOUD.** LØS won the CBLOL 2026 Split 2 final 3-2 over FURIA on 2026-10-10, the last CBLOL series in the data. LOUD is a separate OE team_id: it lost 2-3 to LØS on 09-27 and 0-3 to FURIA on 10-03. The old "LOUD (LØS)" row was wrong. FURIA is CBLOL2.
- **OE names differ from the old report:** `Dplus Kia`, `Team Liquid` (not "Team Liquid Alienware"), `Cloud9` (not "Cloud 9 KIA"), `Invictus Gaming` (not "Shanghai Invictus Gaming"), `LØS`, `FURIA`. The old names are kept as aliases.
- **One OE team_id per team** for 2024–2026 (the script warns if a name maps to two IDs; none did).
- **Seeds:** the LCK, LPL1/2, LEC, LCS and CBLOL seeds are verified against 2026 finals in the data. LCP is inferred from series order (no playoff flag in OE). LPL3/LPL4 (TES/IG) stay unverified (section 5).
- **Starting five found for all 19 teams.** The old report had no starters for most rosters.
- **Crystal Ball players (brief item 6), confirmed:** Faker is on T1, Peyz is on T1 (JD Gaming until 2025-10-08, T1 since 2025-12-07), Gumayusi is on Hanwha Life Esports (T1 until 2025-11-09, HLE since 2025-12-06).
- **Play-In four confirmed in data:** KC (LEC3), C9 (LCS3), MVK (LCP3) and FUR (CBLOL2), matching `config/worlds2026.yaml`.

## 2. Seed evidence (2026 OE data)

- **LCK:** GEN beat HLE 3-1 in the final (09-13). HLE beat T1 3-1 (09-12). T1 beat DK 3-1 (09-06). This gives GEN 1, HLE 2, T1 3, DK 4.
- **LPL:** AL beat BLG 3-1 in the final (09-13). AL also beat IG 3-2 (09-12). BLG beat AL 3-0 (09-07). This gives AL 1 and BLG 2. IG and TES are covered in section 5.
- **WLDQ (LPL last chance, 12 games, 09-17 to 09-19):** TES beat IG 3-1 (09-17). JDG beat WE 3-1 (09-18). IG beat JDG 3-1 (09-19). The brief's IG qualification is confirmed.
- **LEC:** G2 beat KOI 3-0 in the final (09-20). KC lost 0-3 to KOI (09-19). This gives G2 1, KOI 2, KC 3.
- **LCS:** TL beat LYON 3-1 in the final (10-04). C9 lost 1-3 to LYON (10-03). This gives TL 1, LYON 2, C9 3.
- **LCP:** TSW beat CFO 3-0 (08-30), the last LCP series. CFO beat MVK 3-1 (08-29). OE does not flag LCP playoffs, so TSW 1, CFO 2 and MVK 3 are inferred from the series order (medium confidence).
- **CBLOL:** LØS beat FURIA 3-2 in the final (10-10). This gives LØS 1 and FURIA 2.
- **MSI 2026 (context only, not a seed rule):** HLE beat BLG 3-2 in the last MSI series (07-12).

## 3. Starting five and roster flags

Starter = the player with the most games in the role across the team's last 10 domestic + WLDQ games of 2026. `games_2026` = all of that player's 2026 games in OE (any team, all leagues, including academy games). `last_game_date` = the player's latest game in OE, any team.

- **Role changes inside the last 10 games: none.** Every role had one player in every team's last 10 games, so `ROLE_CHANGED_LAST10` is empty for all 95 starters.
- **Mid-season changes** (flag `PARTIAL_2026_TENURE`: the starter played under 80% of the team's 2026 domestic + WLDQ games; the first team game is in the flag). These are the swaps a Worlds roster check should look at:
  - AL Top: Breathe, first game 07-23 (replaced Flandre, who moved to BLG).
  - IG Top: TheShy, first game 07-25 (Breathe moved to AL).
  - TES Top, Jungle, Bot: ZUIAN, Tian, JackeyLove, first game 04-04. TES Support: Zhuo, first game 07-22.
  - C9 Mid and Bot: Loki and Tactical, first game 07-26.
  - CFO Mid and Support: Pout and Kino, first game 04-18.
  - MVK Mid, Bot and Support: Chika, Harky and SiuLoong, first game 04-04.
  - LOS Jungle: Curse, first game 05-03.
  - BLG Top: Bin (first game 01-15, with 30 team games missed); IG Mid Rookie, IG Bot JiaQi, IG Support Meiko, and similar cases are all listed in the generated block.
- **Brief's TES visa headline (ZUIAN out, 369 in):** ZUIAN played TES's WLDQ games on 2026-09-17, the last TES game in OE. 369's last TES game is 2026-03-02. The headline is not confirmed by the data.
- **Crystal Ball players:** Faker (T1, 173 games in 2026, last 09-12); Peyz (T1, 173, last 09-12); Gumayusi (HLE, 160, last 09-13).

## 4. Swiss draw rules (kept from the earlier research; secondary sources)

- **Round 1:** Tier 1 (GEN, AL, TL, G2) vs Tier 4 (CFO, IG, DK, Play-In winner). Tier 2 (LOS, TSW, HLE, BLG) vs Tier 3 (LYON, MKOI, T1, TES). The primer says the R1 draw is random ("τυχαία κλήρωση"), so the pairing is random within the tier-to-tier structure.
- **Round 1 same-region rule:** teams from the same region cannot face each other.
- **Rounds 2–5:** teams are drawn against opponents with the same record. No repeat matchups at any point in the Swiss Stage. Same-region matches are allowed from Round 2.
- **Format:** Bo1 or Bo3 by round. Sources differ on the exact split. The lolesports primer lists 3 wins to advance and 3 losses to be eliminated. The GosuGamers page says "a mix of best-of-one and best-of-three". The secondary guide (rft.gg) says R1 and R2 are Bo1, and in R3 the 2-0 and 0-2 matches are Bo3. Treat the round split as **unconfirmed**.
- **Draw timing:** each round is drawn after the previous one ends.
- **Consistency check:** 15 direct qualifiers (the 19 teams minus the 4 Play-In teams) + 1 Play-In winner = 16 Swiss teams. The tiers above use the seeds verified in section 2. Tier 1 = the four regional #1s; Tier 2 = TSW, LOS, HLE, BLG; Tier 3 = LYON, MKOI, T1, TES; Tier 4 = CFO, IG, DK plus the Play-In winner.

Sources: https://lolesports.com/news/worlds-2026-primer ; https://www.gosugamers.net/lol/news/79302-league-of-legends-worlds-2026-schedule-teams-format-venues-and-where-to-watch ; https://rft.gg/news/league-of-legends-worlds-2026-the-complete-guide

## 5. Open items (before the Oct 14 freeze)

1. **TES vs IG seed (LPL3 vs LPL4):** both show LPL-WLDQ results (TES beat IG 3-1 on 09-17; IG beat JDG 3-1 on 09-19), but the OE data has no bracket. The LPL3/LPL4 order is from earlier research and is unverified. Check lolesports.
2. **LCP playoffs:** OE does not flag them. The TSW/CFO order is inferred from series order. Check the LCP final.
3. **Swiss round split (Bo1/Bo3)** and **Tier assignments** still come from secondary sources. The OE data has no draw information.
4. **Duplicate player name:** "Kratos" is used by two OE player_ids on MVK. The starter (73 games, Top) owns the alias. The bench ID (1 game, 2026-04-11) has its own row in `rosters_2026.csv`.
5. **2027-tagged games:** OE tags some games from 2026-09-28 onward as 2027 (CBLOL and LCS, including LØS and LCS teams). These are excluded from the 2026 windows and from `games_2026`. Only the 2026-tagged games are used.
6. **Recent swaps:** several mid-season changes (section 3) happened after the spring splits. The rosters are the best data-based view, not confirmed by the teams.

<!-- BEGIN GENERATED: rosters_from_db.py -->

### Worlds 2026 teams (generated from the OE data)

| Code | OE name | OE team_id (last 8) | Seed | Entry | Evidence in 2026 data |
|---|---|---|---|---|---|
| GEN | Gen.G | `52ab014f` | LCK1 | swiss | LCK 2026 Split 3 champion: won final 3-1 vs HLE (2026-09-13) |
| HLE | Hanwha Life Esports | `ef068934` | LCK2 | swiss | LCK 2026 Split 3 runner-up: lost final 1-3 to GEN (2026-09-13) |
| T1 | T1 | `da0227e8` | LCK3 | swiss | LCK 2026 Split 3: lost 1-3 to HLE (2026-09-12), last T1 series |
| DK | Dplus Kia | `ba716806` | LCK4 | swiss | LCK 2026 Split 3: lost 1-3 to T1 (2026-09-06), last DK series |
| AL | Anyone's Legend | `cebae73a` | LPL1 | swiss | LPL 2026 Split 3 champion: won final 3-1 vs BLG (2026-09-13) |
| BLG | Bilibili Gaming | `d99c886d` | LPL2 | swiss | LPL 2026 Split 3 runner-up: lost final 1-3 to AL (2026-09-13) |
| TES | Top Esports | `640f5b36` | LPL3 | swiss | WLDQ 2026-09-17: beat IG 3-1; no later TES game in OE data |
| IG | Invictus Gaming | `6a54e151` | LPL4 | swiss | WLDQ 2026-09-19: beat JDG 3-1 (confirmed in OE data) |
| G2 | G2 Esports | `a630da6e` | LEC1 | swiss | LEC Summer 2026 champion: won final 3-0 vs KOI (2026-09-20) |
| MKOI | Movistar KOI | `d3129dfa` | LEC2 | swiss | LEC Summer 2026 runner-up: lost final 0-3 to G2 (2026-09-20) |
| KC | Karmine Corp | `8326bc7c` | LEC3 | playin | LEC Summer 2026: lost 0-3 to KOI (2026-09-19), last KC series |
| TL | Team Liquid | `debb5250` | LCS1 | swiss | LCS Summer 2026 champion: won final 3-1 vs LYON (2026-10-04) |
| LYON | LYON | `17de85b3` | LCS2 | swiss | LCS Summer 2026 runner-up: lost final 1-3 to TL (2026-10-04) |
| C9 | Cloud9 | `d86adea0` | LCS3 | playin | LCS Summer 2026: lost 1-3 to LYON (2026-10-03), last C9 series |
| TSW | Team Secret Whales | `7b923fd5` | LCP1 | swiss | LCP 2026 Split 3: won last series 3-0 vs CFO (2026-08-30) |
| CFO | CTBC Flying Oyster | `3e067f62` | LCP2 | swiss | LCP 2026 Split 3: lost 0-3 to TSW (2026-08-30), inferred runner-up |
| MVK | MVK Esports | `8faa4822` | LCP3 | playin | LCP 2026 Split 3: lost 1-3 to CFO (2026-08-29), last MVK series |
| LOS | LØS | `69a5fca5` | CBLOL1 | swiss | CBLOL 2026 Split 2 champion: won final 3-2 vs FURIA (2026-10-10) |
| FUR | FURIA | `e894d806` | CBLOL2 | playin | CBLOL 2026 Split 2 runner-up: lost 2-3 to LØS (2026-10-10) |

### Starting five (most frequent player per role in the last 10 domestic + WLDQ games of 2026)

#### GEN - Gen.G (LCK1)

| Role | Player | player_id (last 8) | 2026 games | Last game | Flags |
|---|---|---|---|---|---|
| Top | Kiin | `edf41e28` | 132 | 2026-09-13 | - |
| Jungle | Canyon | `6e42e3de` | 130 | 2026-09-13 | - |
| Mid | Chovy | `4ae7c800` | 128 | 2026-09-13 | - |
| Bot | Ruler | `b5fde49b` | 128 | 2026-09-13 | - |
| Support | Duro | `8e463d1b` | 132 | 2026-09-13 | - |

Other 2026 players for this team_id: Ripple (Top, 79g), Courage (Jungle, 79g), Juny (Jungle, 2g), Loid (Mid, 103g), Kemish (Mid, 77g), MUDAI (Bot, 79g), Harusary (Bot, 71g), Lumos (Support, 68g)

#### HLE - Hanwha Life Esports (LCK2)

| Role | Player | player_id (last 8) | 2026 games | Last game | Flags |
|---|---|---|---|---|---|
| Top | Zeus | `265a7f76` | 160 | 2026-09-13 | - |
| Jungle | Kanavi | `133f9968` | 160 | 2026-09-13 | - |
| Mid | Zeka | `a025cec1` | 160 | 2026-09-13 | - |
| Bot | Gumayusi | `81c6f321` | 160 | 2026-09-13 | - |
| Support | Delight | `95fdef4c` | 154 | 2026-09-13 | - |

Other 2026 players for this team_id: Panther (Top, 98g), Jackal (Jungle, 98g), Cracker (Mid, 98g), Pyeonsik (Bot, 98g), Bluffing (Support, 99g)

#### T1 - T1 (LCK3)

| Role | Player | player_id (last 8) | 2026 games | Last game | Flags |
|---|---|---|---|---|---|
| Top | Doran | `073a3dd1` | 173 | 2026-09-12 | - |
| Jungle | Oner | `46adc9b0` | 170 | 2026-09-12 | - |
| Mid | Faker | `3cf795cc` | 173 | 2026-09-12 | - |
| Bot | Peyz | `9ce71bb7` | 173 | 2026-09-12 | - |
| Support | Keria | `95dabd37` | 173 | 2026-09-12 | - |

Other 2026 players for this team_id: Haetae (Top, 156g), Painter (Jungle, 164g), Guti (Mid, 163g), Cypher (Bot, 110g), Cloud (Support, 163g)

#### DK - Dplus Kia (LCK4)

| Role | Player | player_id (last 8) | 2026 games | Last game | Flags |
|---|---|---|---|---|---|
| Top | Siwoo | `2aa4d5e6` | 163 | 2026-09-06 | - |
| Jungle | Lucid | `2632e358` | 161 | 2026-09-06 | - |
| Mid | ShowMaker | `b183a451` | 163 | 2026-09-06 | - |
| Bot | Smash | `053e1f6c` | 163 | 2026-09-06 | - |
| Support | Career | `4fb85a0c` | 163 | 2026-09-06 | - |

Other 2026 players for this team_id: Jaehyuk (Top, 123g), Sharvel (Jungle, 119g), Solid (Jungle, 114g), Garden (Mid, 123g), Wayne (Bot, 123g), Loopy (Support, 123g)

#### AL - Anyone's Legend (LPL1)

| Role | Player | player_id (last 8) | 2026 games | Last game | Flags |
|---|---|---|---|---|---|
| Top | Breathe | `c8eef97c` | 90 | 2026-09-13 | PARTIAL_2026_TENURE: 52/138 team games, first 2026-07-23 |
| Jungle | Tarzan | `4f5586bf` | 142 | 2026-09-13 | - |
| Mid | Shanks | `d6f89f04` | 142 | 2026-09-13 | - |
| Bot | Hope | `a3b4a28e` | 142 | 2026-09-13 | - |
| Support | Kael | `0e43e4bf` | 142 | 2026-09-13 | - |

Other 2026 players for this team_id: Flandre (Top, 100g)

#### BLG - Bilibili Gaming (LPL2)

| Role | Player | player_id (last 8) | 2026 games | Last game | Flags |
|---|---|---|---|---|---|
| Top | Bin | `21dc3a42` | 147 | 2026-09-13 | PARTIAL_2026_TENURE: 110/140 team games, first 2026-01-15 |
| Jungle | Xun | `5da4e4b2` | 177 | 2026-09-13 | - |
| Mid | Knight | `464b990b` | 177 | 2026-09-13 | - |
| Bot | Viper | `0315054f` | 177 | 2026-09-13 | - |
| Support | ON | `57492e17` | 177 | 2026-09-13 | - |

Other 2026 players for this team_id: Flandre (Top, 100g), Wenbo (Top, 20g)

#### TES - Top Esports (LPL3)

| Role | Player | player_id (last 8) | 2026 games | Last game | Flags |
|---|---|---|---|---|---|
| Top | ZUIAN | `3cd2490e` | 97 | 2026-09-17 | PARTIAL_2026_TENURE: 88/131 team games, first 2026-04-04 |
| Jungle | Tian | `4f9de9ab` | 97 | 2026-09-17 | PARTIAL_2026_TENURE: 88/131 team games, first 2026-04-04 |
| Mid | Creme | `64a312a2` | 140 | 2026-09-17 | - |
| Bot | JackeyLove | `051c4855` | 97 | 2026-09-17 | PARTIAL_2026_TENURE: 88/131 team games, first 2026-04-04 |
| Support | Zhuo | `4a8e51ac` | 112 | 2026-09-17 | PARTIAL_2026_TENURE: 45/131 team games, first 2026-07-22 |

Other 2026 players for this team_id: 369 (Top, 43g), naiyou (Jungle, 43g), JiaQi (Bot, 114g), fengyue (Support, 121g)

#### IG - Invictus Gaming (LPL4)

| Role | Player | player_id (last 8) | 2026 games | Last game | Flags |
|---|---|---|---|---|---|
| Top | TheShy | `94f9c994` | 43 | 2026-09-19 | PARTIAL_2026_TENURE: 43/124 team games, first 2026-07-25 |
| Jungle | Wei | `6e9867c0` | 124 | 2026-09-19 | - |
| Mid | Rookie | `f7d0aaa9` | 86 | 2026-09-19 | PARTIAL_2026_TENURE: 86/124 team games, first 2026-01-14 |
| Bot | JiaQi | `e6a8f884` | 114 | 2026-09-19 | PARTIAL_2026_TENURE: 71/124 team games, first 2026-04-04 |
| Support | Meiko | `3dd505cd` | 81 | 2026-09-19 | PARTIAL_2026_TENURE: 81/124 team games, first 2026-04-04 |

Other 2026 players for this team_id: Breathe (Top, 90g), Soboro (Top, 65g), Nia (Mid, 32g), Renard (Mid, 20g), Assum (Bot, 77g), Photic (Bot, 76g), Jwei (Support, 73g)

#### G2 - G2 Esports (LEC1)

| Role | Player | player_id (last 8) | 2026 games | Last game | Flags |
|---|---|---|---|---|---|
| Top | BrokenBlade | `8f676878` | 131 | 2026-09-20 | - |
| Jungle | SkewMond | `3aed1e09` | 131 | 2026-09-20 | - |
| Mid | Caps | `f9e539de` | 131 | 2026-09-20 | - |
| Bot | Hans Sama | `0e9aa8c8` | 131 | 2026-09-20 | - |
| Support | Labrov | `59eb4ddf` | 131 | 2026-09-20 | - |

#### MKOI - Movistar KOI (LEC2)

| Role | Player | player_id (last 8) | 2026 games | Last game | Flags |
|---|---|---|---|---|---|
| Top | Myrwn | `a67802ff` | 111 | 2026-09-20 | - |
| Jungle | Elyoya | `9a526951` | 111 | 2026-09-20 | - |
| Mid | Jojopyun | `d55b5479` | 111 | 2026-09-20 | - |
| Bot | Supa | `65df8133` | 111 | 2026-09-20 | - |
| Support | Alvaro | `e4769ae4` | 111 | 2026-09-20 | - |

#### KC - Karmine Corp (LEC3)

| Role | Player | player_id (last 8) | 2026 games | Last game | Flags |
|---|---|---|---|---|---|
| Top | Canna | `5503e75e` | 138 | 2026-09-19 | - |
| Jungle | Yike | `a8618677` | 138 | 2026-09-19 | - |
| Mid | kyeahoo | `f55bc80c` | 138 | 2026-09-19 | - |
| Bot | Caliste | `0c9a5ffd` | 138 | 2026-09-19 | - |
| Support | Busio | `41805a16` | 138 | 2026-09-19 | - |

#### TL - Team Liquid (LCS1)

| Role | Player | player_id (last 8) | 2026 games | Last game | Flags |
|---|---|---|---|---|---|
| Top | Morgan | `03c4ffeb` | 104 | 2026-10-04 | - |
| Jungle | Josedeodo | `97fa75f4` | 115 | 2026-10-04 | - |
| Mid | Quid | `5c81c91f` | 104 | 2026-10-04 | - |
| Bot | Yeon | `f3046b92` | 104 | 2026-10-04 | - |
| Support | CoreJJ | `68970b9f` | 104 | 2026-10-04 | - |

#### LYON - LYON (LCS2)

| Role | Player | player_id (last 8) | 2026 games | Last game | Flags |
|---|---|---|---|---|---|
| Top | Dhokla | `ee56cf97` | 119 | 2026-10-04 | - |
| Jungle | Inspired | `3d43700e` | 113 | 2026-10-04 | - |
| Mid | Saint | `cbdd6e8e` | 122 | 2026-10-04 | - |
| Bot | Berserker | `07210ab3` | 122 | 2026-10-04 | - |
| Support | Isles | `70de57bd` | 122 | 2026-10-04 | - |

Other 2026 players for this team_id: Castle (Top, 48g), Armao (Jungle, 9g)

#### C9 - Cloud9 (LCS3)

| Role | Player | player_id (last 8) | 2026 games | Last game | Flags |
|---|---|---|---|---|---|
| Top | Thanatos | `00b903f9` | 107 | 2026-10-03 | - |
| Jungle | Blaber | `b5aeb42e` | 107 | 2026-10-03 | - |
| Mid | Loki | `517b3175` | 50 | 2026-10-03 | PARTIAL_2026_TENURE: 32/78 team games, first 2026-07-26 |
| Bot | Tactical | `dd72df1b` | 64 | 2026-10-03 | PARTIAL_2026_TENURE: 32/78 team games, first 2026-07-26 |
| Support | Vulcan | `e9887f84` | 107 | 2026-10-03 | - |

Other 2026 players for this team_id: APA (Mid, 75g), Zven (Bot, 75g)

#### TSW - Team Secret Whales (LCP1)

| Role | Player | player_id (last 8) | 2026 games | Last game | Flags |
|---|---|---|---|---|---|
| Top | Pun | `98130b61` | 109 | 2026-08-30 | - |
| Jungle | Hizto | `d475c9d2` | 110 | 2026-08-30 | - |
| Mid | Dire | `f82a1d3f` | 110 | 2026-08-30 | - |
| Bot | Eddie | `fc8972ae` | 110 | 2026-08-30 | - |
| Support | Bie | `3949fdd0` | 114 | 2026-08-30 | - |

Other 2026 players for this team_id: Hiro02 (Top, 1g)

#### CFO - CTBC Flying Oyster (LCP2)

| Role | Player | player_id (last 8) | 2026 games | Last game | Flags |
|---|---|---|---|---|---|
| Top | Rest | `e76e141f` | 87 | 2026-08-30 | - |
| Jungle | Shad0w | `c7f396fd` | 87 | 2026-08-30 | - |
| Mid | Pout | `bf484fdf` | 65 | 2026-08-30 | PARTIAL_2026_TENURE: 53/79 team games, first 2026-04-18 |
| Bot | Doggo | `8c993366` | 87 | 2026-08-30 | - |
| Support | Kino | `911e17dd` | 61 | 2026-08-30 | PARTIAL_2026_TENURE: 53/79 team games, first 2026-04-18 |

Other 2026 players for this team_id: Pungyeon (Mid, 26g), 2274 (Support, 66g)

#### MVK - MVK Esports (LCP3)

| Role | Player | player_id (last 8) | 2026 games | Last game | Flags |
|---|---|---|---|---|---|
| Top | Kratos | `ae4fc7ec` | 73 | 2026-08-29 | - |
| Jungle | Gury | `0c4ad461` | 86 | 2026-08-29 | - |
| Mid | Chika | `8eeadbea` | 60 | 2026-08-29 | PARTIAL_2026_TENURE: 42/75 team games, first 2026-04-04 |
| Bot | Harky | `c07bb4c4` | 83 | 2026-08-29 | PARTIAL_2026_TENURE: 56/75 team games, first 2026-04-04 |
| Support | SiuLoong | `18fb1f29` | 82 | 2026-08-29 | PARTIAL_2026_TENURE: 56/75 team games, first 2026-04-04 |

Other 2026 players for this team_id: Steller (Top, 56g), Kratos (Top, 1g), SofM (Jungle, 3g), Seany (Mid, 50g), Kati (Mid, 22g), Shogun (Bot, 50g), Elio (Support, 75g)

#### LOS - LØS (CBLOL1)

| Role | Player | player_id (last 8) | 2026 games | Last game | Flags |
|---|---|---|---|---|---|
| Top | Zest | `89a865c1` | 105 | 2026-10-10 | - |
| Jungle | Curse | `8046f110` | 112 | 2026-10-10 | PARTIAL_2026_TENURE: 57/86 team games, first 2026-05-03 |
| Mid | Feisty | `6504ca77` | 105 | 2026-10-10 | - |
| Bot | Duduhh | `5710dd3e` | 105 | 2026-10-10 | - |
| Support | Ackerman | `7d6bb5b6` | 116 | 2026-10-10 | - |

Other 2026 players for this team_id: Drakehero (Jungle, 60g)

#### FUR - FURIA (CBLOL2)

| Role | Player | player_id (last 8) | 2026 games | Last game | Flags |
|---|---|---|---|---|---|
| Top | Guigo | `f542d305` | 102 | 2026-10-10 | - |
| Jungle | Tatu | `e4dd2fc1` | 96 | 2026-10-10 | - |
| Mid | Tutsz | `e83b1544` | 102 | 2026-10-10 | - |
| Bot | Ayu | `c1de83b3` | 102 | 2026-10-10 | - |
| Support | JoJo | `15b04123` | 102 | 2026-10-10 | - |

Other 2026 players for this team_id: Shini (Jungle, 19g), Luuukz (Jungle, 2g)

<!-- END GENERATED: rosters_from_db.py -->
## 6. Files

- `C:\Python\LOL_PICKEMS\ingest\rosters_from_db.py`: rerunnable build. Read-only on the DuckDB file, no network. It regenerates the GENERATED block above.
- `C:\Python\LOL_PICKEMS\data\worlds2026_teams.csv`: 19 rows, OE name, OE team_id, seed, stage entry, route evidence, notes.
- `C:\Python\LOL_PICKEMS\data\rosters_2026.csv`: 150 rows (95 starters, 55 bench) with 2026 games, last game, team history 2025–26 and flags.
- `C:\Python\LOL_PICKEMS\data\aliases.csv`: 49 team aliases (every OE name each team_id used in 2024–26, plus codes and old names) and 150 player aliases (OE playername to OE player_id, starters and bench).
