// The feed merges agent cards with the corner cards. Run: npm test (node --test, no extra packages).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { feedItems, MAX_INSIGHTS } from '../lib/feed.ts';

const lineups = JSON.parse(readFileSync(new URL('../data/lineups/kba-ngr.json', import.meta.url), 'utf8'));

// A full match as the backend sends it with TACTICS_ENABLED=1: the scouting card at 0', a tactics card
// every 5 minutes, substitution cards and the moment cards (goals, cards).
const ins = (id, type, t) => ({ id, type, t, minute: String(Math.floor(t / 60)), text: '', status: 'checked', phase: 'done', evidence: [], generation: 1 });
const match = [
  ins('i-tac-scouting', 'tactics', 0),
  ...Array.from({ length: 18 }, (_, k) => ins(`i-tac-${k}`, 'tactics', 300 * (k + 1) + 21)),
  ins('i-sub-46', 'substitution', 2823), ins('i-sub-59', 'substitution', 3633), ins('i-sub-64', 'substitution', 3923),
  ins('i-goal-24', 'goal', 1394), ins('i-goal-39', 'goal', 2321), ins('i-red-53', 'card', 3259), ins('i-goal-68', 'goal', 4146),
];
const at = (t) => [match.filter((i) => i.t <= t), lineups.corners.filter((c) => c.t <= t)];
const kinds = (items) => items.map((x) => (x.kind === 'corner' ? 'corner' : x.insight.type));

test('at 70\' in Analyst mode the feed has tactics, substitution, moment and corner cards', () => {
  const items = feedItems(...at(4212), 'analyst');
  for (const k of ['tactics', 'substitution', 'goal', 'card', 'corner']) assert.ok(kinds(items).includes(k), k);
});

test('at 50 minutes the scouting card stays: 13 agent cards plus 4 corners do not hit the limit of 14', () => {
  const [insights, corners] = at(3000);
  assert.equal(insights.length, 13);
  assert.equal(corners.length, 4);
  const items = feedItems(insights, corners, 'analyst');
  assert.equal(items.length, 17);
  assert.equal(items.at(-1).kind === 'insight' && items.at(-1).insight.id, 'i-tac-scouting');
});

test('newest first, and corners never push an agent card out', () => {
  for (const t of [600, 2700, 4212, 5821]) {
    const [insights, corners] = at(t);
    const items = feedItems(insights, corners, 'analyst');
    assert.deepEqual(items.map((x) => x.t), [...items.map((x) => x.t)].sort((a, b) => b - a));
    const shown = items.filter((x) => x.kind === 'insight').length;
    assert.equal(shown, Math.min(MAX_INSIGHTS, insights.length));
    assert.equal(items.filter((x) => x.kind === 'corner').length, corners.length);
  }
});

test('casual mode hides the tactics cards but keeps substitutions, moments and corners', () => {
  const items = feedItems(...at(4212), 'casual');
  assert.ok(!kinds(items).includes('tactics'));
  for (const k of ['substitution', 'goal', 'corner']) assert.ok(kinds(items).includes(k), k);
});
