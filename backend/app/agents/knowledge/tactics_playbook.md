# Tactics playbook — Inside the Game

Reference for the **Scout** agent and specification for the **Stats Engine** (`backend/app/stats/tactics.py`).

Each concept has:
- an **id**;
- **what it looks like** on the pitch;
- **signals**: what the code measures from 1 Hz tracking and events. The Scout may only name a concept when its signals are in the FactSheet;
- **consequence**: what it typically means for the match;
- **coach response**: what the opposing staff would adjust.

Coordinates are in metres. x runs 0–105 towards the attacked goal (normalise per half), y runs 0–68. A **phase** is a stretch of possession by one team without interruption.

- **Build-up phase:** the ball is in the team's own third or own half, and play starts from the goalkeeper or centre-backs.
- **Progression phase:** the ball is in the middle third.
- **Final-third phase:** the ball is beyond x 70.

Roles come from the line-up in the match script (GK, CB, FB/WB, DM "6", CM "8", AM "10", W, ST). Use roles, never shirt numbers, to decide who is "the 6".

---

## 1. In possession — build-up

**B1 · Back three via a dropping 6 ("salida lavolpiana")**
- **Looks like:** the 6 drops between the two centre-backs. The centre-backs split wide and the full-backs push high.
- **Signals:** in build-up phases, share of frames where the DM's x is within 6 m of the centre-backs' mean x and its y lies between the two centre-backs. Also the number of players in the last line (3 vs 4), and the full-backs' mean x compared with the centre-backs' x.
- **Consequence:** 3v2 against a two-striker press, so a clean first pass. It costs a body in midfield, and the space in front of the back three becomes the next problem.
- **Coach response:** press with three up front, or let them have the ball and block the passing lanes into midfield.

**B2 · 6 drops beside a centre-back (wide drop)**
- **Looks like:** the 6 drops into the left or right half-space next to one centre-back, and the full-back on that side pushes on.
- **Signals:** the same as B1, but the DM's y is outside the centre-back pair, within 10 m of one of them. Record which side.
- **Consequence:** a back three skewed to one side, and an overload to build up on that flank.
- **Coach response:** show them towards that flank and press with the far-side winger stepping in.

**B3 · Full-back inverts into midfield**
- **Looks like:** a full-back moves inside next to the 6 instead of going up the touchline.
- **Signals:** the full-back's mean y in build-up phases is within 20 m of the centre line (y 34), and its x is level with the DM.
- **Consequence:** a box or 3-2 base and better protection against counters. Width now has to come from the wingers.
- **Coach response:** the opposing winger tracks inside, or the team accepts the 3-2 and presses the centre-backs.

**B4 · Goalkeeper as an extra build-up player**
- **Signals:** the share of build-up passes involving the goalkeeper, the goalkeeper's mean x in build-up, and how often he is touched in a phase.
- **Consequence:** numerical superiority against a high press. Risky under pressure.
- **Coach response:** a striker curves his run to cut the goalkeeper-to-centre-back lane, and the team presses on the goalkeeper's weaker side.

**B5 · Direct build-up / long ball**
- **Signals:** the share of build-up phases where the first progressive pass travels more than 35 m, and the long-ball share of goalkeeper distributions.
- **Consequence:** bypasses the press. Second balls decide possession.
- **Coach response:** win the first header, and stack the midfield around the drop zone.

**B6 · Build-up shape (2-3, 3-2, 3-1, 4-2)**
- **Signals:** clustering of outfield players' mean positions in build-up phases into lines. Report the shape string, for example "3-2-5".
- **Consequence:** shows where the free man is.
- **Coach response:** match the shape in the press, for example a 3-2 is pressed with a 3-2.

## 2. In possession — progression and final third

**P1 · Overload on one flank (overload to isolate)**
- **Signals:** the share of team presence (heatmap) and of passes in the left, centre and right channels in a window. Count the players within 20 m of the ball when it is wide.
- **Consequence:** the far-side winger is isolated 1v1 after a switch of play.
- **Coach response:** the far-side full-back stays narrow, and the team shifts quickly as a block.

**P2 · Switches of play**
- **Signals:** passes with a lateral distance over 30 m, per window.
- **Consequence:** they punish a narrow, ball-oriented block.
- **Coach response:** wingers defend in a line with the full-backs.

**P3 · Half-space occupation**
- **Signals:** the share of presence and receptions in the half-spaces: y between 13.8 and 24.8, and between 43.2 and 54.2, in the final third.
- **Consequence:** creates cut-backs and through balls behind the full-back.
- **Coach response:** the 6 or the 8 screens the half-space, and the full-back steps.

**P4 · Width and depth (pinning the back line)**
- **Signals:** the team's width in possession (y spread of the outfield players), and the striker's mean x relative to the opposition's last line.
- **Consequence:** stretches the block and opens the gaps between the lines.
- **Coach response:** keep the block compact, and accept crosses rather than gaps.

**P5 · Between-the-lines receptions**
- **Signals:** receptions between the opposition's defensive and midfield lines, per window.
- **Consequence:** the most dangerous zone. The receiver faces the goal.
- **Coach response:** reduce the distance between the lines, or let a centre-back step out.

**P6 · Crossing team vs combining team**
- **Signals:** crosses per final-third entry, box entries by pass, carry or cross, and the xG per shot type.
- **Consequence:** a crossing team needs height and runners. Low xG per cross means it is inefficient.
- **Coach response:** defend the box with numbers, and block the crosser.

**P7 · Runs in behind**
- **Signals:** forward runs over 20 km/h past the last line, through balls and long passes behind, and the opposition's line height when the pass is played.
- **Consequence:** pins the line back and opens space in midfield.
- **Coach response:** drop the line, or play offside with a well-timed step.

## 3. Out of possession

**D1 · Block height (high / mid / low block)**
- **Signals:** the mean x of the last line and of the first line when the opponent is in possession, per window.
- **Consequence:** a high block wins the ball near goal but leaves space behind. A low block concedes territory and protects the box.
- **Coach response:** against a high block, play long or over the top. Against a low block, use width, patience and set pieces.

**D2 · Compactness**
- **Signals:** the vertical distance between the deepest and the highest outfield player, and the horizontal width, without the ball.
- **Consequence:** a compact block is hard to play through. Gaps over about 35 m vertically invite passes between the lines.
- **Coach response:** play through the lines, or switch play to stretch the block.

**D3 · Pressing intensity (PPDA) and press triggers**
- **Signals:** PPDA in the opponent's 60%, the time to the first pressure after an opponent receives, and recoveries in the attacking third.
- **Consequence:** a high press wins the ball high but costs energy. Watch whether the intensity drops late in a half.
- **Coach response:** escape with a third man, play long, or use the goalkeeper.

**D4 · Pressing shape and cover shadows**
- **Signals:** the line-up of the first line when pressing: the number of players higher than the opponent's centre-backs, and which build-up player is left free most often (the most frequent first receiver).
- **Consequence:** shows the "free man" the opponent can use.
- **Coach response:** find the free man every time. That is the plan.

**D5 · Man-oriented vs zonal**
- **Signals:** the correlation of each defender's movement with one opponent (a distance kept within 5 m over phases) compared with keeping a zone.
- **Consequence:** man-marking can be dragged out of position by rotations.
- **Coach response:** use rotations and decoy runs to pull markers away.

**D6 · Defensive line behaviour**
- **Signals:** offsides won, the line's x when long balls are played, and how fast the line drops when the ball is released.
- **Consequence:** a high line with poor timing is vulnerable to balls in behind.
- **Coach response:** quick vertical passes, and runs from deep.

## 4. Transitions

**T1 · Counter-pressing (gegenpressing)**
- **Signals:** within 5 s of losing the ball, the players within 10 m of the ball and the recoveries within 5 s.
- **Consequence:** the opponent cannot counter, and the team wins the ball high.
- **Coach response:** the first pass after winning the ball goes forward and wide, away from the pressure.

**T2 · Rest defence**
- **Signals:** the number of outfield players behind the ball, and their spread, when the team has the ball in the final third.
- **Consequence:** few players behind the ball means high risk on a counter.
- **Coach response:** leave runners high and attack the space quickly after winning the ball.

**T3 · Counter-attacks**
- **Signals:** shots or box entries within 10 s of a recovery, and the speed of progression in metres per second.
- **Consequence:** the team is dangerous when the opponent is unbalanced.
- **Coach response:** rest defence, tactical fouls in the middle third, and do not overcommit the full-backs.

**T4 · Retreat after loss**
- **Signals:** the time for 8 outfield players to get behind the ball, and the mean drop speed.
- **Consequence:** shows whether the team defends in a block or in a chase.
- **Coach response:** play quick and vertical after winning the ball.

## 5. Set pieces

**S1 · Corners: zonal vs man, short corners**
- **Signals:** the corners' delivery zone and the share of short corners, the first contact (who wins it), and the shots from corners.
- **Consequence:** a repeated pattern is a scoring chance or a risk.
- **Coach response:** a blocker on the target man, and a defender at the near post.

**S2 · Free-kick and throw-in routines**
- **Signals:** repeated patterns: where the first pass goes after a throw-in in the attacking third.
- **Coach response:** prepare for the pattern.

## 6. Game management and changes

**G1 · Formation change**
- **Signals:** the shape string (B6) and the mean positions, compared with the previous window. Flag a change when two or more players' mean positions move more than 10 m.
- **Consequence:** shows a new plan, often after a goal, a card or a substitution.
- **Coach response:** respond to the new free man and the new overload.

**G2 · Substitution impact**
- **Signals:** 10 minutes before vs after the substitution: possession, xG, channel shares, line height, PPDA, and the substitute's heatmap compared with the replaced player's.
- **Consequence:** like-for-like (same zones) or a tactical switch (new zones, new shape).
- **Coach response:** adjust to the new player's zone, for example double up on a fresh winger.

**G3 · Game state behaviour (leading / drawing / trailing, 11 v 10)**
- **Signals:** the same metrics split by game state and by numbers on the pitch.
- **Consequence:** a team that drops deep when leading invites pressure. With 10 men, the shape and the block height change.
- **Coach response:** against a team that drops deep, use more width and bodies in the box. Against 10 men, switch play to tire them.

**G4 · Fatigue and intensity drop**
- **Signals:** sprint counts, high-speed distance and PPDA in 15-minute buckets, compared with the first 15 minutes.
- **Consequence:** pressing breaks down and space opens late in the game.
- **Coach response:** bring on fresh runners, and attack the tired zone.

## 7. Comparison with the previous match (scouting)

For each concept above, the scouting report from the cup match gives a **baseline value**. Every live fact can then include it, for example *"6 drops between the CBs in 34% of build-up phases (cup match: 71%)"*.

The Scout labels each observation:
- `same`: the plan as scouted;
- `changed`: a different plan today, which is the interesting part for the staff;
- `n/a`: no baseline.

---

## Rules for the Scout

1. Name a concept only if at least one of its signals is in the FactSheet. Cite those fact ids.
2. Use the concept names from this playbook, in plain English. Explain the concept in one clause for fans, for example "a back three in build-up, because the 6 drops in".
3. Order each observation as **structure → change → consequence → coach response**.
4. Consequence and coach response contain **no new numbers and no new names**.
5. Prefer what **changed** (compared with the previous window or the cup match) over what stayed the same. A coach wants the deviation.
6. 2–3 observations per analysis. Quality over coverage.

## Implementation notes for the Stats Engine

- Build a **tactical fingerprint** per team per window. Run each concept's detector and emit a `Fact` only when the signal is meaningful: enough phases or frames, for example at least 5 build-up phases. The fact text should already contain the value, the comparison with the previous window and the cup baseline.
- Pass the Scout **only the concept definitions whose detectors fired**, taken from this file and condensed to one line each. Never pass the whole playbook. That keeps the prompt short and fast.
- **The generator decides what can be found.** Check which behaviours `generate_match.py` actually simulates. If, for example, the 6 never drops in, then B1 can never fire. Where needed, script a few clear tactical behaviours per team and per phase in the match script. Examples:
  - Northgate's 6 drops in during build-up in the cup match, but not today;
  - Kingsbridge overload the left flank until the red card;
  - the substitutes at 64' and 76' change the channel shares.

  Then the demo has real, checkable stories to find. Mark scripted behaviours in the data, so tests can assert that the detectors find them.
