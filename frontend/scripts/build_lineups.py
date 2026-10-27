"""
Builds data/lineups/kba-ngr.json: line-ups, per-player numbers over time, positions and
corners for the Line-ups tab, the player analysis and the corner cards.

Everything is measured by code from the generator output; no AI and no hand-made numbers.

Usage (from the frontend folder):
    python scripts/build_lineups.py [<generator output dir>] [<match_script.json>] [<cup output dir>]

Defaults: ../output, ../script/match_script.json and ../output/cup (repo layout).
Reads data/matches/kba-ngr.json for the roster, the on-pitch intervals and the 1 Hz frames,
so the positions are exactly the ones the pitch shows.

What is in it:
- players: role, starter, on-pitch interval, moments (goal, assist, cards, on/off) and
  the actions behind the stat tiles, as times, so the frontend can show any minute:
  touches, passes (completed/attempted), shots (xG), duels (won/lost), recoveries,
  sprints (>= 23.8 km/h, from the tracking speed), distance per 10 s and top speed.
- positions every 5 s on the pitch, team-relative: the team always attacks left to right.
- formations over time (tactical_states.json).
- corners (heights from pre_match_context.json): the frame at the moment of delivery around the box, the first contact and the
  outcome, stored as a corner from the left (u 0-68 along the goal line, v distance from it).
- goals from corners in the cup match.
"""

import csv
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
MATCH_FILE = os.path.join(HERE, "..", "data", "matches", "kba-ngr.json")
OUT_FILE = os.path.join(HERE, "..", "data", "lineups", "kba-ngr.json")

src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "..", "output")
script_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "..", "script", "match_script.json")
cup_src = sys.argv[3] if len(sys.argv) > 3 else os.path.join(src, "cup")
context_path = os.path.join(os.path.dirname(script_path), "pre_match_context.json")


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


match = load(MATCH_FILE)
events = load(os.path.join(src, "events.json"))
script = load(script_path)
states = load(os.path.join(src, "tactical_states.json"))
# player heights (cm) from the pre-match profiles, for the corner cards
heights = {pid: p["height_cm"] for pid, p in load(context_path).get("player_profiles", {}).items()
           if p.get("height_cm")} if os.path.exists(context_path) else {}

TEAM = {"KBA": match["home"]["id"], "NGR": match["away"]["id"]}
HOME = match["home"]["id"]
duration, halftime = match["duration"], match["halftime"]
roster = match["roster"]
by_id = {p["id"]: p for p in roster}

SPRINT = 23.8 / 3.6          # m/s, as in the generator notes
SAMPLE = 5                   # s between position samples
BUCKET = 10                  # s per distance bucket ("updates every 10 s")

ROLE_SHORT = {"RCB": "CB", "LCB": "CB", "RCM": "CM", "LCM": "CM", "RS": "ST", "LS": "ST", "FW": "ST", "RWB": "RB", "LWB": "LB"}
ROLE_NAME = {
    "GK": "Goalkeeper", "RB": "Right-back", "LB": "Left-back", "CB": "Centre-back", "DM": "Defensive midfield",
    "CM": "Central midfield", "AM": "Attacking midfield", "RM": "Right midfield", "LM": "Left midfield",
    "RW": "Right wing", "LW": "Left wing", "ST": "Striker",
}


def short_role(r):
    return ROLE_SHORT.get(r, r)


def dir_of(team, period):
    """+1 when the team attacks towards x = 105."""
    first = 1 if team == HOME else -1
    return first if period == 1 else -first


def norm(team, t, x, y):
    """Team-relative: the team always attacks left to right."""
    if dir_of(team, 1 if t < halftime else 2) == 1:
        return x, y
    return 105 - x, 68 - y


def minute_of(t):
    if t < halftime:
        m = t // 60
        return str(m) if m <= 45 else f"45+{m - 45}"
    m = 45 + (t - halftime) // 60
    return str(m) if m <= 90 else f"90+{m - 90}"


# ---------------------------------------------------------------- frames (1 Hz, from the match file)
def frame_at(t):
    row = match["frames"][t]
    out = {}
    k = 2
    for p in roster:
        if any(a <= t <= b for a, b in p["on"]):
            out[p["id"]] = (row[k], row[k + 1])
            k += 2
    return out


# ---------------------------------------------------------------- roles and starters (match script, tactical states)
script_players = {}
for side in ("home", "away"):
    for p in script["teams"][side]["players"]:
        script_players[p["id"]] = p
role_of = {}
for s in states:
    for pid, r in s["roles"].items():
        role_of.setdefault(pid, short_role(r))       # the first role a player has on the pitch
formations = defaultdict(list)
for s in states:
    team = TEAM[s["team"]]
    mm, ss = s["clock"].split(":")
    t = (int(mm) * 60 + int(ss)) - (2700 if s["period"] == 2 else 0) + (halftime if s["period"] == 2 else 0)
    shape = s["formation"].replace("-deep", "")
    if not formations[team] or formations[team][-1][1] != shape:
        formations[team].append([max(0, t), shape])

# ---------------------------------------------------------------- tracking: speed per second
speed = defaultdict(dict)    # pid -> frame -> m/s
with open(os.path.join(src, "tracking.csv"), encoding="utf-8") as f:
    for row in csv.DictReader(f):
        if row["object_id"] != "ball":
            speed[row["object_id"]][int(row["frame"])] = float(row["speed_ms_or_ball_holder"] or 0)

# ---------------------------------------------------------------- actions per player
TOUCH = {"pass", "cross", "ball_receipt", "shot", "take_on", "clearance", "interception", "ball_recovery", "corner",
         "free_kick", "throw_in", "goal_kick", "kickoff", "save", "block", "tackle"}
acts = defaultdict(lambda: defaultdict(list))
moments = defaultdict(list)
replaced = {}                # pid off -> (pid on, t, minute)
for e in events:
    pid, t, kind = e.get("player_id"), e["frame"], e["type"]
    if kind in TOUCH and pid in by_id:
        acts[pid]["T"].append(t)
    if kind in ("pass", "cross") and pid in by_id:
        acts[pid]["P" if e["outcome"] == "complete" else "p"].append(t)
    if kind == "shot" and pid in by_id:
        acts[pid]["S"].append([t, round(e.get("xg") or 0, 3)])
    if kind in ("ball_recovery", "interception") and pid in by_id:
        acts[pid]["R"].append(t)
    if kind == "tackle":
        won = e["outcome"] == "won"
        acts[pid]["D" if won else "d"].append(t)
        if e.get("opponent_id") in by_id:
            acts[e["opponent_id"]]["d" if won else "D"].append(t)
    if kind == "take_on":
        won = e["outcome"] == "success"
        acts[pid]["D" if won else "d"].append(t)
        if e.get("opponent_id") in by_id:
            acts[e["opponent_id"]]["d" if won else "D"].append(t)
    if kind == "goal":
        moments[pid].append([t, e["minute"], "goal"])
        if e.get("assist_id"):
            moments[e["assist_id"]].append([t, e["minute"], "assist"])
    if kind == "yellow_card" and not any(f["type"] == "red_card" and f["player_id"] == pid and f["frame"] == t for f in events):
        moments[pid].append([t, e["minute"], "yellow"])      # a second yellow shows as the red card
    if kind == "red_card":
        moments[pid].append([t, e["minute"], "red"])
    if kind == "substitution":
        moments[pid].append([t, e["minute"], "off"])
        moments[e["player_in_id"]].append([t, e["minute"], "on"])
        replaced[pid] = (e["player_in_id"], t, e["minute"])

players = []
for p in roster:
    pid = p["id"]
    a, b = p["on"][0]
    sp = speed[pid]
    # distance per 10 s bucket, from the bucket the player starts in
    first = a // BUCKET
    dist = [0] * (b // BUCKET - first + 1)
    sprints, tops, top, prev = [], [], 0.0, 0.0
    for fr in range(a, b + 1):
        v = sp.get(fr, 0.0)
        dist[fr // BUCKET - first] += v
        if v >= SPRINT and prev < SPRINT:
            sprints.append(fr)
        if v * 3.6 >= top + 0.1:
            top = v * 3.6
            tops.append([fr, round(top, 1)])
        prev = v
    xy = []
    s0 = -(-a // SAMPLE)
    for k in range(s0, b // SAMPLE + 1):
        t = k * SAMPLE
        x, y = frame_at(t)[pid]
        nx, ny = norm(p["team"], t, x, y)
        xy += [round(nx), round(ny)]
    sp_info = script_players.get(pid, {})
    role = role_of.get(pid, short_role(sp_info.get("role") or sp_info.get("pos") or ""))
    off = None
    ms = sorted(moments.get(pid, []))
    red = next((m for m in ms if m[2] == "red"), None)
    if pid in replaced:
        on_id, t, minute = replaced[pid]
        off = {"t": t, "minute": minute, "reason": "sub", "by": on_id}
    elif red:
        off = {"t": red[0], "minute": red[1], "reason": "red"}
    came_on = next((m for m in ms if m[2] == "on"), None)
    players.append({
        "id": pid, "team": p["team"], "n": p["n"], "name": p["name"], "gk": p["gk"],
        "role": role, "roleName": ROLE_NAME.get(role, role),
        "starter": bool(sp_info.get("starter")) if sp_info else a == 0,
        "on": [a, off["t"] if off else b],
        "off": off,
        "replaced": next((k for k, v in replaced.items() if v[0] == pid), None) if came_on else None,
        "moments": [[m[0], m[1], m[2]] for m in ms],
        "acts": {k: v for k, v in acts[pid].items()},
        "sprints": sprints, "tops": tops,
        "d0": first, "dist": [round(d) for d in dist],
        "s0": s0, "xy": xy,
    })

# unused substitutes from the match script (named in the squad, never on the pitch)
for side in ("home", "away"):
    t = script["teams"][side]
    for sp_info in t["players"]:
        if sp_info["id"] in by_id:
            continue
        first, *rest = sp_info["name"].split(" ")
        role = short_role(sp_info["pos"])
        players.append({
            "id": sp_info["id"], "team": TEAM[t["id"]], "n": sp_info["no"], "name": f"{first[0]}. {' '.join(rest)}",
            "gk": sp_info["pos"] == "GK", "role": role, "roleName": ROLE_NAME.get(role, role), "starter": False,
            "on": None, "off": None, "replaced": None, "moments": [], "acts": {}, "sprints": [], "tops": [],
            "d0": 0, "dist": [], "s0": 0, "xy": [],
        })


# ---------------------------------------------------------------- corners
def to_box(goal_at_105, x, y):
    """u along the goal line (0 = the attackers' left), v = distance from the goal line."""
    return (y, 105 - x) if goal_at_105 else (68 - y, x)


def zone_of(u, v, short):
    if short:
        return "short"
    if u < 30.34:
        return "near"
    if u > 37.66:
        return "far"
    return "spot"


ZONE_TEXT = {"near": "near post", "far": "far post", "spot": "penalty spot", "short": "short"}
SHOT_TEXT = {"off_target": "off target", "saved": "saved", "blocked": "blocked", "goal": "goal"}


def surname(pid):
    return by_id[pid]["name"].split(". ", 1)[-1]


def first_contact(evs, i, team):
    """The first event after the delivery that touches the ball (within 4 s)."""
    d = evs[i]
    for f in evs[i + 1:]:
        if f["frame"] > d["frame"] + 4:
            return None
        if f["type"] in ("ball_receipt", "clearance", "interception", "shot", "save", "block", "ball_recovery") and f.get("player_id"):
            return f
    return None


corners = []
nth = defaultdict(int)
for i, e in enumerate(events):
    if e["type"] != "corner":
        continue
    team = TEAM[e["team"]]
    di = next((j for j in range(i + 1, min(i + 6, len(events)))
               if events[j]["type"] in ("pass", "cross") and events[j]["player_id"] == e["player_id"]
               and events[j]["frame"] - e["frame"] <= 5), None)
    if di is None:
        continue                                  # awarded but not taken (e.g. a substitution stopped play)
    d = events[di]
    goal105 = e["x"] > 52.5
    fu, _ = to_box(goal105, e["x"], e["y"])
    right = fu > 34
    mir = (lambda u: 68 - u) if right else (lambda u: u)
    fc = first_contact(events, di, team)
    frame = frame_at(d["frame"])
    att, dfn = [], []
    for pid, (x, y) in frame.items():
        if pid == e["player_id"]:
            continue
        u, v = to_box(goal105, x, y)
        u = mir(u)
        if v > 23.5 or u < -2 or u > 70:
            continue
        item = {"n": by_id[pid]["n"], "u": round(u, 1), "v": round(v, 1), "id": pid}
        if by_id[pid]["gk"]:
            item["gk"] = True
        if pid in heights:
            item["height"] = heights[pid] / 100
        (att if by_id[pid]["team"] == team else dfn).append(item)
    nth[team] += 1
    if fc:
        cu, cv = to_box(goal105, fc["x"], fc["y"])
        cu = mir(cu)
        fc_team = TEAM[fc["team"]]
    else:
        cu, cv = to_box(goal105, d["end_x"], d["end_y"])
        cu, fc_team = mir(cu), None
    in_box = 13.84 <= cu <= 54.16 and cv <= 16.5
    short = d["type"] == "pass" and not in_box
    zone = zone_of(cu, cv, short)
    shot = next((f for f in events[di + 1:di + 6] if f["type"] == "shot" and TEAM[f["team"]] == team
                 and f["frame"] - d["frame"] <= 5), None)
    taker_n = by_id[e["player_id"]]["n"]
    who = (lambda f: f"#{by_id[f['player_id']]['n']} {surname(f['player_id'])}")
    if shot and shot["outcome"] == "goal":
        kind = "goal"
        how = "header" if shot.get("body_part") == "head" else "shot"
        text = f"Goal · {how} by {who(shot)} · xG {shot['xg']:.2f}"
    elif shot:
        kind = "header" if shot.get("body_part") == "head" else "shot"
        text = f"{'Header' if kind == 'header' else 'Shot'} by {who(shot)} · xG {shot['xg']:.2f} · {SHOT_TEXT.get(shot['outcome'], shot['outcome'])}"
    elif short and fc and fc_team == team:
        kind = "short"
        if 16.5 < cv <= 22 and 13.84 <= cu <= 54.16:
            text = f"Played to the edge of the box · {who(fc)}"
        elif cv > 22:
            text = f"Played out · to {who(fc)}"
        else:
            text = f"Short corner · played to {who(fc)}"
    elif fc and fc_team != team:
        kind = "cleared"
        text = f"Cleared by {match['home']['short'] if fc_team == HOME else match['away']['short']} · {who(fc)}, {ZONE_TEXT[zone]}"
    elif fc:
        kind = "header"
        text = f"First contact {who(fc)} · no shot"
    else:
        kind, text = "cleared", "Not reached · out of play"
    corners.append({
        "id": f"corner-{e['event_id']}", "t": d["frame"], "minute": e["minute"], "team": team, "nth": nth[team],
        "side": "right" if right else "left", "taker": taker_n, "takerId": e["player_id"],
        "attackers": att, "defenders": dfn,
        "firstTouch": {"u": round(cu, 1), "v": round(cv, 1), "n": by_id[fc["player_id"]]["n"] if fc else None,
                       "id": fc["player_id"] if fc else None, "team": fc_team},
        "zone": zone,
        "outcome": {"kind": kind, "text": text, **({"xg": shot["xg"]} if shot else {})},
    })


# ---------------------------------------------------------------- goals from corners in the cup match
def corner_goals(evs):
    out = defaultdict(int)
    last = {}
    for e in evs:
        if e["type"] == "corner":
            last[e["team"]] = (e["frame"], e["possession_seq"])
        if e["type"] == "goal" and e["team"] in last:
            fr, seq = last[e["team"]]
            if e["frame"] - fr <= 20 and e["possession_seq"] == seq:
                out[TEAM[e["team"]]] += 1
    return {TEAM["KBA"]: out[TEAM["KBA"]], TEAM["NGR"]: out[TEAM["NGR"]]}


cup_file = os.path.join(cup_src, "events.json")
cup = {"cornerGoals": corner_goals(load(cup_file))} if os.path.exists(cup_file) else None

out = {
    "matchId": match["id"], "duration": duration, "halftime": halftime,
    "sample": SAMPLE, "bucket": BUCKET,
    "formations": formations,
    "players": players,
    "corners": corners,
    "cup": cup,
}
os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
with open(OUT_FILE, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
print(f"wrote {OUT_FILE}: {len(players)} players, {len(corners)} corners, {os.path.getsize(OUT_FILE) // 1024} KB")
