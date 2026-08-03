// Tests applyFilters (power/toughness range checks) by extracting it, along
// with its ptNumStrict helper, from static/app.js between its sentinel comments.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import assert from 'node:assert/strict';

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, '..', '..', 'static', 'app.js'), 'utf8');

const START = '// ── applyFilters ──';
const END = '// ── end applyFilters ──';
const from = src.indexOf(START);
const to = src.indexOf(END);
assert.ok(from !== -1 && to > from, 'applyFilters sentinel comments not found in static/app.js');

const applyFilters = new Function(`${src.slice(from, to)}; return applyFilters;`)();

function baseModel(overrides = {}) {
  return {
    text: '', colors: new Set(), colorlessOnly: false, types: new Set(),
    cmcMin: null, cmcMax: null, powerMin: null, powerMax: null,
    toughnessMin: null, toughnessMax: null, tags: new Set(),
    ...overrides,
  };
}

const cards = [
  { name: 'Grizzly Bears', power: '2', toughness: '2', cmc: 2, type_line: 'Creature — Bear', color_identity: 'G' },
  { name: 'Wise Elephant', power: '3', toughness: '5', cmc: 5, type_line: 'Creature — Elephant', color_identity: 'G' },
  { name: 'Steel Wall', power: '0', toughness: '4', cmc: 1, type_line: 'Artifact Creature — Wall', color_identity: '' },
  { name: 'Mystery Hydra', power: '*', toughness: '*', cmc: 1, type_line: 'Creature — Hydra', color_identity: 'G' },
  { name: 'Ancestral Vision', power: null, toughness: null, cmc: 1, type_line: 'Sorcery', color_identity: 'U' },
  { name: 'Compound Beast', power: '1+*', toughness: '1+*', cmc: 3, type_line: 'Creature — Beast', color_identity: 'G' },
];

const names = (result) => result.map(c => c.name);

const cases = [
  ['power range 1-3 excludes non-numeric/missing/out-of-range',
    baseModel({ powerMin: 1, powerMax: 3 }),
    ['Grizzly Bears', 'Wise Elephant']],
  ['toughness range 2-4 excludes non-numeric/missing/out-of-range',
    baseModel({ toughnessMin: 2, toughnessMax: 4 }),
    ['Grizzly Bears', 'Steel Wall']],
  ['power min only',
    baseModel({ powerMin: 2 }),
    ['Grizzly Bears', 'Wise Elephant']],
  ['power filter excludes compound variable power (1+*)',
    baseModel({ powerMin: 0 }),
    ['Grizzly Bears', 'Wise Elephant', 'Steel Wall']],
  ['no power/toughness filter passes everything through',
    baseModel(),
    ['Grizzly Bears', 'Wise Elephant', 'Steel Wall', 'Mystery Hydra', 'Ancestral Vision', 'Compound Beast']],
];

let failed = 0;
for (const [label, model, expectedNames] of cases) {
  const result = names(applyFilters(cards, model));
  try {
    assert.deepEqual(result, expectedNames);
    console.log(`  ok  ${label}`);
  } catch {
    failed++;
    console.error(`  FAIL ${label} -> ${JSON.stringify(result)}, expected ${JSON.stringify(expectedNames)}`);
  }
}
console.log(failed ? `\n${failed} failing` : `\nall ${cases.length} passing`);
process.exit(failed ? 1 : 0);
