// Tests groupCardsByType by extracting it from static/app.js (a plain browser
// script with no exports) between its sentinel comments.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import assert from 'node:assert/strict';

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, '..', '..', 'static', 'app.js'), 'utf8');

const START = '// ── groupCardsByType ──';
const END = '// ── end groupCardsByType ──';
const from = src.indexOf(START);
const to = src.indexOf(END);
assert.ok(from !== -1 && to > from, 'groupCardsByType sentinel comments not found in static/app.js');

const groupCardsByType = new Function(`${src.slice(from, to)}; return groupCardsByType;`)();

const commander  = { id: 'c', name: 'Atraxa',  is_commander: true,  type_line: 'Legendary Creature — Phyrexian Angel' };
const creature    = { id: 'r', name: 'Bear',    is_commander: false, type_line: 'Creature — Bear' };
const instant     = { id: 'i', name: 'Bolt',    is_commander: false, type_line: 'Instant' };
const artifact    = { id: 'a', name: 'Signet',  is_commander: false, type_line: 'Artifact' };
const noTypeLine  = { id: 'n', name: 'Mystery', is_commander: false, type_line: '' };

let failed = 0;
function check(label, actual, expected) {
  try {
    assert.deepEqual(actual, expected);
    console.log(`  ok  ${label}`);
  } catch {
    failed++;
    console.error(`  FAIL ${label} -> ${JSON.stringify(actual)}, expected ${JSON.stringify(expected)}`);
  }
}

check(
  'commander gets its own leading group, others bucket by type',
  groupCardsByType([creature, commander, instant, artifact])
    .map(g => ({ label: g.label, ids: g.cards.map(c => c.id) })),
  [
    { label: 'Commander', ids: ['c'] },
    { label: 'Creature',  ids: ['r'] },
    { label: 'Instant',   ids: ['i'] },
    { label: 'Artifact',  ids: ['a'] },
  ]
);

check(
  'empty type groups are omitted',
  groupCardsByType([creature]).map(g => g.label),
  ['Creature']
);

check(
  'no commander in the list means no Commander group',
  groupCardsByType([creature, instant]).map(g => g.label),
  ['Creature', 'Instant']
);

check(
  'missing/blank type_line falls into Other',
  groupCardsByType([noTypeLine]).map(g => g.label),
  ['Other']
);

console.log(failed ? `\n${failed} failing` : `\nall 4 checks passing`);
process.exit(failed ? 1 : 0);
