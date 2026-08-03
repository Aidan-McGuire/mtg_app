// Tests applyFilters (power/toughness range checks, color identity, and exact
// color match) by extracting it, along with its ptNumStrict helper, from
// static/app.js between its sentinel comments.
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
    toughnessMin: null, toughnessMax: null, exactColors: new Set(),
    exactColorlessOnly: false, tags: new Set(),
    ...overrides,
  };
}

const cards = [
  { name: 'Grizzly Bears', power: '2', toughness: '2', cmc: 2, type_line: 'Creature — Bear', color_identity: 'G', colors: 'G' },
  { name: 'Wise Elephant', power: '3', toughness: '5', cmc: 5, type_line: 'Creature — Elephant', color_identity: 'G', colors: 'G' },
  { name: 'Steel Wall', power: '0', toughness: '4', cmc: 1, type_line: 'Artifact Creature — Wall', color_identity: '', colors: '' },
  { name: 'Mystery Hydra', power: '*', toughness: '*', cmc: 1, type_line: 'Creature — Hydra', color_identity: 'G', colors: 'G' },
  { name: 'Ancestral Vision', power: null, toughness: null, cmc: 1, type_line: 'Sorcery', color_identity: 'U', colors: 'U' },
  { name: 'Compound Beast', power: '1+*', toughness: '1+*', cmc: 3, type_line: 'Creature — Beast', color_identity: 'G', colors: 'G' },
  { name: 'Deathrite Shaman', power: '1', toughness: '2', cmc: 1, type_line: 'Creature — Elf Shaman', color_identity: 'BG', colors: 'BG' },
];

const names = (result) => result.map(c => c.name);

const cases = [
  // Note: Deathrite Shaman (power 1, toughness 2) is numeric, so it now
  // satisfies these three pre-existing power/toughness ranges too — its name
  // was added to their expected lists when the color fixture card was added.
  ['power range 1-3 excludes non-numeric/missing/out-of-range',
    baseModel({ powerMin: 1, powerMax: 3 }),
    ['Grizzly Bears', 'Wise Elephant', 'Deathrite Shaman']],
  ['toughness range 2-4 excludes non-numeric/missing/out-of-range',
    baseModel({ toughnessMin: 2, toughnessMax: 4 }),
    ['Grizzly Bears', 'Steel Wall', 'Deathrite Shaman']],
  ['power min only',
    baseModel({ powerMin: 2 }),
    ['Grizzly Bears', 'Wise Elephant']],
  ['power filter excludes compound variable power (1+*)',
    baseModel({ powerMin: 0 }),
    ['Grizzly Bears', 'Wise Elephant', 'Steel Wall', 'Deathrite Shaman']],
  ['exact color match on single letter excludes multicolor card',
    baseModel({ exactColors: new Set(['G']) }),
    ['Grizzly Bears', 'Wise Elephant', 'Mystery Hydra', 'Compound Beast']],
  ['exact color match on multiple letters matches only that precise set',
    baseModel({ exactColors: new Set(['B', 'G']) }),
    ['Deathrite Shaman']],
  ['exact colorless matches only the colorless card',
    baseModel({ exactColorlessOnly: true }),
    ['Steel Wall']],
  ['no power/toughness/color filter passes everything through',
    baseModel(),
    ['Grizzly Bears', 'Wise Elephant', 'Steel Wall', 'Mystery Hydra', 'Ancestral Vision', 'Compound Beast', 'Deathrite Shaman']],
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
