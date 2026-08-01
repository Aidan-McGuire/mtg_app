// Tests filterDecks by extracting it from static/app.js (a plain browser
// script with no exports) between its sentinel comments.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import assert from 'node:assert/strict';

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, '..', '..', 'static', 'app.js'), 'utf8');

const START = '// ── filterDecks ──';
const END = '// ── end filterDecks ──';
const from = src.indexOf(START);
const to = src.indexOf(END);
assert.ok(from !== -1 && to > from, 'filterDecks sentinel comments not found in static/app.js');

const filterDecks = new Function(`${src.slice(from, to)}; return filterDecks;`)();

const decks = [
  { id: 1, name: 'Atraxa, Praetors\' Voice' },
  { id: 2, name: 'Lightning Aggro' },
  { id: 3, name: 'atraxa reanimator' },
  { id: 4, name: 'Mono Black Control' },
];

const cases = [
  ['atraxa', [1, 3]],
  ['ATRAXA', [1, 3]],
  ['aggro',  [2]],
  ['',       [1, 2, 3, 4]],
  ['   ',    [1, 2, 3, 4]],
  ['xyz',    []],
];

let failed = 0;
for (const [query, expectedIds] of cases) {
  const result = filterDecks(decks, query).map(d => d.id);
  try {
    assert.deepEqual(result, expectedIds);
    console.log(`  ok  ${JSON.stringify(query)}`);
  } catch {
    failed++;
    console.error(`  FAIL ${JSON.stringify(query)} -> ${JSON.stringify(result)}, expected ${JSON.stringify(expectedIds)}`);
  }
}
console.log(failed ? `\n${failed} failing` : `\nall ${cases.length} passing`);
process.exit(failed ? 1 : 0);
