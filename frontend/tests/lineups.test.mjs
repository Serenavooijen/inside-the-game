// The Formation view of the Line-ups tab and the line height under Average positions. Run: npm test.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { formationAt, formationSpots, lineHeight } from '../lib/lineups.ts';

const data = JSON.parse(readFileSync(new URL('../data/lineups/kba-ngr.json', import.meta.url), 'utf8'));
const n = Object.fromEntries(data.players.map((p) => [p.id, p.n]));

/** Shirt numbers per line from the own goal outwards, each line from left to right (top to bottom). */
const lines = (team, t) => {
  const byX = new Map();
  for (const s of [...formationSpots(data, team, t)].sort((a, b) => a.x - b.x || a.y - b.y)) {
    if (!byX.has(s.x)) byX.set(s.x, []);
    byX.get(s.x).push(n[s.id]);
  }
  return [...byX.values()];
};

test('kick-off: 4-3-3 and 4-4-2, goalkeeper at the own goal, lines on the own half', () => {
  assert.deepEqual(lines('kba', 600), [[1], [3, 4, 5, 2], [10, 6, 8], [11, 9, 7]]);
  assert.deepEqual(lines('ngr', 600), [[1], [3, 5, 4, 2], [11, 8, 6, 7], [10, 9]]);
  for (const team of ['kba', 'ngr']) {
    const spots = formationSpots(data, team, 600);
    assert.equal(spots.length, 11);
    assert.ok(spots.every((s) => s.x < 52.5 && s.y > 0 && s.y < 68));
    assert.equal(spots.find((s) => n[s.id] === 1 && s.x === 5)?.y, 34);
  }
});

test('after the red card Kingsbridge play 4-4-1 with ten', () => {
  assert.equal(formationAt(data, 'kba', 3400), '4-4-1');
  assert.deepEqual(lines('kba', 3400), [[1], [3, 4, 5, 2], [11, 10, 8, 7], [9]]);
});

test('a substitute stands in the place of the player he replaced', () => {
  // 59': Achterberg (14) for Kovač (10) in central midfield; 46': Whitfield (22) for Quiroga (2) at right-back
  assert.deepEqual(lines('kba', 4212)[2], [11, 8, 14, 7]);
  assert.deepEqual(lines('ngr', 3000)[1], [3, 5, 4, 22]);
});

test('average line height: Kingsbridge play a much higher line than Northgate', () => {
  const kba = lineHeight(data, 'kba', 4212), ngr = lineHeight(data, 'ngr', 4212);
  assert.ok(kba > 35 && ngr < 35 && kba > ngr, `${kba} vs ${ngr}`);
});
