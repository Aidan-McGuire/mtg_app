// Tests sortGroupsByCollapsed by extracting it from static/app.js (a plain
// browser script with no exports) between its sentinel comments.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import assert from 'node:assert/strict';

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, '..', '..', 'static', 'app.js'), 'utf8');

const START = '// ── sortGroupsByCollapsed ──';
const END = '// ── end sortGroupsByCollapsed ──';
const from = src.indexOf(START);
const to = src.indexOf(END);
assert.ok(from !== -1 && to > from, 'sortGroupsByCollapsed sentinel comments not found in static/app.js');

const sortGroupsByCollapsed = new Function(`${src.slice(from, to)}; return sortGroupsByCollapsed;`)();

const A = { label: 'A' };
const B = { label: 'B' };
const C = { label: 'C' };
const D = { label: 'D' };

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
  'nothing collapsed leaves order unchanged',
  sortGroupsByCollapsed([A, B, C, D], new Set()).map(g => g.label),
  ['A', 'B', 'C', 'D']
);

check(
  'middle group collapsed moves to the end, others keep their order',
  sortGroupsByCollapsed([A, B, C, D], new Set(['B'])).map(g => g.label),
  ['A', 'C', 'D', 'B']
);

check(
  'two non-adjacent groups collapsed move to the end in original relative order',
  sortGroupsByCollapsed([A, B, C, D], new Set(['B', 'D'])).map(g => g.label),
  ['A', 'C', 'B', 'D']
);

check(
  'all groups collapsed leaves order unchanged',
  sortGroupsByCollapsed([A, B, C, D], new Set(['A', 'B', 'C', 'D'])).map(g => g.label),
  ['A', 'B', 'C', 'D']
);

check(
  'single group, not collapsed, leaves order unchanged',
  sortGroupsByCollapsed([A], new Set()).map(g => g.label),
  ['A']
);

check(
  'single group, collapsed, leaves order unchanged',
  sortGroupsByCollapsed([A], new Set(['A'])).map(g => g.label),
  ['A']
);

check(
  'empty array returns empty array',
  sortGroupsByCollapsed([], new Set()),
  []
);

console.log(failed ? `\n${failed} failing` : `\nall 7 checks passing`);
process.exit(failed ? 1 : 0);
