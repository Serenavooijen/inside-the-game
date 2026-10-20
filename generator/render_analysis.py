"""
Writes MATCH_ANALYSIS.md from output/analysis.json (run analyze_match.py first).
Structure follows the 12 components of football analysis.
"""
import json
import os
import sys

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
A = json.load(open(os.path.join(ROOT, "output", "analysis.json")))
S = json.load(open(os.path.join(ROOT, "script", "match_script.json")))
CTX = json.load(open(os.path.join(ROOT, "script", "pre_match_context.json")))
H, W_ = S["teams"]["home"], S["teams"]["away"]
HID, AID = H["id"], W_["id"]
NAME = {HID: H["short"], AID: W_["short"]}
T, TR, SP, GS = A["teams"], A["transitions"], A["set_pieces"], A["game_state"]
L = []
w = L.append


def fmt(v, suf=""):
    if v is None:
        return "–"
    if isinstance(v, float):
        v = round(v, 2)
    return f"{v}{suf}"


def table(rows, src, keys_labels, suffix=None):
    w(f"| | {NAME[HID]} | {NAME[AID]} |")
    w("|---|---|---|")
    for k, lab in keys_labels:
        hv, av = src[HID].get(k), src[AID].get(k)
        sfx = "%" if k.endswith("_pct") else ""
        w(f"| {lab} | {fmt(hv, sfx)} | {fmt(av, sfx)} |")
    w("")


hs, as_ = T[HID], T[AID]
w(f"# Match analysis: {H['name']} {hs['goals']} – {as_['goals']} {W_['name']}\n")
w("> Synthetic match. Every number is computed from the generated event and tracking data by `generator/analyze_match.py`. "
  "Pre-match context (form, absences, schedule, coach profiles) comes from `script/pre_match_context.json`. "
  "Mental factors are partly modelled and are labelled as such.\n")

# ------------------------------------------------------------- key insights
w("## Key insights\n")
w(f"- **Result vs. performance:** {NAME[HID]} won the xG battle {hs['xg']} – {as_['xg']} with {hs['possession_pct']}% possession and {hs['field_tilt_pct']}% field tilt, "
  f"but Northgate turned {as_['big_chances']} big chances into {as_['big_chances_scored']} goals (goals − xG: {as_['goals_minus_xg']:+}).")
w(f"- **Transitions decided it:** Northgate scored twice from fast attacks. Kingsbridge's rest defence averaged only {hs['rest_defence_players']} players "
  f"(Northgate {as_['rest_defence_players']}), and the high line ({hs['shape_in_possession']['def_line']} m in possession) was beaten by balls in behind.")
w(f"- **Pressing worked, but not enough:** Kingsbridge regained the ball within 5 s after {TR[HID]['counterpress_success_pct']}% of their losses "
  f"(Northgate {TR[AID]['counterpress_success_pct']}%), with PPDA {hs['ppda']} vs {as_['ppda']} and {hs['high_turnovers']} high turnovers.")
w("- **Discipline and the red card:** Brannigan's two yellows both came in duels with Adeyemi-Clarke, the second one stopping a counter. With 10 men Kingsbridge's possession fell to "
  f"{A['phases'][3][HID]['possession_pct']}% and their xG in that phase was {A['phases'][3][HID]['xg']}.")
w("- **Substitutions:** every goal after the 60th minute was scored and assisted by substitutes (Halvorsen → Diallo-Kerr, Castellanos → Moore-Asante).")
w(f"- **Card effect:** after Quiroga's yellow (12'), Kingsbridge's share of attacks down their left rose from "
  f"{A['matchups'][1]['measured']['left_flank_share_before_card_pct']}% to {A['matchups'][1]['measured']['left_flank_share_after_card_pct']}%. The equaliser came from that flank.\n")

# ------------------------------------------------------------- overview table
w("## The 12 components at a glance\n")
w("| # | Component | Key finding |")
w("|---|---|---|")
over = [
    ("Attacking play", f"Kingsbridge: {hs['progressive_passes']} progressive passes, {hs['deep_completions']} deep completions, {hs['crosses']} crosses. Northgate: direct, {as_['xg_per_shot']} xG per shot (Kingsbridge {hs['xg_per_shot']})."),
    ("Defensive play", f"Northgate's low block (line {as_['shape_out_of_possession']['def_line']} m) conceded many low-quality shots; Kingsbridge conceded {hs['big_chances_conceded']} big chances from only {hs['shots_conceded']} shots."),
    ("Transitions", f"Fast attacks (shot ≤ 15 s after a regain): Kingsbridge {TR[HID]['xg_from_fast_attacks']} xG, Northgate {TR[AID]['xg_from_fast_attacks']} xG. Both Northgate goals came from quick transitions."),
    ("Tactical systems", f"{A['coaching'][HID]['formation_changes'] + A['coaching'][AID]['formation_changes']} formation changes in total; the red card (4-3-3 → 4-4-1) and Northgate's 4-3-3 switch were the turning points."),
    ("Individual players", f"Best rated: {max(A['players'], key=lambda r: r['rating'])['name']} ({max(A['players'], key=lambda r: r['rating'])['rating']})."),
    ("Physical", f"Kingsbridge (120 min three days earlier) dropped from {A['physical_per_15'][HID][0]['m_per_player_min']} to {A['physical_per_15'][HID][-1]['m_per_player_min']} m/player/min."),
    ("Mental", "Discipline cost Kingsbridge: their least disciplined player (discipline 38) was sent off at 1-1. Confidence effects are modelled; the measured reactions after each goal are in section 7."),
    ("Set pieces", f"Set-piece xG {SP[HID]['set_piece_xg']} vs {SP[AID]['set_piece_xg']}; no set-piece goals, no penalties."),
    ("Statistics", f"xG {hs['xg']} – {as_['xg']}, xGOT {hs['xgot']} – {as_['xgot']}, field tilt {hs['field_tilt_pct']}% – {as_['field_tilt_pct']}%."),
    ("Opponent / match-ups", "High line vs pace and the booked right-back were the decisive match-ups (see section 10)."),
    ("Context", "Home side with a heavy midweek cup match vs a rested underdog; strict referee on tactical fouls."),
    ("Coaching & subs", "Both coaches reacted. Solberg's back three earned the point; Kowalczyk's 4-3-3 switch won the period after the red card."),
]
for i, (c, f) in enumerate(over, 1):
    w(f"| {i} | {c} | {f} |")
w("")

# ------------------------------------------------------------- 2 attacking
w("## 2. Attacking play\n")
w("### Build-up from the back\n")
table(None, T, [("build_up_players_own_third", "Players in own third during build-up"), ("goal_kicks", "Goal kicks"),
                ("goal_kicks_short_pct", "Goal kicks played short"), ("goalkeeper_passes", "Goalkeeper passes"),
                ("goalkeeper_pass_accuracy_pct", "Goalkeeper pass accuracy"), ("first_line_breaks", "Passes breaking the first pressing line"),
                ("passes_under_pressure", "Passes under pressure"), ("pass_accuracy_under_pressure_pct", "Pass accuracy under pressure"),
                ("long_pass_share_pct", "Long passes (>32 m)")])
w(f"Kingsbridge build up with a back three (Mbeki inverting) and play short from the goalkeeper. Northgate avoid the press: "
  f"{as_['goal_kicks_short_pct']}% of goal kicks short, and Saarinen completed only {as_['goalkeeper_pass_accuracy_pct']}% of his passes.\n")
w("### Midfield progression\n")
table(None, T, [("possession_pct", "Possession"), ("passes", "Passes"), ("pass_accuracy_pct", "Pass accuracy"),
                ("progressive_passes", "Progressive passes"), ("progressive_carries", "Progressive carries"),
                ("receptions_between_lines", "Receptions between the lines (≥3 m space)"),
                ("halfspace_receptions_final_40pct", "Half-space receptions (final 40%)"), ("switches", "Switches of play (>30 m wide)")])
w("![Pass networks](output/figures/analysis_pass_networks.png)\n")
w("### Final third\n")
table(None, T, [("final_third_entries", "Final-third entries"), ("box_entries", "Box entries"), ("deep_completions", "Deep completions"),
                ("crosses", "Crosses"), ("crosses_completed", "Crosses reaching a team-mate"), ("cutbacks", "Cutbacks"),
                ("zone14_receptions", "Receptions in zone 14")])
w("### Finishing\n")
table(None, T, [("shots", "Shots"), ("shots_on_target", "On target"), ("goals", "Goals"), ("xg", "xG"), ("xg_per_shot", "xG per shot"),
                ("xgot", "xGOT"), ("goals_minus_xg", "Goals − xG"), ("big_chances", "Big chances (xG ≥ 0.3)"),
                ("big_chances_scored", "Big chances scored"), ("shots_in_box_pct", "Shots from inside the box"), ("headers", "Headed shots")])
w("![Shot map](output/figures/analysis_shot_map.png)\n")
fin = sorted([p for p in A["players"] if p["shots"]], key=lambda r: -r["xg"])[:6]
w("| Player | Team | Shots | On target | xG | Goals |")
w("|---|---|---|---|---|---|")
for p in fin:
    w(f"| {p['name']} | {p['team']} | {p['shots']} | {p['shots_on_target']} | {p['xg']:.2f} | {p['goals']} |")
w("")

# ------------------------------------------------------------- 3 defending
w("## 3. Defensive play\n")
w("Goals conceded say little on their own. What matters is how hard each side made it for the opponent to create chances.\n")
w(f"| | {NAME[HID]} | {NAME[AID]} |")
w("|---|---|---|")
rows = [("xGA", "xga"), ("Shots conceded", "shots_conceded"), ("Big chances conceded", "big_chances_conceded"),
        ("PPDA (lower = more pressing)", "ppda"), ("Tackles", "tackles"), ("Tackles won %", "tackles_won_pct"), ("Interceptions", "interceptions"),
        ("Take-ons conceded (1v1)", "take_ons_conceded"), ("Opponent crosses reaching target %", "opp_cross_success_pct"),
        ("Zone-14 receptions conceded", "zone14_receptions_conceded"), ("Offsides won", "offsides_won"),
        ("Rest defence (players behind ball when attacking)", "rest_defence_players"), ("Fouls", "fouls")]
for lab, k in rows:
    w(f"| {lab} | {fmt(T[HID][k])} | {fmt(T[AID][k])} |")
for lab, k in (("Defensive line out of possession (m)", "def_line"), ("Team length out of possession (m)", "length"),
               ("Team width out of possession (m)", "width"), ("Gap defence–midfield (m)", "line_gap")):
    w(f"| {lab} | {fmt(T[HID]['shape_out_of_possession'][k])} | {fmt(T[AID]['shape_out_of_possession'][k])} |")
w("")
w(f"Northgate defended low and compact (length {as_['shape_out_of_possession']['length']} m) and conceded many shots, but mostly low-quality ones "
  f"({hs['xg_per_shot']} xG per Kingsbridge shot). Kingsbridge conceded few shots but {hs['big_chances_conceded']} big chances: the classic profile of a "
  "possession side with a high line that is vulnerable in transition.\n")

# ------------------------------------------------------------- 4 transitions
w("## 4. Transitions\n")
w("### Losing the ball (attack → defence)\n")
table(None, TR, [("losses_in_play", "Ball losses in open play"), ("regains_within_5s_after_loss", "Won back within 5 s (counter-press)"),
                 ("counterpress_success_pct", "Counter-press success"), ("median_seconds_to_regain", "Median seconds to win the ball back"),
                 ("exposed_losses", "Losses with fewer than 7 behind the ball"), ("median_recovery_seconds_7_behind_ball", "Median seconds to get 7 back behind the ball"),
                 ("counter_shots_conceded", "Counter-attack shots conceded"), ("counter_xg_conceded", "Counter-attack xG conceded")])
w("### Winning the ball (defence → attack)\n")
table(None, TR, [("regains_in_play", "Regains in open play"), ("avg_regain_height_m", "Average regain height (m from own goal)"),
                 ("first_pass_forward_after_regain_pct", "First pass forward after regain"), ("regains_to_shot_within_15s", "Regains leading to a shot within 15 s"),
                 ("xg_from_fast_attacks", "xG from fast attacks"), ("median_seconds_regain_to_shot", "Median seconds regain → shot")])
w("![Regains](output/figures/analysis_regains.png)\n")
w("Two different transition profiles: Kingsbridge win the ball high and immediately (counter-press), Northgate win it deep and go forward fast. "
  "Northgate's two counter-attack goals came from exactly the weakness the pre-match analysis predicted.\n")

# ------------------------------------------------------------- 5 tactics
w("## 5. Tactical systems and match-ups\n")
w("### Formations over time\n")
w("| Clock | Team | Formation | Players |")
w("|---|---|---|---|")
for x in json.load(open(os.path.join(ROOT, "output", "tactical_states.json"))):
    w(f"| {x['clock']} | {x['team']} | {x['formation']} | {x['players_on_pitch']} |")
w("")
w("### By match phase\n")
w(f"| Phase | Min | Poss {HID} | Field tilt {HID} | PPDA {HID} | xG {HID} | xG {AID} | PPDA {AID} | Line {HID} (out of poss.) | Line {AID} (out of poss.) |")
w("|---|---|---|---|---|---|---|---|---|---|")
for p in A["phases"]:
    h, a = p[HID], p[AID]
    w(f"| {p['phase']} | {p['minutes']} | {fmt(h['possession_pct'], '%')} | {fmt(h['field_tilt_pct'], '%')} | {fmt(h['ppda'])} | {fmt(h['xg'])} | {fmt(a['xg'])} | {fmt(a['ppda'])} | {fmt(h['def_line_out_of_possession'])} | {fmt(a['def_line_out_of_possession'])} |")
w("")
w("![Kingsbridge shapes](output/figures/shape_kingsbridge.png)\n")
w("![Northgate shapes](output/figures/shape_northgate.png)\n")
w("### Pressing triggers\n")
w(f"| Trigger | {NAME[HID]} | {NAME[AID]} |")
w("|---|---|---|")
trig = sorted(set(T[HID]["pressures_by_trigger"]) | set(T[AID]["pressures_by_trigger"]))
for k in trig:
    w(f"| {k.replace('_', ' ')} | {T[HID]['pressures_by_trigger'].get(k, 0)} | {T[AID]['pressures_by_trigger'].get(k, 0)} |")
w(f"| total pressures | {hs['pressures']} | {as_['pressures']} |")
w(f"| of which counter-press | {hs['counterpress_pressures']} | {as_['counterpress_pressures']} |")
w("")
w("### Game state\n")
w("| Team | State | Minutes | Possession | xG for | xG against | Avg def. line (m) |")
w("|---|---|---|---|---|---|---|")
for t in (HID, AID):
    for st, v in GS[t].items():
        w(f"| {NAME[t]} | {st} | {v['minutes']} | {fmt(v['possession_pct'], '%')} | {v['xg_for']} | {v['xg_against']} | {fmt(v['avg_def_line_m'])} |")
w("")
ngl, ngv = GS[AID].get("leading", {}).get("avg_def_line_m"), GS[AID].get("level", {}).get("avg_def_line_m")
kbl, kbt = GS[HID].get("level", {}).get("avg_def_line_m"), GS[HID].get("trailing", {}).get("avg_def_line_m")
w(f"Northgate's defensive line: {ngv} m when level vs {ngl} m when leading. Kingsbridge: {kbl} m when level vs {kbt} m when trailing. "
  "Note that the trailing periods overlap with the red card, so game state and numerical inferiority are mixed.\n")

# ------------------------------------------------------------- 6 players
w("## 6. Individual players\n")
w("Match rating = a transparent formula (6.0 + goals, assists, xG, xA, xT, defensive actions, pass accuracy − cards and fouls). It is not a scout's judgement.\n")
w("| Player | Team | Min | Rating | Form (last 5) | xG | xA | xT added | Prog. actions | Between lines | Tackles won | Key note |")
w("|---|---|---|---|---|---|---|---|---|---|---|---|")
for p in sorted(A["players"], key=lambda r: -r["rating"]):
    note = CTX["player_profiles"].get(p["player_id"], {}).get("note", "")
    w(f"| {p['name']} | {p['team']} | {p['minutes']:.0f} | **{p['rating']}** | {fmt(p['form_last5'])} | {p['xg']:.2f} | {fmt(p['xa'])} | {fmt(p['xt_added'])} | {p['progressive_actions']} | {p['receptions_between_lines']} | {p['tackles_won']} | {note} |")
w("")
w("### Absences and squad composition\n")
for t, side in ((HID, "home"), (AID, "away")):
    for ab in CTX["teams"][side]["absences"]:
        w(f"- **{NAME[t]} – {ab['player']} ({ab['pos']})**: {ab['reason']}. {ab['impact']}")
w("- **In-match:** losing Brannigan (red card) hurt more than any other absence. Without a holding midfielder Northgate found the space between the lines (Halvorsen's assist at 67').\n")

# ------------------------------------------------------------- 7 physical & mental
w("## 7. Physical and mental factors\n")
w("### Physical (measured from tracking)\n")
w(f"| Block | {HID} m/player/min | {HID} HI m/player/min | {AID} m/player/min | {AID} HI m/player/min |")
w("|---|---|---|---|---|")
for a, b in zip(A["physical_per_15"][HID], A["physical_per_15"][AID]):
    w(f"| {a['block']} | {a['m_per_player_min']} | {a['hi_m_per_player_min']} | {b['m_per_player_min']} | {b['hi_m_per_player_min']} |")
w("")
w("![Physical](output/figures/analysis_physical.png)\n")
top = sorted([p for p in A["players"] if p["minutes"] > 60 and p["position"] != "GK"], key=lambda r: -r["distance_km"])[:6]
w("| Player | Km | HI runs | HI km | Sprints | Accelerations | Top km/h |")
w("|---|---|---|---|---|---|---|")
for p in top:
    w(f"| {p['name']} | {p['distance_km']} | {p['hi_runs']} | {p['hi_distance_km']} | {p['sprints']} | {p['accelerations']} | {p['top_speed_kmh']} |")
w("")
sch = CTX["match_context"]["schedule"]
w(f"*Context:* {NAME[HID]} – {sch['home']['previous_match']} ({sch['home']['rest_days']} days rest, load: {sch['home']['load']}). "
  f"{NAME[AID]} – {sch['away']['rest_days']} days rest, travel: {sch['away']['travel']}. The model applies a higher fatigue rate to Kingsbridge.\n")
w("### Mental (partly modelled, use as supporting evidence only)\n")
w("![Morale](output/figures/analysis_morale.png)\n")
w("**Measured reaction after each goal (conceding team, 10 min before vs. 10 min after):**\n")
w("| Goal | Conceding team | Score after | Possession | Pass accuracy | Fouls | xG |")
w("|---|---|---|---|---|---|---|")
for r in A["reaction_after_goals"]:
    b, a = r["before"], r["after"]
    w(f"| {r['clock']} | {r['conceding_team']} | {r['score_after']} | {fmt(b['possession_pct'])}% → {fmt(a['possession_pct'])}% | {fmt(b['pass_accuracy_pct'])}% → {fmt(a['pass_accuracy_pct'])}% | {b['fouls']} → {a['fouls']} | {fmt(b['xg'])} → {fmt(a['xg'])} |")
w("")
for t, side in ((HID, "home"), (AID, "away")):
    m = CTX["teams"][side]["mental"]
    w(f"- **{NAME[t]}:** {m['summary']} {m['behind_record']} {m['pressure_handling']}")
w(f"- **Discipline:** {hs['yellow_cards']} yellow + {hs['red_cards']} red for Kingsbridge, {as_['yellow_cards']} yellow for Northgate "
  f"(referee average {CTX['match_context']['referee']['avg_yellows_per_game']} yellows per game). Pass accuracy under pressure: "
  f"{hs['pass_accuracy_under_pressure_pct']}% vs {as_['pass_accuracy_under_pressure_pct']}%.\n")

# ------------------------------------------------------------- 8 set pieces
w("## 8. Set pieces\n")
w(f"| | {NAME[HID]} | {NAME[AID]} |")
w("|---|---|---|")
for lab, k in (("Corners", "corners"), ("Short corners", "corners_short"), ("Corner deliveries", "corner_deliveries"),
               ("First contact won from corners", "corner_first_contact_won"), ("Long throws into the box", "long_throws_into_box"),
               ("Free-kick crosses", "free_kick_crosses"), ("Direct free-kick shots", "direct_free_kick_shots"),
               ("Set-piece shots", "set_piece_shots"), ("Set-piece xG", "set_piece_xg"), ("Set-piece goals", "set_piece_goals"), ("Penalties", "penalties"),
               ("Corner delivery", "delivery"), ("Defending corners", "marking_scheme_defending")):
    w(f"| {lab} | {fmt(SP[HID][k])} | {fmt(SP[AID][k])} |")
w(f"| Markers beaten in the air (by opponent) | {', '.join(f'{k} ({v})' for k, v in SP[AID]['beaten_markers'].items()) or '–'} | {', '.join(f'{k} ({v})' for k, v in SP[HID]['beaten_markers'].items()) or '–'} |")
w("")
w("Kingsbridge's corners came mainly from pressure on the box. Northgate used Gallagher's long throws as an extra set-piece weapon. "
  "No penalties were given (the generator never adds penalties because they would change the scripted score).\n")

# ------------------------------------------------------------- 9 advanced
w("## 9. Advanced statistics\n")
adv = [("xG", "xg"), ("xGA", "xga"), ("xG difference", "xgd"), ("xG per shot", "xg_per_shot"), ("xGOT", "xgot"), ("PPDA", "ppda"),
       ("Field tilt", "field_tilt_pct"), ("Progressive passes", "progressive_passes"), ("Deep completions", "deep_completions"),
       ("Big chances", "big_chances"), ("xT added (passes + carries)", "xt_added"), ("Set-piece xG", "set_piece_xg"),
       ("Open-play xG", "xg_open_play"), ("Counter-attack xG", "xg_counter"), ("High turnovers", "high_turnovers"),
       ("High turnovers → shot ≤15 s", "high_turnovers_to_shot_15s")]
w(f"| Metric | {NAME[HID]} | {NAME[AID]} |")
w("|---|---|---|")
for lab, k in adv:
    w(f"| {lab} | {fmt(T[HID][k], '%' if k.endswith('_pct') else '')} | {fmt(T[AID][k], '%' if k.endswith('_pct') else '')} |")
w("")
w("### Opponent quality: form over the last 8 matches\n")
w(f"| | {NAME[HID]} | {NAME[AID]} |")
w("|---|---|---|")
F = A["form"]
for lab, f in (("Last 5", lambda x: x["last5"]), ("Points per game", lambda x: x["points_per_game"]), ("xG / xGA per game", lambda x: f"{x['xg_per_game']} / {x['xga_per_game']}"),
               ("vs top-half teams (ppg, xG/xGA)", lambda x: f"{x['vs_top_half']['ppg']} ({x['vs_top_half']['xg']}/{x['vs_top_half']['xga']})"),
               ("vs bottom-half teams (ppg, xG/xGA)", lambda x: f"{x['vs_bottom_half']['ppg']} ({x['vs_bottom_half']['xg']}/{x['vs_bottom_half']['xga']})"),
               ("Average possession", lambda x: x["possession_avg"]), ("Set-piece xG per game", lambda x: x["set_piece_xg_per_game"])):
    w(f"| {lab} | {f(F[HID])} | {f(F[AID])} |")
w("")
w("Kingsbridge's numbers are inflated by bottom-half opponents (xGA 0.50 against them, 1.72 against top-half sides). Northgate are clearly weaker against top-half teams. "
  "Against each other the gap was smaller than the table suggests.\n")

# ------------------------------------------------------------- 10 match-ups
w("## 10. Opponent analysis: match-ups\n")
w("The key question is not how good each team is, but how their specific strengths and weaknesses fit together.\n")
for m in A["matchups"]:
    w(f"### {m['id']} – {m['title']}\n")
    w(f"*Pre-match expectation:* {m['expectation']} (favoured: {m['favoured_pre_match']})\n")
    w("*Measured:* " + "; ".join(f"{k.replace('_', ' ')}: {v}" for k, v in m["measured"].items()) + "\n")
    w(f"**Verdict:** {m['verdict']}\n")

# ------------------------------------------------------------- 11 context
w("## 11. Match context\n")
mc = CTX["match_context"]
w(f"- **Venue:** {mc['venue']['name']}, {mc['venue']['surface']} ({mc['venue']['pitch_condition']}), {mc['venue']['attendance']:,} spectators ({mc['venue']['away_fans']:,} away).")
w(f"- **Weather:** {mc['weather']['summary']}. {mc['weather']['impact']}")
w(f"- **Referee:** {mc['referee']['name']}: {mc['referee']['style']} Season averages {mc['referee']['avg_yellows_per_game']} yellows, {mc['referee']['avg_fouls_per_game']} fouls. "
  f"This match: {hs['yellow_cards'] + as_['yellow_cards']} yellows (including a second yellow), {hs['fouls'] + as_['fouls']} fouls. {mc['referee']['impact']}")
w(f"- **Stakes:** {mc['stakes']['summary']}")
w(f"- **Schedule:** Kingsbridge {mc['schedule']['home']['rest_days']} days rest after 120 minutes in the cup; Northgate {mc['schedule']['away']['rest_days']} days rest, {mc['schedule']['away']['travel']}.")
w("- **Head to head:** " + "; ".join(f"{h['result']} ({h['note']})" for h in mc["head_to_head"]) + ".")
w(f"- **Game flow:** Kingsbridge trailed for {GS[HID].get('trailing', {}).get('minutes', 0)} minutes and never led. That partly explains their territorial dominance and Northgate's deep line.\n")

# ------------------------------------------------------------- 12 coaching
w("## 12. Coaching and substitutions\n")
for t in (HID, AID):
    c = A["coaching"][t]
    w(f"### {c['coach']} ({NAME[t]})\n")
    w(f"- Game plan: {CTX['teams']['home' if t == HID else 'away']['coach_profile']['game_plan']}")
    w(f"- First substitution: {c['first_sub_this_match']}' (season average {c['profile_first_sub_avg']}'), {c['subs_made']} substitutions, {c['formation_changes']} formation changes.")
    w(f"- Expected when trailing: {c['behaviour_when_behind_expected']} Expected when leading: {c['behaviour_when_ahead_expected']}")
    w(f"- Did they follow their profile? {c['followed_profile']}")
    w(f"- Bench quality (pre-match rating): {c['bench_quality_rating']}/100\n")
    w("| Clock | Off | On | New formation | On-player: min / G / A / xG / rating |")
    w("|---|---|---|---|---|")
    for s in c["substitutions"]:
        o = s["on_player_contribution"]
        w(f"| {s['clock']} | {s['off']} | {s['on']} | {s['new_formation'] or '–'} | {fmt(o['minutes'])} / {fmt(o['goals'])} / {fmt(o['assists'])} / {fmt(o['xg'])} / {fmt(o['rating'])} |")
    w("")

# ------------------------------------------------------------- definitions
w("## Definitions and limitations\n")
for k, v in A["definitions"].items():
    w(f"- **{k.replace('_', ' ')}:** {v}")
w("- **Model limits:** synthetic 1 Hz data; xG, xGOT and xT come from simple location models; confidence/morale is a model state, not a measurement; "
  "penalties are never generated; only scripted shots can become goals.")
open(os.path.join(ROOT, "MATCH_ANALYSIS.md"), "w").write("\n".join(L))
print("MATCH_ANALYSIS.md written")
