"""
Builds the human-readable match script (DRAAIBOEK.md) and figures from the
script + generated output. Every number in the document is measured from the
generated data, so script and data can never drift apart.

Usage: python render_draaiboek.py [root_dir]
"""
import csv
import json
import os
import sys
from collections import defaultdict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
OUT = os.path.join(ROOT, "output")
FIG = os.path.join(OUT, "figures")
os.makedirs(FIG, exist_ok=True)

S = json.load(open(os.path.join(ROOT, "script", "match_script.json")))
EV = json.load(open(os.path.join(OUT, "events.json")))
MIN = json.load(open(os.path.join(OUT, "stats_per_minute.json")))
PS = json.load(open(os.path.join(OUT, "player_stats.json")))
TACT = json.load(open(os.path.join(OUT, "tactical_states.json")))

H, A = S["teams"]["home"], S["teams"]["away"]
TEAM = {H["id"]: H, A["id"]: A}
SIDE = {H["id"]: "home", A["id"]: "away"}
PL = {p["id"]: p for t in (H, A) for p in t["players"]}
P1 = (45 + S["meta"]["added_time"]["1"]) * 60


def gsec(period, t):
    return t if period == 1 else P1 + t


def parse_clock(clock, period):
    mm, ss = clock.split(":")
    extra = 0
    if "+" in mm:
        mm, extra = mm.split("+")
    return (int(mm) - 45 * (period - 1)) * 60 + int(extra) * 60 + int(ss)


# ---------------------------------------------------------------- tracking (load once)
TR = defaultdict(dict)       # gsec -> {object_id: (x, y, team, role)}
with open(os.path.join(OUT, "tracking.csv")) as f:
    for r in csv.DictReader(f):
        g = gsec(int(r["period"]), int(r["second_in_period"]))
        TR[g][r["object_id"]] = (float(r["x"]), float(r["y"]), r["team"], r["role_or_state"], int(r["period"]))


def rel(team, period, x, y):
    flip = (SIDE[team] == "home") == (period == 2)
    return (105 - x, 68 - y) if flip else (x, y)


def window_metrics(team, g0, g1):
    """Team metrics in [g0, g1) global seconds."""
    opp = A["id"] if team == H["id"] else H["id"]
    m = defaultdict(float)
    for e in EV:
        g = gsec(e["period"], e["second_in_period"])
        if not (g0 <= g < g1) or e["team"] is None:
            continue
        own = e["team"] == team
        if e["type"] == "pass" and own:
            m["passes"] += 1
            m["passes_ok"] += e["outcome"] == "complete"
        if e["type"] == "shot":
            m["shots" if own else "shots_against"] += 1
            m["xg" if own else "xg_against"] += e.get("xg") or 0
        if e["type"] == "cross" and own:
            m["crosses"] += 1
        if e["type"] in ("tackle", "interception") and own:
            m["def_actions"] += 1
    poss = {team: 0, opp: 0}
    lines, widths, n = [], [], 0
    for g in range(int(g0), int(g1)):
        fr = TR.get(g)
        if not fr:
            continue
        b = fr.get("ball")
        if b and b[3] == "live":
            holder = None
        xs, ys = [], []
        for oid, (x, y, t, role, period) in fr.items():
            if t == team and role not in ("GK",):
                rx, ry = rel(team, period, x, y)
                xs.append(rx)
                ys.append(ry)
        if len(xs) >= 6:
            xs.sort()
            lines.append(np.mean(xs[:4]))     # deepest four outfield players = defensive line
            widths.append(np.percentile(ys, 90) - np.percentile(ys, 10))
    for r in MIN:
        pass
    # possession from per-minute rows
    tot_own = tot = 0
    for r in MIN:
        p = r["period"]
        lab = r["minute"]
        m0 = (int(lab.split("+")[0]) - 45 * (p - 1) - 1 + (int(lab.split("+")[1]) if "+" in lab else 0)) * 60
        g = gsec(p, m0)
        if g0 <= g < g1 and r[f"{team}_possession_pct_minute"] is not None:
            tot_own += r[f"{team}_possession_pct_minute"]
            tot += 1
    m["possession"] = tot_own / tot if tot else float("nan")
    m["line"] = float(np.mean(lines)) if lines else float("nan")
    m["width"] = float(np.mean(widths)) if widths else float("nan")
    m["pass_acc"] = 100 * m["passes_ok"] / m["passes"] if m["passes"] else float("nan")
    return m


def impact_table(team, g, span=600):
    before = window_metrics(team, max(0, g - span), g)
    after = window_metrics(team, g, g + span)
    rows = [("Possession %", "possession", "{:.0f}"), ("Passes", "passes", "{:.0f}"), ("Pass accuracy %", "pass_acc", "{:.0f}"),
            ("Shots (for/against)", None, None), ("xG (for/against)", None, None), ("Crosses", "crosses", "{:.0f}"),
            ("Tackles + interceptions", "def_actions", "{:.0f}"),
            ("Defensive line (m from own goal)", "line", "{:.1f}"), ("Team width (m)", "width", "{:.1f}")]
    out = [f"| {TEAM[team]['short']} | 10 min before | 10 min after |", "|---|---|---|"]
    for label, k, fmt in rows:
        if label.startswith("Shots"):
            out.append(f"| {label} | {before['shots']:.0f} / {before['shots_against']:.0f} | {after['shots']:.0f} / {after['shots_against']:.0f} |")
        elif label.startswith("xG"):
            out.append(f"| {label} | {before['xg']:.2f} / {before['xg_against']:.2f} | {after['xg']:.2f} / {after['xg_against']:.2f} |")
        else:
            out.append(f"| {label} | {fmt.format(before[k])} | {fmt.format(after[k])} |")
    return "\n".join(out)


def depth_vs_line(pid, g0, g1):
    """Player x minus the mean x of his team's other three deepest outfield players (negative = deeper)."""
    diffs = []
    for g in range(int(g0), int(g1)):
        fr = TR.get(g)
        if not fr or pid not in fr:
            continue
        x, y, t, role, period = fr[pid]
        px = rel(t, period, x, y)[0]
        others = sorted(rel(t2, p2, x2, y2)[0] for oid, (x2, y2, t2, r2, p2) in fr.items()
                        if t2 == t and oid != pid and r2 != "GK")[:3]
        diffs.append(px - np.mean(others))
    return np.mean(diffs) if diffs else float("nan")


def player_rel_depth(pid, g0, g1):
    xs = []
    team = PL[pid]["id"][:3]
    for g in range(int(g0), int(g1)):
        fr = TR.get(g)
        if fr and pid in fr:
            x, y, t, role, period = fr[pid]
            xs.append(rel(t, period, x, y)[0])
    return np.mean(xs) if xs else float("nan")


def flank_share(team, g0, g1):
    tot = left = right = 0
    for e in EV:
        g = gsec(e["period"], e["second_in_period"])
        if e["team"] == team and e["type"] in ("pass", "cross") and g0 <= g < g1 and e["end_x"] is not None:
            ex, ey = rel(team, e["period"], e["end_x"], e["end_y"])
            if ex > 52.5:
                tot += 1
                left += ey > 45
                right += ey < 23
    return (100 * left / tot, 100 * right / tot, tot) if tot else (float("nan"), float("nan"), 0)


def duels(pid, g0, g1):
    won = lost = fouls = 0
    for e in EV:
        g = gsec(e["period"], e["second_in_period"])
        if e["player_id"] == pid and g0 <= g < g1:
            if e["type"] == "tackle":
                won += e["outcome"] == "won"
                lost += e["outcome"] == "lost"
            if e["type"] == "foul":
                fouls += 1
    return won, lost, fouls


# ---------------------------------------------------------------- figures
def draw_pitch(ax):
    ax.add_patch(plt.Rectangle((-3, -3), 111, 74, color="#2e7d32", zorder=0))
    lc = "white"
    ax.plot([0, 105, 105, 0, 0], [0, 0, 68, 68, 0], c=lc, lw=1)
    ax.plot([52.5, 52.5], [0, 68], c=lc, lw=1)
    ax.add_patch(plt.Circle((52.5, 34), 9.15, fill=False, ec=lc, lw=1))
    for x0, s in ((0, 1), (105, -1)):
        ax.plot([x0, x0 + s * 16.5, x0 + s * 16.5, x0], [13.84, 13.84, 54.16, 54.16], c=lc, lw=1)
        ax.plot([x0, x0 + s * 5.5, x0 + s * 5.5, x0], [24.84, 24.84, 43.16, 43.16], c=lc, lw=1)
    ax.set_xlim(-3, 108)
    ax.set_ylim(-3, 71)
    ax.set_aspect("equal")
    ax.axis("off")


def fig_goal(goal_ev, fname, lead=22):
    g1 = gsec(goal_ev["period"], goal_ev["second_in_period"])
    g0 = g1 - lead
    fig, ax = plt.subplots(figsize=(10, 6.6))
    draw_pitch(ax)
    tracks = defaultdict(list)
    ball = []
    for g in range(g0, g1 + 1):
        for oid, (x, y, t, role, period) in TR.get(g, {}).items():
            if oid == "ball":
                ball.append((x, y))
            else:
                tracks[oid].append((x, y, t))
    involved = {goal_ev["player_id"], goal_ev.get("assist_id")}
    chain = [c for c in S["timeline"] if c["type"] == "goal" and c["scorer"] == goal_ev["player_id"]]
    if chain:
        involved |= {s["player"] for s in chain[0]["chain"]}
    for oid, pts in tracks.items():
        pts = np.array([(x, y) for x, y, t in pts])
        team = tracks[oid][0][2]
        col = TEAM[team]["colours"]["primary"]
        hl = oid in involved
        ax.plot(pts[:, 0], pts[:, 1], c=col, lw=2.6 if hl else 1.0, alpha=1 if hl else 0.55)
        ax.scatter(pts[0, 0], pts[0, 1], s=12, c=col, alpha=0.8)
        ax.scatter(pts[-1, 0], pts[-1, 1], s=90 if hl else 40, c=col, ec="black", zorder=5)
        if hl or oid in ("KBA-05",):
            ax.text(pts[-1, 0] + 1, pts[-1, 1] + 1.2, PL[oid]["name"].split()[-1], fontsize=8, color="white", weight="bold")
    b = np.array(ball)
    ax.plot(b[:, 0], b[:, 1], c="white", lw=1.5, ls="--")
    ax.scatter(b[-1, 0], b[-1, 1], c="white", s=30, zorder=6)
    ax.set_title(f"{goal_ev['clock']}  {goal_ev['player_name']} ({goal_ev['team']}) – movement over the last {lead} seconds", fontsize=11)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, fname), dpi=110)
    plt.close(fig)


def avg_positions(team, g0, g1):
    acc = defaultdict(list)
    for g in range(g0, g1):
        for oid, (x, y, t, role, period) in TR.get(g, {}).items():
            if t == team:
                acc[oid].append(rel(t, period, x, y))
    return {k: np.mean(v, axis=0) for k, v in acc.items() if len(v) > 60}


def fig_shapes(team, windows, fname, title):
    fig, axes = plt.subplots(1, len(windows), figsize=(6.2 * len(windows), 4.6))
    for ax, (label, g0, g1) in zip(axes, windows):
        draw_pitch(ax)
        pos = avg_positions(team, g0, g1)
        col = TEAM[team]["colours"]["primary"]
        for oid, (x, y) in pos.items():
            ax.scatter(x, y, s=260, c=col, ec="black", zorder=5)
            ax.text(x, y, str(PL[oid]["no"]), ha="center", va="center", fontsize=8, weight="bold", zorder=6)
        ax.set_title(label, fontsize=10)
    fig.suptitle(title + "  (average positions, attacking left → right)", fontsize=11)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, fname), dpi=110)
    plt.close(fig)


def fig_timeline(fname):
    hid, aid = H["id"], A["id"]
    x = np.arange(len(MIN))
    poss = np.array([r[f"{hid}_possession_pct_minute"] if r[f"{hid}_possession_pct_minute"] is not None else np.nan for r in MIN])
    idx_ok = ~np.isnan(poss)
    poss = np.interp(x, x[idx_ok], poss[idx_ok])
    s = np.convolve(poss, np.ones(5) / 5, mode="same")
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6), sharex=True)
    ax1.fill_between(x, 50, s, where=s >= 50, color=H["colours"]["primary"], alpha=0.8, label=H["short"])
    ax1.fill_between(x, 50, s, where=s < 50, color=A["colours"]["primary"], alpha=0.8, label=A["short"])
    ax1.axhline(50, c="grey", lw=0.8)
    ax1.set_ylim(15, 85)
    ax1.set_ylabel(f"{H['short']} possession %\n(5-min rolling)")
    ax1.legend(loc="upper right", fontsize=8)
    ax2.step(x, [r[f"{hid}_xg_cum"] for r in MIN], c=H["colours"]["primary"], lw=2, label=f"{H['short']} xG")
    ax2.step(x, [r[f"{aid}_xg_cum"] for r in MIN], c=A["colours"]["primary"], lw=2, label=f"{A['short']} xG")
    ax2.set_ylabel("Cumulative xG")
    ax2.legend(loc="upper left", fontsize=8)
    idx = {(r["period"], r["minute"]): i for i, r in enumerate(MIN)}
    for e in EV:
        if e["type"] in ("goal", "red_card", "yellow_card", "substitution", "tactical_change"):
            i = idx.get((e["period"], e["minute"]))
            if i is None:
                continue
            c = {"goal": "black", "red_card": "red", "yellow_card": "#e0b000", "substitution": "#1565c0", "tactical_change": "#6a1b9a"}[e["type"]]
            for ax in (ax1, ax2):
                ax.axvline(i, c=c, lw=1.2 if e["type"] == "goal" else 0.8, ls="-" if e["type"] in ("goal", "red_card") else ":")
            if e["type"] == "goal":
                ax1.text(i, 80, f"{e['score_home']}-{e['score_away']}", ha="center", fontsize=9, weight="bold")
    ticks = [i for i, r in enumerate(MIN) if r["minute"] in ("1", "15", "30", "45", "46", "60", "75", "90")]
    ax2.set_xticks(ticks)
    ax2.set_xticklabels([MIN[i]["minute"] + "'" for i in ticks])
    fig.suptitle("Match flow – black: goal · red: red card · yellow: yellow card · blue: substitution · purple: tactical change", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, fname), dpi=110)
    plt.close(fig)



def pre_match_section(w):
    cp = os.path.join(ROOT, "script", "pre_match_context.json")
    if not os.path.exists(cp):
        return
    C = json.load(open(cp))
    mc = C["match_context"]
    w("## Pre-match context\n")
    w(f"- **Venue:** {mc['venue']['name']} ({mc['venue']['surface']}, {mc['venue']['pitch_condition']}), {mc['venue']['attendance']:,} spectators.")
    w(f"- **Weather:** {mc['weather']['summary']}. {mc['weather']['impact']}")
    w(f"- **Referee:** {mc['referee']['name']}: {mc['referee']['style']} ({mc['referee']['avg_yellows_per_game']} yellows and {mc['referee']['avg_fouls_per_game']} fouls per game).")
    w(f"- **Stakes:** {mc['stakes']['summary']}")
    for side, t in (("home", H), ("away", A)):
        s_ = mc["schedule"][side]
        w(f"- **Schedule {t['short']}:** {s_['rest_days']} days rest. Previous match: {s_['previous_match']}. Travel: {s_['travel']}. Load: {s_['load']}.")
    w("- **Head to head:** " + "; ".join(f"{h['result']} ({h['note']})" for h in mc["head_to_head"]) + ".\n")
    for side, t in (("home", H), ("away", A)):
        c = C["teams"][side]
        lg = c["league"]
        w(f"### {t['name']}: {lg['position']}th, {lg['points']} points (W{lg['won']} D{lg['drawn']} L{lg['lost']}, goals {lg['goals_for']}-{lg['goals_against']})\n")
        w("| MD | Opponent (rank) | H/A | Score | xG | xGA | Poss. | Set-piece xG | Note |")
        w("|---|---|---|---|---|---|---|---|---|")
        for m in c["last_matches"]:
            w(f"| {m['md']} | {m['opponent']} ({m['opp_rank']}) | {m['venue']} | {m['score']} {m['result']} | {m['xg']} | {m['xga']} | {m['possession']}% | {m['set_piece_xg']} | {m['note']} |")
        w("")
        for ab in c["absences"]:
            w(f"- **Absent:** {ab['player']} ({ab['pos']}): {ab['reason']}. {ab['impact']}")
        m = c["mental"]
        w(f"- **Mental:** {m['summary']} {m['behind_record']} {m['pressure_handling']}")
        cp_ = c["coach_profile"]
        w(f"- **Coach {cp_['name']}:** {cp_['approach']}. First substitution on average at {cp_['avg_first_sub_minute']}'. When trailing: {cp_['behaviour_when_behind']} When leading: {cp_['behaviour_when_ahead']}")
        w(f"- **Game plan:** {cp_['game_plan']}")
        w(f"- **Bench ({c['bench']['quality_rating']}/100):** {c['bench']['summary']}")
        st = c["structure"]
        w(f"- **Build-up:** {st['build_up']}")
        w(f"- **Pressing:** {st['pressing']}")
        w(f"- **Defending:** line {st['defensive_line']}, marking {st['marking']}, target compactness {st['compactness_target_m']} m.")
        w(f"- **Attacking patterns:** {'; '.join(st['attacking_patterns'])}.")
        w(f"- **Known weaknesses:** {'; '.join(st['known_weaknesses'])}.")
        sp = c["set_pieces"]
        takers = ", ".join(PL[x]["name"] for x in sp["corner_takers"])
        lt = PL[sp["long_throw_taker"]]["name"] if sp["long_throw_taker"] else "none"
        w(f"- **Set pieces:** corners {sp['corner_delivery']} (takers: {takers}), {int(sp['corner_short_share'] * 100)}% short; direct free kicks: {PL[sp['free_kick_direct']]['name']}; "
          f"penalties: {PL[sp['penalty_taker']]['name']}; long throws: {lt}; defending corners: {sp['defending_corners']}; average outfield height {sp['avg_height_outfield_cm']} cm. {sp['note']}\n")
    w("### Player profiles (age, height, foot, form, confidence)\n")
    w("| Player | Team | Age | Height | Foot | Form last 5 | Confidence | Pressure handling | Fitness |")
    w("|---|---|---|---|---|---|---|---|---|")
    for pid, pr in C["player_profiles"].items():
        w(f"| {PL[pid]['name']} | {pid[:3]} | {pr['age']} | {pr['height_cm']} | {pr['foot']} | {pr['form_last5'] if pr['form_last5'] is not None else '–'} | {pr['confidence']} | {pr['pressure_handling']} | {pr['fitness']} |")
    w("")
    w("### Key match-ups (pre-match expectation)\n")
    w("| # | Match-up | Kingsbridge side | Northgate side | Expectation | Favours |")
    w("|---|---|---|---|---|---|")
    for m in C["matchups"]:
        w(f"| {m['id']} | {m['title']} | {m['home_side']} | {m['away_side']} | {m['expectation']} | {m['favours']} |")
    w("\nWhat actually happened in each match-up is measured in MATCH_ANALYSIS.md, section 10.\n")

# ---------------------------------------------------------------- build document
def g_of(ev):
    p = ev.get("period", 1)
    return gsec(p, parse_clock(ev["clock"], p))


def main():
    hid, aid = H["id"], A["id"]
    goals = [e for e in EV if e["type"] == "goal"]
    for e in goals:
        fig_goal(e, f"goal_{e['minute'].replace('+', 'plus')}_{e['player_id']}.png")
    red = next(e for e in EV if e["type"] == "red_card")
    gred = gsec(red["period"], red["second_in_period"])
    fig_shapes(hid, [("4-3-3 (46'–52')", P1, gred), ("4-4-1 after red card (54'–58')", gred + 90, P1 + 13 * 60 + 30),
                     ("3-4-2 all-in (76'–86')", P1 + 31 * 60, P1 + 41 * 60)], "shape_kingsbridge.png",
               f"{H['name']}: shape changes")
    fig_shapes(aid, [("4-4-2 (1'–45')", 0, P1), ("4-3-3 after double sub (64'–75')", P1 + 19 * 60 + 30, P1 + 30 * 60),
                     ("5-4-1 to hold on (87'–90+5')", P1 + 41 * 60 + 30, P1 + 50 * 60)], "shape_northgate.png",
               f"{A['name']}: shape changes")
    fig_timeline("match_flow.png")

    last = MIN[-1]
    L = []
    w = L.append
    m = S["meta"]
    w(f"# Match script: {m['title']}\n")
    w(f"**{m['competition']}** · {m['venue']} · {m['date']} {m['kickoff_local']} · Referee: {m['referee']} · {m['weather']}\n")
    w(f"**Final score: {H['name']} {last[hid+'_score']} – {last[aid+'_score']} {A['name']}**\n")
    w("> Fully synthetic match. Clubs, players and events are fictional. This script is the source of truth; "
      "all data in `output/` is generated from it (`generator/generate_match.py`) and every number below is measured from that data.\n")
    w("## Storyline\n")
    w(m["storyline"] + "\n")
    w("![Match flow](output/figures/match_flow.png)\n")
    w("The full analysis of this match along the 12 components of football analysis is in [MATCH_ANALYSIS.md](MATCH_ANALYSIS.md).\n")
    pre_match_section(w)

    # teams
    for t in (H, A):
        w(f"## {t['name']} ({'home' if t is H else 'away'})\n")
        w(f"**Coach:** {t['coach']} · **Starting formation:** {t['start_formation']}\n")
        w(t["identity"] + "\n")
        st = t["style"]
        w(f"Style parameters: press {st['press']}, line height {st['line']:+} m, tempo {st['tempo']}, width {st['width']}, directness {st['directness']}.\n")
        for title, starter in (("Starting XI", True), ("Substitutes", False)):
            w(f"### {title}\n")
            w("| # | Player | Pos | Pace | Pass | Drib | Fin | Tack | Disc | Stam | Strengths | Weaknesses |")
            w("|---|---|---|---|---|---|---|---|---|---|---|---|")
            for p in t["players"]:
                if p["starter"] != starter:
                    continue
                a = p["attr"]
                w(f"| {p['no']} | {p['name']} | {p['role'] or p['pos']} | {a['pace']} | {a['passing']} | {a['dribbling']} | {a['finishing']} | "
                  f"{a['tackling']} | {a['discipline']} | {a['stamina']} | {'; '.join(p['strengths'])} | {'; '.join(p['weaknesses'])} |")
            w("")
    # phases
    w("## Match phases\n")
    w("| Minutes | Phase | Target possession KBA | Measured possession KBA | What happens |")
    w("|---|---|---|---|---|")
    for ph in S["phases"]:
        g0 = ph["from"] * 60 if ph["from"] < 45 else P1 + (ph["from"] - 45) * 60
        g1 = ph["to"] * 60 if ph["to"] <= 45 else P1 + (ph["to"] - 45) * 60
        if ph["to"] == 52:
            g0b = ph["from"] * 60
        meas = window_metrics(hid, g0, g1)["possession"]
        w(f"| {ph['from']}–{ph['to']} | {ph['name']} | {100*ph['home_possession']:.0f}% | {meas:.0f}% | {ph['narrative']} |")
    w("")

    # timeline
    w("## Minute-by-minute script\n")
    w("Every scripted moment, in order. Unscripted play (passes, duels, other shots, set pieces) is filled in by the generator.\n")
    for ev in S["timeline"]:
        t = ev["type"]
        if t in ("kickoff", "period_end"):
            continue
        g = g_of(ev)
        team = TEAM[(H if ev.get("team") == "home" else A)["id"]] if ev.get("team") else None
        tid = team["id"] if team else None
        if t == "goal":
            w(f"### {ev['clock']} ⚽ GOAL {team['short']}: {PL[ev['scorer']]['name']} (assist {PL[ev['assist']]['name']})\n")
            w(f"*Pattern:* {ev['pattern'].replace('_', ' ')} · *xG:* {ev['xg']} · *Body part:* {ev['body_part'].replace('_', ' ')}\n")
            w(ev["description"] + "\n")
            w(f"**Why it matters:** {ev['significance']}\n")
            ge = next(e for e in goals if e["player_id"] == ev["scorer"])
            w(f"![Goal {ev['clock']}](output/figures/goal_{ge['minute'].replace('+', 'plus')}_{ev['scorer']}.png)\n")
            if ev["scorer"] == "NGR-09":
                # the race: line height when the ball is played and the gap at the shot
                lp = next(e for e in EV if e["type"] == "pass" and e["player_id"] == "NGR-08" and g - 15 <= gsec(e["period"], e["second_in_period"]) <= g)
                gl = gsec(lp["period"], lp["second_in_period"])
                fr0, fr1 = TR[gl], TR[g]
                lx = rel(hid, 1, *fr0["KBA-05"][:2])[0]
                gap = np.hypot(fr1["KBA-05"][0] - fr1["NGR-09"][0], fr1["KBA-05"][1] - fr1["NGR-09"][1])
                w(f"*Data check:* when Duarte played the ball ({lp['clock']}), Dijkhuis stood {lx:.0f} m from his own goal. "
                  f"At the moment of the shot he was {gap:.0f} m away from Adeyemi-Clarke.\n")
        elif t == "chance":
            w(f"### {ev['clock']} Chance {team['short']} – {ev['outcome'].replace('_', ' ')} (xG {ev['xg']})\n")
            w(ev["description"] + " " + ev["significance"] + "\n")
        elif t == "card":
            pid = ev["player"]
            icon = "🟥 SECOND YELLOW → RED" if ev["card"] == "second_yellow" else "🟨 YELLOW"
            w(f"### {ev['clock']} {icon}: {PL[pid]['name']} ({team['short']})\n")
            w(f"**Reason:** {ev['reason']}\n")
            w(f"**Effect on the player and the match:** {ev['effect_text']}\n")
            eff = ev.get("effect", {})
            if eff and not eff.get("sent_off"):
                parts = []
                nice = {"aggression": "duel aggression ×", "foul_rate": "foul rate ×", "depth_offset": "position shift (m)",
                        "duel_penalty": "duel win chance −", "opponent_target_bias": "opponents target his zone ×",
                        "dribble_attempts": "dribble attempts ×"}
                for k, v in eff.items():
                    parts.append(f"{nice.get(k, k)} {v}")
                w(f"*Model parameters:* {', '.join(parts)}.\n")
            # measured
            if pid == "NGR-02":
                b = depth_vs_line(pid, 0, g)
                a = depth_vs_line(pid, g + 30, P1)
                lb, rb, nb = flank_share(hid, 0, g)
                la, ra, na = flank_share(hid, g + 30, P1)
                w(f"*Data check:* relative to the other Northgate defenders, Quiroga's average position went from {b:+.1f} m to {a:+.1f} m (negative = deeper). "
                  f"Share of Kingsbridge passes into the opponent's half that went to their left flank: {lb:.0f}% before → {la:.0f}% after the card.\n")
            elif ev["card"] == "second_yellow":
                w("**Impact on the team (measured):**\n")
                w(impact_table(hid, g) + "\n")
                w("![Kingsbridge shape](output/figures/shape_kingsbridge.png)\n")
        elif t == "substitution":
            w(f"### {ev['clock']} 🔁 Substitution {team['short']}: {PL[ev['in']]['name']} on, {PL[ev['out']]['name']} off\n")
            w(f"**Reason:** {ev['reason']}\n")
            if ev.get("new_formation"):
                w(f"**Formation:** {ev['new_formation']}" + (" (tactical change)" if ev.get("tactical_change") else " (system unchanged)") + "\n")
            w(f"**What it means for the game:** {ev['impact']}\n")
            if ev["out"] == "NGR-02":
                lb, rb, nb = flank_share(hid, 760, P1)
                la, ra, na = flank_share(hid, P1, P1 + 7 * 60)
                w(f"*Data check:* Kingsbridge passes into the final half towards the left flank: {lb:.0f}% (12'–45') → {la:.0f}% (46'–52'); to the right: {rb:.0f}% → {ra:.0f}%.\n")
            nxt = [e for e in S["timeline"] if e["type"] == "substitution" and e["clock"] == ev["clock"] and e["team"] == ev["team"]]
            if nxt and nxt[-1] is ev and ev.get("tactical_change"):
                w("**Impact (measured, 10 minutes before vs. after):**\n")
                w(impact_table(tid, g) + "\n")
                if ev["team"] == "away" and ev["new_formation"] == "4-3-3-deep":
                    w("![Northgate shape](output/figures/shape_northgate.png)\n")
        elif t == "tactical_change":
            w(f"### {ev['clock']} 📋 Tactical change {team['short']}: {ev['new_formation']}\n")
            w(f"**Reason:** {ev['reason']}\n")
            w(f"**What it means for the game:** {ev['impact']}\n")
    # final stats
    w("## Final statistics\n")
    w(f"| | {H['short']} | {A['short']} |")
    w("|---|---|---|")
    for label, k in (("Goals", "score"), ("Possession %", "possession_pct_cum"), ("Passes", "passes_cum"),
                     ("Pass accuracy %", "pass_accuracy_cum"), ("Shots", "shots_cum"), ("Shots on target", "shots_on_target_cum"),
                     ("xG", "xg_cum"), ("Corners", "corners_cum"), ("Crosses", "crosses_cum"), ("Fouls", "fouls_cum"),
                     ("Yellow cards", "yellow_cards_cum"), ("Red cards", "red_cards_cum"), ("Offsides", "offsides_cum"),
                     ("Tackles", "tackles_cum"), ("Interceptions", "interceptions_cum"), ("Distance covered (km)", "distance_km_cum")):
        hv, av = last[hid + "_" + k], last[aid + "_" + k]
        if k == "xg_cum":
            hv, av = f"{hv:.2f}", f"{av:.2f}"
        w(f"| {label} | {hv} | {av} |")
    w("")
    w("## Player statistics\n")
    w("| Team | # | Player | Min | Km | Sprints | Top km/h | Passes (acc %) | Shots | xG | G | A | Tackles won/att | Int | Fouls | Cards |")
    w("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for p in sorted(PS, key=lambda r: (r["team"] != hid, not r["starter"], r["no"])):
        cards = "🟨" * p["yellow_cards"] + ("🟥" if p["red_cards"] else "")
        acc = f"{p['passes']} ({p['pass_accuracy']:.0f})" if p["passes"] else "0"
        w(f"| {p['team']} | {p['no']} | {p['name']} | {p['minutes']:.0f} | {p['distance_km']:.1f} | {p['sprints']} | {p['top_speed_kmh']:.0f} | {acc} | "
          f"{p['shots']} | {p['xg']:.2f} | {p['goals']} | {p['assists']} | {p['tackles_won']}/{p['tackles']} | {p['interceptions']} | {p['fouls_committed']} | {cards} |")
    w("")
    # data
    w("## Data files\n")
    w("""| File | Contents |
|---|---|
| `script/match_script.json` | This script as data: clubs, players (attributes, strengths, weaknesses), formations, phases, all scripted moments |
| `output/events.json` / `.csv` | Every event (pass, cross, shot, goal, tackle, interception, foul, card, substitution, tactical change, set pieces …) with clock, team, player, start/end position, outcome, xG, possession sequence, score |
| `output/tracking.csv` | 1 frame per second: x/y position and speed of every player on the pitch + ball (with ball holder / live-dead state) |
| `output/stats_per_minute.json` / `.csv` | Per minute and cumulative per team: score, formation, players on pitch, possession, passes, accuracy, shots, on target, xG, corners, crosses, fouls, cards, offsides, tackles, interceptions, distance |
| `output/player_stats.json` / `.csv` | Per player: minutes, distance, sprints, top speed, passes, key passes, shots, xG, goals, assists, duels, fouls, cards |
| `output/player_status.json` | Over time: cards with the effect parameters applied to the player, substitutions, effects of substitutions on opponents |
| `output/tactical_states.json` | Formation and role of every player after each tactical change |
| `script/pre_match_context.json` | Pre-match context: venue, weather, referee, stakes, schedule, form (last 8), absences, mental state, coach profiles, bench, set-piece profiles, structures, player profiles, key match-ups |
| `output/analysis.json` | Full analysis (12 components): per team, per phase, per player, match-ups, coaching |
| `output/morale_timeline.json` | Modelled team confidence per minute and the events that moved it |
| `output/figures/` | Movement lines for every goal, shape changes, match flow, shot map, pass networks, regains, physical load, confidence |
| `MATCH_ANALYSIS.md` | Readable analysis along the 12 components |

**Coordinates:** metres, pitch 105 × 68, origin at the bottom-left corner. Kingsbridge attack towards x = 105 in the first half and towards x = 0 in the second half.

**Regenerate:** `python generator/generate_match.py && python generator/analyze_match.py && python generator/render_analysis.py && python generator/render_draaiboek.py`. Change `meta.seed` for a different version of the unscripted play; the scripted moments and the final score stay the same.
""")
    w("## Model notes and limitations\n")
    w("- Tracking is 1 Hz and generated by a movement model (formation anchors + ball-oriented shifts + pressing + scripted runs), not real optical tracking. Fine for heatmaps, average positions, shape, distance and sprints; too coarse for exact biomechanics.\n"
      "- Only scripted shots can become goals; the generator never adds an extra goal.\n"
      "- Card effects work through parameters (aggression, foul rate, depth, duel win chance, how much opponents target the player). The 'data checks' show how strongly this shows up in the data.\n"
      "- Sprint = a 1-second sample above 23.8 km/h (threshold lowered from the usual 25.2 km/h because 1 Hz averaging flattens peaks). High-intensity run = entering > 19.8 km/h. Top speeds are lower than in real data.\n")
    open(os.path.join(ROOT, "DRAAIBOEK.md"), "w").write("\n".join(L))
    print("written", os.path.join(ROOT, "DRAAIBOEK.md"))


if __name__ == "__main__":
    main()
