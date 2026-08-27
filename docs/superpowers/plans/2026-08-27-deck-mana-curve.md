# Deck Mana Curve in Preview Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show a small mana-curve bar chart in the deck list (text) view's
preview panel, always visible regardless of hover/focus state.

**Architecture:** One new pure function `computeManaCurve(deckCards)` returns
an array of 8 `{ label, count }` buckets. One new render function
`renderDeckManaCurve()` turns that into a CSS bar-chart markup string.
`renderDeckPreviewPanel()` prepends that markup unconditionally, before its
existing card-preview-or-empty-state block. New CSS classes reuse
`--accent`/`--muted`, no new palette.

**Tech Stack:** Vanilla JS (`static/app.js`), CSS (`static/style.css`), no
backend changes.

**Spec:** `docs/superpowers/backlog/031-deck-mana-curve.md`

## Global Constraints

- 8 buckets: CMC 0, 1, 2, 3, 4, 5, 6, "7+" (`cmc >= 7`), each card's cmc
  rounded via `Math.round(c.cmc ?? 0)`.
- Excludes from every bucket: commander (`c.is_commander`), Considering
  cards (`c.is_considering`), lands (`(c.type_line || '').includes('Land')`
  — same check as `hideLands` at `static/app.js:280`).
- Each card contributes its full `quantity` to its bucket.
- Not filtered by the content-search box — reads `deckState.deckCards`
  directly, not the `applyFilters(...)`-narrowed list.
- Bar chart is a single series (one hue: `--accent`) — no legend needed
  (dataviz skill: a single series needs no legend box). No interactivity
  (out of scope per spec) — so no hover/tooltip layer is added, and count
  labels are shown directly on every bar instead (acceptable here because
  there are only 8 fixed, always-visible buckets, unlike an information-dense
  chart where labeling every point would be chaos).
- Bars grow from a single baseline, capped thickness, small radius on the
  bar's top (rounded data-end), CMC label underneath each bar, count label
  above each bar's cap.
- No new charting library, no new color palette.

---

### Task 1: Add `computeManaCurve` and `renderDeckManaCurve`, wire into the preview panel

**Files:**
- Modify: `static/app.js` (new functions near `renderDeckPreviewPanel`,
  currently at `static/app.js:2045-2062`)
- Modify: `static/style.css` (new `.deck-mana-curve*` rules, placed near the
  existing `.deck-preview-*` rules at `static/style.css:575-624`)

**Interfaces:**
- Produces: `computeManaCurve(deckCards)` → `Array<{ label: string, count: number }>`
  of length 8, labels `'0','1','2','3','4','5','6','7+'` in order.
- Produces: `renderDeckManaCurve()` → HTML string, reads
  `deckState.deckCards` directly (module-level state already used
  throughout `app.js`).
- Consumes: `deckState.deckCards` (existing global), each card having
  `cmc`, `quantity`, `is_commander`, `is_considering`, `type_line`.

- [ ] **Step 1: Implement `computeManaCurve`**

Add just above `renderDeckPreviewPanel` (`static/app.js:2045`):

```js
function computeManaCurve(deckCards) {
  const labels = ['0', '1', '2', '3', '4', '5', '6', '7+'];
  const counts = new Array(8).fill(0);
  for (const c of deckCards) {
    if (c.is_commander || c.is_considering) continue;
    if ((c.type_line || '').includes('Land')) continue;
    const cmc = Math.round(c.cmc ?? 0);
    const idx = Math.min(Math.max(cmc, 0), 7);
    counts[idx] += c.quantity;
  }
  return labels.map((label, i) => ({ label, count: counts[i] }));
}
```

- [ ] **Step 2: Implement `renderDeckManaCurve`**

Add directly below it:

```js
function renderDeckManaCurve() {
  const buckets = computeManaCurve(deckState.deckCards);
  const max = Math.max(1, ...buckets.map(b => b.count));
  const bars = buckets.map(b => {
    const pct = Math.round((b.count / max) * 100);
    return `
      <div class="deck-mana-curve-col">
        <div class="deck-mana-curve-count">${b.count || ''}</div>
        <div class="deck-mana-curve-track">
          <div class="deck-mana-curve-bar" style="height: ${pct}%"></div>
        </div>
        <div class="deck-mana-curve-label">${esc(b.label)}</div>
      </div>`;
  }).join('');
  return `<div class="deck-mana-curve">${bars}</div>`;
}
```

Notes: `esc()` is already defined/used elsewhere in `app.js` for escaping
text into HTML (e.g. `esc(card.name)` in `renderDeckPreviewPanel`) — reuse
it rather than redefining escaping logic. Bucket labels are static digits/
`'7+'` so escaping is defensive, not load-bearing, but keeps style
consistent with the rest of the file.

- [ ] **Step 3: Wire into `renderDeckPreviewPanel`**

Current (`static/app.js:2045-2062`):

```js
function renderDeckPreviewPanel() {
  const el = document.getElementById('deck-preview-panel');
  if (!el) return;
  const card = resolvePreviewCard();
  if (!card) {
    el.innerHTML = '<div class="deck-preview-empty">Hover or focus a card to preview it here.</div>';
    return;
  }
  const imgHtml = card.image_uri
    ? `<img src="${API.imageUrl(card.image_uri)}" alt="${esc(card.name)}">`
    : `<div class="deck-preview-img-placeholder">${esc(card.name)}</div>`;
  el.innerHTML = `
    <div class="deck-preview-img">${imgHtml}</div>
    <div class="deck-preview-name">${esc(card.name)}</div>
    <div class="deck-preview-mana">${esc(card.mana_cost || '—')}</div>
    <div class="deck-preview-type">${esc(card.type_line || '')}</div>
    <div class="deck-preview-oracle">${esc(card.oracle_text || '')}</div>`;
}
```

Replace with (prepend the curve unconditionally, before the
card-preview-or-empty-state block):

```js
function renderDeckPreviewPanel() {
  const el = document.getElementById('deck-preview-panel');
  if (!el) return;
  const curveHtml = renderDeckManaCurve();
  const card = resolvePreviewCard();
  if (!card) {
    el.innerHTML = curveHtml + '<div class="deck-preview-empty">Hover or focus a card to preview it here.</div>';
    return;
  }
  const imgHtml = card.image_uri
    ? `<img src="${API.imageUrl(card.image_uri)}" alt="${esc(card.name)}">`
    : `<div class="deck-preview-img-placeholder">${esc(card.name)}</div>`;
  el.innerHTML = curveHtml + `
    <div class="deck-preview-img">${imgHtml}</div>
    <div class="deck-preview-name">${esc(card.name)}</div>
    <div class="deck-preview-mana">${esc(card.mana_cost || '—')}</div>
    <div class="deck-preview-type">${esc(card.type_line || '')}</div>
    <div class="deck-preview-oracle">${esc(card.oracle_text || '')}</div>`;
}
```

This function is only ever invoked from `renderDeckContent()` after list
view is made visible (grid view hides `#deck-preview-panel` and never calls
into this HTML), so no extra grid-view guard is needed here — matching the
spec's "no changes needed to the panel's grid-view-hides/list-view-shows
logic."

- [ ] **Step 4: Add CSS for the chart**

Add to `static/style.css`, after the existing `.deck-preview-oracle` rule
(around line 624):

```css
.deck-mana-curve {
  display: flex;
  align-items: flex-end;
  gap: 4px;
  height: 100px;
  padding-bottom: 4px;
  margin-bottom: 14px;
  border-bottom: 1px solid var(--border);
}
.deck-mana-curve-col {
  flex: 1 1 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  height: 100%;
  min-width: 0;
}
.deck-mana-curve-count {
  font-size: 11px;
  color: var(--muted);
  line-height: 1.4;
  height: 15px;
}
.deck-mana-curve-track {
  flex: 1;
  width: 100%;
  max-width: 22px;
  display: flex;
  align-items: flex-end;
}
.deck-mana-curve-bar {
  width: 100%;
  min-height: 2px;
  background: var(--accent);
  border-radius: 3px 3px 0 0;
}
.deck-mana-curve-label {
  font-size: 11px;
  color: var(--muted);
  line-height: 1.4;
  margin-top: 4px;
}
```

Notes on dataviz-skill mark specs applied here: bar top gets a small
rounded "data-end" (`3px 3px 0 0`), square at the baseline; bars share a
single baseline (`align-items: flex-end` on both the row and each track);
a `4px` gap separates adjacent bars (the skill's "surface gap" — here
implemented as inter-column gap since bars don't touch); count label acts
as the sparse direct label (values are visually small/coarse so all 8 are
labeled, which is acceptable for a fixed small bucket count, not a dense
point series); text (`count`, `label`) uses `--muted` (a text token), never
the bar's accent color, per "text never wears the data color."

- [ ] **Step 5: Manual reasoning / syntax check**

Run (prefer the ARM node, avoid dead Intel node at `/usr/local`):

```bash
/opt/homebrew/bin/node --check static/app.js
```

Expected: no output (syntax OK). Then manually trace, re-reading the diff,
that:
- `computeManaCurve` is called with `deckState.deckCards` (not a filtered
  list), so it's unaffected by the content-search box.
- The exclusion checks (`is_commander`, `is_considering`, land check) match
  the spec exactly and mirror the existing `hideLands` check's substring
  test.
- `renderDeckManaCurve()`'s output is prepended in both branches of
  `renderDeckPreviewPanel` (empty-state and card-preview state), so the
  curve is visible either way.
- `renderDeckContent()` still only calls `renderDeckPreviewPanel()`
  unconditionally at the end (`static/app.js:2088`), while the
  grid-view/list-view toggle (`static/app.js:2078-2086`) is untouched — so
  the panel (curve included) stays hidden in grid view exactly as before.

- [ ] **Step 6: Run the backend test suite**

```bash
python3 -m pytest
```

Expected: all tests pass (this change touches no backend code, so this is
a regression check only).

- [ ] **Step 7: Commit**

```bash
git add static/app.js static/style.css
git commit -m "feat: show mana curve in deck list-view preview panel"
```
