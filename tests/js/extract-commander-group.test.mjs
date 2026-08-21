// Tests extractCommanderGroup by extracting it from static/app.js (a plain
// browser script with no exports) between its sentinel comments.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import assert from 'node:assert/strict';

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, '..', '..', 'static', 'app.js'), 'utf8');

const START = '// ── extractCommanderGroup ──';
const END = '// ── end extractCommanderGroup ──';
const from = src.indexOf(START);
const to = src.indexOf(END);
assert.ok(from !== -1 && to > from, 'extractCommanderGroup sentinel comments not found in static/app.js');

const extractCommanderGroup = new Function(`${src.slice(from, to)}; return extractCommanderGroup;`)();

const commander = { id: 'c', name: 'Atraxa', is_commander: true };
const tagged     = { id: 't', name: 'Bear',   is_commander: false, deck_tags: ['ramp'] };
const untagged   = { id: 'u', name: 'Bolt',   is_commander: false, deck_tags: [] };

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

{
  const { commanderGroup, rest } = extractCommanderGroup([tagged, commander, untagged]);
  check(
    'commander is split into its own group',
    commanderGroup,
    { label: 'Commander', cards: [commander] }
  );
  check(
    'rest excludes the commander, preserves order',
    rest.map(c => c.id),
    ['t', 'u']
  );
}

{
  const { commanderGroup, rest } = extractCommanderGroup([tagged, untagged]);
  check(
    'no commander in the list means commanderGroup is null',
    commanderGroup,
    null
  );
  check(
    'rest is unchanged when there is no commander',
    rest.map(c => c.id),
    ['t', 'u']
  );
}

console.log(failed ? `\n${failed} failing` : `\nall 4 checks passing`);
process.exit(failed ? 1 : 0);
