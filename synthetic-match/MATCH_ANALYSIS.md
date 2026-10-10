# Match analysis: Kingsbridge Athletic 2 – 2 Northgate Rovers

> Synthetic match. Every number is computed from the generated event and tracking data by `generator/analyze_match.py`. Pre-match context (form, absences, schedule, coach profiles) comes from `script/pre_match_context.json`. Mental factors are partly modelled and are labelled as such.

## Key insights

- **Result vs. performance:** Kingsbridge won the xG battle 2.48 – 1.52 with 57.8% possession and 78.9% field tilt, but Northgate turned 3 big chances into 2 goals (goals − xG: +0.48).
- **Transitions decided it:** Northgate scored twice from fast attacks. Kingsbridge's rest defence averaged only 1.9 players (Northgate 4.1), and the high line (48.0 m in possession) was beaten by balls in behind.
- **Pressing worked, but not enough:** Kingsbridge regained the ball within 5 s after 30.3% of their losses (Northgate 18.6%), with PPDA 5.1 vs 11.1 and 36 high turnovers.
- **Discipline and the red card:** Brannigan's two yellows both came in duels with Adeyemi-Clarke, the second one stopping a counter. With 10 men Kingsbridge's possession fell to 43.9% and their xG in that phase was 0.08.
- **Substitutions:** every goal after the 60th minute was scored and assisted by substitutes (Halvorsen → Diallo-Kerr, Castellanos → Moore-Asante).
- **Card effect:** after Quiroga's yellow (12'), Kingsbridge's share of attacks down their left rose from 24.1% to 47.7%. The equaliser came from that flank.

## The 12 components at a glance

| # | Component | Key finding |
|---|---|---|
| 1 | Attacking play | Kingsbridge: 75 progressive passes, 30 deep completions, 23 crosses. Northgate: direct, 0.138 xG per shot (Kingsbridge 0.13). |
| 2 | Defensive play | Northgate's low block (line 17.0 m) conceded many low-quality shots; Kingsbridge conceded 3 big chances from only 11 shots. |
| 3 | Transitions | Fast attacks (shot ≤ 15 s after a regain): Kingsbridge 1.25 xG, Northgate 0.51 xG. Both Northgate goals came from quick transitions. |
| 4 | Tactical systems | 4 formation changes in total; the red card (4-3-3 → 4-4-1) and Northgate's 4-3-3 switch were the turning points. |
| 5 | Individual players | Best rated: Kai Nakamura-Brooks (9.3). |
| 6 | Physical | Kingsbridge (120 min three days earlier) dropped from 108.8 to 101.7 m/player/min. |
| 7 | Mental | Discipline cost Kingsbridge: their least disciplined player (discipline 38) was sent off at 1-1. Confidence effects are modelled; the measured reactions after each goal are in section 7. |
| 8 | Set pieces | Set-piece xG 0.43 vs 0.23; no set-piece goals, no penalties. |
| 9 | Statistics | xG 2.48 – 1.52, xGOT 1.46 – 1.71, field tilt 78.9% – 21.1%. |
| 10 | Opponent / match-ups | High line vs pace and the booked right-back were the decisive match-ups (see section 10). |
| 11 | Context | Home side with a heavy midweek cup match vs a rested underdog; strict referee on tactical fouls. |
| 12 | Coaching & subs | Both coaches reacted. Solberg's back three earned the point; Kowalczyk's 4-3-3 switch won the period after the red card. |

## 2. Attacking play

### Build-up from the back

| | Kingsbridge | Northgate |
|---|---|---|
| Players in own third during build-up | 4.3 | 8.0 |
| Goal kicks | 10 | 15 |
| Goal kicks played short | 100.0% | 13.3% |
| Goalkeeper passes | 13 | 11 |
| Goalkeeper pass accuracy | 92.3% | 54.5% |
| Passes breaking the first pressing line | 49 | 25 |
| Passes under pressure | 206 | 147 |
| Pass accuracy under pressure | 80.1% | 77.6% |
| Long passes (>32 m) | 17.1% | 15.3% |

Kingsbridge build up with a back three (Mbeki inverting) and play short from the goalkeeper. Northgate avoid the press: 13.3% of goal kicks short, and Saarinen completed only 54.5% of his passes.

### Midfield progression

| | Kingsbridge | Northgate |
|---|---|---|
| Possession | 57.8% | 42.2% |
| Passes | 487 | 374 |
| Pass accuracy | 83.6% | 81.6% |
| Progressive passes | 75 | 44 |
| Progressive carries | 24 | 26 |
| Receptions between the lines (≥3 m space) | 46 | 64 |
| Half-space receptions (final 40%) | 88 | 12 |
| Switches of play (>30 m wide) | 44 | 29 |

![Pass networks](output/figures/analysis_pass_networks.png)

### Final third

| | Kingsbridge | Northgate |
|---|---|---|
| Final-third entries | 85 | 45 |
| Box entries | 44 | 11 |
| Deep completions | 30 | 6 |
| Crosses | 23 | 5 |
| Crosses reaching a team-mate | 9 | 2 |
| Cutbacks | 2 | 0 |
| Receptions in zone 14 | 30 | 26 |

### Finishing

| | Kingsbridge | Northgate |
|---|---|---|
| Shots | 19 | 11 |
| On target | 7 | 4 |
| Goals | 2 | 2 |
| xG | 2.48 | 1.52 |
| xG per shot | 0.13 | 0.14 |
| xGOT | 1.46 | 1.71 |
| Goals − xG | -0.48 | 0.48 |
| Big chances (xG ≥ 0.3) | 1 | 3 |
| Big chances scored | 0 | 2 |
| Shots from inside the box | 73.7% | 45.5% |
| Headed shots | 8 | 2 |

![Shot map](output/figures/analysis_shot_map.png)

| Player | Team | Shots | On target | xG | Goals |
|---|---|---|---|---|---|
| Oscar Lindqvist | KBA | 9 | 4 | 1.16 | 0 |
| Declan Moore-Asante | KBA | 4 | 2 | 1.03 | 1 |
| Ismael Diallo-Kerr | NGR | 2 | 2 | 0.71 | 1 |
| Marcus Adeyemi-Clarke | NGR | 6 | 2 | 0.67 | 1 |
| Jonas Petrov | NGR | 2 | 0 | 0.10 | 0 |
| Kai Nakamura-Brooks | KBA | 1 | 1 | 0.09 | 1 |

## 3. Defensive play

Goals conceded say little on their own. What matters is how hard each side made it for the opponent to create chances.

| | Kingsbridge | Northgate |
|---|---|---|
| xGA | 1.52 | 2.48 |
| Shots conceded | 11 | 19 |
| Big chances conceded | 3 | 1 |
| PPDA (lower = more pressing) | 5.1 | 11.1 |
| Tackles | 51 | 52 |
| Tackles won % | 78.4 | 40.4 |
| Interceptions | 11 | 28 |
| Take-ons conceded (1v1) | 11 | 31 |
| Opponent crosses reaching target % | 40.0 | 39.1 |
| Zone-14 receptions conceded | 26 | 30 |
| Offsides won | 2 | 4 |
| Rest defence (players behind ball when attacking) | 1.9 | 4.1 |
| Fouls | 12 | 8 |
| Defensive line out of possession (m) | 38.6 | 17.0 |
| Team length out of possession (m) | 24.9 | 25.9 |
| Team width out of possession (m) | 32.7 | 33.9 |
| Gap defence–midfield (m) | 16.3 | 16.7 |

Northgate defended low and compact (length 25.9 m) and conceded many shots, but mostly low-quality ones (0.13 xG per Kingsbridge shot). Kingsbridge conceded few shots but 3 big chances: the classic profile of a possession side with a high line that is vulnerable in transition.

## 4. Transitions

### Losing the ball (attack → defence)

| | Kingsbridge | Northgate |
|---|---|---|
| Ball losses in open play | 89 | 97 |
| Won back within 5 s (counter-press) | 27 | 18 |
| Counter-press success | 30.3% | 18.6% |
| Median seconds to win the ball back | 6.0 | 13.0 |
| Losses with fewer than 7 behind the ball | 54 | 44 |
| Median seconds to get 7 back behind the ball | 8.0 | 6.0 |
| Counter-attack shots conceded | 3 | 2 |
| Counter-attack xG conceded | 0.77 | 0.2 |

### Winning the ball (defence → attack)

| | Kingsbridge | Northgate |
|---|---|---|
| Regains in open play | 97 | 89 |
| Average regain height (m from own goal) | 58.0 | 31.9 |
| First pass forward after regain | 30.9% | 32.6% |
| Regains leading to a shot within 15 s | 7 | 3 |
| xG from fast attacks | 1.25 | 0.51 |
| Median seconds regain → shot | 7.0 | 11.0 |

![Regains](output/figures/analysis_regains.png)

Two different transition profiles: Kingsbridge win the ball high and immediately (counter-press), Northgate win it deep and go forward fast. Northgate's two counter-attack goals came from exactly the weakness the pre-match analysis predicted.

## 5. Tactical systems and match-ups

### Formations over time

| Clock | Team | Formation | Players |
|---|---|---|---|
| 00:00 | KBA | 4-3-3 | 11 |
| 00:00 | NGR | 4-4-2 | 11 |
| 45:00 | NGR | 4-4-2 | 11 |
| 52:50 | KBA | 4-4-1 | 10 |
| 58:30 | KBA | 4-4-1 | 10 |
| 63:20 | NGR | 4-3-3-deep | 11 |
| 75:00 | KBA | 3-4-2 | 10 |
| 86:10 | NGR | 5-4-1 | 11 |

### By match phase

| Phase | Min | Poss KBA | Field tilt KBA | PPDA KBA | xG KBA | xG NGR | PPDA NGR | Line KBA (out of poss.) | Line NGR (out of poss.) |
|---|---|---|---|---|---|---|---|---|---|
| Kingsbridge in control | 0-23 | 66.6% | 92.7% | 6.7 | 0.87 | 0.03 | 19.5 | 43.4 | 14.9 |
| Shock and frustration | 23-38 | 56.0% | 86.0% | 8.0 | 0.17 | 0.41 | 15.0 | 42.5 | 13.8 |
| Back on terms | 38-52 | 58.9% | 75.5% | 8.8 | 0.23 | 0.09 | 14.0 | 38.3 | 19.2 |
| Ten men | 52-63 | 43.9% | 12.5% | 3.0 | 0.08 | 0.08 | 9.7 | 28.3 | 32.3 |
| Northgate exploit the extra man | 63-75 | 38.9% | 19.4% | 4.2 | 0 | 0.53 | 8.0 | 23.0 | 31.6 |
| All in | 75-86 | 63.8% | 96.4% | 5.1 | 0.22 | 0.38 | 4.7 | 48.2 | 12.4 |
| Holding on | 86-96 | 64.1% | 100.0% | 2.0 | 0.91 | 0 | – | 57.2 | 8.1 |

![Kingsbridge shapes](output/figures/shape_kingsbridge.png)

![Northgate shapes](output/figures/shape_northgate.png)

### Pressing triggers

| Trigger | Kingsbridge | Northgate |
|---|---|---|
| back pass | 24 | 26 |
| ball near touchline | 6 | 2 |
| goalkeeper in possession | 18 | 10 |
| none | 171 | 237 |
| total pressures | 219 | 275 |
| of which counter-press | 94 | 0 |

### Game state

| Team | State | Minutes | Possession | xG for | xG against | Avg def. line (m) |
|---|---|---|---|---|---|---|
| Kingsbridge | level | 67.0 | 57.9% | 2.0 | 1.37 | 44.1 |
| Kingsbridge | trailing | 30.0 | 57.6% | 0.48 | 0.15 | 43.7 |
| Northgate | leading | 30.0 | 42.4% | 0.15 | 0.48 | 20.7 |
| Northgate | level | 67.0 | 42.1% | 1.37 | 2.0 | 21.3 |

Northgate's defensive line: 21.3 m when level vs 20.7 m when leading. Kingsbridge: 44.1 m when level vs 43.7 m when trailing. Note that the trailing periods overlap with the red card, so game state and numerical inferiority are mixed.

## 6. Individual players

Match rating = a transparent formula (6.0 + goals, assists, xG, xA, xT, defensive actions, pass accuracy − cards and fouls). It is not a scout's judgement.

| Player | Team | Min | Rating | Form (last 5) | xG | xA | xT added | Prog. actions | Between lines | Tackles won | Key note |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Kai Nakamura-Brooks | KBA | 97 | **9.3** | 7.4 | 0.09 | 0.97 | 0.95 | 18 | 2 | 0 |  |
| Elias Kovač | KBA | 60 | **8.5** | 7.6 | 0.05 | 0.73 | 0.75 | 11 | 6 | 2 | League leader in key passes (2.9 per 90) |
| Declan Moore-Asante | KBA | 20 | **7.8** | 6.8 | 1.03 | 0.0 | -0.26 | 3 | 6 | 3 | 4 headed goals as a substitute this season |
| Viktor Halvorsen | NGR | 32 | **7.8** | 7.1 | 0.00 | 0.71 | 0.05 | 4 | 8 | 2 |  |
| Ismael Diallo-Kerr | NGR | 32 | **7.8** | 6.9 | 0.71 | 0.0 | 0.13 | 2 | 0 | 0 |  |
| Rafael Duarte | NGR | 97 | **7.7** | 7.2 | 0.00 | 0.46 | 0.15 | 10 | 4 | 2 |  |
| Marcus Adeyemi-Clarke | NGR | 88 | **7.7** | 7.5 | 0.67 | 0.0 | -0.0 | 10 | 25 | 1 | 5 goals, 4 of them from counter-attacks |
| Ruben Castellanos | KBA | 20 | **7.3** | 6.9 | 0.07 | 0.22 | 0.27 | 7 | 0 | 1 |  |
| Henrik Saarinen | NGR | 97 | **7.0** | 7.5 | 0.00 | 0.0 | 0.01 | 4 | 0 | 0 | Highest save percentage in the league (78%) |
| Samir El-Haddad | KBA | 97 | **6.7** | 6.7 | 0.00 | 0.14 | 0.25 | 14 | 2 | 3 |  |
| Tomás Ferreira-Lind | KBA | 97 | **6.6** | 6.9 | 0.00 | 0.0 | 0.01 | 0 | 0 | 0 |  |
| Theo Lindgren | NGR | 97 | **6.6** | 6.7 | 0.00 | 0.3 | 0.17 | 13 | 1 | 2 |  |
| Marten Dijkhuis | KBA | 97 | **6.4** | 7.1 | 0.03 | 0.0 | 0.05 | 8 | 0 | 7 |  |
| Oscar Lindqvist | KBA | 97 | **6.4** | 7.3 | 1.16 | 0.02 | -1.42 | 2 | 21 | 6 | 6 goals from 4.8 xG this season |
| Finn Gallagher | NGR | 97 | **6.3** | 6.9 | 0.00 | 0.02 | 0.03 | 4 | 0 | 2 | Long throw up to 35 m |
| Jonas Petrov | NGR | 65 | **6.3** | 6.8 | 0.10 | 0.0 | -0.01 | 5 | 23 | 1 |  |
| Callum Reyes | KBA | 97 | **6.2** | 6.9 | 0.00 | 0.0 | 0.06 | 5 | 0 | 6 |  |
| Aaron Whitfield | NGR | 50 | **6.2** | 6.7 | 0.00 | 0.0 | 0.01 | 1 | 0 | 1 |  |
| Jayden Okafor-Hale | KBA | 77 | **6.1** | 7.0 | 0.00 | 0.0 | 0.13 | 7 | 0 | 1 |  |
| Idris Mbeki | KBA | 97 | **6.1** | 7.0 | 0.00 | 0.0 | 0.07 | 6 | 0 | 0 |  |
| Noah Visser | KBA | 77 | **6.1** | 7.0 | 0.02 | 0.0 | 0.04 | 3 | 8 | 5 |  |
| Bram Hollander | NGR | 97 | **6.1** | 7.1 | 0.03 | 0.0 | 0.01 | 1 | 0 | 4 |  |
| Desmond Achebe-Ward | NGR | 97 | **6.1** | 6.8 | 0.00 | 0.0 | 0.0 | 0 | 0 | 2 |  |
| Jules Moreau | NGR | 65 | **6.0** | 6.8 | 0.00 | 0.0 | 0.02 | 6 | 0 | 0 |  |
| Lewis Okoro | NGR | 9 | **6.0** | 6.6 | 0.00 | 0.0 | 0.0 | 0 | 0 | 1 |  |
| Felix Achterberg | KBA | 36 | **5.9** | 6.8 | 0.02 | 0.0 | 0.11 | 8 | 1 | 3 |  |
| Yannick Brouwer | NGR | 97 | **5.9** | 7.0 | 0.00 | 0.0 | 0.07 | 7 | 3 | 2 | Most tackles in the league (4.1 per 90) |
| Mateo Quiroga | NGR | 47 | **5.8** | 6.5 | 0.00 | 0.0 | 0.01 | 3 | 0 | 1 |  |
| Luca Brannigan | KBA | 54 | **4.2** | 7.2 | 0.00 | 0.0 | 0.18 | 7 | 0 | 3 | One red card this season, 4 yellows in 8 matches |

### Absences and squad composition

- **Kingsbridge – Rasmus Holt (CB)**: Hamstring injury, out for 3 weeks. Holt is the fastest centre-back in the squad and normally covers for Dijkhuis. Without him the pairing is slower and the high line is riskier.
- **Kingsbridge – Jonah Ekwueme (W)**: Ill. One less attacking option on the bench.
- **Northgate – Stefan Varga (CB)**: Knee injury, out for 6 weeks. First-choice centre-back and organiser. Okoro is now the only aerial back-up for the 5-4-1.
- **In-match:** losing Brannigan (red card) hurt more than any other absence. Without a holding midfielder Northgate found the space between the lines (Halvorsen's assist at 67').

## 7. Physical and mental factors

### Physical (measured from tracking)

| Block | KBA m/player/min | KBA HI m/player/min | NGR m/player/min | NGR HI m/player/min |
|---|---|---|---|---|
| 0-15 | 108.8 | 12.66 | 109.6 | 5.66 |
| 15-30 | 103.3 | 9.87 | 95.3 | 2.94 |
| 30-45+ | 122.3 | 12.88 | 106.1 | 2.68 |
| 45-60 | 89.0 | 7.12 | 83.9 | 6.91 |
| 60-75 | 94.0 | 3.07 | 93.7 | 7.28 |
| 75-90+ | 101.7 | 9.86 | 90.3 | 3.58 |

![Physical](output/figures/analysis_physical.png)

| Player | Km | HI runs | HI km | Sprints | Accelerations | Top km/h |
|---|---|---|---|---|---|---|
| Kai Nakamura-Brooks | 11.67 | 96 | 1.23 | 51 | 130 | 30.0 |
| Samir El-Haddad | 11.46 | 80 | 1.03 | 49 | 100 | 27.6 |
| Marcus Adeyemi-Clarke | 10.99 | 93 | 0.98 | 53 | 134 | 28.4 |
| Oscar Lindqvist | 10.8 | 98 | 1.11 | 37 | 113 | 27.3 |
| Yannick Brouwer | 10.55 | 35 | 0.31 | 2 | 81 | 25.0 |
| Theo Lindgren | 10.52 | 38 | 0.34 | 9 | 64 | 26.7 |

*Context:* Kingsbridge – Cup round 3 away at Pellham Town on Wednesday, won on penalties after 120 minutes (3 days rest, load: high: 120 minutes three days ago, six starters played the full match). Northgate – 6 days rest, travel: 210 km by coach, arrived the evening before. The model applies a higher fatigue rate to Kingsbridge.

### Mental (partly modelled, use as supporting evidence only)

![Morale](output/figures/analysis_morale.png)

**Measured reaction after each goal (conceding team, 10 min before vs. 10 min after):**

| Goal | Conceding team | Score after | Possession | Pass accuracy | Fouls | xG |
|---|---|---|---|---|---|---|
| 23:14 | KBA | 0-1 | 60.4% → 57.3% | 90.9% → 87.0% | 0 → 3 | 0.33 → 0.17 |
| 38:41 | NGR | 1-1 | 35.4% → 45.3% | 78.9% → 78.8% | 0 → 0 | 0 → 0.09 |
| 67:05 | KBA | 1-2 | 38.0% → 52.8% | 77.8% → 65.1% | 1 → 2 | 0 → 0 |
| 81:37 | NGR | 2-2 | 45.3% → 33.9% | 78.6% → 65.5% | 2 → 0 | 0 → 0.38 |

- **Kingsbridge:** Confident: 4 wins and 2 draws in the last 6. Expected to win at home. Struggle emotionally when behind: 2 red cards this season, both while trailing. Good at home, nervous when chasing a result late.
- **Northgate:** Resilient underdog, unbeaten in four away games, good at defending a lead. Rarely come back from behind (1 point from losing positions). Calm under pressure, but they fade late: 5 of their 10 goals conceded came after the 75th minute.
- **Discipline:** 3 yellow + 1 red for Kingsbridge, 3 yellow for Northgate (referee average 4.6 yellows per game). Pass accuracy under pressure: 80.1% vs 77.6%.

## 8. Set pieces

| | Kingsbridge | Northgate |
|---|---|---|
| Corners | 7 | 4 |
| Short corners | 3 | 2 |
| Corner deliveries | 4 | 2 |
| First contact won from corners | 1 | 1 |
| Long throws into the box | 0 | 1 |
| Free-kick crosses | 3 | 1 |
| Direct free-kick shots | 0 | 1 |
| Set-piece shots | 4 | 3 |
| Set-piece xG | 0.43 | 0.23 |
| Set-piece goals | 0 | 0 |
| Penalties | 0 | 0 |
| Corner delivery | in-swinging to the near post | out-swinging to the far post |
| Defending corners | zonal (six in zones, two on man) | man-marking |
| Markers beaten in the air (by opponent) | Noah Visser (1) | Bram Hollander (1), Yannick Brouwer (1) |

Kingsbridge's corners came mainly from pressure on the box. Northgate used Gallagher's long throws as an extra set-piece weapon. No penalties were given (the generator never adds penalties because they would change the scripted score).

## 9. Advanced statistics

| Metric | Kingsbridge | Northgate |
|---|---|---|
| xG | 2.48 | 1.52 |
| xGA | 1.52 | 2.48 |
| xG difference | 0.96 | -0.96 |
| xG per shot | 0.13 | 0.14 |
| xGOT | 1.46 | 1.71 |
| PPDA | 5.1 | 11.1 |
| Field tilt | 78.9% | 21.1% |
| Progressive passes | 75 | 44 |
| Deep completions | 30 | 6 |
| Big chances | 1 | 3 |
| xT added (passes + carries) | 1.17 | 0.67 |
| Set-piece xG | 0.43 | 0.23 |
| Open-play xG | 1.84 | 0.51 |
| Counter-attack xG | 0.2 | 0.77 |
| High turnovers | 36 | 6 |
| High turnovers → shot ≤15 s | 5 | 1 |

### Opponent quality: form over the last 8 matches

| | Kingsbridge | Northgate |
|---|---|---|
| Last 5 | WDWWD | DWDLW |
| Points per game | 2.12 | 1.5 |
| xG / xGA per game | 1.92 / 1.11 | 1.15 / 1.35 |
| vs top-half teams (ppg, xG/xGA) | 1.75 (1.67/1.72) | 1.0 (0.9/1.8) |
| vs bottom-half teams (ppg, xG/xGA) | 2.5 (2.18/0.5) | 2.0 (1.4/0.9) |
| Average possession | 63.88 | 42.0 |
| Set-piece xG per game | 0.3 | 0.29 |

Kingsbridge's numbers are inflated by bottom-half opponents (xGA 0.50 against them, 1.72 against top-half sides). Northgate are clearly weaker against top-half teams. Against each other the gap was smaller than the table suggests.

## 10. Opponent analysis: match-ups

The key question is not how good each team is, but how their specific strengths and weaknesses fit together.

### M1 – High line vs elite pace

*Pre-match expectation:* Northgate's best route to goal. Each ball over the top is a big chance. (favoured: away)

*Measured:* kba def line in possession m: 48.0; balls in behind to fast forwards: 30; ngr xg after balls in behind: 1.33; ngr counter xg: 0.51

**Verdict:** Confirmed: Northgate's balls in behind produced 1.33 xG and the opening goal; Kingsbridge held their line around 48.0 m in possession.

### M2 – Fast winger vs vulnerable right-back

*Pre-match expectation:* Kingsbridge will target their left flank; card risk for Quiroga. (favoured: home)

*Measured:* left flank share before card pct: 24.1; left flank share after card pct: 47.7; nakamura take ons vs quiroga: 3; quiroga card: 12:40; equaliser vs quiroga: 38:41

**Verdict:** Confirmed: after the card Kingsbridge shifted play to their left, and the equaliser came from Nakamura-Brooks against the booked Quiroga.

### M3 – High press vs weak build-up

*Pre-match expectation:* Kingsbridge win the ball high up; Northgate avoid playing out and go long. (favoured: home)

*Measured:* kba ppda: 5.1; ngr ppda: 11.1; kba high turnovers: 36; ngr goal kicks short pct: 13.3; saarinen pass accuracy pct: 54.5

**Verdict:** Kingsbridge pressed more intensely (PPDA 5.1 vs 11.1). The press did bite: Kingsbridge won the ball high 36 times (Northgate 6), and Northgate avoided playing out by going long from goal kicks (13.3% short; Saarinen 54.5% pass accuracy).

### M4 – Creator between the lines vs compact block

*Pre-match expectation:* Little space for Kovač; Kingsbridge depend on width and crosses. (favoured: away)

*Measured:* kovac receptions between lines: 6; kovac minutes: 60.5; kba receptions between lines: 46; kba crosses: 23

**Verdict:** Kovač found 6 receptions between the lines in 60 minutes; Kingsbridge needed width and crosses (23) to progress.

### M5 – Hot-headed anchor vs counter-attacks

*Pre-match expectation:* Brannigan will have to commit fouls to stop counters. Card risk is high with a strict referee. (favoured: away)

*Measured:* brannigan fouls: 2; brannigan cards: 2 yellow → red (31', 52'); fouls on counter attacks: 2

**Verdict:** Confirmed, and decisive: both yellows came in duels with Adeyemi-Clarke (the second stopping a break), and the red card changed the game.

### M6 – Set pieces: zonal Kingsbridge vs aerial Northgate

*Pre-match expectation:* Set pieces are Northgate's second route to goal. At the other end Achebe-Ward's marking is a target. (favoured: even)

*Measured:* kba set piece xg: 0.43; ngr set piece xg: 0.23; ngr long throws: 1; beaten markers ngr: {'Bram Hollander': 1, 'Yannick Brouwer': 1}; beaten markers kba: {'Noah Visser': 1}

**Verdict:** Set pieces were not decisive: 0.43 vs 0.23 set-piece xG, no set-piece goals.

### M7 – Late fatigue

*Pre-match expectation:* Both sides tire. Whoever's bench brings fresh energy decides the final 20 minutes. (favoured: even)

*Measured:* m per player min first vs last block: {'KBA': [108.8, 101.7], 'NGR': [109.6, 90.3]}; substitute contributions: {'KBA': {'goals': 1, 'assists': 1, 'xg': 1.13}, 'NGR': {'goals': 1, 'assists': 1, 'xg': 0.71}}

**Verdict:** The benches decided the last half hour: every goal after the 60th minute came from a substitute (Diallo-Kerr, Moore-Asante), both assisted by substitutes.

## 11. Match context

- **Venue:** Kingsbridge Park, natural grass (good, slightly firm), 21,400 spectators (1,800 away).
- **Weather:** Dry, 13°C, light wind (11 km/h) from the west. No significant impact. A dry, firm pitch slightly favours fast ball circulation and the Kingsbridge passing game.
- **Referee:** Alan Ostrowski (fictional): Plays advantage a lot, lets physical duels go, strict on simulation and on tactical fouls that stop counter-attacks. Season averages 4.6 yellows, 23.1 fouls. This match: 6 yellows (including a second yellow), 20 fouls. Good for Northgate's duels in midfield; risky for a hot-headed holding midfielder who has to stop counters.
- **Stakes:** Matchday 9. Kingsbridge (4th) need a win to stay in touch with the top three. Northgate (9th) are unbeaten in four away games and would be happy with a point.
- **Schedule:** Kingsbridge 3 days rest after 120 minutes in the cup; Northgate 6 days rest, 210 km by coach, arrived the evening before.
- **Head to head:** Kingsbridge 2-1 Northgate (Northgate scored on the counter; Kingsbridge won with a late set-piece header); Northgate 0-0 Kingsbridge (Kingsbridge 71% possession, 0.9 xG against a low block).
- **Game flow:** Kingsbridge trailed for 30.0 minutes and never led. That partly explains their territorial dominance and Northgate's deep line.

## 12. Coaching and substitutions

### Ingrid Solberg (Kingsbridge)

- Game plan: Dominate the ball, high press on Northgate's weak build-up, overload the left side through Kovač and Nakamura-Brooks, keep Brannigan as the anchor.
- First substitution: 58.0' (season average 58'), 3 substitutions, 2 formation changes.
- Expected when trailing: Goes to a back three with wing-backs and an extra striker (done 3 times this season, one winner). Expected when leading: Keeps the ball, rarely drops deep.
- Did they follow their profile? Yes: went to a back three with an extra striker while trailing (75'), and it produced the equaliser.
- Bench quality (pre-match rating): 72/100

| Clock | Off | On | New formation | On-player: min / G / A / xG / rating |
|---|---|---|---|---|
| 58:30 | Elias Kovač | Felix Achterberg | 4-4-1 | 36.5 / 0 / 0 / 0.02 / 5.9 |
| 75:00 | Jayden Okafor-Hale | Ruben Castellanos | 3-4-2 | 20.0 / 0 / 1 / 0.07 / 7.3 |
| 75:00 | Noah Visser | Declan Moore-Asante | 3-4-2 | 20.0 / 1 / 0 / 1.03 / 7.8 |

### Darren Kowalczyk (Northgate)

- Game plan: Stay compact in a 4-4-2 mid/low block, jump on passes into Kingsbridge's holding midfielder, then hit Adeyemi-Clarke early in behind the high line. Avoid playing out from the back against the press.
- First substitution: 45.0' (season average 66'), 4 substitutions, 2 formation changes.
- Expected when trailing: Brings on an extra striker but keeps the 4-4-2. Expected when leading: Goes to a 5-4-1 with an extra centre-back (done 4 times this season).
- Did they follow their profile? Partly: switched to 4-3-3 to exploit the extra man (not in the usual profile), then to 5-4-1 at 2-2 to protect a point instead of a lead.
- Bench quality (pre-match rating): 66/100

| Clock | Off | On | New formation | On-player: min / G / A / xG / rating |
|---|---|---|---|---|
| 45:00 | Mateo Quiroga | Aaron Whitfield | 4-4-2 | 50.0 / 0 / 0 / 0.0 / 6.2 |
| 63:20 | Jules Moreau | Viktor Halvorsen | 4-3-3-deep | 31.7 / 0 / 1 / 0.0 / 7.8 |
| 63:20 | Jonas Petrov | Ismael Diallo-Kerr | 4-3-3-deep | 31.7 / 1 / 0 / 0.71 / 7.8 |
| 86:10 | Marcus Adeyemi-Clarke | Lewis Okoro | 5-4-1 | 8.8 / 0 / 0 / 0.0 / 6.0 |

## Definitions and limitations

- **progressive:** Completed pass or carry that moves the ball at least 10 m and 25% closer to goal, ending beyond 40 m.
- **deep completion:** Completed pass (not a cross) ending within 20 m of the opponent's goal.
- **ppda:** Opponent passes in their own 60% of the pitch divided by our tackles, interceptions and fouls in that zone.
- **field tilt:** Share of all final-third passes made by the team.
- **big chance:** Shot with xG >= 0.30.
- **xgot:** Post-shot xG for shots on target, based on placement in the goal mouth.
- **xt:** Expected threat added by completed passes and carries, using a smooth location-value surface (approximation of a grid xT model).
- **high turnover:** Possession won within 42 m of the opponent's goal (x > 63).
- **counterpress success:** Share of open-play losses where the ball was won back within 5 seconds.
- **rest defence:** Average number of outfield players more than 15 m behind the ball and in their own half while attacking in the opponent's half.
- **between lines:** Receptions between the opponent's defensive line (deepest 4) and midfield line (next 4).
- **carry:** Movement with the ball between a reception and the same player's next action (>= 3 m).
- **sprint:** 1-second sample above 23.8 km/h; high-intensity run: entering > 19.8 km/h.
- **Model limits:** synthetic 1 Hz data; xG, xGOT and xT come from simple location models; confidence/morale is a model state, not a measurement; penalties are never generated; only scripted shots can become goals.