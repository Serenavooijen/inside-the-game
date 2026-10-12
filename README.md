# Premier-League-Hackathon

A fully synthetic, scripted football match for the *Inside the Game* hackathon, with a full analysis along the 12 components of football analysis.

| File | What |
|---|---|
| `DRAAIBOEK.md` | Match script: pre-match context (form, absences, schedule, coaches, set-piece profiles, match-ups), teams and players, phases, minute-by-minute moments, card and substitution effects with measured impact |
| `MATCH_ANALYSIS.md` | Analysis: attacking, defending, transitions, tactics, players, physical/mental, set pieces, advanced stats (xG, xGA, xGOT, PPDA, field tilt, progressive passes, deep completions, big chances, xT, set-piece xG), match-ups, context, coaching |
| `script/match_script.json` | The script as data (source of truth for the match) |
| `script/pre_match_context.json` | Pre-match context as data |
| `generator/generate_match.py` | 1 Hz match simulator that follows the script |
| `generator/analyze_match.py` | Computes all analysis metrics → `output/analysis.json` + figures |
| `generator/render_analysis.py` / `render_draaiboek.py` | Build the two Markdown documents |
| `output/` | events, tracking (1 frame/sec), per-minute stats, player stats, analysis, morale timeline, tactics, figures |

```bash
pip install numpy matplotlib
python generator/generate_match.py
python generator/analyze_match.py
python generator/render_analysis.py
python generator/render_draaiboek.py
```
