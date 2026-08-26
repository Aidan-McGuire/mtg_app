# Deck-Page "Locked Elsewhere" Indicator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show a distinct visual indicator — on cards already in the currently-open deck, and in the "Add cards" search results for that deck — when a card is owned but every copy is committed to *other* built decks (excluding the deck currently open).

**Architecture:** One new lightweight endpoint, `GET /api/decks/{deck_id}/allocations`, returns a `{card_id: qty}` map of everything allocated to built decks other than `deck_id`. The frontend fetches it once per deck-open (alongside the existing `deckCards` fetch in `selectDeck`), stores it in `deckState.allocatedElsewhere`, and a small `isLockedElsewhere(cardId)` helper does a plain client-side lookup — reused identically in `buildDeckCardTile`, `buildDeckTextRow`, and `renderDeckSearchResults`. This avoids touching the shared, multi-branch `/api/cards` search endpoint entirely.

**Tech Stack:** Python (FastAPI, sqlite3), vanilla JS, pytest.

**Spec:** `docs/superpowers/backlog/020-deck-page-allocated-elsewhere-indicator.md`

## Global Constraints

- Depends on items 018 (`decks.built`, merged) and 019 (`allocated_qty` on `/api/collection`, merged) — this item introduces the deck-relative variant of the same allocation rule.
- "Allocated" only counts a built deck's non-Considering `deck_cards` rows (`is_considering = 0`), matching items 018/019.
- The indicator is deck-relative: always excludes whichever deck is currently open, never the global total from item 019.
- Additive to the existing green owned checkmark — never replace it. Use a visually distinct color (this codebase has no existing "warning" CSS variable; reuse the existing danger-red already used by `.action-btn-danger:hover` — `#e74c3c` — rather than inventing a new color family).
- Do not modify `/api/cards` (the shared search endpoint) — this is a deck-specific concern, solved entirely by the new endpoint + client-side lookup.

---

### Task 1: Backend — `GET /api/decks/{deck_id}/allocations`

**Files:**
- Modify: `app.py` (new endpoint, placed after `get_deck_cards`)
- Test: `tests/test_deck_allocations.py` (new)

**Interfaces:**
- Produces: `GET /api/decks/{deck_id}/allocations` → `{card_id: quantity}` (JSON object, string keys per JSON semantics but FastAPI serializes int keys as strings automatically — the frontend only ever looks values up by card id, so this is transparent), consumed by Task 2.

- [ ] **Step 1: Write failing tests**

Create `tests/test_deck_allocations.py`. The base seeded DB (`tests/conftest.py`) has deck id 1 ("Test Deck") holding 4 copies of card id 1 ("Lightning Bolt"), and deck id 1 is NOT built by default.

```python
import sqlite3


def test_allocations_empty_when_no_other_built_decks(client):
    r = client.get("/api/decks/1/allocations")
    assert r.status_code == 200
    assert r.json() == {}


def test_allocations_excludes_the_deck_itself_even_if_built(client, db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE decks SET built = 1 WHERE id = 1")
    conn.commit()
    conn.close()

    r = client.get("/api/decks/1/allocations")
    assert r.status_code == 200
    assert r.json() == {}


def test_allocations_counts_other_built_decks(client, db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute("INSERT INTO decks (id, name, built) VALUES (2, 'Other Built Deck', 1)")
    conn.execute("INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (2, 1, 3)")
    conn.commit()
    conn.close()

    # From deck 1's perspective, card 1 is allocated 3 elsewhere (deck 2).
    r = client.get("/api/decks/1/allocations")
    assert r.json() == {"1": 3}

    # From deck 2's own perspective, its own 3 copies aren't "elsewhere" —
    # but deck 1's 4 copies would be, if deck 1 were built too. It isn't
    # (base fixture default), so deck 2 sees nothing allocated elsewhere.
    r2 = client.get("/api/decks/2/allocations")
    assert r2.json() == {}


def test_allocations_ignores_non_built_decks(client, db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute("INSERT INTO decks (id, name, built) VALUES (2, 'Not Built', 0)")
    conn.execute("INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (2, 1, 3)")
    conn.commit()
    conn.close()

    r = client.get("/api/decks/1/allocations")
    assert r.json() == {}


def test_allocations_ignores_considering_cards(client, db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute("INSERT INTO decks (id, name, built) VALUES (2, 'Other Built Deck', 1)")
    conn.execute("INSERT INTO deck_cards (deck_id, card_id, quantity, is_considering) VALUES (2, 1, 3, 1)")
    conn.commit()
    conn.close()

    r = client.get("/api/decks/1/allocations")
    assert r.json() == {}


def test_allocations_sums_across_multiple_other_built_decks(client, db_path):
    conn = sqlite3.connect(str(db_path))
    conn.execute("INSERT INTO decks (id, name, built) VALUES (2, 'Built Deck Two', 1)")
    conn.execute("INSERT INTO decks (id, name, built) VALUES (3, 'Built Deck Three', 1)")
    conn.execute("INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (2, 1, 2)")
    conn.execute("INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (3, 1, 1)")
    conn.commit()
    conn.close()

    r = client.get("/api/decks/1/allocations")
    assert r.json() == {"1": 3}
```

- [ ] **Step 2: Run them to verify they fail**

Run: `pytest tests/test_deck_allocations.py -v`
Expected: all FAIL with 404 (the route doesn't exist yet).

- [ ] **Step 3: Implement**

In `app.py`, immediately after `get_deck_cards` (ends with `return rows`), add:

```python
@app.get("/api/decks/{deck_id}/allocations")
def get_deck_allocations(deck_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT dc.card_id, SUM(dc.quantity) AS qty
            FROM deck_cards dc
            JOIN decks d ON d.id = dc.deck_id
            WHERE dc.is_considering = 0 AND d.built = 1 AND d.id != ?
            GROUP BY dc.card_id
        """, (deck_id,))
        return {row["card_id"]: row["qty"] for row in cur.fetchall()}
```

- [ ] **Step 4: Run the tests again to verify they pass**

Run: `pytest tests/test_deck_allocations.py -v`
Expected: PASS for all 6 tests.

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `pytest -v`
Expected: PASS for everything — purely additive new endpoint.

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_deck_allocations.py
git commit -m "feat: add GET /api/decks/{id}/allocations endpoint"
```

---

### Task 2: Frontend — fetch, lookup helper, and the two display locations

**Files:**
- Modify: `static/app.js` (`API`, `deckState`, `selectDeck`, `buildDeckCardTile`, `buildDeckTextRow`, `renderDeckSearchResults`)
- Modify: `static/style.css`

**Interfaces:**
- Consumes: `GET /api/decks/{id}/allocations` from Task 1.
- Produces: `isLockedElsewhere(cardId)` helper, used by all three render sites in this task.

- [ ] **Step 1: Add `API.getDeckAllocations`**

In `static/app.js`, find the existing `getDeckCards` method:

```js
  async getDeckCards(id) {
    const r = await fetch(`/api/decks/${id}/cards`);
    if (!r.ok) throw new Error('Failed to load deck');
    return r.json();
  },
```

Add immediately after it:

```js
  async getDeckAllocations(id) {
    const r = await fetch(`/api/decks/${id}/allocations`);
    if (!r.ok) throw new Error('Failed to load deck allocations');
    return r.json();
  },
```

- [ ] **Step 2: Add `allocatedElsewhere` to `deckState`**

In `static/app.js`, find:

```js
const deckState = {
  decks:          [],
  currentDeckId:  null,
  deckCards:      [],
```

Replace with:

```js
const deckState = {
  decks:              [],
  currentDeckId:      null,
  deckCards:          [],
  allocatedElsewhere: {},   // card id -> qty allocated to OTHER built decks
```

- [ ] **Step 3: Fetch it in `selectDeck`, in parallel with the existing calls**

In `static/app.js`, find:

```js
  try {
    deckState.deckCards = await API.getDeckCards(id);
    const [collTags, deckTags] = await Promise.all([
      API.listCollectionTags(),
      API.listDeckTags(id),
    ]);
```

Replace with:

```js
  try {
    const [cards, allocations, collTags, deckTags] = await Promise.all([
      API.getDeckCards(id),
      API.getDeckAllocations(id),
      API.listCollectionTags(),
      API.listDeckTags(id),
    ]);
    deckState.deckCards = cards;
    deckState.allocatedElsewhere = allocations;
```

- [ ] **Step 4: Add the `isLockedElsewhere` helper next to `qty()`**

In `static/app.js`, find:

```js
// ── qty ──
function qty(cardId) {
  return state.collection[cardId] || 0;
}
// ── end qty ──
```

Replace with:

```js
// ── qty ──
function qty(cardId) {
  return state.collection[cardId] || 0;
}
// ── end qty ──

function isLockedElsewhere(cardId) {
  const owned = qty(cardId);
  if (owned <= 0) return false;
  return owned <= (deckState.allocatedElsewhere[cardId] || 0);
}
```

(Placed right after the `qty` sentinel block, not inside it, since this helper is deck-specific — `qty()` itself stays generic/reusable and the existing `apply-filters.test.mjs` sentinel extraction is unaffected.)

- [ ] **Step 5: Show the indicator on grid tiles**

In `static/app.js`, find, inside `buildDeckCardTile`:

```js
  const ownedBadgeHtml = q > 0 ? OWNED_BADGE_HTML : '';
```

Replace with:

```js
  const ownedBadgeHtml = q > 0 ? OWNED_BADGE_HTML : '';
  const lockedBadgeHtml = isLockedElsewhere(card.id)
    ? '<div class="deck-card-locked-badge" role="img" aria-label="Locked in other built decks">⚠</div>'
    : '';
```

Find:

```js
  div.innerHTML = `
    <div class="deck-card-img-wrap" data-owned-wrap-for="${card.id}">${ownedBadgeHtml}${imgHtml}</div>
```

Replace with:

```js
  div.innerHTML = `
    <div class="deck-card-img-wrap" data-owned-wrap-for="${card.id}">${ownedBadgeHtml}${lockedBadgeHtml}${imgHtml}</div>
```

- [ ] **Step 6: Show the indicator on text rows**

In `static/app.js`, find, inside `buildDeckTextRow`:

```js
  row.innerHTML = `
    <span class="deck-text-qty">${card.quantity}x</span>
    <span class="deck-text-name">${esc(card.name)}</span>
    <span class="deck-text-mana">${esc(card.mana_cost || '')}</span>
    ${tagChipsHtml(card.deck_tags, 'deck-tag')}
```

Replace with:

```js
  const lockedHtml = isLockedElsewhere(card.id)
    ? '<span class="deck-text-locked" title="All owned copies are in other built decks">⚠</span>'
    : '';
  row.innerHTML = `
    <span class="deck-text-qty">${card.quantity}x</span>
    <span class="deck-text-name">${esc(card.name)}</span>
    ${lockedHtml}
    <span class="deck-text-mana">${esc(card.mana_cost || '')}</span>
    ${tagChipsHtml(card.deck_tags, 'deck-tag')}
```

- [ ] **Step 7: Show the indicator in the add-card search results**

In `static/app.js`, find, inside `renderDeckSearchResults`:

```js
    row.innerHTML = `
      <span class="dsearch-name">${esc(card.name)}</span>
      <span class="dsearch-type">${esc(card.type_line || '')}</span>
      <span class="dsearch-indeck">${inDeck ? `in deck: ${inDeck.quantity}` : ''}</span>
      <button class="dsearch-add-btn" title="Add to deck">+</button>`;
```

Replace with:

```js
    const lockedHtml = isLockedElsewhere(card.id)
      ? '<span class="dsearch-locked" title="All owned copies are in other built decks">⚠</span>'
      : '';
    row.innerHTML = `
      <span class="dsearch-name">${esc(card.name)}</span>
      <span class="dsearch-type">${esc(card.type_line || '')}</span>
      ${lockedHtml}
      <span class="dsearch-indeck">${inDeck ? `in deck: ${inDeck.quantity}` : ''}</span>
      <button class="dsearch-add-btn" title="Add to deck">+</button>`;
```

- [ ] **Step 8: Add CSS for the three new elements**

In `static/style.css`, find:

```css
/* Shared by .card-img-wrap (Cards grid) and .deck-card-img-wrap (Deck view) */
.card-owned-badge {
  position: absolute;
  top: 6px;
  left: 6px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--accent);
  color: #111;
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1;
```

Leave that rule untouched, and add a new rule right after its closing `}` (find the `}` that closes `.card-owned-badge` — it's followed by whatever rule comes next in the file; insert between them):

```css
.deck-card-locked-badge {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: #e74c3c;
  color: #111;
  font-size: 11px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1;
}
.deck-text-locked, .dsearch-locked {
  color: #e74c3c;
  font-size: 12px;
}
```

(`.deck-card-locked-badge` mirrors `.card-owned-badge`'s shape/sizing but sits at `top-right` instead of `top-left` so both can appear on the same tile without overlapping, and uses the existing danger-red `#e74c3c` already used elsewhere in this file for warning/danger meaning, instead of the gold `--accent` already claimed by "owned".)

- [ ] **Step 9: Run the full check**

Run:
```bash
node --check static/app.js
for f in tests/js/*.test.mjs; do node "$f" || echo "FAILED: $f"; done
pytest -v
```
Expected: PASS everywhere (no existing JS test exercises these three DOM-building functions directly — they're DOM-wiring functions, consistent with how `buildDeckCardTile`/`buildDeckTextRow` have no existing sentinel-based unit tests either, per prior items' established convention — so this step is a syntax/regression check, not new unit coverage).

- [ ] **Step 10: Manual verification**

In this worktree, ensure `mtg.db` is migrated (`python3 main.py` if needed), then `uvicorn app:app --reload --port 8001`. In a browser:
- Mark one deck built (via item 018's toggle) that contains a card you own exactly as many copies of as that deck uses (fully allocated) and another card where you own more than that deck uses (has a spare copy).
- Open a *different* deck and use "Add cards" to search for both cards: the fully-allocated one should show the new warning indicator next to its search row; the one with a spare copy should not.
- Add the fully-allocated card to this second deck anyway (the indicator doesn't block adding, it's informational) — now open this second deck's grid/text view and confirm the same card shows the locked indicator there too (additive to, not replacing, the existing green owned checkmark/left-edge highlight).
- Switch back to the *built* deck holding the real allocation — confirm that same card does NOT show the locked indicator there (deck-relative exclusion: it's not "elsewhere" from that deck's own point of view).

- [ ] **Step 11: Commit**

```bash
git add static/app.js static/style.css
git commit -m "feat: show locked-elsewhere indicator on deck cards and add-card search"
```

---

### Task 3: Check off acceptance criteria and finish

**Files:**
- Modify: `docs/superpowers/backlog/020-deck-page-allocated-elsewhere-indicator.md`

- [ ] **Step 1: Verify each acceptance criterion against the finished work, then check it off**

Re-read the item's "Acceptance criteria" section and mark each `- [ ]` as `- [x]` only once genuinely confirmed — Tasks 1-2's tests and manual verification already cover all of them (single request per deck switch, deck-relative exclusion in both directions, search-results indicator, Considering exclusion, non-built-deck exclusion, visual distinctness from the owned checkmark).

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/backlog/020-deck-page-allocated-elsewhere-indicator.md
git commit -m "docs(backlog): check off item 020 acceptance criteria"
```

- [ ] **Step 3: Run the full test suite one last time**

Run: `pytest -v && for f in tests/js/*.test.mjs; do node "$f"; done`
Expected: PASS for everything.
