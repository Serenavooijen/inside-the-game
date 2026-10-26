"""
Turns the output of generator/generate_match.py into data/matches/kba-ngr.json,
the recording that the frontend's mock backend plays.

Usage (from the frontend folder):
    python scripts/import_generator.py <generator output dir> [<match_script.json>]

Defaults: ../output and ../script/match_script.json (repo layout).

What is real and what is not:
- Positions, ball, events, score, xG, possession, shots: straight from the generator.
- Sprints: from the tracking speeds (threshold 23.8 km/h, as in the generator notes).
- Pass quality: a PLACEHOLDER score from pass length and progression. The Stats
  Engine (backend) should replace it with the real pass-difficulty model.
- Insights: recorded "agent output" for the demo. Goal/card/tactical texts come from
  the match script; every number in them is computed from the generator output.
"""

import csv
import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_FILE = os.path.join(HERE, "..", "data", "matches", "kba-ngr.json")

src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "..", "..", "output")
script_path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "..", "..", "script", "match_script.json")

events = json.load(open(os.path.join(src, "events.json")))
per_min = json.load(open(os.path.join(src, "stats_per_minute.json")))
script = json.load(open(script_path))

TEAM = {"KBA": "kba", "NGR": "ngr"}
NAME = {"kba": "Kingsbridge", "ngr": "Northgate"}


def r1(v):
    return round(float(v), 1)


# ---------------------------------------------------------------- roster
players = {}
for side in ("home", "away"):
    t = script["teams"][side]
    for p in t["players"]:
        first, *rest = p["name"].split(" ")
        short = f"{first[0]}. {' '.join(rest)}" if rest else p["name"]
        players[p["id"]] = {"id": p["id"], "team": TEAM[t["id"]], "n": p["no"], "name": short, "surname": " ".join(rest) or p["name"], "gk": p["pos"] == "GK"}

# ---------------------------------------------------------------- tracking
frames_pl = defaultdict(dict)   # frame -> pid -> (x, y, speed)
ball = {}
period_of = {}
with open(os.path.join(src, "tracking.csv")) as f:
    for row in csv.DictReader(f):
        fr = int(row["frame"])
        period_of[fr] = int(row["period"])
        if row["object_id"] == "ball":
            ball[fr] = (float(row["x"]), float(row["y"]), row["speed_ms_or_ball_holder"] or None)
        else:
            frames_pl[fr][row["object_id"]] = (float(row["x"]), float(row["y"]), float(row["speed_ms_or_ball_holder"] or 0))

duration = max(ball)
halftime = min(fr for fr, p in period_of.items() if p == 2)

# on-pitch intervals per player
present = defaultdict(list)
for fr in range(duration + 1):
    for pid in frames_pl[fr]:
        present[pid].append(fr)
roster = []
for pid, frs in present.items():
    ivs = []
    start = prev = frs[0]
    for fr in frs[1:]:
        if fr != prev + 1:
            ivs.append([start, prev]); start = fr
        prev = fr
    ivs.append([start, prev])
    roster.append({**{k: v for k, v in players[pid].items() if k != "surname"}, "on": ivs})
roster.sort(key=lambda p: (p["team"], p["n"]))
order = [p["id"] for p in roster]

frames = []
for fr in range(duration + 1):
    bx, by, _ = ball[fr]
    row = [r1(bx), r1(by)]
    for pid in order:
        if pid in frames_pl[fr]:
            x, y, _ = frames_pl[fr][pid]
            row += [r1(x), r1(y)]
    frames.append(row)


# ---------------------------------------------------------------- helpers
def minute_label(period, s):
    if period == 1:
        return str(s // 60 + 1) if s < 2700 else f"45+{(s - 2700) // 60 + 1}"
    tot = 2700 + s
    return str(tot // 60 + 1) if s < 2700 else f"90+{(s - 2700) // 60 + 1}"


def label_at(fr):
    p = period_of[fr]
    s = fr if p == 1 else fr - halftime
    return minute_label(p, s)


def surname(pid):
    return players[pid]["surname"]


def cum_row(fr):
    """Per-minute stats row that covers frame fr."""
    p1 = [r for r in per_min if r["period"] == 1]
    p2 = [r for r in per_min if r["period"] == 2]
    if fr < halftime:
        return p1[min(len(p1) - 1, fr // 60)]
    return p2[min(len(p2) - 1, (fr - halftime) // 60)]


def shots_between(team, a, b):
    return sum(1 for e in events if e["type"] == "shot" and e["team"] == team and a <= e["frame"] <= b)


def pct(a, b):
    return round(100 * a / b) if b else 0


# ---------------------------------------------------------------- stats timeline
stats = [{"t": 0, "xg": [0, 0], "possession": [50, 50]}]
for i, r in enumerate(per_min):
    if r["period"] == 1:
        fr = i * 60 + 59
    else:
        j = i - sum(1 for x in per_min if x["period"] == 1)
        fr = halftime + j * 60 + 59
    fr = min(fr, duration)
    stats.append({"t": fr, "xg": [round(r["KBA_xg_cum"], 2), round(r["NGR_xg_cum"], 2)],
                  "possession": [round(r["KBA_possession_pct_cum"]), round(r["NGR_possession_pct_cum"])]})

# ---------------------------------------------------------------- match events (scorebar, timeline, key moments)
match_events = []
for e in events:
    t = e["type"]
    if t not in ("goal", "yellow_card", "red_card", "substitution"):
        continue
    team = TEAM[e["team"]]
    m = e["minute"]
    base = {"id": f"e-{e['event_id']}", "t": e["frame"], "minute": m, "team": team}
    if t == "goal":
        a = e.get("assist_id")
        detail = f"{surname(e['player_id'])} ({players[e['player_id']]['n']})" + (f" · assist {surname(a)} ({players[a]['n']})" if a else "")
        match_events.append({**base, "kind": "goal", "playerId": e["player_id"], "text": f"{surname(e['player_id'])} {m}'", "detail": detail, "key": True})
    elif t == "yellow_card" and not e.get("second_yellow"):
        match_events.append({**base, "kind": "yellow", "playerId": e["player_id"], "text": f"{surname(e['player_id'])} {m}'"})
    elif t == "red_card":
        match_events.append({**base, "kind": "red", "playerId": e["player_id"], "text": f"{surname(e['player_id'])} {m}'",
                             "detail": f"{surname(e['player_id'])} ({players[e['player_id']]['n']}) · {e.get('reason', 'sent off').lower()}", "key": True})
    elif t == "substitution":
        match_events.append({**base, "kind": "sub", "playerId": e["player_in_id"], "text": f"{surname(e['player_in_id'])} {m}'"})

# ---------------------------------------------------------------- overlays (fast lane)
overlays = []
oid = 0


def add(o):
    global oid
    oid += 1
    overlays.append({"id": f"o-{oid}", **o})


goal_frames = [e["frame"] for e in events if e["type"] == "goal"]
quiet = lambda fr: any(g - 15 < fr < g + 50 for g in goal_frames)

# shots: line to the goal mouth, badge with xG
for e in events:
    if e["type"] == "shot":
        add({"t": e["frame"], "slot": "shot", "playerId": e["player_id"], "value": round(e.get("xg", 0), 2),
             "to": {"x": e["end_x"], "y": e["end_y"]}})
        if e.get("outcome") == "goal" or e.get("scripted"):
            add({"t": e["frame"], "slot": "tag", "playerId": e["player_id"]})
    if e["type"] in ("yellow_card", "red_card"):
        add({"t": e["frame"] + 1, "slot": "tag", "playerId": e["player_id"]})

# passes: one every ~12 s, longer passes only. PLACEHOLDER quality score.
last = -99
for e in events:
    if e["type"] != "pass" or e.get("outcome") != "complete" or e.get("length_m", 0) < 14:
        continue
    if e["frame"] - last < 12 or quiet(e["frame"]):
        continue
    attack = 1 if (TEAM[e["team"]] == "kba") == (e["period"] == 1) else -1
    progress = (e["end_x"] - e["x"]) * attack
    q = max(0.5, min(0.97, 0.55 + 0.012 * e["length_m"] + 0.008 * max(0, progress)))
    add({"t": e["frame"], "slot": "pass", "playerId": e["player_id"], "value": round(q, 2),
         "to": {"x": e["end_x"], "y": e["end_y"]}})
    last = e["frame"]

# sprints: from tracking speed, 23.8 km/h = 6.61 m/s
SPRINT = 23.8 / 3.6
last_sprint = -99
for fr in range(5, duration + 1):
    if fr - last_sprint < 20 or quiet(fr):
        continue
    best = None
    for pid, (x, y, sp) in frames_pl[fr].items():
        prev = frames_pl[fr - 1].get(pid)
        if prev and sp >= SPRINT and prev[2] < SPRINT and not players[pid]["gk"]:
            peak = max(frames_pl[f].get(pid, (0, 0, 0))[2] for f in range(fr, min(duration, fr + 4) + 1))
            if not best or peak > best[1]:
                best = (pid, peak)
    if best:
        pid, peak = best
        f0 = frames_pl[max(0, fr - 3)].get(pid) or frames_pl[fr][pid]
        add({"t": fr + 2, "slot": "sprint", "playerId": pid, "value": round(peak * 3.6, 1), "from": {"x": r1(f0[0]), "y": r1(f0[1])}})
        last_sprint = fr

# ball-carrier tags every ~30 s
last_tag = -99
for fr in range(0, duration + 1):
    holder = ball[fr][2]
    if holder and holder in players and fr - last_tag >= 30 and not quiet(fr):
        add({"t": fr, "slot": "tag", "playerId": holder})
        last_tag = fr

overlays.sort(key=lambda o: o["t"])

# ---------------------------------------------------------------- insights (recorded agent output)
ev_by_clock = {}
for e in events:
    if e.get("scripted"):
        ev_by_clock.setdefault((e["period"], e["clock"], e["type"]), e)


def find(period, clock, typ):
    return ev_by_clock.get((period, clock, typ))


def first_sentence(text, n=2):
    parts = [p.strip() for p in text.replace("\n", " ").split(". ") if p.strip()]
    s = ". ".join(parts[:n])
    return s if s.endswith(".") else s + "."


insights = []
ev_id = {e["t"]: e["id"] for e in match_events}


def ins(**kw):
    kw.setdefault("evidence", [])
    kw.setdefault("status", "checked")
    kw["minute"] = label_at(kw["t"])
    insights.append(kw)


def key_stats(fr):
    r = cum_row(fr)
    return [{"k": "Possession", "v": f"{round(r['KBA_possession_pct_cum'])}–{round(r['NGR_possession_pct_cum'])}"},
            {"k": "xG", "v": f"{r['KBA_xg_cum']:.2f}–{r['NGR_xg_cum']:.2f}"},
            {"k": "Shots", "v": f"{r['KBA_shots_cum']}–{r['NGR_shots_cum']}"}]


# goals
for e in events:
    if e["type"] != "goal":
        continue
    shot = next(s for s in events if s["type"] == "shot" and s["frame"] == e["frame"] and s["player_id"] == e["player_id"])
    team = TEAM[e["team"]]
    evid = [f"Shot xG {shot['xg']:.2f}" + (f" · xGOT {shot['xgot']:.2f}" if shot.get("xgot") is not None else ""),
            f"Distance {shot['distance_m']:.1f} m · {shot['body_part'].replace('_', ' ')}",
            f"Score after the goal: {e['score_home']}–{e['score_away']}"]
    zone = None
    if e.get("pattern") == "counter_attack" and team == "ngr" and e["period"] == 1:
        # Where was Kingsbridge's last defender when the ball over the top was played?
        lp = [p for p in events if p["type"] == "pass" and p["team"] == "NGR" and e["frame"] - 20 <= p["frame"] <= e["frame"] and p.get("pass_type") in ("long_pass", "through_ball", "pass")]
        if lp:
            pf = lp[-1]["frame"]
            xs = sorted(x for pid, (x, y, s) in frames_pl[pf].items() if players[pid]["team"] == "kba" and not players[pid]["gk"])
            line = round(xs[0])
            evid.append(f"Kingsbridge's last defender when the ball was played: {line} m from goal")
            zone = {"x": 0, "y": 0, "w": line, "h": 68, "line": line, "label": f"Space behind the line · {line} m", "dir": -1}
    ins(id=f"i-goal-{e['event_id']}", t=e["frame"] + 1, momentId=ev_id[e["frame"]], type="goal", team=team,
        text=e["description"], evidence=evid, zone=zone, analystStats=key_stats(e["frame"]))

# yellow card Quiroga + the left-flank effect
q = find(1, "12:40", "yellow_card")
if q:
    ins(id="i-card-quiroga", t=q["frame"] + 2, momentId=ev_id.get(q["frame"]), type="card", card="yellow", team="ngr",
        text=first_sentence(q["effect_text"]), evidence=[f"Yellow card: Quiroga (NGR 2), {q['minute']}'", q["reason"]])

    def left_share(a, b):
        # Kingsbridge attack towards x = 105 in the first half; their left flank is large y.
        ps = [p for p in events if p["type"] in ("pass", "cross") and p["team"] == "KBA" and a <= p["frame"] < b and p.get("end_x") and p["end_x"] > 52.5]
        return pct(sum(1 for p in ps if p["end_y"] > 45.33), len(ps)), len(ps)

    before, nb = left_share(0, q["frame"])
    after, na = left_share(q["frame"], 1800)
    ins(id="i-left-flank", t=1800, type="momentum", team="kba",
        text=f"Kingsbridge are going at the booked Quiroga: {after}% of their passes into the Northgate half now go down their left, up from {before}% before the card.",
        evidence=[f"Passes into the Northgate half, left third: {after}% of {na} since 13'", f"Before the card: {before}% of {nb}"],
        zone={"x": 52.5, "y": 45.33, "w": 52.5, "h": 22.67, "label": "Kingsbridge attack zone · left flank", "dir": 1},
        analystStats=[{"k": "Left share now", "v": f"{after}%"}, {"k": "Before card", "v": f"{before}%"}, {"k": "Passes", "v": str(na)}])

b = find(1, "31:05", "yellow_card")
if b:
    ins(id="i-card-brannigan", t=b["frame"] + 2, momentId=ev_id.get(b["frame"]), type="card", card="yellow", team="kba",
        text=first_sentence(b["effect_text"], 1), evidence=[f"Yellow card: Brannigan (KBA 6), {b['minute']}'", b["reason"]])

# half time
r = cum_row(halftime - 1)
ins(id="i-ht", t=halftime - 1, type="update",
    text=f"Half time, 1–1. Kingsbridge had {round(r['KBA_possession_pct_cum'])}% of the ball and {r['KBA_shots_cum']} shots to Northgate's {r['NGR_shots_cum']}, but xG is close: {r['KBA_xg_cum']:.2f} to {r['NGR_xg_cum']:.2f}.",
    evidence=[f"Possession {round(r['KBA_possession_pct_cum'])}% – {round(r['NGR_possession_pct_cum'])}%", f"Shots {r['KBA_shots_cum']} – {r['NGR_shots_cum']}", f"xG {r['KBA_xg_cum']:.2f} – {r['NGR_xg_cum']:.2f}"],
    analystStats=key_stats(halftime - 1))

# red card and the reshape
red = next((e for e in events if e["type"] == "red_card"), None)
if red:
    ins(id="i-red", t=red["frame"] + 1, momentId=ev_id.get(red["frame"]), type="card", card="red", team="kba",
        text="Second yellow for Brannigan. Kingsbridge are down to ten men and lose their tempo-setter and main ball-winner.",
        evidence=[f"Second yellow: Brannigan (KBA 6), {red['minute']}'", "Booked earlier at 32'"])
    tc = find(2, "52:50", "tactical_change")
    if tc:
        ins(id="i-reshape", t=tc["frame"] + 1, type="momentum", team="kba", text=first_sentence(tc["impact"], 1),
            evidence=["New shape: 4-4-1", "Players on the pitch: 10"])
    # possession before and after the red card (per-minute values)
    a0 = [x for x in per_min if x["period"] == 2 and x["minute_index"] and x["minute_index"] < 53]
    a1 = [x for x in per_min if x["period"] == 2 and x["minute_index"] and 53 <= x["minute_index"] <= 62]
    pb = round(sum(x["KBA_possession_pct_minute"] for x in a0) / len(a0))
    pa = round(sum(x["KBA_possession_pct_minute"] for x in a1) / len(a1))
    fr62 = halftime + (62 - 45) * 60
    ins(id="i-62", t=fr62, type="update", team="kba",
        text=f"Ten men changes everything: Kingsbridge's possession dropped from {pb}% to {pa}% after the red card.",
        evidence=[f"Possession 46'–52': {pb}%", f"Possession 53'–62': {pa}%"],
        analystStats=[{"k": "Before red", "v": f"{pb}%"}, {"k": "After red", "v": f"{pa}%"}, {"k": "Players", "v": "10 v 11"}])

s = find(2, "63:20", "substitution")
if s:
    ins(id="i-ngr-switch", t=s["frame"] + 1, type="momentum", team="ngr", text=first_sentence(s["impact"], 1),
        evidence=["Halvorsen and Diallo-Kerr on, 64'", "4-4-2 → 4-3-3"])

s = find(2, "75:00", "substitution")
if s:
    ins(id="i-kba-allin", t=s["frame"] + 1, type="momentum", team="kba", text=first_sentence(s["impact"], 1),
        evidence=["Castellanos and Moore-Asante on, 76'", "4-4-1 → 3-4-2"])

# fallback example at 80'
fr80 = halftime + (80 - 45) * 60
r = cum_row(fr80)
ins(id="i-80", t=fr80, type="update", status="fallback", fallbackReason="Model timed out after 6 s",
    text=f"Kingsbridge {r['KBA_score']}, Northgate {r['NGR_score']} after 80 minutes. xG {r['KBA_xg_cum']:.2f} to {r['NGR_xg_cum']:.2f}.")

c = find(2, "84:02", "shot")
if c:
    ins(id="i-chance-84", t=c["frame"] + 1, type="bigchance", team="ngr",
        text="Counter against the back three: Diallo-Kerr runs through alone, Ferreira-Lind saves with his legs.",
        evidence=[f"Shot xG {c['xg']:.2f}", f"Outcome: {c['outcome']}"])

# corrected claim: shots after the red card (computed, the draft says the opposite)
if red:
    fr_c = halftime + (87 - 45) * 60
    kb, ng = shots_between("KBA", red["frame"], fr_c), shots_between("NGR", red["frame"], fr_c)
    lead, trail = ("ngr", "kba") if ng > kb else ("kba", "ngr")
    hi, lo = max(ng, kb), min(ng, kb)
    claim = f"{NAME[trail]} created more chances than {NAME[lead]} after the red card"
    text = f"{NAME[lead]} had more shots after the red card: {hi} against {lo}." if hi != lo else f"Both sides had {hi} shots after the red card."
    ins(id="i-corrected", t=fr_c, type="momentum", status="corrected", claim=claim, text=text,
        stats={"a": str(ng), "aLabel": f"Northgate shots {red['minute']}'–87'", "aTeam": "ngr",
               "b": str(kb), "bLabel": f"Kingsbridge shots {red['minute']}'–87'", "bTeam": "kba"},
        evidence=[f"Shots {red['minute']}'–87': NGR {ng}, KBA {kb}", "Source: momentum agent", "Checked against event data"])

# full time
r = per_min[-1]
ins(id="i-ft", t=duration, type="fulltime",
    text=f"2–2. Kingsbridge finished with {round(r['KBA_possession_pct_cum'])}% of the ball and xG {r['KBA_xg_cum']:.2f} to {r['NGR_xg_cum']:.2f}. Three of the four goals involved a substitute or the booked full-back.",
    evidence=[f"xG {r['KBA_xg_cum']:.2f} – {r['NGR_xg_cum']:.2f}", f"Shots {r['KBA_shots_cum']} – {r['NGR_shots_cum']}", f"Possession {round(r['KBA_possession_pct_cum'])}% – {round(r['NGR_possession_pct_cum'])}%"],
    analystStats=key_stats(duration))

for i in insights:
    for k in [k for k, v in i.items() if v is None]:
        del i[k]
insights.sort(key=lambda i: i["t"])

fixture = {
    "id": "kba-ngr",
    "source": "generate_match.py, seed " + str(script["meta"].get("seed")),
    "home": {"id": "kba", "name": script["teams"]["home"]["name"], "short": "KBA"},
    "away": {"id": "ngr", "name": script["teams"]["away"]["name"], "short": "NTG"},
    "duration": duration,
    "halftime": halftime,
    "roster": roster,
    "frameFormat": "row per frame (1 Hz): [ball.x, ball.y, then x,y for every roster player that is on the pitch at that frame, in roster order]",
    "frames": frames,
    "events": match_events,
    "overlays": overlays,
    "insights": insights,
    "stats": stats,
}
os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
with open(OUT_FILE, "w") as f:
    json.dump(fixture, f, separators=(",", ":"), ensure_ascii=False)
print(f"wrote {os.path.normpath(OUT_FILE)}: {len(frames)} frames, {len(roster)} players, {len(match_events)} events, {len(overlays)} overlays, {len(insights)} insights")
