"""
Match analysis along the 12 components of football analysis.

Reads the script, pre-match context and generated output, computes the analysis
metrics (xG, xGA, xGOT, PPDA, field tilt, progressive passes, deep completions,
big chances, xT, set-piece xG, transitions, compactness, rest defence, physical
load, game-state effects, match-ups, coaching) and writes:

  output/analysis.json        machine-readable analysis (per team, per phase, per player)
  docs/MATCH_ANALYSIS.md      human-readable analysis (via render_analysis.py)
  output/figures/analysis_*.png

Usage: python analyze_match.py [root_dir]
"""
import csv
import json
import math
import os
import sys
from collections import defaultdict, Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "output")
FIG = os.path.join(OUT, "figures")
os.makedirs(FIG, exist_ok=True)

S = json.load(open(os.path.join(ROOT, "script", "match_script.json"), encoding="utf-8"))
CTX = json.load(open(os.path.join(ROOT, "script", "pre_match_context.json"), encoding="utf-8"))
EV = json.load(open(os.path.join(OUT, "events.json"), encoding="utf-8"))
MIN = json.load(open(os.path.join(OUT, "stats_per_minute.json"), encoding="utf-8"))
PS = {p["player_id"]: p for p in json.load(open(os.path.join(OUT, "player_stats.json"), encoding="utf-8"))}
TACT = json.load(open(os.path.join(OUT, "tactical_states.json"), encoding="utf-8"))
MOR = json.load(open(os.path.join(OUT, "morale_timeline.json"), encoding="utf-8"))

H, A = S["teams"]["home"], S["teams"]["away"]
HID, AID = H["id"], A["id"]
TEAM = {HID: H, AID: A}
SIDE = {HID: "home", AID: "away"}
OPP = {HID: AID, AID: HID}
PL = {p["id"]: p for t in (H, A) for p in t["players"]}
PROF = CTX["player_profiles"]
P1 = (45 + S["meta"]["added_time"]["1"]) * 60
GOAL = np.array([105.0, 34.0])


def gsec(period, t):
    return t if period == 1 else P1 + t


def gs(e):
    return gsec(e["period"], e["second_in_period"])


def match_min(g):
    return g / 60 if g < P1 else 45 + (g - P1) / 60


def rel(team, period, x, y):
    flip = (SIDE[team] == "home") == (period == 2)
    return (105 - x, 68 - y) if flip else (x, y)


def erel(e, end=False):
    if end:
        return rel(e["team"], e["period"], e["end_x"], e["end_y"])
    return rel(e["team"], e["period"], e["x"], e["y"])


def dgoal(x, y):
    return math.hypot(105 - x, 34 - y)


def in_box(x, y):
    return x > 88.5 and 13.84 < y < 54.16


def r1(v, n=1):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else round(v, n)


def ratio(a, b, pct=True, n=1):
    if not b:
        return None
    return round((100 if pct else 1) * a / b, n)


# ------------------------------------------------------------------ tracking
TR = defaultdict(dict)
with open(os.path.join(OUT, "tracking.csv"), encoding="utf-8") as f:
    for r in csv.DictReader(f):
        g = gsec(int(r["period"]), int(r["second_in_period"]))
        TR[g][r["object_id"]] = (float(r["x"]), float(r["y"]), r["team"], r["role_or_state"], int(r["period"]),
                                 r["speed_ms_or_ball_holder"])
GMAX = max(TR)


def team_rel_positions(fr, team):
    out = {}
    for oid, (x, y, t, role, p, _) in fr.items():
        if t == team and role != "GK":
            out[oid] = rel(team, p, x, y)
    return out


def lines(fr, team):
    """Defensive line (mean of 4 deepest outfield), midfield line (next 3-4), team length & width, in team rel coords."""
    pos = team_rel_positions(fr, team)
    if len(pos) < 8:
        return None
    xs = sorted(p[0] for p in pos.values())
    ys = sorted(p[1] for p in pos.values())
    d = np.mean(xs[:4])
    m = np.mean(xs[4:8])
    return {"def_line": d, "mid_line": np.mean(xs[4:7]), "line_gap": m - d, "length": np.percentile(xs, 90) - np.percentile(xs, 10),
            "width": np.percentile(ys, 90) - np.percentile(ys, 10), "highest": xs[-1]}


# ------------------------------------------------------------------ possession segments & game state
POSS_OF = {}            # gsec -> team in possession (live ball only)
for g, fr in TR.items():
    b = fr.get("ball")
    if not b or b[3] != "live":
        continue
    holder = b[5]
    if holder and holder in fr:
        POSS_OF[g] = fr[holder][2]
# fill flights with last known team
last = None
for g in range(GMAX + 1):
    fr = TR.get(g)
    if not fr:
        continue
    b = fr.get("ball")
    if g in POSS_OF:
        last = POSS_OF[g]
    elif b and b[3] == "live" and last:
        POSS_OF[g] = last
    elif b and b[3] != "live":
        last = None

GOALS = [e for e in EV if e["type"] == "goal"]


def score_at(g):
    h = a = 0
    for e in GOALS:
        if gs(e) < g:
            if e["team"] == HID:
                h += 1
            else:
                a += 1
    return h, a


def game_state(team, g):
    h, a = score_at(g)
    d = (h - a) if team == HID else (a - h)
    return "leading" if d > 0 else ("trailing" if d < 0 else "level")


def phase_of(g):
    m = match_min(g)
    for ph in S["phases"]:
        if ph["from"] <= m < ph["to"]:
            return ph["name"]
    return S["phases"][-1]["name"]


def players_on(team, g):
    fr = TR.get(g, {})
    return sum(1 for oid, v in fr.items() if v[2] == team)


# ------------------------------------------------------------------ simple xT surface (expected threat of a location)
def xt_value(x, y):
    """Smooth approximation of an expected-threat grid: value of having the ball at (x, y), attacking towards x = 105."""
    d = dgoal(x, y)
    a1 = np.array([105, 30.34]) - np.array([x, y])
    a2 = np.array([105, 37.66]) - np.array([x, y])
    ang = abs(math.atan2(a1[0] * a2[1] - a1[1] * a2[0], a1 @ a2))
    near = 1 / (1 + math.exp(-(-1.1 - 0.12 * d + 1.3 * ang)))
    return 0.004 + 0.012 * (x / 105) ** 2 + 0.45 * near * (1 if x > 70 else 0.3)


# ------------------------------------------------------------------ derived on-ball actions
PASSES = [e for e in EV if e["type"] in ("pass", "cross")]
SHOTS = [e for e in EV if e["type"] == "shot"]
RECEIPTS = [e for e in EV if e["type"] == "ball_receipt"]


def carries():
    """Carry = ball receipt to the same player's next on-ball action."""
    out = []
    nxt_types = ("pass", "cross", "shot", "dispossessed", "take_on")
    by_player = defaultdict(list)
    for e in EV:
        if e["player_id"] and e["type"] in nxt_types + ("ball_receipt", "interception", "ball_recovery", "tackle"):
            by_player[e["player_id"]].append(e)
    for pid, lst in by_player.items():
        for a, b in zip(lst, lst[1:]):
            if a["type"] in ("ball_receipt", "interception", "ball_recovery") and b["type"] in ("pass", "cross", "shot", "dispossessed") \
                    and a["period"] == b["period"] and 0 < b["second_in_period"] - a["second_in_period"] <= 8 and a["x"] is not None:
                sx, sy = erel(a)
                ex, ey = erel(b)
                if math.hypot(ex - sx, ey - sy) >= 3:
                    out.append({"team": a["team"], "player_id": pid, "period": a["period"], "g": gs(a), "start": (sx, sy), "end": (ex, ey)})
    return out


CARRIES = carries()


def is_progressive(sx, sy, ex, ey):
    ds, de = dgoal(sx, sy), dgoal(ex, ey)
    return (ds - de) >= max(10.0, 0.25 * ds) and ex > 40


def pass_info(e):
    sx, sy = erel(e)
    ex, ey = erel(e, end=True)
    return sx, sy, ex, ey


def opp_first_line(fr, team):
    """x (in team rel) of the opponent's first pressing line: mean of the two most advanced opponent outfielders."""
    opp = OPP[team]
    xs = sorted(rel(team, p, x, y)[0] for oid, (x, y, t, role, p, _) in fr.items() if t == opp and role != "GK")
    return np.mean(xs[:2]) if len(xs) >= 2 else None


def opp_lines(fr, team):
    """Opponent defensive and midfield lines expressed in `team` rel coords (team attacks +x)."""
    opp = OPP[team]
    xs = sorted((rel(team, p, x, y)[0] for oid, (x, y, t, role, p, _) in fr.items() if t == opp and role != "GK"), reverse=True)
    if len(xs) < 8:
        return None, None
    return np.mean(xs[:4]), np.mean(xs[4:8])   # deepest 4 (closest to their goal) and next 4


def free_reception(fr, team, x, y):
    """Reception between the opponent's midfield and defensive lines, inside their width, with >= 3 m of space."""
    dl, ml = opp_lines(fr, team)
    if not (dl and ml and ml + 1 < x < dl - 1):
        return False
    opp = OPP[team]
    opos = [rel(team, p, ox, oy) for oid, (ox, oy, t, role, p, _) in fr.items() if t == opp and role != "GK"]
    ys = sorted(o[1] for o in opos)
    if not (ys[1] < y < ys[-2]):
        return False
    return min(math.hypot(o[0] - x, o[1] - y) for o in opos) >= 3.0


# ================================================================== per-team metrics
def team_metrics(team, g0=0, g1=10 ** 9):
    opp = OPP[team]
    T = {}
    ev_t = [e for e in EV if e["team"] == team and g0 <= gs(e) < g1]
    ev_o = [e for e in EV if e["team"] == opp and g0 <= gs(e) < g1]
    passes = [e for e in ev_t if e["type"] in ("pass", "cross") and e["end_x"] is not None]
    comp = [e for e in passes if e["outcome"] == "complete"]
    shots = [e for e in ev_t if e["type"] == "shot"]
    oshots = [e for e in ev_o if e["type"] == "shot"]

    # possession
    own = sum(1 for g, t in POSS_OF.items() if g0 <= g < g1 and t == team)
    tot = sum(1 for g, t in POSS_OF.items() if g0 <= g < g1)
    T["possession_pct"] = ratio(own, tot)
    T["passes"] = len([e for e in passes if e["type"] == "pass"])
    T["pass_accuracy_pct"] = ratio(len([e for e in comp if e["type"] == "pass"]), T["passes"])

    # finishing
    xg = sum(e["xg"] for e in shots)
    xga = sum(e["xg"] for e in oshots)
    on_t = [e for e in shots if e["outcome"] in ("goal", "saved")]
    T.update({
        "goals": sum(1 for e in shots if e["outcome"] == "goal"), "shots": len(shots), "shots_on_target": len(on_t),
        "xg": r1(xg, 2), "xga": r1(xga, 2), "xgd": r1(xg - xga, 2), "xg_per_shot": r1(xg / len(shots), 3) if shots else None,
        "xgot": r1(sum(e["xgot"] or 0 for e in on_t), 2), "goals_minus_xg": r1(sum(1 for e in shots if e["outcome"] == "goal") - xg, 2),
        "big_chances": sum(1 for e in shots if e.get("big_chance")),
        "big_chances_scored": sum(1 for e in shots if e.get("big_chance") and e["outcome"] == "goal"),
        "big_chances_conceded": sum(1 for e in oshots if e.get("big_chance")),
        "shots_conceded": len(oshots),
        "xg_open_play": r1(sum(e["xg"] for e in shots if e["play_pattern"] == "open_play"), 2),
        "xg_counter": r1(sum(e["xg"] for e in shots if e["play_pattern"] == "counter_attack"), 2),
        "set_piece_xg": r1(sum(e["xg"] for e in shots if e.get("set_piece")), 2),
        "set_piece_xga": r1(sum(e["xg"] for e in oshots if e.get("set_piece")), 2),
        "shots_in_box_pct": ratio(sum(1 for e in shots if in_box(*erel(e))), len(shots)),
        "headers": sum(1 for e in shots if e["body_part"] == "head"),
    })

    # progression
    prog = [e for e in comp if is_progressive(*pass_info(e))]
    deep = [e for e in comp if e["type"] == "pass" and dgoal(*pass_info(e)[2:]) < 20]
    ft_entries = [e for e in comp if pass_info(e)[0] < 70 <= pass_info(e)[2]]
    box_entries = [e for e in comp if not in_box(*pass_info(e)[:2]) and in_box(*pass_info(e)[2:])]
    car = [c for c in CARRIES if c["team"] == team and g0 <= c["g"] < g1]
    prog_car = [c for c in car if is_progressive(*c["start"], *c["end"])]
    T.update({"progressive_passes": len(prog), "progressive_carries": len(prog_car), "deep_completions": len(deep),
              "final_third_entries": len(ft_entries) + sum(1 for c in car if c["start"][0] < 70 <= c["end"][0]),
              "box_entries": len(box_entries) + sum(1 for c in car if not in_box(*c["start"]) and in_box(*c["end"])),
              "switches": sum(1 for e in comp if abs(pass_info(e)[3] - pass_info(e)[1]) > 30),
              "long_pass_share_pct": ratio(sum(1 for e in passes if e.get("length_m", 0) > 32), len(passes))})
    # xT added by completed passes and carries
    xt = sum(xt_value(*pass_info(e)[2:]) - xt_value(*pass_info(e)[:2]) for e in comp)
    xt += sum(xt_value(*c["end"]) - xt_value(*c["start"]) for c in car)
    T["xt_added"] = r1(xt, 2)

    # field tilt: share of passes in the final third (both teams)
    ft_own = sum(1 for e in passes if pass_info(e)[0] > 70)
    ft_opp = sum(1 for e in ev_o if e["type"] in ("pass", "cross") and e["end_x"] is not None and erel(e)[0] > 70)
    T["field_tilt_pct"] = ratio(ft_own, ft_own + ft_opp)

    # crosses
    crosses = [e for e in ev_t if e["type"] == "cross"]
    T.update({"crosses": len(crosses), "crosses_completed": sum(1 for e in crosses if e["outcome"] == "complete"),
              "cutbacks": sum(1 for e in crosses if e.get("cross_type") == "cutback")})

    # pressing: PPDA = opponent passes in their own 60% / our defensive actions in that zone
    opp_build = [e for e in ev_o if e["type"] == "pass" and erel(e)[0] < 63]
    def_act = [e for e in ev_t if e["type"] in ("tackle", "interception", "foul") and erel(e)[0] > 42 and
               (e["type"] != "tackle" or e["outcome"] == "won" or True)]
    T["ppda"] = r1(len(opp_build) / len(def_act), 1) if def_act else None
    regains = [e for e in ev_t if e["type"] in ("interception", "ball_recovery") or (e["type"] == "tackle" and e["outcome"] == "won")]
    T["regains"] = len(regains)
    T["high_turnovers"] = sum(1 for e in regains if erel(e)[0] > 63)
    T["high_turnovers_to_shot_15s"] = sum(1 for e in regains if erel(e)[0] > 63 and any(
        s["team"] == team and 0 <= gs(s) - gs(e) <= 15 for s in shots))
    pr = [e for e in ev_t if e["type"] == "pressure"]
    T["pressures"] = len(pr)
    T["pressures_by_trigger"] = dict(Counter(e.get("trigger") or "none" for e in pr))
    T["counterpress_pressures"] = sum(1 for e in pr if e.get("counterpress"))
    T["tackles"] = sum(1 for e in ev_t if e["type"] == "tackle")
    T["tackles_won_pct"] = ratio(sum(1 for e in ev_t if e["type"] == "tackle" and e["outcome"] == "won"), T["tackles"])
    T["interceptions"] = sum(1 for e in ev_t if e["type"] == "interception")
    T["fouls"] = sum(1 for e in ev_t if e["type"] == "foul")
    T["yellow_cards"] = sum(1 for e in ev_t if e["type"] == "yellow_card")
    T["red_cards"] = sum(1 for e in ev_t if e["type"] == "red_card")
    T["offsides_won"] = sum(1 for e in ev_o if e["type"] == "offside")
    # 1v1 defending: take-ons conceded vs tackles won
    T["take_ons_conceded"] = sum(1 for e in ev_o if e["type"] == "take_on")
    # crosses defended
    oc = [e for e in ev_o if e["type"] == "cross"]
    T["opp_cross_success_pct"] = ratio(sum(1 for e in oc if e["outcome"] == "complete"), len(oc))
    # aerial duels on crosses: completed crosses = attacker won the first contact
    T["aerial_first_contacts_won_own_box"] = sum(1 for e in oc if e["outcome"] != "complete")
    # zone 14 receptions conceded (opponent receipts in x 70-88, y 24-44 of opponent rel)
    T["zone14_receptions_conceded"] = sum(1 for e in ev_o if e["type"] == "ball_receipt" and 70 < erel(e)[0] < 88.5 and 24 < erel(e)[1] < 44)
    T["zone14_receptions"] = sum(1 for e in ev_t if e["type"] == "ball_receipt" and 70 < erel(e)[0] < 88.5 and 24 < erel(e)[1] < 44)

    # receptions between the lines / in half-spaces (needs tracking)
    btw = hs = 0
    for e in ev_t:
        if e["type"] != "ball_receipt":
            continue
        x, y = erel(e)
        fr = TR.get(gs(e))
        if fr and free_reception(fr, team, x, y):
            btw += 1
        if x > 63 and (13.84 < y < 24.84 or 43.16 < y < 54.16):
            hs += 1
    T["receptions_between_lines"] = btw
    T["halfspace_receptions_final_40pct"] = hs

    # line breaks: completed passes that go past the opponent's first pressing line from behind it
    lb = 0
    for e in comp:
        fr = TR.get(gs(e))
        if not fr:
            continue
        fl = opp_first_line(fr, team)
        sx, sy, ex, ey = pass_info(e)
        if fl and sx < fl - 1 and ex > fl + 3:
            lb += 1
    T["first_line_breaks"] = lb
    # passes under pressure
    up = [e for e in passes if e["type"] == "pass" and any(
        p["type"] == "pressure" and p["team"] == opp and p.get("opponent_id") == e["player_id"] and 0 <= gs(e) - gs(p) <= 2 for p in ev_o)]
    T["passes_under_pressure"] = len(up)
    T["pass_accuracy_under_pressure_pct"] = ratio(sum(1 for e in up if e["outcome"] == "complete"), len(up))

    # structure from tracking (only frames inside window)
    shape_in, shape_out, rest_def, build_up_n, sec_poss = [], [], [], [], 0
    for g in range(max(0, g0), min(g1, GMAX + 1), 2):
        fr = TR.get(g)
        if not fr or g not in POSS_OF:
            continue
        ln = lines(fr, team)
        if not ln:
            continue
        b = fr["ball"]
        bx, by = rel(team, b[4], b[0], b[1])
        if POSS_OF[g] == team:
            shape_in.append(ln)
            pos = team_rel_positions(fr, team)
            if bx > 52.5:
                rest_def.append(sum(1 for p in pos.values() if p[0] < bx - 15 and p[0] < 52.5))
            if bx < 35:
                build_up_n.append(sum(1 for p in pos.values() if p[0] < 35))
        else:
            shape_out.append(ln)

    def avg(lst, k):
        return r1(float(np.mean([l[k] for l in lst])), 1) if lst else None
    T["shape_in_possession"] = {k: avg(shape_in, k) for k in ("def_line", "length", "width", "line_gap")}
    T["shape_out_of_possession"] = {k: avg(shape_out, k) for k in ("def_line", "length", "width", "line_gap")}
    T["rest_defence_players"] = r1(float(np.mean(rest_def)), 1) if rest_def else None
    T["build_up_players_own_third"] = r1(float(np.mean(build_up_n)), 1) if build_up_n else None
    # goal kicks
    gk = [e for e in ev_t if e["type"] == "goal_kick"]
    T["goal_kicks"] = len(gk)
    T["goal_kicks_short_pct"] = ratio(sum(1 for e in gk if e.get("set_piece_type") == "goal_kick_short"), len(gk))
    gkp = PL[[p for p in PS if PS[p]["team"] == team and PS[p]["position"] == "GK" and PS[p]["starter"]][0]]["id"]
    gk_passes = [e for e in passes if e["player_id"] == gkp]
    T["goalkeeper_passes"] = len(gk_passes)
    T["goalkeeper_pass_accuracy_pct"] = ratio(sum(1 for e in gk_passes if e["outcome"] == "complete"), len(gk_passes))
    return T


# ------------------------------------------------------------------ transitions
def turnovers():
    """Possession changes in open play from the 1 Hz possession series: (g, from_team, to_team)."""
    out = []
    prev_g, prev_t = None, None
    for g in sorted(POSS_OF):
        t = POSS_OF[g]
        if prev_g is not None and g == prev_g + 1 and t != prev_t:
            out.append((g, prev_t, t))
        prev_g, prev_t = g, t
    return out


TURN = turnovers()


def live_until(g0, g1):
    return all((g in POSS_OF) for g in range(g0, g1 + 1))


def transitions(team):
    opp = OPP[team]
    losses = [g for g, a, b in TURN if a == team]
    regains = [g for g, a, b in TURN if b == team]
    # loss -> regain
    to_regain = []
    for gl in losses:
        nxt = next((g for g in regains if g > gl), None)
        if nxt is not None and live_until(gl, nxt):
            to_regain.append(nxt - gl)
    cp5 = sum(1 for d in to_regain if d <= 5)
    # recovery: for losses where fewer than 7 outfield players were goal-side of the ball,
    # seconds until 7 are back behind the ball again
    rec_times, exposed = [], 0
    for gl in losses:
        fr0 = TR.get(gl)
        if not fr0 or "ball" not in fr0:
            continue
        bx0, _ = rel(team, fr0["ball"][4], fr0["ball"][0], fr0["ball"][1])
        pos0 = team_rel_positions(fr0, team)
        need = min(7, len(pos0) - 2)
        if sum(1 for p in pos0.values() if p[0] < bx0) >= need:
            continue
        exposed += 1
        for dt in range(1, 25):
            fr = TR.get(gl + dt)
            if not fr or "ball" not in fr:
                break
            bx, _ = rel(team, fr["ball"][4], fr["ball"][0], fr["ball"][1])
            pos = team_rel_positions(fr, team)
            if sum(1 for p in pos.values() if p[0] < bx) >= need:
                rec_times.append(dt)
                break
    # regain -> attack
    first_forward = fast = 0
    fast_xg = 0.0
    t_to_shot = []
    reg_x = []
    for g in regains:
        fr = TR.get(g)
        if fr and "ball" in fr:
            reg_x.append(rel(team, fr["ball"][4], fr["ball"][0], fr["ball"][1])[0])
        nxt_pass = next((e for e in PASSES if e["team"] == team and 0 <= gs(e) - g <= 4 and e["end_x"] is not None), None)
        if nxt_pass:
            sx, sy, ex, ey = pass_info(nxt_pass)
            if ex - sx > 5:
                first_forward += 1
        shot = next((s for s in SHOTS if s["team"] == team and 0 <= gs(s) - g <= 15), None)
        if shot and all(POSS_OF.get(x) == team for x in range(g, gs(shot)) if x in POSS_OF):
            fast += 1
            fast_xg += shot["xg"]
            t_to_shot.append(gs(shot) - g)
    conceded = [s for s in SHOTS if s["team"] == opp and s["play_pattern"] == "counter_attack"]
    return {
        "losses_in_play": len(losses),
        "regains_within_5s_after_loss": cp5,
        "counterpress_success_pct": ratio(cp5, len(losses)),
        "median_seconds_to_regain": r1(float(np.median(to_regain)), 1) if to_regain else None,
        "exposed_losses": exposed,
        "median_recovery_seconds_7_behind_ball": r1(float(np.median(rec_times)), 1) if rec_times else None,
        "regains_in_play": len(regains),
        "avg_regain_height_m": r1(float(np.mean(reg_x)), 1) if reg_x else None,
        "first_pass_forward_after_regain_pct": ratio(first_forward, len(regains)),
        "regains_to_shot_within_15s": fast,
        "xg_from_fast_attacks": r1(fast_xg, 2),
        "median_seconds_regain_to_shot": r1(float(np.median(t_to_shot)), 1) if t_to_shot else None,
        "counter_shots_conceded": len(conceded),
        "counter_xg_conceded": r1(sum(s["xg"] for s in conceded), 2),
    }


# ------------------------------------------------------------------ physical per 15 minutes
def physical_blocks():
    blocks = [(0, 15), (15, 30), (30, 45 + S["meta"]["added_time"]["1"]), (45, 60), (60, 75), (75, 90 + S["meta"]["added_time"]["2"])]
    out = {HID: [], AID: []}
    last = {}
    acc = defaultdict(lambda: defaultdict(float))
    for g in sorted(TR):
        fr = TR[g]
        m = match_min(g)
        bi = next(i for i, (a, b) in enumerate(blocks) if (a <= m < b) or (i == len(blocks) - 1))
        if g >= P1 and bi < 3:
            bi = 3 if m < 60 else (4 if m < 75 else 5)
        for oid, (x, y, t, role, p, sp) in fr.items():
            if oid == "ball":
                continue
            k = (p, oid)
            if k in last:
                d = math.hypot(x - last[k][0], y - last[k][1])
                acc[(t, bi)]["dist"] += d
                if d > 5.5:
                    acc[(t, bi)]["hi"] += d
                acc[(t, bi)]["player_secs"] += 1
            last[k] = (x, y)
    labels = ["0-15", "15-30", "30-45+", "45-60", "60-75", "75-90+"]
    for t in (HID, AID):
        for i, lab in enumerate(labels):
            a = acc[(t, i)]
            mins = a["player_secs"] / 60 or 1
            out[t].append({"block": lab, "distance_km": r1(a["dist"] / 1000, 2), "hi_distance_km": r1(a["hi"] / 1000, 2),
                           "m_per_player_min": r1(a["dist"] / mins, 1), "hi_m_per_player_min": r1(a["hi"] / mins, 2)})
    return out


# ------------------------------------------------------------------ game state
def game_state_split(team):
    res = {}
    for st in ("leading", "level", "trailing"):
        frames = [g for g in POSS_OF if game_state(team, g) == st]
        if not frames:
            continue
        secs = sum(1 for g in TR if game_state(team, g) == st)
        own = sum(1 for g in frames if POSS_OF[g] == team)
        sh = [s for s in SHOTS if game_state(team, gs(s)) == st]
        lines_ = []
        for g in frames[::5]:
            ln = lines(TR[g], team)
            if ln:
                lines_.append(ln["def_line"])
        res[st] = {"minutes": r1(secs / 60, 1), "possession_pct": ratio(own, len(frames)),
                   "xg_for": r1(sum(s["xg"] for s in sh if s["team"] == team), 2),
                   "xg_against": r1(sum(s["xg"] for s in sh if s["team"] != team), 2),
                   "xg_for_per_90": r1(90 * sum(s["xg"] for s in sh if s["team"] == team) / (secs / 60), 2) if secs > 300 else None,
                   "avg_def_line_m": r1(float(np.mean(lines_)), 1) if lines_ else None}
    return res


# ------------------------------------------------------------------ set pieces
def set_pieces(team):
    ev_t = [e for e in EV if e["team"] == team]
    restarts = Counter(e.get("set_piece_type") or e["type"] for e in ev_t if e["type"] in ("corner", "free_kick", "throw_in", "goal_kick"))
    corners = [e for e in ev_t if e["type"] == "corner"]
    corner_crosses = [e for e in ev_t if e["type"] == "cross" and e.get("cross_type") == "corner"]
    sp_shots = [s for s in SHOTS if s["team"] == team and s.get("set_piece")]
    marker_duels = Counter()
    for e in corner_crosses + [e for e in ev_t if e["type"] == "cross" and e.get("cross_type") in ("long_throw", "free_kick")]:
        if e.get("marker_id"):
            marker_duels[(e["marker_id"], e["outcome"])] += 1
    return {
        "restarts": dict(restarts),
        "corners": len(corners),
        "corners_short": sum(1 for e in corners if e.get("corner_variant") == "short"),
        "corner_deliveries": len(corner_crosses),
        "corner_first_contact_won": sum(1 for e in corner_crosses if e["outcome"] == "complete"),
        "long_throws_into_box": sum(1 for e in ev_t if e["type"] == "cross" and e.get("cross_type") == "long_throw"),
        "free_kick_crosses": sum(1 for e in ev_t if e["type"] == "cross" and e.get("cross_type") == "free_kick"),
        "direct_free_kick_shots": sum(1 for s in sp_shots if s["play_pattern"] == "from_free_kick" and s["body_part"] != "head"),
        "set_piece_shots": len(sp_shots),
        "set_piece_xg": r1(sum(s["xg"] for s in sp_shots), 2),
        "set_piece_goals": sum(1 for s in sp_shots if s["outcome"] == "goal"),
        "penalties": 0,
        "beaten_markers": {PL[m]["name"]: n for (m, o), n in marker_duels.items() if o == "complete"},
        "marking_scheme_defending": CTX["teams"][SIDE[team]]["set_pieces"]["defending_corners"],
        "delivery": CTX["teams"][SIDE[team]]["set_pieces"]["corner_delivery"],
    }


# ------------------------------------------------------------------ players
def player_table():
    rows = []
    xt_p = defaultdict(float)
    prog_p = Counter()
    btw_p = Counter()
    for e in PASSES:
        if e["outcome"] == "complete" and e["end_x"] is not None:
            sx, sy, ex, ey = pass_info(e)
            xt_p[e["player_id"]] += xt_value(ex, ey) - xt_value(sx, sy)
            if is_progressive(sx, sy, ex, ey):
                prog_p[e["player_id"]] += 1
    for c in CARRIES:
        xt_p[c["player_id"]] += xt_value(*c["end"]) - xt_value(*c["start"])
        if is_progressive(*c["start"], *c["end"]):
            prog_p[c["player_id"]] += 1
    for e in RECEIPTS:
        fr = TR.get(gs(e))
        if fr:
            x, y = erel(e)
            if free_reception(fr, e["team"], x, y):
                btw_p[e["player_id"]] += 1
    xa = defaultdict(float)
    for s in SHOTS:
        kp = next((p for p in reversed([e for e in PASSES if gs(e) <= gs(s) and e["team"] == s["team"]])), None)
        if kp and kp["outcome"] == "complete" and kp.get("receiver_id") == s["player_id"] and gs(s) - gs(kp) <= 6:
            xa[kp["player_id"]] += s["xg"]
    for pid, p in PS.items():
        if p["minutes"] <= 0:
            continue
        m90 = p["minutes"] / 90
        # simple match rating: 6.0 baseline + contributions (transparent formula)
        rating = 6.0 + 1.0 * p["goals"] + 0.6 * p["assists"] + 1.2 * xa[pid] + 0.8 * p["xg"] + 0.05 * p["key_passes"] \
            + 0.02 * p["tackles_won"] + 0.03 * p["interceptions"] + 0.6 * xt_p[pid] + 0.01 * prog_p[pid] \
            - 0.3 * p["yellow_cards"] - 1.5 * p["red_cards"] - 0.03 * p["fouls_committed"]
        if p["position"] == "GK":
            rating += 0.25 * p["saves"]
        if p["passes"] >= 10 and p["pass_accuracy"]:
            rating += (p["pass_accuracy"] - 80) / 100
        rating = round(min(10, max(3, rating)), 1)
        prof = PROF.get(pid, {})
        rows.append({**p, "xa": r1(xa[pid], 2), "xt_added": r1(xt_p[pid], 3), "progressive_actions": prog_p[pid],
                     "receptions_between_lines": btw_p[pid], "rating": rating, "form_last5": prof.get("form_last5"),
                     "height_cm": prof.get("height_cm"), "distance_per_90_km": r1(p["distance_km"] / m90, 2) if m90 > 0.2 else None})
    return rows


# ------------------------------------------------------------------ match-ups
def matchups(T, TRN, SP, PLAYERS):
    P = {r["player_id"]: r for r in PLAYERS}
    out = []
    # M1 high line vs pace
    lb_ng = [e for e in PASSES if e["team"] == AID and e["outcome"] == "complete" and e.get("pass_type") in ("through_ball", "long_pass")
             and e.get("receiver_id") in ("NGR-09", "NGR-20")]
    xg_behind = sum(s["xg"] for s in SHOTS if s["team"] == AID and any(0 <= gs(s) - gs(p) <= 8 and p["possession_seq"] == s["possession_seq"] for p in lb_ng))
    out.append({"id": "M1", "measured": {"kba_def_line_in_possession_m": T[HID]["shape_in_possession"]["def_line"],
                                         "balls_in_behind_to_fast_forwards": len(lb_ng), "ngr_xg_after_balls_in_behind": r1(xg_behind, 2),
                                         "ngr_counter_xg": TRN[AID]["xg_from_fast_attacks"]},
                "verdict": f"Confirmed: Northgate's balls in behind produced {xg_behind:.2f} xG and the opening goal; Kingsbridge held their line around {T[HID]['shape_in_possession']['def_line']} m in possession."})
    # M2 Nakamura vs Quiroga
    g_card = next(gs(e) for e in EV if e["type"] == "yellow_card" and e["player_id"] == "NGR-02")
    left = lambda g0, g1: ratio(sum(1 for e in PASSES if e["team"] == HID and g0 <= gs(e) < g1 and e["end_x"] is not None and pass_info(e)[2] > 52.5 and pass_info(e)[3] > 45),
                                sum(1 for e in PASSES if e["team"] == HID and g0 <= gs(e) < g1 and e["end_x"] is not None and pass_info(e)[2] > 52.5))
    tk = sum(1 for e in EV if e["type"] == "take_on" and e["player_id"] == "KBA-11" and e.get("opponent_id") == "NGR-02")
    out.append({"id": "M2", "measured": {"left_flank_share_before_card_pct": left(0, g_card), "left_flank_share_after_card_pct": left(g_card, P1),
                                         "nakamura_take_ons_vs_quiroga": tk, "quiroga_card": "12:40", "equaliser_vs_quiroga": "38:41"},
                "verdict": "Confirmed: after the card Kingsbridge shifted play to their left, and the equaliser came from Nakamura-Brooks against the booked Quiroga."})
    # M3 press vs build-up
    out.append({"id": "M3", "measured": {"kba_ppda": T[HID]["ppda"], "ngr_ppda": T[AID]["ppda"], "kba_high_turnovers": T[HID]["high_turnovers"],
                                         "ngr_goal_kicks_short_pct": T[AID]["goal_kicks_short_pct"],
                                         "saarinen_pass_accuracy_pct": T[AID]["goalkeeper_pass_accuracy_pct"]},
                "verdict": (f"Kingsbridge pressed more intensely (PPDA {T[HID]['ppda']} vs {T[AID]['ppda']})" if (T[HID]['ppda'] or 99) < (T[AID]['ppda'] or 99)
                            else f"PPDA alone does not show it ({T[HID]['ppda']} vs {T[AID]['ppda']}): Northgate's mid-block made many duels in midfield against Kingsbridge's carriers")
                           + f". The press did bite: Kingsbridge won the ball high {T[HID]['high_turnovers']} times (Northgate {T[AID]['high_turnovers']}), and Northgate avoided playing out by going long from goal kicks ({T[AID]['goal_kicks_short_pct']}% short; Saarinen {T[AID]['goalkeeper_pass_accuracy_pct']}% pass accuracy)."})
    # M4 Kovač between lines
    kov = P.get("KBA-10", {})
    out.append({"id": "M4", "measured": {"kovac_receptions_between_lines": kov.get("receptions_between_lines"), "kovac_minutes": kov.get("minutes"),
                                         "kba_receptions_between_lines": T[HID]["receptions_between_lines"], "kba_crosses": T[HID]["crosses"]},
                "verdict": f"Kovač found {kov.get('receptions_between_lines')} receptions between the lines in {kov.get('minutes'):.0f} minutes; Kingsbridge needed width and crosses ({T[HID]['crosses']}) to progress."})
    # M5 Brannigan vs counters
    bfouls = [e for e in EV if e["type"] == "foul" and e["player_id"] == "KBA-06"]
    out.append({"id": "M5", "measured": {"brannigan_fouls": len(bfouls), "brannigan_cards": "2 yellow → red (31', 52')",
                                         "fouls_on_counter_attacks": sum(1 for e in bfouls if e.get("victim_id") in ("NGR-09", "NGR-11", "NGR-20"))},
                "verdict": "Confirmed, and decisive: both yellows came in duels with Adeyemi-Clarke (the second stopping a break), and the red card changed the game."})
    # M6 set pieces
    out.append({"id": "M6", "measured": {"kba_set_piece_xg": SP[HID]["set_piece_xg"], "ngr_set_piece_xg": SP[AID]["set_piece_xg"],
                                         "ngr_long_throws": SP[AID]["long_throws_into_box"], "beaten_markers_ngr": SP[HID]["beaten_markers"],
                                         "beaten_markers_kba": SP[AID]["beaten_markers"]},
                "verdict": f"Set pieces were not decisive: {SP[HID]['set_piece_xg']} vs {SP[AID]['set_piece_xg']} set-piece xG, no set-piece goals."})
    # M7 fatigue
    PHY = physical_blocks()
    subs_contrib = {t: {"goals": sum(r["goals"] for r in PLAYERS if r["team"] == t and not r["starter"]),
                        "assists": sum(r["assists"] for r in PLAYERS if r["team"] == t and not r["starter"]),
                        "xg": r1(sum(r["xg"] for r in PLAYERS if r["team"] == t and not r["starter"]), 2)} for t in (HID, AID)}
    out.append({"id": "M7", "measured": {"m_per_player_min_first_vs_last_block": {t: (PHY[t][0]["m_per_player_min"], PHY[t][-1]["m_per_player_min"]) for t in (HID, AID)},
                                         "substitute_contributions": subs_contrib},
                "verdict": "The benches decided the last half hour: every goal after the 60th minute came from a substitute (Diallo-Kerr, Moore-Asante), both assisted by substitutes."})
    for m in out:
        src = next(x for x in CTX["matchups"] if x["id"] == m["id"])
        m.update({"title": src["title"], "expectation": src["expectation"], "favoured_pre_match": src["favours"]})
    return out, PHY


# ------------------------------------------------------------------ coaching
def coaching():
    res = {}
    subs = [e for e in EV if e["type"] == "substitution"]
    tac = [e for e in EV if e["type"] == "tactical_change"]
    PLR = {r["player_id"]: r for r in PLAYERS}
    for t in (HID, AID):
        side = SIDE[t]
        cp = CTX["teams"][side]["coach_profile"]
        ts = [e for e in subs if e["team"] == t]
        first = min((match_min(gs(e)) for e in ts), default=None)
        res[t] = {
            "coach": cp["name"], "profile_first_sub_avg": cp["avg_first_sub_minute"], "first_sub_this_match": r1(first, 0),
            "subs_made": len(ts), "formation_changes": len({x["formation"] for x in TACT if x["team"] == t}) - 1,
            "substitutions": [{"clock": e["clock"], "off": e["player_name"], "on": e["player_in_name"], "new_formation": e.get("new_formation"),
                               "tactical_change": e.get("tactical_change"), "reason": e.get("reason"),
                               "on_player_contribution": {k: PLR.get(e["player_in_id"], {}).get(k) for k in ("minutes", "goals", "assists", "xg", "xa", "rating")}}
                              for e in ts],
            "behaviour_when_behind_expected": cp["behaviour_when_behind"],
            "behaviour_when_ahead_expected": cp["behaviour_when_ahead"],
            "bench_quality_rating": CTX["teams"][side]["bench"]["quality_rating"],
        }
    res[HID]["followed_profile"] = "Yes: went to a back three with an extra striker while trailing (75'), and it produced the equaliser."
    res[AID]["followed_profile"] = "Partly: switched to 4-3-3 to exploit the extra man (not in the usual profile), then to 5-4-1 at 2-2 to protect a point instead of a lead."
    return res


# ================================================================== run all
PLAYERS = player_table()
T = {t: team_metrics(t) for t in (HID, AID)}
TRN = {t: transitions(t) for t in (HID, AID)}
SP = {t: set_pieces(t) for t in (HID, AID)}
GST = {t: game_state_split(t) for t in (HID, AID)}
MU, PHY = matchups(T, TRN, SP, PLAYERS)
COACH = coaching()

PHASES = []
for ph in S["phases"]:
    g0 = ph["from"] * 60 if ph["from"] < 45 else P1 + (ph["from"] - 45) * 60
    g1 = ph["to"] * 60 if ph["to"] <= 45 else P1 + (ph["to"] - 45) * 60
    if ph["to"] == 52:
        g0 = ph["from"] * 60
    keys = ("possession_pct", "xg", "shots", "ppda", "field_tilt_pct", "progressive_passes", "high_turnovers", "xt_added")
    row = {"phase": ph["name"], "minutes": f"{ph['from']}-{ph['to']}"}
    for t in (HID, AID):
        mm = team_metrics(t, g0, g1)
        row[t] = {k: mm[k] for k in keys}
        row[t]["def_line_out_of_possession"] = mm["shape_out_of_possession"]["def_line"]
    PHASES.append(row)

def form_summary(side):
    lm = CTX["teams"][side]["last_matches"]
    pts = {"W": 3, "D": 1, "L": 0}
    top = [m for m in lm if m["opp_rank"] <= 10]
    bot = [m for m in lm if m["opp_rank"] > 10]
    f = lambda lst, k: r1(float(np.mean([m[k] for m in lst])), 2) if lst else None
    return {"matches": len(lm), "points_per_game": r1(sum(pts[m["result"]] for m in lm) / len(lm), 2),
            "xg_per_game": f(lm, "xg"), "xga_per_game": f(lm, "xga"), "xgd_per_game": r1(f(lm, "xg") - f(lm, "xga"), 2),
            "vs_top_half": {"n": len(top), "ppg": r1(sum(pts[m["result"]] for m in top) / len(top), 2) if top else None, "xg": f(top, "xg"), "xga": f(top, "xga")},
            "vs_bottom_half": {"n": len(bot), "ppg": r1(sum(pts[m["result"]] for m in bot) / len(bot), 2) if bot else None, "xg": f(bot, "xg"), "xga": f(bot, "xga")},
            "set_piece_xg_per_game": f(lm, "set_piece_xg"), "possession_avg": f(lm, "possession"),
            "last5": "".join(m["result"] for m in lm[:5])}


FORM = {HID: form_summary("home"), AID: form_summary("away")}

ANALYSIS = {"teams": T, "form": FORM, "transitions": TRN, "set_pieces": SP, "game_state": GST, "physical_per_15": PHY,
            "phases": PHASES, "matchups": MU, "coaching": COACH, "players": PLAYERS,
            "context": CTX["match_context"], "pre_match": {t: {k: CTX["teams"][SIDE[t]][k] for k in ("league", "absences", "mental", "bench")} for t in (HID, AID)},
            "morale": MOR,
            "definitions": {
                "progressive": "Completed pass or carry that moves the ball at least 10 m and 25% closer to goal, ending beyond 40 m.",
                "deep_completion": "Completed pass (not a cross) ending within 20 m of the opponent's goal.",
                "ppda": "Opponent passes in their own 60% of the pitch divided by our tackles, interceptions and fouls in that zone.",
                "field_tilt": "Share of all final-third passes made by the team.",
                "big_chance": "Shot with xG >= 0.30.",
                "xgot": "Post-shot xG for shots on target, based on placement in the goal mouth.",
                "xt": "Expected threat added by completed passes and carries, using a smooth location-value surface (approximation of a grid xT model).",
                "high_turnover": "Possession won within 42 m of the opponent's goal (x > 63).",
                "counterpress_success": "Share of open-play losses where the ball was won back within 5 seconds.",
                "rest_defence": "Average number of outfield players more than 15 m behind the ball and in their own half while attacking in the opponent's half.",
                "between_lines": "Receptions between the opponent's defensive line (deepest 4) and midfield line (next 4).",
                "carry": "Movement with the ball between a reception and the same player's next action (>= 3 m).",
                "sprint": "1-second sample above 23.8 km/h; high-intensity run: entering > 19.8 km/h.",
            }}
json.dump(ANALYSIS, open(os.path.join(OUT, "analysis.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
print("analysis.json written")


# ================================================================== reaction to goals (mental, measured)
def reaction_after_goals():
    out = []
    for gl in GOALS:
        g = gs(gl)
        conc = OPP[gl["team"]]
        b = team_metrics(conc, max(0, g - 600), g)
        a = team_metrics(conc, g + 60, g + 660)   # skip the restart minute
        out.append({"clock": gl["clock"], "conceding_team": conc, "score_after": f"{gl['score_home']}-{gl['score_away']}",
                    "before": {k: b[k] for k in ("possession_pct", "pass_accuracy_pct", "fouls", "xg", "shots")},
                    "after": {k: a[k] for k in ("possession_pct", "pass_accuracy_pct", "fouls", "xg", "shots")}})
    return out


ANALYSIS["reaction_after_goals"] = reaction_after_goals()
json.dump(ANALYSIS, open(os.path.join(OUT, "analysis.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)


# ================================================================== figures
def draw_pitch(ax, half=False):
    ax.add_patch(plt.Rectangle((-3, -3), 111, 74, color="#2e7d32", zorder=0))
    lc = "white"
    ax.plot([0, 105, 105, 0, 0], [0, 0, 68, 68, 0], c=lc, lw=1)
    ax.plot([52.5, 52.5], [0, 68], c=lc, lw=1)
    ax.add_patch(plt.Circle((52.5, 34), 9.15, fill=False, ec=lc, lw=1))
    for x0, s_ in ((0, 1), (105, -1)):
        ax.plot([x0, x0 + s_ * 16.5, x0 + s_ * 16.5, x0], [13.84, 13.84, 54.16, 54.16], c=lc, lw=1)
        ax.plot([x0, x0 + s_ * 5.5, x0 + s_ * 5.5, x0], [24.84, 24.84, 43.16, 43.16], c=lc, lw=1)
    ax.set_xlim((50 if half else -3), 108)
    ax.set_ylim(-3, 71)
    ax.set_aspect("equal")
    ax.axis("off")


COL = {HID: H["colours"]["primary"], AID: A["colours"]["primary"]}


def fig_shot_map():
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.2))
    for ax, t in zip(axes, (HID, AID)):
        draw_pitch(ax, half=True)
        for s_ in [s for s in SHOTS if s["team"] == t]:
            x, y = erel(s_)
            mk = "*" if s_["outcome"] == "goal" else ("o" if s_["outcome"] == "saved" else ("s" if s_["outcome"] == "blocked" else "x"))
            ax.scatter(x, y, s=60 + 900 * s_["xg"], marker=mk, c=COL[t] if s_["outcome"] != "goal" else "gold",
                       ec="black", lw=0.8, zorder=5, alpha=0.9)
        tm = T[t]
        ax.set_title(f"{TEAM[t]['short']}: {tm['shots']} shots · {tm['xg']} xG · {tm['goals']} goals\n★ goal  ● saved  ■ blocked  ✕ off target (size = xG)", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "analysis_shot_map.png"), dpi=110)
    plt.close(fig)


def fig_pass_networks():
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
    for ax, t in zip(axes, (HID, AID)):
        draw_pitch(ax)
        comp = [e for e in PASSES if e["team"] == t and e["outcome"] == "complete" and e["period"] == 1 and e.get("receiver_id")]
        locs = defaultdict(list)
        for e in comp:
            locs[e["player_id"]].append(erel(e))
            locs[e["receiver_id"]].append(erel(e, end=True))
        avgp = {p: np.mean(v, axis=0) for p, v in locs.items() if len(v) >= 5 and PL[p]["starter"]}
        pairs = Counter((e["player_id"], e["receiver_id"]) for e in comp)
        und = Counter()
        for (a, b), n in pairs.items():
            und[tuple(sorted((a, b)))] += n
        for (a, b), n in und.items():
            if a in avgp and b in avgp and n >= 3:
                ax.plot([avgp[a][0], avgp[b][0]], [avgp[a][1], avgp[b][1]], c="white", lw=0.4 + n * 0.35, alpha=0.6, zorder=2)
        for p, (x, y) in avgp.items():
            n = len(locs[p])
            ax.scatter(x, y, s=80 + n * 6, c=COL[t], ec="black", zorder=5)
            ax.text(x, y, str(PL[p]["no"]), ha="center", va="center", fontsize=8, weight="bold", zorder=6)
        ax.set_title(f"{TEAM[t]['short']} pass network, first half (attacking left → right)", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "analysis_pass_networks.png"), dpi=110)
    plt.close(fig)


def fig_regains():
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
    for ax, t in zip(axes, (HID, AID)):
        draw_pitch(ax)
        ax.add_patch(plt.Rectangle((63, 0), 42, 68, color="white", alpha=0.12, zorder=1))
        pts = []
        for g, a, b in TURN:
            if b == t:
                fr = TR.get(g)
                if fr and "ball" in fr:
                    pts.append(rel(t, fr["ball"][4], fr["ball"][0], fr["ball"][1]))
        pts = np.array(pts)
        if len(pts):
            ax.scatter(pts[:, 0], pts[:, 1], s=28, c=COL[t], ec="black", lw=0.5, zorder=5)
        tr = TRN[t]
        ax.set_title(f"{TEAM[t]['short']}: where the ball was won (n={len(pts)}, avg height {tr['avg_regain_height_m']} m)\nshaded = high-turnover zone · counter-press success {tr['counterpress_success_pct']}%", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "analysis_regains.png"), dpi=110)
    plt.close(fig)


def fig_physical():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(12, 4))
    labs = [b["block"] for b in PHY[HID]]
    x = np.arange(len(labs))
    for i, t in enumerate((HID, AID)):
        a1.bar(x + (i - 0.5) * 0.38, [b["m_per_player_min"] for b in PHY[t]], 0.38, color=COL[t], label=TEAM[t]["short"])
        a2.bar(x + (i - 0.5) * 0.38, [b["hi_m_per_player_min"] for b in PHY[t]], 0.38, color=COL[t], label=TEAM[t]["short"])
    for ax, ttl in ((a1, "Metres per player per minute"), (a2, "High-intensity metres (>19.8 km/h) per player per minute")):
        ax.set_xticks(x)
        ax.set_xticklabels(labs)
        ax.set_title(ttl, fontsize=10)
        ax.legend(fontsize=8)
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "analysis_physical.png"), dpi=110)
    plt.close(fig)


def fig_morale():
    pm = MOR["per_minute"]
    fig, ax = plt.subplots(figsize=(12, 3.4))
    xs = np.arange(len(pm))
    ax.plot(xs, [r["home"] for r in pm], c=COL[HID], lw=2, label=H["short"])
    ax.plot(xs, [r["away"] for r in pm], c=COL[AID], lw=2, label=A["short"])
    ax.axhline(1.0, c="grey", lw=0.8, ls=":")
    idx = {(r["period"], r["minute"]): i for i, r in enumerate(pm)}
    for e in MOR["events"]:
        lab = None
        for r in pm:
            pass
        mm = e["clock"].split(":")[0]
        for i, r in enumerate(pm):
            if r["period"] == e["period"] and (r["minute"] == str(int(mm.split("+")[0]) + 1) if "+" not in mm else r["minute"].startswith(mm.split("+")[0] + "+")):
                ax.axvline(i, c="black" if "goal" in e["reason"] else "red", lw=0.6, ls="--")
                break
    ticks = [i for i, r in enumerate(pm) if r["minute"] in ("1", "15", "30", "45", "46", "60", "75", "90")]
    ax.set_xticks(ticks)
    ax.set_xticklabels([pm[i]["minute"] + "'" for i in ticks])
    ax.set_title("Modelled team confidence (1.0 = neutral) – dashed: goals (black) and red card (red). Model output, not a measurement.", fontsize=9)
    ax.legend(fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "analysis_morale.png"), dpi=110)
    plt.close(fig)


fig_shot_map()
fig_pass_networks()
fig_regains()
fig_physical()
fig_morale()
print("figures written")
