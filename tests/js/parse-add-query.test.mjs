// Tests parseAddQuery by extracting it from static/app.js (a plain browser
// script with no exports) between its sentinel comments.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import assert from 'node:assert/strict';

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, '..', '..', 'static', 'app.js'), 'utf8');

const START = '// ── parseAddQuery ──';
const END = '// ── end parseAddQuery ──';
const from = src.indexOf(START);
const to = src.indexOf(END);
assert.ok(from !== -1 && to > from, 'parseAddQuery sentinel comments not found in static/app.js');

const parseAddQuery = new Function(`${src.slice(from, to)}; return parseAddQuery;`)();

const cases = [
  ['swamp',                { quantity: 1,   name: 'swamp' }],
  ['x20 swamp',            { quantity: 20,  name: 'swamp' }],
  ['X4 Bolt',              { quantity: 4,   name: 'Bolt' }],
  ['x1 swamp',             { quantity: 1,   name: 'swamp' }],
  ['20 swamp',             { quantity: 1,   name: '20 swamp' }],
  ['20x swamp',            { quantity: 1,   name: '20x swamp' }],
  ['x20',                  { quantity: 1,   name: 'x20' }],
  ['x20 ',                 { quantity: 1,   name: 'x20' }],
  ['x0 swamp',             { quantity: 1,   name: 'swamp' }],
  ['x9999 swamp',          { quantity: 999, name: 'swamp' }],
  ['1996 World Champion',  { quantity: 1,   name: '1996 World Champion' }],
  ['  x3   Forest  ',      { quantity: 3,   name: 'Forest' }],
  ['',                     { quantity: 1,   name: '' }],
];

let failed = 0;
for (const [input, expected] of cases) {
  try {
    assert.deepEqual(parseAddQuery(input), expected);
    console.log(`  ok  ${JSON.stringify(input)}`);
  } catch {
    failed++;
    console.error(`  FAIL ${JSON.stringify(input)} -> ${JSON.stringify(parseAddQuery(input))}, expected ${JSON.stringify(expected)}`);
  }
}
console.log(failed ? `\n${failed} failing` : `\nall ${cases.length} passing`);
process.exit(failed ? 1 : 0);
