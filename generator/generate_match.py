"""
Synthetic match generator.

Reads a match script (script/match_script.json) and simulates the match second by
second (1 Hz). Scripted moments (goals, chances, cards, substitutions, tactical
changes) are forced to happen exactly as written; everything in between is filled
in by a simple stochastic model driven by player attributes, team style, phase of
the match and card effects.

Outputs (in output/):
  events.json / events.csv        every on-ball and match event
  tracking.csv                    x, y, speed for all players + ball, 1 frame/sec
  stats_per_minute.json / .csv    team stats per minute (per-minute and cumulative)
  player_stats.json / .csv        per-player match totals
  player_status.json              card effects, substitutions, role changes over time
  tactical_states.json            formation + role per player over time
  match_summary.json              final score, totals, scripted moments

Usage: python generate_match.py [script_path] [output_dir]
"""
import csv
import json
import math
import os
import sys
from collections import defaultdict

import numpy as np

L, W = 105.0, 68.0
GOAL = np.array([105.0, 34.0])

# ----------------------------------------------------------------------------- helpers

def parse_clock(clock, period):
    """'23:14' or '45+2:00' -> seconds since the start of `period`."""
    mm, ss = clock.split(":")
    extra = 0
    if "+" in mm:
        mm, extra = mm.split("+")
        extra = int(extra)
    return (int(mm) - 45 * (period - 1)) * 60 + extra * 60 + int(ss)


def fmt_clock(period, t):
    base = 45 * period
    start = 45 * (period - 1) * 60
    if t >= 45 * 60:
        extra = t - 45 * 60
        return f"{base}+{extra // 60}:{extra % 60:02d}"
    total = start + t
    return f"{total // 60:02d}:{total % 60:02d}"


def match_minute(period, t):
    return 45 * (period - 1) + t / 60.0


def minute_label(period, t):
    m = int(t // 60)
    if m >= 45:
        return f"{45 * period}+{m - 45 + 1}"
    return str(45 * (period - 1) + m + 1)  # football convention: 0:00-0:59 is the 1st minute


def clamp(v, a, b):
    return max(a, min(b, v))


class Match:
    def __init__(self, script, out_dir):
        self.s = script
        self.out = out_dir
        self.rng = np.random.default_rng(script["meta"].get("seed", 1))
        self.formations = {k: {r: np.array(v, float) for r, v in f.items()} for k, f in script["formations"].items()}

        self.players = {}
        self.team_of = {}
        self.teams = {}
        for side in ("home", "away"):
            t = script["teams"][side]
            self.teams[side] = {
                "info": t,
                "formation": t["start_formation"],
                "base_style": dict(t["style"]),
                "lineup": {},  # player_id -> role
            }
            for p in t["players"]:
                self.players[p["id"]] = p
                self.team_of[p["id"]] = side
                if p["starter"]:
                    self.teams[side]["lineup"][p["id"]] = p["role"]

        self.mods = defaultdict(dict)   # player_id -> modifier dict (card effects etc.)
        self.yellows = defaultdict(int)
        self.pos = {}
        self.vel = {}
        self.noise = {}
        self.dist = defaultdict(float)
        self.sprinting = defaultdict(bool)
        self.sprints = defaultdict(int)
        self.prev_fast = {}
        self.top_speed = defaultdict(float)
        self.minutes_on = {}            # player_id -> [ (period, t_on, t_off) ]
        self.on_since = {}

        self.events = []
        self.tracking_rows = []
        self.status_log = []
        self.tactical_log = []
        self.score = {"home": 0, "away": 0}
        self.poss_seq = 0
        self.poss_team = None
        self.poss_ema = 0.5
        self.minute_poss = defaultdict(lambda: {"home": 0, "away": 0})
        self.frame = 0
        self.last_shot_chain = {}

        # pre-match context (optional file script/pre_match_context.json)
        ctx = script.get("_context", {})
        self.ctx = ctx
        self.tprof = {s_: ctx.get("teams", {}).get(s_, {}) for s_ in ("home", "away")}
        sched = ctx.get("match_context", {}).get("schedule", {})
        self.fatigue_factor = {s_: sched.get(s_, {}).get("fatigue_factor", 1.0) for s_ in ("home", "away")}
        self.pprof = ctx.get("player_profiles", {})
        self.morale_base = {s_: 0.85 + 0.3 * self.tprof[s_].get("mental", {}).get("confidence", 0.5) for s_ in ("home", "away")}
        self.morale = dict(self.morale_base)
        self.morale_log = []
        self.morale_events = []
        self.hi_runs = defaultdict(int)
        self.hi_dist = defaultdict(float)
        self.accels = defaultdict(int)
        self.decels = defaultdict(int)
        self.prev_speed = {}
        self.poss_origin = {"type": "kickoff", "p": 1, "t": 0, "x": 52.5}
        self.last_loss = {}
        self.pressure_logged = set()
        self.press_state = {"home": {}, "away": {}}

        self._build_schedule()

    # ------------------------------------------------------------------ geometry
    def flip(self, side, period):
        return (side == "home") == (period == 2)

    def to_abs(self, side, rel):
        rel = np.asarray(rel, float)
        if self.flip(side, self.period):
            return np.array([L - rel[0], W - rel[1]])
        return rel.copy()

    def to_rel(self, side, a):
        return self.to_abs(side, a)  # the transform is its own inverse

    def other(self, side):
        return "away" if side == "home" else "home"

    def on_pitch(self, side=None):
        if side:
            return list(self.teams[side]["lineup"].keys())
        return self.on_pitch("home") + self.on_pitch("away")

    def attr(self, pid, a):
        return self.players[pid]["attr"].get(a, 60)

    def mod(self, pid, k, default=1.0):
        return self.mods[pid].get(k, default)

    # ------------------------------------------------------------------ style / phase
    def phase(self):
        m = match_minute(self.period, self.t)
        for ph in self.s["phases"]:
            if ph["from"] <= m < ph["to"]:
                return ph
        return self.s["phases"][-1]

    def style(self, side):
        st = dict(self.teams[side]["base_style"])
        st.update(self.phase().get(side, {}))
        return st

    # ------------------------------------------------------------------ schedule
    def _build_schedule(self):
        self.instant = defaultdict(list)   # (period, t) -> list of events
        self.chains = []
        for ev in self.s["timeline"]:
            p = ev.get("period", 1)
            T = parse_clock(ev["clock"], p)
            ev = dict(ev, _p=p, _T=T)
            if ev["type"] in ("goal", "chance"):
                steps = []
                for st in ev["chain"]:
                    if st.get("lost_by"):
                        # the opponent who loses the ball gets it first, so the interception is real
                        steps.append({"player": st["lost_by"], "action": "pass", "t": T - st["dt"] - 3,
                                      "at": [105 - st["at"][0] - 3, 68 - st["at"][1]]})
                    steps.append({"player": st["player"], "action": st["action"], "t": T - st["dt"], "at": st["at"]})
                ev["_steps"] = steps
                self.chains.append(ev)
            elif ev["type"] == "card":
                victim = ev.get("victim")
                carrier = victim if victim else ev["player"]
                ev["_steps"] = [{"player": carrier, "action": "carry", "t": T - 6, "at": ev["at_victim_rel"]},
                                {"player": carrier, "action": "foul_end", "t": T, "at": ev["at_victim_rel"]}]
                self.chains.append(ev)
            elif ev["type"] in ("substitution", "tactical_change"):
                self.instant[(p, T)].append(ev)
        for c in self.chains:
            c["_start"] = min(s["t"] for s in c["_steps"]) - 7
            c["_done"] = False

    def chain_soon(self, window=50):
        """True shortly before a scripted chain: keep the ball in open play so the scripted move starts naturally."""
        return any(c["_p"] == self.period and not c["_done"] and 0 < c["_start"] - self.t <= window for c in self.chains)

    def active_chain(self):
        for c in self.chains:
            if c["_p"] == self.period and not c["_done"] and c["_start"] <= self.t <= c["_T"]:
                return c
        return None

    def override_target(self, pid):
        """Scripted run targets for players involved in an upcoming/active chain."""
        for c in self.chains:
            if c["_p"] != self.period or c["_done"]:
                continue
            if not (c["_start"] - 4 <= self.t <= c["_T"]):
                continue
            side = c["team"]
            if c["type"] != "card":
                side = self.team_of[pid] if pid in self.team_of else side
            if c["type"] == "card":
                victim = c.get("victim")
                if pid == c["player"] and victim:
                    # offender: first get near the spot, then chase the victim
                    if self.t >= c["_T"] - 8 and victim in self.pos:
                        return self.pos[victim], 1.0
                    vic_side = self.team_of[victim]
                    spot_abs = self.to_abs(vic_side, c["at_victim_rel"])
                    return spot_abs, 0.8
                carrier = victim if victim else c["player"]
                if pid == carrier:
                    cs = self.team_of[carrier]
                    if self.t < c["_T"] - 6:
                        return self.to_abs(cs, c["at_victim_rel"]), 0.9
                    return self.to_abs(cs, np.array(c["at_victim_rel"]) + [6, 0]), 0.8
                continue
            steps = c["_steps"]
            for i, st in enumerate(steps):
                if st["player"] != pid:
                    continue
                if self.t <= st["t"]:
                    return self.to_abs(side, st["at"]), self._timed_speed(pid, self.to_abs(side, st["at"]), st["t"])
            # after own last step but before the end of the chain: keep moving with play
            if pid in [s["player"] for s in steps]:
                last = [s for s in steps if s["player"] == pid][-1]
                if self.t <= last["t"] + 2:
                    return self.to_abs(side, np.array(last["at"]) + [4, 0]), 0.6
        return None

    def _timed_speed(self, pid, target, t_due):
        d = np.linalg.norm(target - self.pos[pid])
        remain = max(1, t_due - self.t)
        need = d / remain
        return clamp(need / self.vmax(pid), 0.2, 1.0)

    # ------------------------------------------------------------------ events
    def log(self, etype, side, player=None, xy=None, end=None, outcome=None, scripted=False, **extra):
        ev = {
            "event_id": len(self.events) + 1,
            "frame": self.frame,
            "period": self.period,
            "clock": fmt_clock(self.period, self.t),
            "minute": minute_label(self.period, self.t),
            "second_in_period": self.t,
            "type": etype,
            "team": self.teams[side]["info"]["id"] if side else None,
            "player_id": player,
            "player_name": self.players[player]["name"] if player else None,
            "x": round(float(xy[0]), 2) if xy is not None else None,
            "y": round(float(xy[1]), 2) if xy is not None else None,
            "end_x": round(float(end[0]), 2) if end is not None else None,
            "end_y": round(float(end[1]), 2) if end is not None else None,
            "outcome": outcome,
            "possession_seq": self.poss_seq,
            "score_home": self.score["home"],
            "score_away": self.score["away"],
            "scripted": scripted,
        }
        ev.update(extra)
        self.events.append(ev)
        return ev

    def set_possession(self, side, origin=None):
        if side != self.poss_team:
            if self.poss_team is not None:
                self.last_loss[self.poss_team] = (self.period, self.t)
            self.poss_seq += 1
            self.poss_team = side
            self.poss_start = (self.period, self.t)
            rx = float(self.to_rel(side, self.ball_pos)[0]) if hasattr(self, "ball_pos") else 50.0
            self.poss_origin = {"type": origin or "regain", "p": self.period, "t": self.t, "x": rx}
        elif origin:
            rx = float(self.to_rel(side, self.ball_pos)[0])
            self.poss_origin = {"type": origin, "p": self.period, "t": self.t, "x": rx}

    def play_pattern(self, side):
        o = self.poss_origin
        dt = self.t - o["t"] if o["p"] == self.period else 999
        if o["type"] in ("corner", "free_kick", "throw_in") and dt <= 12:
            return "from_" + o["type"]
        if o["type"] == "goal_kick" and dt <= 10:
            return "from_goal_kick"
        if o["type"] == "regain" and dt <= 12 and o["x"] < 60:
            return "counter_attack"
        return "open_play"

    def shift_morale(self, side, delta, reason):
        self.morale[side] = clamp(self.morale[side] + delta, 0.7, 1.3)
        self.morale_events.append({"period": self.period, "clock": fmt_clock(self.period, self.t),
                                   "team": self.teams[side]["info"]["id"], "delta": round(delta, 3),
                                   "morale": round(self.morale[side], 3), "reason": reason})

    def in_transition(self, side):
        """True during the first seconds after winning the ball (counter-attack window)."""
        ps = getattr(self, "poss_start", (0, -99))
        return self.poss_team == side and ps[0] == self.period and self.t - ps[1] <= 10

    # ------------------------------------------------------------------ movement
    def vmax(self, pid):
        pace = self.attr(pid, "pace")
        stam = self.attr(pid, "stamina")
        ff = self.fatigue_factor[self.team_of[pid]]
        fat = clamp(1 - 0.22 * ff * self.dist[pid] / (8000 + 60 * stam), 0.76, 1.0)
        return (5.6 + 3.9 * pace / 100.0) * fat

    def role_of(self, pid):
        return self.teams[self.team_of[pid]]["lineup"].get(pid)

    def anchor(self, pid):
        side = self.team_of[pid]
        f = self.formations[self.teams[side]["formation"]]
        role = self.role_of(pid)
        if role in f:
            return f[role].copy()
        return np.array([40.0, 34.0])

    def offside_line(self, side):
        """x (in `side` rel coords) of the second-last defender of the opponent."""
        opp = self.other(side)
        xs = sorted(self.to_rel(side, self.pos[q])[0] for q in self.on_pitch(opp))
        if len(xs) < 2:
            return 105
        return max(xs[-2], 52.5)

    def targets(self, ball_abs, in_poss, kickoff=False):
        """Compute a target position (abs) and intensity for every player on the pitch."""
        tg = {}
        for side in ("home", "away"):
            st = self.style(side)
            ball_rel = self.to_rel(side, ball_abs)
            has = (in_poss == side)
            off_line = self.offside_line(side)
            outfield = [q for q in self.on_pitch(side) if self.role_of(q) != "GK"]
            # pressers: nearest players to the ball when defending
            pressers = []
            cp_active = False
            trigger = None
            if not has and not kickoff and in_poss is not None:
                k = 1 + int(round(st.get("press", 0.5) * 2))
                ranked = sorted(outfield, key=lambda q: np.linalg.norm(self.pos[q] - ball_abs))
                carrier = self.ball.get("carrier") if self.ball and self.ball["state"] == "carry" else None
                if carrier:
                    if self.role_of(carrier) == "GK":
                        trigger = "goalkeeper_in_possession"
                    elif (ball_abs[1] < 6 or ball_abs[1] > W - 6) and ball_rel[0] > 55:
                        trigger = "ball_near_touchline"
                    elif self.ball.get("recv_t") == self.t - 1 and self.ball.get("back_pass"):
                        trigger = "back_pass"
                if trigger and st.get("press", 0.5) > 0.5:
                    k += 1
                ll = self.last_loss.get(side)
                if ll and ll[0] == self.period and self.t - ll[1] <= 5:
                    cpv = self.tprof[side].get("structure", {}).get("counterpress", 0.5)
                    cp_active = cpv > 0.4
                    k += int(round(cpv * 2))
                # high press only when the ball is far from own goal, otherwise just the nearest one
                if ball_rel[0] < 35:
                    k = min(k, 2)
                pressers = ranked[:k]
            self.press_state[side] = {"trigger": trigger, "counterpress": cp_active}
            for q in self.on_pitch(side):
                a = self.anchor(q)
                role = self.role_of(q) or ""
                inten = 0.55
                if role == "GK":
                    x = 4 + (max(0, ball_rel[0] - 40) * 0.14 if has else max(0, ball_rel[0] - 50) * 0.06)
                    y = 34 + (ball_rel[1] - 34) * 0.22
                    tg[q] = (self.to_abs(side, [x, y]), 0.5)
                    continue
                line = st.get("line", 0) * (1.0 if role.endswith("B") or "CB" in role else 0.7)
                depth = self.mod(q, "depth_offset", 0.0)
                if kickoff:
                    x = min(a[0] * 0.9 + line * 0.3, 50.5)
                    y = a[1]
                    tg[q] = (self.to_abs(side, [x, y]), 0.5)
                    continue
                if has:
                    push = 0.0
                    if role in ("RB", "LB"):
                        push = 14 * st.get("width", 1.0) - 6
                    elif role in ("RWB", "LWB"):
                        push = 12
                    elif "CM" in role or role in ("RM", "LM", "AM"):
                        push = 7
                    elif role in ("ST", "RS", "LS", "RW", "LW"):
                        push = 6
                    x = a[0] + 0.42 * (ball_rel[0] - 45) + line + push + depth
                    y = 34 + (a[1] - 34) * st.get("width", 1.0) + 0.15 * (ball_rel[1] - 34)
                    x = min(x, off_line - 0.8)
                    if role in ("ST", "RS", "LS", "RW", "LW"):
                        inten = 0.45          # forwards hold position rather than chase every shift
                    else:
                        inten = 0.5 + 0.3 * st.get("tempo", 0.5)
                else:
                    fwd = role in ("ST", "RS", "LS", "RW", "LW")
                    x = a[0] + (0.3 if fwd else 0.45) * (ball_rel[0] - 50) + line + depth
                    y = 34 + (a[1] - 34) * 0.78 + (0.18 if fwd else 0.3) * (ball_rel[1] - 34)
                    x = min(x, max(ball_rel[0] + 2, 12))   # stay goal-side of the ball
                    inten = 0.5
                    if q in pressers:
                        idx = pressers.index(q)
                        agg = self.mod(q, "aggression")
                        if idx == 0:
                            tgt = ball_rel + (np.array([-1.2, 0]))
                            inten = (0.6 + 0.4 * st.get("press", 0.5)) * agg
                            if cp_active:
                                inten = max(inten, 0.95 * agg)
                        else:
                            tgt = ball_rel + np.array([-6, (34 - ball_rel[1]) * 0.25 + (4 if idx == 1 else -4)])
                            inten = 0.6 + 0.2 * st.get("press", 0.5)
                        x, y = tgt
                x = clamp(x, 7.5, 103)   # outfield players never camp on the goal line
                y = clamp(y, 1.5, 66.5)
                tg[q] = (self.to_abs(side, [x, y]), inten)
        if self.ball and self.ball["state"] == "dead" and self.ball.get("sp_type") in ("corner", "long_throw"):
            self.set_piece_targets(tg)
        return tg

    def set_piece_targets(self, tg):
        """Box occupation for corners / long throws: attackers to slots, defenders mark (man or zonal)."""
        b = self.ball
        att, dfn = b["side"], self.other(b["side"])
        near_y = self.to_rel(att, b["pos"])[1]
        sgn = 1 if near_y < 34 else -1
        cand = [q for q in self.on_pitch(att) if self.role_of(q) != "GK" and q != b["taker"]]
        cand.sort(key=lambda q: -self.attr(q, "heading"))
        box_slots = [(96, 34 - 3 * sgn), (98, 31 + 2 * sgn), (94, 38), (99, 36 - 4 * sgn), (91, 33)]
        edge_slots = [(82, 27), (82, 41)]
        rest_slots = [(52, 24), (52, 44), (45, 34)]
        attackers_in_box = []
        for i, q in enumerate(cand):
            if i < 5:
                slot = box_slots[i]
                attackers_in_box.append((q, slot))
            elif i < 7:
                slot = edge_slots[i - 5]
            else:
                slot = rest_slots[min(i - 7, 2)]
            tg[q] = (self.to_abs(att, slot), 0.6)
        marking = self.tprof[dfn].get("set_pieces", {}).get("marking", "zonal")
        defs = [q for q in self.on_pitch(dfn) if self.role_of(q) != "GK"]
        defs.sort(key=lambda q: -self.attr(q, "heading"))
        used = set()
        self.sp_markers = {}
        if marking == "man":
            for (q, slot), d in zip(attackers_in_box, defs):
                tg[d] = (self.to_abs(att, (slot[0] + 1, slot[1])), 0.7)
                self.sp_markers[q] = d
                used.add(d)
            zones = [(101, 30), (101, 38), (88, 34)]
        else:
            zones = [(101, 31), (101, 37), (99, 34), (98, 28), (98, 40), (95, 33), (95, 37), (88, 34)]
        rest = [d for d in defs if d not in used]
        for d, z in zip(rest, zones):
            tg[d] = (self.to_abs(att, z), 0.6)
        for d in rest[len(zones):]:
            tg[d] = (self.to_abs(att, (70, 34)), 0.5)

    def move_players(self, tg, carrier=None, carry_target=None):
        for q in self.on_pitch():
            target, inten = tg[q]
            ov = self.override_target(q)
            if ov is not None:
                target, inten = ov
            if q == carrier and carry_target is not None and ov is None:
                target, inten = carry_target, (0.7 if self.in_transition(self.team_of[q]) else 0.48)
            # individual wander (Ornstein-Uhlenbeck) so lines are not perfectly rigid
            n = self.noise.setdefault(q, np.zeros(2))
            n += -0.08 * n + self.rng.normal(0, 0.42, 2)
            if ov is None and q != carrier and self.role_of(q) != "GK":
                target = target + n
            p = self.pos[q]
            v = self.vel.setdefault(q, np.zeros(2))
            d = target - p
            dist = np.linalg.norm(d)
            vmax = self.vmax(q)
            if ov is not None:
                cap = vmax * inten
            elif dist > 25:
                cap = vmax * max(inten, 0.85)      # sprint to recover position
            elif dist > 15:
                cap = vmax * max(inten, 0.68)
            elif dist > 7:
                cap = vmax * max(inten * 0.75, 0.5)
            elif dist > 4:
                cap = vmax * inten * 0.5
            else:
                cap = dist * 0.42 + 0.15
            if ov is None and q != carrier and dist <= 25 and (self.role_of(q) or "") in ("ST", "RS", "LS", "RW", "LW", "RM", "LM"):
                cap *= 0.82           # attackers jog back into shape; long recovery runs stay at full intensity
            desired = d / dist * min(cap, dist) if dist > 1e-6 else np.zeros(2)
            dv = desired - v
            acc = np.linalg.norm(dv)
            if acc > 3.2:
                dv = dv / acc * 3.2
            v = v + dv
            sp = np.linalg.norm(v)
            if sp > vmax:
                v = v / sp * vmax
            newp = p + v
            newp[0] = clamp(newp[0], -1, L + 1)
            newp[1] = clamp(newp[1], -1, W + 1)
            step = np.linalg.norm(newp - p)
            self.dist[q] += step
            self.pos[q] = newp
            self.vel[q] = v
            spd = step
            self.top_speed[q] = max(self.top_speed[q], spd)
            fast = spd > 6.6
            if fast and not self.sprinting[q]:
                self.sprints[q] += 1          # sprint = entering > 23.8 km/h (1 Hz sample, see notes)
                self.sprinting[q] = True
            elif spd < 4.0:
                self.sprinting[q] = False
            self.prev_fast[q] = fast
            ps_ = self.prev_speed.get(q, 0.0)
            if spd > 5.5:
                self.hi_dist[q] += step
                if ps_ <= 5.5:
                    self.hi_runs[q] += 1          # high-intensity run: entering > 19.8 km/h
            if spd - ps_ >= 3.0:
                self.accels[q] += 1
            elif ps_ - spd >= 3.0:
                self.decels[q] += 1
            self.prev_speed[q] = spd

    # ------------------------------------------------------------------ ball state
    def give_ball(self, pid, origin=None, back_pass=False):
        self.ball = {"state": "carry", "carrier": pid, "hold": self.hold_time(pid), "set_piece": False,
                     "recv_t": self.t, "back_pass": back_pass}
        self.set_possession(self.team_of[pid], origin)

    def hold_time(self, pid):
        side = self.team_of[pid]
        if self.role_of(pid) == "GK":
            return int(self.rng.integers(2, 5))
        tempo = self.style(side).get("tempo", 0.5)
        mean = 2.0 * (1 - tempo) + 0.8
        if self.morale[side] < 0.97 and self.score[side] < self.score[self.other(side)]:
            mean *= 0.75     # rushed when behind and low on confidence
        h = 1 + self.rng.poisson(mean)
        rel = self.to_rel(side, self.pos[pid])
        if rel[0] > 70:
            h = int(h * self.mod(pid, "dribble_attempts"))
        return max(1, int(h))

    def dead(self, restart, side, pos_abs, wait, taker=None):
        sp = self.tprof[side].get("set_pieces", {})
        rel = self.to_rel(side, np.array(pos_abs, float))
        sp_type = None
        onp = set(self.on_pitch(side))
        if restart == "corner":
            sp_type = "corner"
            tk = [q for q in sp.get("corner_takers", []) if q in onp]
            if tk:
                taker = tk[0]
        elif restart == "free_kick":
            dgoal = float(np.linalg.norm(GOAL - rel))
            if dgoal < 30 and abs(rel[1] - 34) < 16 and rel[0] < 88:
                sp_type = "direct_free_kick"
                if sp.get("free_kick_direct") in onp:
                    taker = sp["free_kick_direct"]
            elif rel[0] > 72:
                sp_type = "free_kick_cross"
                tk = [q for q in sp.get("corner_takers", []) if q in onp]
                if tk:
                    taker = tk[0]
        elif restart == "throw_in" and rel[0] > 72 and sp.get("long_throw_taker") in onp:
            sp_type = "long_throw"
            taker = sp["long_throw_taker"]
        elif restart == "goal_kick":
            sp_type = "goal_kick_short" if self.rng.random() < self.tprof[side].get("structure", {}).get("goal_kicks_short_share", 0.6) else "goal_kick_long"
        if taker is None:
            cands = [q for q in self.on_pitch(side) if (restart == "goal_kick") == (self.role_of(q) == "GK")]
            if not cands:
                cands = self.on_pitch(side)
            taker = min(cands, key=lambda q: np.linalg.norm(self.pos[q] - pos_abs))
        self.ball = {"state": "dead", "restart": restart, "side": side, "pos": np.array(pos_abs, float),
                     "resume": self.t + wait, "taker": taker, "sp_type": sp_type}
        if restart != "kickoff" or self.t == 0:
            self.ball_pos = np.array(pos_abs, float)

    def launch(self, passer, receiver, kind, success=True, interceptor=None, arrive=None, end=None, forced=False):
        side = self.team_of[passer]
        start = self.ball_pos.copy()
        if end is None:
            end = self.pos[receiver].copy() if receiver else start
        d = np.linalg.norm(end - start)
        speed = 22 if kind in ("long_pass", "cross", "clearance") else 15
        if arrive is None:
            arrive = self.t + max(1, int(round(d / speed)))
        self.ball = {"state": "flight", "from": start, "receiver": receiver, "passer": passer, "kind": kind,
                     "t0": self.t, "t1": arrive, "success": success, "interceptor": interceptor,
                     "end": end, "forced": forced, "back_pass": getattr(self, "next_back_pass", False)}
        self.next_back_pass = False
        if kind in ("pass", "long_pass", "through_ball", "cross"):
            etype = "cross" if kind == "cross" else "pass"
            outcome = "complete" if success else "incomplete"
            self.log(etype, side, passer, start, end, outcome, scripted=forced, pass_type=kind,
                     receiver_id=receiver if success else None, length_m=round(float(d), 1))

    # ------------------------------------------------------------------ main step logic
    def step_live(self):
        """Unscripted play for one second."""
        b = self.ball
        if b["state"] == "flight":
            self.advance_flight()
            return
        if b["state"] == "dead":
            if self.t >= b["resume"]:
                self.resume()
            return
        pid = b["carrier"]
        side = self.team_of[pid]
        opp = self.other(side)
        rel = self.to_rel(side, self.ball_pos)
        st = self.style(side)
        ost = self.style(opp)

        # --- duel with nearest opponent
        nearest = min(self.on_pitch(opp), key=lambda q: np.linalg.norm(self.pos[q] - self.ball_pos))
        dn = np.linalg.norm(self.pos[nearest] - self.ball_pos)
        in_box = rel[0] > 88.5 and abs(rel[1] - 34) < 20.16
        key = (pid, b.get("recv_t"))
        if dn < 2.8 and key not in self.pressure_logged and self.role_of(nearest) != "GK":
            self.pressure_logged.add(key)
            ps_ = self.press_state.get(opp, {})
            self.log("pressure", opp, nearest, self.ball_pos, opponent_id=pid,
                     trigger=ps_.get("trigger"), counterpress=bool(ps_.get("counterpress")))
        cp_on = bool(self.press_state.get(opp, {}).get("counterpress"))
        if dn < 2.4 and self.role_of(nearest) != "GK" and self.rng.random() < (0.22 if in_box else (0.4 if cp_on else 0.12)):
            agg = self.mod(nearest, "aggression")
            mult = self.turnover_mult(side)
            ratio = self.attr(nearest, "tackling") / ((self.attr(nearest, "tackling") + self.attr(pid, "dribbling")) / 2)
            p_win = 0.55 * ratio * agg * (1 - self.mod(nearest, "duel_penalty", 0.0)) * mult * (0.8 + 0.4 * ost.get("press", 0.5))
            p_win /= max(self.mod(pid, "dribble_success"), 0.3)
            if cp_on:
                p_win *= 1.35      # counter-press: carrier is still disorganised right after winning the ball
            p_foul = 0.3 * (1.7 - self.attr(nearest, "discipline") / 100) * self.mod(nearest, "foul_rate") * agg
            mor = self.morale[opp]
            ph = self.pprof.get(nearest, {}).get("pressure_handling", 70)
            p_foul *= 1 + max(0.0, 1 - mor) * 4 * (1.3 - ph / 100)
            if in_box or self.chain_soon():
                p_foul = 0.0     # no penalties (they would change the scripted score); no stoppages right before scripted moves
            r = self.rng.random()
            if r < p_foul:
                self.log("foul", opp, nearest, self.ball_pos, outcome="free_kick", victim_id=pid)
                self.log("foul_won", side, pid, self.ball_pos)
                self.dead("free_kick", side, self.ball_pos, int(self.rng.integers(14, 32)), taker=pid)
                return
            if r < p_foul + p_win:
                self.log("tackle", opp, nearest, self.ball_pos, outcome="won", opponent_id=pid)
                self.log("dispossessed", side, pid, self.ball_pos)
                self.give_ball(nearest)
                return
            self.log("take_on", side, pid, self.ball_pos, outcome="success", opponent_id=nearest)
            self.log("tackle", opp, nearest, self.ball_pos, outcome="lost", opponent_id=pid)

        b["hold"] -= 1
        if b["hold"] > 0:
            return

        # --- decide action
        dgoal = np.linalg.norm(GOAL - rel)
        central = abs(rel[1] - 34) < 18
        spt = b.get("set_piece")
        if self.chain_soon() and not spt:
            self.do_pass(pid)
            return
        if spt in ("corner", "long_throw", "free_kick_cross") or (spt and rel[0] > 78):
            self.do_cross(pid, sp=spt if isinstance(spt, str) else "free_kick_cross")
            return
        if spt == "direct_free_kick":
            self.do_shot(pid, direct_fk=True)
            return
        if rel[0] > 96 and abs(rel[1] - 34) > 9 and self.rng.random() < 0.35:
            self.do_cutback(pid)
            return
        if rel[0] > 82 and abs(rel[1] - 34) > 16 and self.rng.random() < 0.06 * (1 + 2.0 * st.get("directness", 0.4)) * st.get("cross_appetite", 1.0):
            self.do_cross(pid)
            return
        if central and dgoal < (30 if st.get("shot_appetite", 1.0) > 1.3 else 26):
            p_shot = (0.075 if dgoal < 16 else 0.04) * (0.6 + self.attr(pid, "finishing") / 200) * st.get("shot_appetite", 1.0)
            if self.in_transition(side):
                p_shot *= 1.5 + 2.5 * st.get("directness", 0.4)
            if self.rng.random() < p_shot:
                self.do_shot(pid)
                return
        self.do_pass(pid)

    def turnover_mult(self, side):
        """Possession controller: nudges turnovers so possession tracks the script's target."""
        target = self.phase()["home_possession"]
        err = self.poss_ema - target
        m = math.exp(10.0 * err)
        return m if side == "home" else 1 / m

    def do_pass(self, pid):
        side = self.team_of[pid]
        opp = self.other(side)
        st = self.style(side)
        rel_b = self.to_rel(side, self.ball_pos)
        gk_mode = self.ball.get("goal_kick")
        cands, ws = [], []
        for q in self.on_pitch(side):
            if q == pid:
                continue
            if self.role_of(q) == "GK" and rel_b[0] > 35:
                continue
            d = np.linalg.norm(self.pos[q] - self.ball_pos)
            if d < 4 or d > (78 if gk_mode == "long" else 60):
                continue
            rq = self.to_rel(side, self.pos[q])
            if gk_mode == "long" and rq[0] < 45:
                continue
            if gk_mode == "short" and d > 28:
                continue
            prog = rq[0] - rel_b[0]
            openness = min(np.linalg.norm(self.pos[o] - self.pos[q]) for o in self.on_pitch(opp))
            dirn = st.get("directness", 0.4) * (1.8 if self.in_transition(side) else 1.0)
            w = math.exp(dirn * prog / 14.0) * (min(openness, 9) / 9 + 0.05)
            w *= math.exp(-((d - 17) / (16 + 14 * st.get("directness", 0.4))) ** 2)
            # attack the side of a booked opponent
            for o in self.on_pitch(opp):
                bias = self.mod(o, "opponent_target_bias")
                if bias != 1.0 and np.linalg.norm(self.pos[o] - self.pos[q]) < 18:
                    w *= bias
            if self.role_of(q) in ("ST", "RS", "LS"):
                w *= 0.45
            cands.append(q)
            ws.append(max(w, 1e-4))
        if not cands:
            b = self.ball
            b["hold"] = 1
            return
        ws = np.array(ws) / sum(ws)
        q = cands[int(self.rng.choice(len(cands), p=ws))]
        d = np.linalg.norm(self.pos[q] - self.ball_pos)
        rq = self.to_rel(side, self.pos[q])
        prog = rq[0] - rel_b[0]
        openness = min(np.linalg.norm(self.pos[o] - self.pos[q]) for o in self.on_pitch(opp))
        pressure = min(np.linalg.norm(self.pos[o] - self.ball_pos) for o in self.on_pitch(opp))
        kind = "long_pass" if d > 32 else "pass"
        self.next_back_pass = prog < -5
        if prog > 10 and self.role_of(q) in ("ST", "RS", "LS", "RW", "LW") and openness > 3:
            kind = "through_ball"
        p_ok = 0.955 - 0.0045 * max(0, d - 15) - (0.07 if pressure < 3 else 0) - 0.16 * max(0, (4 - openness) / 4)
        p_ok += (self.attr(pid, "passing") - 75) / 350
        p_ok += (self.morale[side] - 1.0) * 0.08
        if rq[0] > 82:
            p_ok -= 0.08
        p_fail = (1 - clamp(p_ok, 0.3, 0.99)) * self.turnover_mult(side)
        if self.press_state.get(opp, {}).get("counterpress"):
            p_fail *= 1.6
        # offside
        if prog > 8 and rq[0] > 70 and self.rng.random() < 0.035 and not self.chain_soon():
            self.launch(pid, q, kind, success=False, end=self.pos[q].copy())
            self.events[-1]["outcome"] = "offside"
            self.ball["offside"] = q
            return
        if self.rng.random() < p_fail:
            if self.rng.random() < 0.72 or self.chain_soon():
                mid = (self.ball_pos + self.pos[q]) / 2
                icpt = min(self.on_pitch(opp), key=lambda o: np.linalg.norm(self.pos[o] - mid) + 0.5 * np.linalg.norm(self.pos[o] - self.pos[q]))
                self.launch(pid, q, kind, success=False, interceptor=icpt, end=self.pos[icpt].copy())
            else:
                # ball runs out of play
                end = self.pos[q] + self.rng.normal(0, 6, 2)
                out = end.copy()
                if self.rng.random() < 0.6:
                    out[1] = -0.5 if end[1] < 34 else W + 0.5
                else:
                    gx = self.to_abs(side, [105.5, end[1]])[0]
                    out[0] = gx
                self.launch(pid, q, kind, success=False, end=out)
                self.ball["out"] = True
            return
        self.launch(pid, q, kind, success=True)

    def do_cross(self, pid, sp=None):
        side = self.team_of[pid]
        opp = self.other(side)
        box = [q for q in self.on_pitch(side) if q != pid and self.to_rel(side, self.pos[q])[0] > 84
               and abs(self.to_rel(side, self.pos[q])[1] - 34) < 14]
        ctype = {"corner": "corner", "long_throw": "long_throw", "free_kick_cross": "free_kick"}.get(sp, "open_play")
        if box:
            q = max(box, key=lambda x: self.attr(x, "heading") + self.rng.normal(0, 8))
            hd = self.attr(q, "heading")
            # who defends the target: assigned marker (man-marking) or nearest defender (zonal / open play)
            marker = getattr(self, "sp_markers", {}).get(q) if sp else None
            if marker not in self.teams[opp]["lineup"]:
                marker = min([o for o in self.on_pitch(opp) if self.role_of(o) != "GK"],
                             key=lambda o: np.linalg.norm(self.pos[o] - self.pos[q]))
            p_ok = 0.24 + (hd - self.attr(marker, "heading")) / 170 + (self.attr(pid, "passing") - 70) / 400
            if "set piece" in " ".join(self.players[marker].get("weaknesses", [])).lower():
                p_ok += 0.12     # e.g. Achebe-Ward loses his man at set pieces
            gk = self.gk(opp)
            if "cross" in " ".join(self.players[gk].get("weaknesses", [])).lower():
                p_ok += 0.05     # keeper weak on high balls
            if not sp:
                p_ok /= self.turnover_mult(side) ** 0.5
            if self.rng.random() < p_ok:
                self.launch(pid, q, "cross", success=True)
                self.events[-1].update(cross_type=ctype, set_piece=bool(sp), marker_id=marker)
                self.ball["then"] = "header"
                return
            end = self.pos[q].copy()
        else:
            end = self.to_abs(side, [96, 34 + self.rng.normal(0, 5)])
            q = None
        defs = [o for o in self.on_pitch(opp)]
        clearer = min(defs, key=lambda o: np.linalg.norm(self.pos[o] - end))
        self.launch(pid, q, "cross", success=False, interceptor=clearer, end=end)
        self.events[-1].update(cross_type=ctype, set_piece=bool(sp))
        self.ball["clear"] = True

    def do_cutback(self, pid):
        side = self.team_of[pid]
        opp = self.other(side)
        cands = [q for q in self.on_pitch(side) if q != pid and 84 < self.to_rel(side, self.pos[q])[0] < 96
                 and abs(self.to_rel(side, self.pos[q])[1] - 34) < 11]
        if not cands:
            self.do_pass(pid)
            return
        q = min(cands, key=lambda c: min(np.linalg.norm(self.pos[o] - self.pos[c]) for o in self.on_pitch(opp)) * -1)
        if self.rng.random() < 0.5:
            self.launch(pid, q, "cross", success=True)
            self.events[-1].update(cross_type="cutback", set_piece=False)
            self.ball["then"] = "shot"
        else:
            clearer = min(self.on_pitch(opp), key=lambda o: np.linalg.norm(self.pos[o] - self.pos[q]))
            self.launch(pid, q, "cross", success=False, interceptor=clearer, end=self.pos[q].copy())
            self.events[-1].update(cross_type="cutback", set_piece=False)
            self.ball["clear"] = True

    def xg(self, side, xy_abs, header=False):
        rel = self.to_rel(side, xy_abs)
        d = np.linalg.norm(GOAL - rel)
        a1 = np.array([105, 30.34]) - rel
        a2 = np.array([105, 37.66]) - rel
        ang = abs(math.atan2(a1[0] * a2[1] - a1[1] * a2[0], a1 @ a2))
        z = -1.1 - 0.12 * d + 1.3 * ang
        v = 1 / (1 + math.exp(-z))
        return round(v * (0.55 if header else 1.0), 3)

    def gk(self, side):
        for q in self.on_pitch(side):
            if self.role_of(q) == "GK":
                return q
        return self.on_pitch(side)[0]

    def do_shot(self, pid, header=False, forced=None, direct_fk=False):
        side = self.team_of[pid]
        opp = self.other(side)
        xg = self.xg(side, self.ball_pos, header)
        if direct_fk:
            xg = round(xg * 0.55, 3)      # wall + keeper set: direct free kicks are low quality
        body = "head" if header else "foot"
        pattern = "from_free_kick" if direct_fk else self.play_pattern(side)
        goal_abs = self.to_abs(side, [105, 34 + self.rng.normal(0, 2.5)])
        if forced is not None:
            outcome = forced["outcome"]
            xg = forced.get("xg", xg)
            pattern = forced.get("play_pattern") or pattern
            body = forced.get("body_part", body)
        else:
            r = self.rng.random()
            pressure = min(np.linalg.norm(self.pos[o] - self.ball_pos) for o in self.on_pitch(opp) if self.role_of(o) != "GK")
            if r < (0.45 if pressure < 2.5 else 0.2) + (0.15 if direct_fk else 0):
                outcome = "blocked"
            elif r < 0.24 + 0.33 + (self.attr(pid, "finishing") - 70) / 300:
                outcome = "saved"
            else:
                outcome = "off_target"
        # shot placement in the goal mouth (y: -3.66..3.66 from centre, z: 0..2.44 m) -> xGOT for shots on target
        gy = gz = xgot = None
        if outcome in ("goal", "saved"):
            sgn = 1 if self.rng.random() < 0.5 else -1
            if outcome == "goal":
                gy, gz = sgn * self.rng.uniform(1.6, 3.5), self.rng.uniform(0.1, 2.3)
            else:
                gy, gz = float(np.clip(self.rng.normal(0, 1.5), -3.4, 3.4)), self.rng.uniform(0.1, 1.9)
            qual = 0.6 * abs(gy) / 3.66 + 0.4 * (1.0 if (gz > 1.6 or gz < 0.35) else 0.3)
            xgot = round(clamp(xg * (0.55 + 1.5 * qual) + 0.02, 0.01, 0.97), 3)
            if outcome == "goal":
                xgot = max(xgot, round(min(0.97, xg * 1.1), 3))
            goal_abs = self.to_abs(side, [105, 34 + gy])
        elif outcome == "off_target":
            gy = float(self.rng.choice([-1, 1]) * self.rng.uniform(3.8, 7.0)) if self.rng.random() < 0.6 else float(self.rng.normal(0, 2))
            gz = self.rng.uniform(0, 1.0) if abs(gy) > 3.66 else self.rng.uniform(2.5, 4.5)
            goal_abs = self.to_abs(side, [105, 34 + gy])
        self.log("shot", side, pid, self.ball_pos, goal_abs, outcome, scripted=forced is not None, xg=xg, body_part=body,
                 distance_m=round(float(np.linalg.norm(GOAL - self.to_rel(side, self.ball_pos))), 1),
                 play_pattern=pattern, set_piece=pattern in ("from_corner", "from_free_kick", "from_throw_in"),
                 big_chance=xg >= 0.3, xgot=xgot,
                 goal_mouth_y=round(gy, 2) if gy is not None else None, goal_mouth_z=round(gz, 2) if gz is not None else None)
        if outcome == "goal":
            self.score[side] += 1
            self.events[-1]["score_home"] = self.score["home"]
            self.events[-1]["score_away"] = self.score["away"]
            self.ball_pos = goal_abs
            self.log("goal", side, pid, goal_abs, scripted=True, assist_id=forced.get("assist"),
                     pattern=forced.get("pattern"), description=forced.get("description"))
            self.shift_morale(side, 0.07, "goal scored")
            comp = self.tprof[opp].get("mental", {}).get("composure_when_behind", 0.7)
            d = -0.06 * (1.6 - comp)
            if self.score[opp] < self.score[side]:
                d -= 0.03
            self.shift_morale(opp, d, "goal conceded")
            self.dead("kickoff", opp, np.array([52.5, 34.0]), 55)
            return
        if outcome == "saved":
            g = self.gk(opp)
            self.log("save", opp, g, goal_abs, outcome="saved", shot_xg=xg)
            if self.rng.random() < 0.42:
                corner = self.to_abs(side, [104.5, 0.5 if self.to_rel(side, self.ball_pos)[1] < 34 else 67.5])
                self.dead("corner", side, corner, int(self.rng.integers(18, 30)))
            else:
                self.ball_pos = self.pos[g].copy()
                self.give_ball(g)
            return
        if outcome == "blocked":
            blk = min(self.on_pitch(opp), key=lambda o: np.linalg.norm(self.pos[o] - self.ball_pos))
            self.log("block", opp, blk, self.ball_pos)
            if self.rng.random() < 0.5:
                corner = self.to_abs(side, [104.5, 0.5 if self.to_rel(side, self.ball_pos)[1] < 34 else 67.5])
                self.dead("corner", side, corner, int(self.rng.integers(18, 30)))
            else:
                self.give_ball(blk)
            return
        self.dead("goal_kick", opp, self.to_abs(opp, [5.5, 34 + self.rng.choice([-9, 9])]), int(self.rng.integers(18, 32)))

    def advance_flight(self):
        b = self.ball
        frac = clamp((self.t - b["t0"]) / max(1, b["t1"] - b["t0"]), 0, 1)
        end = b["end"]
        if b["success"] and b["receiver"]:
            end = self.pos[b["receiver"]]
        elif b.get("interceptor") and not b.get("clear"):
            end = self.pos[b["interceptor"]]
        self.ball_pos = b["from"] + (end - b["from"]) * frac
        if self.t < b["t1"]:
            return
        passer = b["passer"]
        side = self.team_of[passer]
        opp = self.other(side)
        if b.get("offside"):
            self.log("offside", side, b["offside"], self.ball_pos)
            self.dead("free_kick", opp, self.ball_pos, int(self.rng.integers(8, 15)))
            return
        if b["success"] and b["receiver"]:
            q = b["receiver"]
            self.ball_pos = self.pos[q].copy()
            self.log("ball_receipt", side, q, self.ball_pos, scripted=b.get("forced", False))
            if b.get("then") == "header":
                self.do_shot(q, header=True)
                return
            if b.get("then") == "shot":
                self.do_shot(q)
                return
            self.give_ball(q, back_pass=b.get("back_pass", False))
            return
        if b.get("out"):
            end = b["end"]
            rel_end = self.to_rel(side, end)
            if rel_end[0] > 105:
                self.dead("goal_kick", opp, self.to_abs(opp, [5.5, 34 + self.rng.choice([-9, 9])]), int(self.rng.integers(18, 32)))
            else:
                pos = np.array([clamp(end[0], 1, 104), 0.0 if end[1] < 34 else W])
                self.ball_pos = pos
                self.log("out_of_play", side, passer, pos, outcome="throw_in")
                self.dead("throw_in", opp, pos, int(self.rng.integers(9, 20)))
            return
        icpt = b.get("interceptor")
        if icpt:
            if b.get("clear"):
                self.log("clearance", opp, icpt, self.pos[icpt])
                if self.rng.random() < 0.3:
                    corner = self.to_abs(side, [104.5, 0.5 if self.to_rel(side, self.ball_pos)[1] < 34 else 67.5])
                    self.dead("corner", side, corner, int(self.rng.integers(18, 30)))
                    return
                # loose clearance: whoever is closest to the landing spot
                land = self.to_abs(opp, [self.rng.uniform(35, 55), self.rng.uniform(10, 58)])
                self.ball_pos = self.pos[icpt].copy()
                self.ball = {"state": "flight", "from": self.ball_pos.copy(), "receiver": None, "passer": icpt,
                             "kind": "clearance", "t0": self.t, "t1": self.t + 2, "success": False,
                             "interceptor": None, "end": land, "loose": True}
                return
            self.ball_pos = self.pos[icpt].copy()
            self.log("interception" if self.rng.random() < 0.4 else "ball_recovery", opp, icpt, self.ball_pos)
            self.give_ball(icpt)
            return
        if b.get("loose"):
            land = b["end"]
            q = min(self.on_pitch(), key=lambda o: np.linalg.norm(self.pos[o] - land))
            self.ball_pos = land.copy()
            self.log("ball_recovery", self.team_of[q], q, land)
            self.give_ball(q)
            return
        # fallback: nearest player
        q = min(self.on_pitch(), key=lambda o: np.linalg.norm(self.pos[o] - self.ball_pos))
        self.log("ball_recovery", self.team_of[q], q, self.ball_pos)
        self.give_ball(q)

    def resume(self):
        b = self.ball
        side = b["side"]
        taker = b["taker"]
        if taker not in self.teams[side]["lineup"]:
            taker = min(self.on_pitch(side), key=lambda q: np.linalg.norm(self.pos[q] - b["pos"]))
        self.pos[taker] = b["pos"].copy()
        self.ball_pos = b["pos"].copy()
        restart = b["restart"]
        spt = b.get("sp_type")
        self.log(restart, side, taker, self.ball_pos, set_piece_type=spt)
        self.give_ball(taker, origin=restart)
        self.ball["hold"] = 1
        if spt == "corner":
            short = self.tprof[side].get("set_pieces", {}).get("corner_short_share", 0.15)
            self.ball["set_piece"] = False if self.rng.random() < short else "corner"
            if not self.ball["set_piece"]:
                self.events[-1]["corner_variant"] = "short"
        elif spt in ("long_throw", "direct_free_kick", "free_kick_cross"):
            self.ball["set_piece"] = spt
        elif restart == "free_kick":
            self.ball["set_piece"] = True
        elif spt in ("goal_kick_short", "goal_kick_long"):
            self.ball["goal_kick"] = "short" if spt == "goal_kick_short" else "long"

    # ------------------------------------------------------------------ scripted chains
    def step_chain(self, c):
        side = c["team"]
        steps = c["_steps"]
        b = self.ball
        if not c.get("_started"):
            c["_started"] = True
            if b["state"] == "flight":
                # finish the flight instantly
                self.t1_save = self.t
                b["t1"] = self.t
                self.advance_flight()
            if self.ball["state"] == "dead":
                self.resume()
        b = self.ball
        if b["state"] == "flight":
            self.advance_flight()
            if self.ball["state"] != "carry":
                return
            self.after_arrival_in_chain(c)
            return
        if b["state"] == "dead":
            self.resume()
            return
        holder = b["carrier"]
        # which step is next?
        nxt = None
        for i, st in enumerate(steps):
            if not st.get("_done"):
                nxt = i
                break
        if nxt is None:
            return
        st = steps[nxt]
        if self.t >= st["t"] and holder == st["player"]:
            self.execute_step(c, nxt)
            return
        if holder != st["player"]:
            # deliver the ball to the step player so it arrives at st["t"]
            dist = np.linalg.norm(self.pos[st["player"]] - self.ball_pos)
            prev_action = steps[nxt - 1]["action"] if nxt > 0 else "pass"
            kind = prev_action if prev_action in ("long_pass", "through_ball", "cross") else ("long_pass" if dist > 32 else "pass")
            speed = 21 if kind in ("long_pass", "cross") else 15
            flight = max(1, int(math.ceil(dist / speed)))
            if self.t + flight >= st["t"] or self.t >= st["t"]:
                arrive = max(st["t"], self.t + 1)
                same_team = self.team_of[holder] == self.team_of[st["player"]]
                if same_team:
                    self.launch(holder, st["player"], kind, success=True, arrive=arrive, forced=True)
                    if steps[nxt]["action"] == "header":
                        self.ball["then_chain"] = True
                else:
                    self.launch(holder, None, "pass", success=False, interceptor=st["player"], arrive=arrive,
                                end=self.pos[st["player"]].copy(), forced=True)
            return
        # holder is the right player but too early: carry towards the step position
        return

    def after_arrival_in_chain(self, c):
        steps = c["_steps"]
        for i, st in enumerate(steps):
            if not st.get("_done"):
                if self.ball["state"] == "carry" and self.ball["carrier"] == st["player"] and self.t >= st["t"]:
                    self.execute_step(c, i)
                return

    def execute_step(self, c, i):
        st = c["_steps"][i]
        st["_done"] = True
        side = self.team_of[st["player"]]
        pid = st["player"]
        a = st["action"]
        last = i == len(c["_steps"]) - 1
        if a == "interception":
            # interception event was logged on arrival
            self.ball["hold"] = 99
        elif a in ("shot", "header"):
            if c["type"] == "goal":
                forced = {"outcome": "goal", "xg": c.get("xg"), "body_part": c.get("body_part"), "assist": c.get("assist"),
                          "play_pattern": c.get("play_pattern"),
                          "pattern": c.get("pattern"), "description": c.get("description")}
            else:
                forced = {"outcome": c["outcome"], "xg": c.get("xg"), "body_part": "head" if a == "header" else "foot"}
            self.do_shot(pid, header=(a == "header"), forced=forced)
            self.events[-1]["chain_description"] = c.get("description")
            self.events[-1]["significance"] = c.get("significance")
            c["_done"] = True
        elif a == "foul_end":
            self.do_card(c)
            c["_done"] = True
        else:
            self.ball["hold"] = 99   # keep the ball until the chain moves it on
        if last:
            c["_done"] = True

    def do_card(self, c):
        offender = c["player"]
        side = c["team"]
        victim = c.get("victim")
        pos = self.ball_pos.copy()
        if victim:
            self.log("foul", side, offender, pos, outcome="free_kick", victim_id=victim, scripted=True, reason=c["reason"])
            self.log("foul_won", self.team_of[victim], victim, pos, scripted=True)
        else:
            self.log("simulation", side, offender, pos, scripted=True, reason=c["reason"])
        card = c["card"]
        self.yellows[offender] += 1
        self.log("yellow_card" if card != "red" else "red_card", side, offender, pos, scripted=True,
                 reason=c["reason"], effect_text=c.get("effect_text"),
                 second_yellow=(card == "second_yellow"))
        fk_side = self.team_of[victim] if victim else self.other(side)
        self.dead("free_kick", fk_side, pos, 40 if card != "second_yellow" else 75)
        eff = c.get("effect", {})
        if card == "second_yellow" or eff.get("sent_off"):
            self.log("red_card", side, offender, pos, scripted=True, reason="Second yellow card")
            self.shift_morale(side, -0.06, "red card")
            self.shift_morale(self.other(side), 0.03, "opponent down to ten men")
            self.remove_player(offender)
            self.status_log.append({"clock": fmt_clock(self.period, self.t), "period": self.period, "player_id": offender,
                                    "change": "sent_off", "effect": c.get("effect_text")})
        else:
            for k, v in eff.items():
                self.mods[offender][k] = v
            self.status_log.append({"clock": fmt_clock(self.period, self.t), "period": self.period, "player_id": offender,
                                    "change": "yellow_card", "modifiers": eff, "effect": c.get("effect_text")})

    # ------------------------------------------------------------------ instant events
    def remove_player(self, pid):
        side = self.team_of[pid]
        self.teams[side]["lineup"].pop(pid, None)
        self.minutes_on.setdefault(pid, []).append((self.period, self.on_since.pop(pid, 0), self.t))
        self.pos.pop(pid, None)

    def add_player(self, pid, role):
        side = self.team_of[pid]
        self.teams[side]["lineup"][pid] = role
        self.pos[pid] = np.array([52.5, 0.5])
        self.vel[pid] = np.zeros(2)
        self.on_since[pid] = self.t

    def apply_instant(self, evs):
        if not evs:
            return
        if self.ball["state"] in ("carry", "flight") and self.active_chain() is None:
            side = self.poss_team or "home"
            pos = np.array([clamp(self.ball_pos[0], 2, 103), 0.0 if self.ball_pos[1] < 34 else W])
            self.log("stoppage", side, None, pos, outcome="substitution")
            self.dead("throw_in", side, pos, 30)
        role_maps = {}
        for ev in evs:
            side = ev["team"]
            if ev["type"] == "substitution":
                out, inn = ev["out"], ev["in"]
                role = self.teams[side]["lineup"].get(out)
                self.log("substitution", side, out, scripted=True, player_in_id=inn,
                         player_in_name=self.players[inn]["name"], reason=ev["reason"],
                         new_formation=ev.get("new_formation"), tactical_change=ev.get("tactical_change"),
                         impact=ev.get("impact"))
                self.remove_player(out)
                self.add_player(inn, role)
                self.status_log.append({"clock": fmt_clock(self.period, self.t), "period": self.period,
                                        "player_id": inn, "change": "substituted_on", "replaces": out})
                for tgt, m in {**ev.get("effects_on_opponent", {}), **ev.get("player_effects", {})}.items():
                    self.mods[tgt].update(m)
                    self.status_log.append({"clock": fmt_clock(self.period, self.t), "period": self.period,
                                            "player_id": tgt, "change": "effect_from_substitution", "modifiers": m,
                                            "effect": ev.get("impact")})
            else:
                self.log("tactical_change", side, None, scripted=True, new_formation=ev["new_formation"],
                         reason=ev.get("reason"), impact=ev.get("impact"))
            role_maps.setdefault(side, {}).update(ev.get("role_map", {}))
            if ev.get("new_formation"):
                role_maps[side]["__formation__"] = ev["new_formation"]
        for side, rm in role_maps.items():
            old = self.teams[side]["formation"]
            f = rm.pop("__formation__", old)
            self.teams[side]["formation"] = f
            for pid, role in rm.items():
                if pid in self.teams[side]["lineup"]:
                    self.teams[side]["lineup"][pid] = role
            self.snapshot_tactics(side)

    def snapshot_tactics(self, side):
        self.tactical_log.append({
            "clock": fmt_clock(self.period, self.t), "period": self.period,
            "team": self.teams[side]["info"]["id"], "formation": self.teams[side]["formation"],
            "players_on_pitch": len(self.teams[side]["lineup"]),
            "roles": dict(self.teams[side]["lineup"]),
        })

    # ------------------------------------------------------------------ run
    def run(self):
        added = self.s["meta"]["added_time"]
        kick = {1: "home", 2: "away"}
        for ev in self.s["timeline"]:
            if ev["type"] == "kickoff":
                kick[ev["period"]] = ev["team"]
        for pid in self.on_pitch():
            self.on_since[pid] = 0
        for period in (1, 2):
            self.period = period
            self.t = 0
            if period == 1:
                for side in ("home", "away"):
                    self.snapshot_tactics(side)
            else:
                for pid in self.on_pitch():
                    self.on_since[pid] = 0
            # line up for kick-off
            for side in ("home", "away"):
                for q in self.on_pitch(side):
                    a = self.anchor(q)
                    self.pos[q] = self.to_abs(side, [min(a[0] * 0.9, 50), a[1]])
                    self.vel[q] = np.zeros(2)
            self.ball_pos = np.array([52.5, 34.0])
            ks = kick[period]
            st_player = min(self.on_pitch(ks), key=lambda q: np.linalg.norm(self.pos[q] - self.ball_pos))
            self.dead("kickoff", ks, self.ball_pos, 0, taker=st_player)
            # instant events at t=0 (half-time subs) happen before the kick-off
            self.apply_instant(self.instant.get((period, 0), []))
            self.log("period_start", None, None)
            duration = (45 + added[str(period)]) * 60
            for t in range(duration + 1):
                self.t = t
                if t > 0:
                    self.apply_instant(self.instant.get((period, t), []))
                c = self.active_chain()
                if c is not None:
                    self.step_chain(c)
                else:
                    self.step_live()
                # movement
                in_poss = None
                kickoff = self.ball["state"] == "dead" and self.ball["restart"] == "kickoff"
                if self.ball["state"] == "carry":
                    in_poss = self.team_of[self.ball["carrier"]]
                elif self.ball["state"] == "flight":
                    in_poss = self.team_of[self.ball["passer"]]
                elif self.ball["state"] == "dead":
                    in_poss = self.ball["side"]
                tg = self.targets(self.ball_pos, in_poss, kickoff=kickoff)
                carrier = self.ball.get("carrier") if self.ball["state"] == "carry" else None
                carry_target = None
                if self.ball["state"] == "dead":
                    tk = self.ball["taker"]
                    if tk in tg:
                        tg[tk] = (self.ball["pos"], 0.8)
                if carrier:
                    side = self.team_of[carrier]
                    rel = self.to_rel(side, self.pos[carrier])
                    if self.role_of(carrier) == "GK":
                        carry_target = self.pos[carrier]
                    else:
                        boost = 9 if self.in_transition(side) and self.style(side).get("directness", 0.4) > 0.5 else 5
                        nx = min(rel[0] + boost, 94.0) if rel[0] < 94 else rel[0]
                        carry_target = self.to_abs(side, [nx, rel[1] + (34 - rel[1]) * 0.08])
                self.move_players(tg, carrier, carry_target)
                if carrier:
                    self.ball_pos = self.pos[carrier] + self.vel[carrier] * 0.15
                # possession bookkeeping (ball in play only)
                live = self.ball["state"] in ("carry", "flight")
                ml = (period, int(t // 60))
                if live and in_poss:
                    self.minute_poss[ml][in_poss] += 1
                    self.poss_ema += ((1.0 if in_poss == "home" else 0.0) - self.poss_ema) / 240
                # confidence slowly drifts back towards the pre-match level
                for sd in ("home", "away"):
                    self.morale[sd] += (self.morale_base[sd] - self.morale[sd]) / 1200
                if t % 60 == 0:
                    self.morale_log.append({"period": period, "minute": minute_label(period, t),
                                            "home": round(self.morale["home"], 3), "away": round(self.morale["away"], 3)})
                self.record_frame(live)
                self.frame += 1
            self.log("period_end", None, None)
            for pid in self.on_pitch():
                self.minutes_on.setdefault(pid, []).append((period, self.on_since.pop(pid, 0), duration))
        self.write_outputs()

    def record_frame(self, live):
        for q in self.on_pitch():
            sp = float(np.linalg.norm(self.vel[q]))
            self.tracking_rows.append((self.frame, self.period, self.t, fmt_clock(self.period, self.t), q,
                                       self.teams[self.team_of[q]]["info"]["id"], self.role_of(q),
                                       round(float(self.pos[q][0]), 2), round(float(self.pos[q][1]), 2), round(sp, 2)))
        holder = self.ball.get("carrier") if self.ball["state"] == "carry" else None
        self.tracking_rows.append((self.frame, self.period, self.t, fmt_clock(self.period, self.t), "ball",
                                   None, "live" if live else "dead",
                                   round(float(self.ball_pos[0]), 2), round(float(self.ball_pos[1]), 2), holder))

    # ------------------------------------------------------------------ outputs
    def write_outputs(self):
        os.makedirs(self.out, exist_ok=True)
        with open(os.path.join(self.out, "events.json"), "w", encoding="utf-8") as f:
            json.dump(self.events, f, indent=1, ensure_ascii=False)
        keys = []
        for e in self.events:
            for k in e:
                if k not in keys:
                    keys.append(k)
        with open(os.path.join(self.out, "events.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            for e in self.events:
                w.writerow(e)
        with open(os.path.join(self.out, "tracking.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["frame", "period", "second_in_period", "clock", "object_id", "team", "role_or_state", "x", "y",
                        "speed_ms_or_ball_holder"])
            w.writerows(self.tracking_rows)
        with open(os.path.join(self.out, "player_status.json"), "w", encoding="utf-8") as f:
            json.dump(self.status_log, f, indent=1, ensure_ascii=False)
        with open(os.path.join(self.out, "tactical_states.json"), "w", encoding="utf-8") as f:
            json.dump(self.tactical_log, f, indent=1, ensure_ascii=False)
        with open(os.path.join(self.out, "morale_timeline.json"), "w", encoding="utf-8") as f:
            json.dump({"note": "Modelled team confidence (1.0 = neutral). Drives pass accuracy, foul risk and tempo. Model output, not a measurement.",
                       "per_minute": self.morale_log, "events": self.morale_events}, f, indent=1)
        self.write_minute_stats()
        self.write_player_stats()

    def write_minute_stats(self):
        side_of = {self.teams[s]["info"]["id"]: s for s in ("home", "away")}
        added = self.s["meta"]["added_time"]
        buckets = []
        for p in (1, 2):
            for m in range(45 + added[str(p)]):
                buckets.append((p, m))
        cum = {s: defaultdict(float) for s in ("home", "away")}
        # distance per player per minute from tracking
        dist_min = defaultdict(float)
        last = {}
        for row in self.tracking_rows:
            fr, p, t, _, oid, team, role, x, y, _sp = row
            if oid == "ball":
                continue
            key = (p, oid)
            if key in last:
                lx, ly = last[key]
                dist_min[(p, int(t // 60), side_of[team])] += math.hypot(x - lx, y - ly)
            last[key] = (x, y)
        ev_by = defaultdict(list)
        for e in self.events:
            if e["team"]:
                ev_by[(e["period"], int(e["second_in_period"] // 60))].append(e)
        rows = []
        score = {"home": 0, "away": 0}
        tact = {"home": None, "away": None}
        tl = sorted(self.tactical_log, key=lambda r: (r["period"], r["clock"]))
        for (p, m) in buckets:
            for r in tl:
                if r["period"] < p or (r["period"] == p and parse_clock(r["clock"], p) <= m * 60 + 59):
                    tact[side_of[r["team"]]] = (r["formation"], r["players_on_pitch"])
            per = {s: defaultdict(float) for s in ("home", "away")}
            for e in ev_by[(p, m)]:
                s = side_of[e["team"]]
                t = e["type"]
                pm = per[s]
                if t == "pass":
                    pm["passes"] += 1
                    if e["outcome"] == "complete":
                        pm["passes_completed"] += 1
                elif t == "cross":
                    pm["crosses"] += 1
                    if e["outcome"] == "complete":
                        pm["crosses_completed"] += 1
                elif t == "shot":
                    pm["shots"] += 1
                    pm["xg"] += e.get("xg") or 0
                    if e["outcome"] in ("goal", "saved"):
                        pm["shots_on_target"] += 1
                elif t == "goal":
                    pm["goals"] += 1
                    score[s] += 1
                elif t == "corner":
                    pm["corners"] += 1
                elif t == "foul":
                    pm["fouls"] += 1
                elif t == "yellow_card":
                    pm["yellow_cards"] += 1
                elif t == "red_card":
                    pm["red_cards"] += 1
                elif t == "offside":
                    pm["offsides"] += 1
                elif t == "tackle":
                    pm["tackles"] += 1
                    if e["outcome"] == "won":
                        pm["tackles_won"] += 1
                elif t == "interception":
                    pm["interceptions"] += 1
                elif t == "substitution":
                    pm["substitutions"] += 1
            ph, pa = self.minute_poss[(p, m)]["home"], self.minute_poss[(p, m)]["away"]
            row = {"period": p, "minute": minute_label(p, m * 60), "minute_index": 45 * (p - 1) + m + 1 if m < 45 else None}
            ml = next((x for x in self.morale_log if x["period"] == p and x["minute"] == minute_label(p, m * 60)), None)
            if ml:
                row[f"{self.teams['home']['info']['id']}_morale"] = ml["home"]
                row[f"{self.teams['away']['info']['id']}_morale"] = ml["away"]
            for s in ("home", "away"):
                pm = per[s]
                own = ph if s == "home" else pa
                tot = ph + pa
                pm["possession_seconds"] = own
                pm["distance_km"] = dist_min[(p, m, s)] / 1000
                for k, v in pm.items():
                    cum[s][k] += v
                c = cum[s]
                pfx = self.teams[s]["info"]["id"]
                row[f"{pfx}_score"] = score[s]
                row[f"{pfx}_formation"] = tact[s][0] if tact[s] else None
                row[f"{pfx}_players_on_pitch"] = tact[s][1] if tact[s] else 11
                row[f"{pfx}_possession_pct_minute"] = round(100 * own / tot, 1) if tot else None
                ctot = cum["home"]["possession_seconds"] + cum["away"]["possession_seconds"] if s == "away" else None
                for k in ("passes", "passes_completed", "shots", "shots_on_target", "goals", "corners", "fouls",
                          "yellow_cards", "red_cards", "offsides", "tackles", "tackles_won", "interceptions", "crosses",
                          "substitutions"):
                    row[f"{pfx}_{k}_minute"] = int(pm[k])
                    row[f"{pfx}_{k}_cum"] = int(c[k])
                row[f"{pfx}_xg_minute"] = round(pm["xg"], 3)
                row[f"{pfx}_xg_cum"] = round(c["xg"], 3)
                row[f"{pfx}_pass_accuracy_cum"] = round(100 * c["passes_completed"] / c["passes"], 1) if c["passes"] else None
                row[f"{pfx}_distance_km_minute"] = round(pm["distance_km"], 3)
                row[f"{pfx}_distance_km_cum"] = round(c["distance_km"], 2)
            ctot = cum["home"]["possession_seconds"] + cum["away"]["possession_seconds"]
            for s in ("home", "away"):
                pfx = self.teams[s]["info"]["id"]
                row[f"{pfx}_possession_pct_cum"] = round(100 * cum[s]["possession_seconds"] / ctot, 1) if ctot else None
            rows.append(row)
        with open(os.path.join(self.out, "stats_per_minute.json"), "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=1)
        with open(os.path.join(self.out, "stats_per_minute.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        self.minute_rows = rows

    def write_player_stats(self):
        st = {}
        for pid, p in self.players.items():
            side = self.team_of[pid]
            mins = sum((b - a) for (_, a, b) in self.minutes_on.get(pid, [])) / 60
            st[pid] = {"player_id": pid, "name": p["name"], "team": self.teams[side]["info"]["id"], "no": p["no"],
                       "position": p["pos"], "starter": p["starter"], "minutes": round(mins, 1),
                       "distance_km": round(self.dist[pid] / 1000, 2), "sprints": self.sprints[pid],
                       "top_speed_kmh": round(self.top_speed[pid] * 3.6, 1),
                       "hi_runs": self.hi_runs[pid], "hi_distance_km": round(self.hi_dist[pid] / 1000, 2),
                       "accelerations": self.accels[pid], "decelerations": self.decels[pid], "pressures": 0,
                       "passes": 0, "passes_completed": 0, "key_passes": 0, "crosses": 0, "shots": 0,
                       "shots_on_target": 0, "xg": 0.0, "goals": 0, "assists": 0, "tackles": 0, "tackles_won": 0,
                       "interceptions": 0, "fouls_committed": 0, "fouls_won": 0, "yellow_cards": 0, "red_cards": 0,
                       "touches": 0, "take_ons": 0, "saves": 0}
        prev = None
        for e in self.events:
            pid = e["player_id"]
            if not pid:
                continue
            s = st[pid]
            t = e["type"]
            if t in ("pass", "cross", "shot", "take_on", "ball_receipt", "interception", "ball_recovery", "clearance"):
                s["touches"] += 1
            if t == "pass":
                s["passes"] += 1
                s["passes_completed"] += e["outcome"] == "complete"
            elif t == "cross":
                s["crosses"] += 1
            elif t == "shot":
                s["shots"] += 1
                s["xg"] = round(s["xg"] + (e.get("xg") or 0), 3)
                s["shots_on_target"] += e["outcome"] in ("goal", "saved")
                # key pass = last completed pass/cross to the shooter
                for pe in reversed(self.events[:e["event_id"] - 1]):
                    if pe["type"] in ("pass", "cross") and pe["team"] == e["team"]:
                        if pe["outcome"] == "complete" and pe.get("receiver_id") == pid:
                            st[pe["player_id"]]["key_passes"] += 1
                        break
            elif t == "goal":
                s["goals"] += 1
                if e.get("assist_id"):
                    st[e["assist_id"]]["assists"] += 1
            elif t == "tackle":
                s["tackles"] += 1
                s["tackles_won"] += e["outcome"] == "won"
            elif t == "interception":
                s["interceptions"] += 1
            elif t == "foul":
                s["fouls_committed"] += 1
            elif t == "foul_won":
                s["fouls_won"] += 1
            elif t == "yellow_card":
                s["yellow_cards"] += 1
            elif t == "red_card" and e.get("reason") == "Second yellow card":
                s["red_cards"] += 1
            elif t == "take_on":
                s["take_ons"] += 1
            elif t == "save":
                s["saves"] += 1
            elif t == "pressure":
                s["pressures"] += 1
        rows = [r for r in st.values() if r["minutes"] > 0]
        for r in rows:
            r["pass_accuracy"] = round(100 * r["passes_completed"] / r["passes"], 1) if r["passes"] else None
        with open(os.path.join(self.out, "player_stats.json"), "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=1, ensure_ascii=False)
        with open(os.path.join(self.out, "player_stats.csv"), "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        self.player_rows = rows


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    script_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "..", "script", "match_script.json")
    out_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.join(here, "..", "output")
    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)
    ctx_path = os.path.join(os.path.dirname(script_path), "pre_match_context.json")
    if os.path.exists(ctx_path):
        with open(ctx_path, encoding="utf-8") as f:
            script["_context"] = json.load(f)
    m = Match(script, out_dir)
    m.run()
    print("Final score:", m.score)
    print("Events:", len(m.events), "Tracking rows:", len(m.tracking_rows))
