// Languages: the dictionary, which text a card shows, and the corner outcomes. Run: npm test.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { DICTS, LANGS, cardView, cornerOutcome, translator } from '../lib/dictionary.ts';

const lineups = JSON.parse(readFileSync(new URL('../data/lineups/kba-ngr.json', import.meta.url), 'utf8'));
const placeholders = (s) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
const numbers = (s) => (s.match(/\d+(?:[.,]\d+)?/g) ?? []).map((n) => n.replace(',', '.')).sort();

test('every language has every text, with the same placeholders as English', () => {
  assert.deepEqual(LANGS.map((l) => l.code), ['en', 'nl', 'es', 'fr']);
  for (const { code } of LANGS) {
    for (const [key, en] of Object.entries(DICTS.en)) {
      const s = DICTS[code][key];
      assert.ok(typeof s === 'string' && s.length > 0, `${code}.${key} is missing`);
      assert.deepEqual(placeholders(s), placeholders(en), `${code}.${key}`);
    }
  }
  assert.equal(translator('nl')('lineHeight', { h: 42 }), 'Gemiddelde linie: 42 m van eigen doel');
  assert.equal(translator('fr')('cornerFor', { nth: '4e', team: 'KBA' }), '4e corner pour KBA');
});

test('a card shows its translation only when it is checked, and English while it is analysed or streamed', () => {
  const tr = { nl: { status: 'checked', text: 'Doelpunt' }, es: { status: 'rejected', reason: 'Numbers differ' } };
  const done = { phase: 'done', translations: tr };
  assert.equal(cardView('en', done, false), 'source');
  assert.equal(cardView('nl', done, false), 'translated');
  assert.equal(cardView('nl', done, true), 'original');                   // the click on "translated · checked"
  assert.equal(cardView('es', done, false), 'english');                   // rejected: English with "EN"
  assert.equal(cardView('fr', done, false), 'english');                   // not (yet) there: English with "EN"
  assert.equal(cardView('nl', { phase: 'streaming', translations: tr }, false), 'source');
  assert.equal(cardView('nl', { phase: 'analysing' }, false), 'source');
  assert.equal(cardView('nl', { translations: tr }, false), 'translated'); // commentary has no phase
});

test('corner outcomes in every language keep their numbers and names', () => {
  for (const c of lineups.corners) {
    const names = c.outcome.text.match(/#\d+ [\p{L}-]+/gu) ?? [];
    for (const { code } of LANGS) {
      const out = cornerOutcome(c.outcome.text, code);
      assert.deepEqual(numbers(out), numbers(c.outcome.text), `${code}: ${out}`);
      for (const n of names) assert.ok(out.includes(n), `${code}: ${n} in ${out}`);
      if (code !== 'en') assert.notEqual(out, c.outcome.text, `${code}: ${out}`);
    }
  }
  assert.equal(cornerOutcome('Header by #5 Dijkhuis · xG 0.03 · off target', 'nl'), 'Kopbal van #5 Dijkhuis · xG 0.03 · naast');
  assert.equal(cornerOutcome('Cleared by NTG · #10 Petrov, penalty spot', 'es'), 'Despejado por NTG · #10 Petrov, punto de penalti');
});
