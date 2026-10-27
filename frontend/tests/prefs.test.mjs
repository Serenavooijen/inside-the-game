// Preferences: Neutral changes nothing; My club / My player filters; the followed player's four states. Run: npm test.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { feedItems } from '../lib/feed.ts';
import { DEFAULT_PREFS, emphasisOf, parsePrefs } from '../lib/prefs.ts';
import { applyFeedFilter, insightTeam, mentionsPlayer } from '../lib/feed.ts';
import { playerFocus } from '../lib/lineups.ts';

const lineups = JSON.parse(readFileSync(new URL('../data/lineups/kba-ngr.json', import.meta.url), 'utf8'));
const byName = (n) => lineups.players.find((p) => p.name.endsWith(n));
const ins = (id, type, t, extra = {}) => ({ id, type, t, minute: String(Math.floor(t / 60)), text: '', status: 'checked', phase: 'done', evidence: [], generation: 1, ...extra });
const match = [
  ins('i-tac-scouting', 'tactics', 0, { observations: [{ observation: 'Kingsbridge built up in a 2-3-2-3.', factIds: ['C1'], consequence: '', compareToCup: 'n/a', team: 'kba' }] }),
  ...Array.from({ length: 18 }, (_, k) => ins(`i-tac-${k}`, 'tactics', 300 * (k + 1) + 21, { observations: [{ observation: 'Shape.', factIds: ['T1'], consequence: '', compareToCup: 'n/a', team: k % 2 ? 'kba' : 'ngr' }] })),
  ins('i-sub-46', 'substitution', 2823, { substitution: { team: 'ngr', minute: '46', stage: 'watch', kind: 'like-for-like', off: [{ playerId: 'NGR-02', n: 2, name: 'M. Quiroga', role: 'RB' }], on: [{ playerId: 'NGR-22', n: 22, name: 'A. Whitfield', role: 'RB' }], watch: [], heatmaps: [], heatmapLabels: [] } }),
  ins('i-goal-24', 'goal', 1394, { team: 'ngr', text: 'Adeyemi-Clarke finishes after Duarte’s long pass.' }),
  ins('i-goal-39', 'goal', 2321, { team: 'kba', text: 'Nakamura-Brooks scores.' }),
  ins('i-red-53', 'card', 3259, { team: 'kba', text: 'Brannigan is sent off.' }),
];
const at = (t) => [match.filter((i) => i.t <= t), lineups.corners.filter((c) => c.t <= t)];

test('Neutral changes nothing: no club, no player, any filter value gives the feed of before', () => {
  for (const t of [600, 2700, 4212, 5821]) {
    for (const mode of ['casual', 'analyst']) {
      const before = feedItems(...at(t), mode);
      assert.deepEqual(feedItems(...at(t), mode, { filter: 'all', club: 'neutral', player: null }), before);
      assert.deepEqual(feedItems(...at(t), mode, { filter: 'club', club: 'neutral', player: null }), before);
      assert.deepEqual(feedItems(...at(t), mode, { filter: 'player', club: 'neutral', player: null }), before);
    }
  }
  for (const i of match) assert.equal(emphasisOf(insightTeam(i), 'neutral'), 'none');
  assert.deepEqual(DEFAULT_PREFS, { club: 'neutral', playerId: null, stripCollapsed: true, tacticsView: 'club', mode: 'casual' });
});

test('saved preferences: broken or missing values fall back to the defaults', () => {
  assert.deepEqual(parsePrefs(null), DEFAULT_PREFS);
  assert.deepEqual(parsePrefs('{not json'), DEFAULT_PREFS);
  assert.deepEqual(parsePrefs('{"club":"ngr","playerId":"NGR-08","mode":"analyst","stripCollapsed":false}'),
    { club: 'ngr', playerId: 'NGR-08', stripCollapsed: false, tacticsView: 'club', mode: 'analyst' });
  assert.deepEqual(parsePrefs('{"club":42,"mode":"expert"}'), DEFAULT_PREFS);
});

test('My club: only Northgate cards and corners, the rules of the feed still hold', () => {
  const items = feedItems(...at(5821), 'analyst', { filter: 'club', club: 'ngr', player: null });
  assert.ok(items.length > 0);
  for (const x of items) assert.equal(x.kind === 'corner' ? x.corner.team : insightTeam(x.insight), 'ngr');
  assert.deepEqual(items.map((x) => x.t), [...items.map((x) => x.t)].sort((a, b) => b - a));
  // casual mode still hides the tactics cards
  assert.ok(!feedItems(...at(5821), 'casual', { filter: 'club', club: 'ngr', player: null }).some((x) => x.kind === 'insight' && x.insight.type === 'tactics'));
  assert.equal(emphasisOf('ngr', 'ngr'), 'mine');
  assert.equal(emphasisOf('kba', 'ngr'), 'opponent');
});

test('My player: cards that name the player or have him in a substitution, and his corners', () => {
  const duarte = { id: 'NGR-08', name: byName('Duarte').name };
  const [cards] = applyFeedFilter(...at(5821), { filter: 'player', club: 'neutral', player: duarte });
  assert.deepEqual(cards.map((i) => i.id), ['i-goal-24']);
  assert.ok(mentionsPlayer(match.find((i) => i.id === 'i-sub-46'), { id: 'NGR-02', name: 'M. Quiroga' }));
  assert.ok(!mentionsPlayer(match.find((i) => i.id === 'i-goal-39'), duarte));
});

test('the followed player in four states, from the line-up data', () => {
  const duarte = playerFocus(lineups, byName('Duarte').id, 1800);
  assert.equal(duarte.status, 'on');
  assert.ok(duarte.stats.touches > 0 && duarte.stats.km > 0);

  const quiroga = playerFocus(lineups, byName('Quiroga').id, 3000);
  assert.equal(quiroga.status, 'off');
  assert.equal(quiroga.player.off.minute, '46');
  assert.equal(quiroga.replacedBy.name, 'A. Whitfield');
  assert.deepEqual(quiroga.stats, playerFocus(lineups, byName('Quiroga').id, 5000).stats);   // final numbers

  const brannigan = playerFocus(lineups, byName('Brannigan').id, 3400);
  assert.equal(brannigan.status, 'red');
  assert.equal(brannigan.player.off.minute, '53');
  assert.equal(brannigan.formationAfter, '4-4-1');

  const dk = playerFocus(lineups, byName('Diallo-Kerr').id, 3000);
  assert.equal(dk.status, 'bench');
  assert.equal(dk.stats, null);
  assert.equal(playerFocus(lineups, byName('Diallo-Kerr').id, 4000).status, 'on');
  assert.equal(playerFocus(lineups, 'XXX', 100), null);
});

test('tactics per club: the right variant for ngr, kba and Neutral; otherwise the neutral card', async () => {
  const { perspectiveFor } = await import('../lib/prefs.ts');
  const report = JSON.parse(readFileSync(new URL('../../fixtures/scouting/kba-ngr-cup.json', import.meta.url), 'utf8'));
  const p = report.perspectives;
  const analyst = (club, tacticsView = 'club') => ({ club, mode: 'analyst', tacticsView });
  assert.equal(perspectiveFor(p, analyst('ngr')), p.ngr);            // Northgate fan: how to beat Kingsbridge
  assert.equal(perspectiveFor(p, analyst('kba')), p.kba);
  assert.match(p.ngr.levers[0].coachAction, /^Northgate/);
  assert.match(p.kba.levers[0].coachAction, /^Kingsbridge/);
  assert.equal(perspectiveFor(p, analyst('neutral')), null);         // Neutral: the card as it is
  assert.equal(perspectiveFor(p, { club: 'ngr', mode: 'casual', tacticsView: 'club' }), null);
  assert.equal(perspectiveFor(p, analyst('ngr', 'neutral')), null);  // the switch on the card
  assert.equal(perspectiveFor({ ngr: { status: 'rejected', levers: [], changes: [] } }, analyst('ngr')), null);
  assert.equal(perspectiveFor(undefined, analyst('ngr')), null);     // flag off: no perspectives at all
});
