# Deck "Considering" Category Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Considering" category to deck cards — a card stays in `deck_cards` but is flagged `is_considering`, excluded from the deck's total count, and grouped into its own dedicated (collapsed-by-default) section instead of being scattered across tag/type groups, in every deck view.

**Architecture:** A new `is_considering` boolean column on `deck_cards`, mutually exclusive with the existing `is_commander` column (enforced server-side). Backend endpoints expose and update it. Frontend gets a toggle button on each deck-card tile, and the three deck-rendering paths (grid grouped-by-tag, grid ungrouped, text view) each get a "Considering" bucket appended last.

**Tech Stack:** FastAPI + sqlite3 backend (`app.py`, `main.py`), vanilla JS/CSS frontend (`static/app.js`, `static/style.css`), pytest for backend tests. No JS test runner exists in this repo — frontend verification is manual in the browser.

## Global Constraints

- Column name: `is_considering INTEGER NOT NULL DEFAULT 0` on `deck_cards`, schema migration v3 → v4.
- Mutual exclusion with `is_commander` is enforced in `update_deck_card` itself (not just the frontend): setting `is_commander=true` forces `is_considering=false`; setting `is_considering=true` forces `is_commander=false`. If a single request sets both true, `is_commander` wins.
- The category label shown in the UI is exactly `Considering`.
- Considering cards are excluded from: the deck editor header's total count, the deck-switcher palette's per-deck card count (`GET /api/decks` → `card_count`), and tag-based grouping (they never appear in a tag/type bucket).
- Considering cards always render in their own section, sorted last, after every other group/bucket, in all three deck views (grid grouped-by-tag, grid ungrouped, text view).
- The Considering section defaults to collapsed in both grid views (existing `deckGroupCollapsed` collapse mechanic, reused — no new UI concept). The text view has no collapse mechanic for any section and none is added; Considering is simply always-expanded there, like `Commander`/`Creature`/etc.
- The Considering toggle button is omitted entirely on the current commander's tile.
- No changes to the add-card palette, drag-and-drop, Cards/Collection pages, or the card detail modal.

---

### Task 1: Backend — schema, mutual exclusion, and API exposure

**Files:**
- Modify: `main.py` — `migrate_database()` (add v4 migration)
- Modify: `app.py` — `DeckCardUpdate`, `update_deck_card`, `get_deck_cards`, `add_card_to_deck`, `list_decks`
- Modify: `tests/conftest.py` — `_SCHEMA` (test DB is built from this literal string, not from `migrate_database()`, so it needs the new column and version bump directly)
- Create: `tests/test_deck_considering.py`

**Interfaces:**
- Consumes: existing `deck_cards` table (`main.py`), existing `get_db()`/`CARD_COLS_C` helpers in `app.py`.
- Produces: `deck_cards.is_considering` column; `PATCH /api/decks/{deck_id}/cards/{card_id}` accepts and returns `is_considering`; `GET /api/decks/{deck_id}/cards` and `POST /api/decks/{deck_id}/cards` responses include `is_considering`; `GET /api/decks` `card_count` excludes considering cards. Task 2 (frontend) depends on all of these response shapes.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_deck_considering.py`. This relies on the base seed from `conftest.py`: deck id `1` ("Test Deck") contains only card id `1` ("Lightning Bolt") at quantity 4, and card id `2` ("Forest") exists but isn't in any deck.

```python
def test_update_deck_card_sets_is_considering(client):
    r = client.patch("/api/decks/1/cards/1", json={"is_considering": True})
    assert r.status_code == 200
    body = r.json()
    assert body["is_considering"] is True
    assert body["is_commander"] is False


def test_setting_commander_clears_considering(client):
    client.patch("/api/decks/1/cards/1", json={"is_considering": True})
    r = client.patch("/api/decks/1/cards/1", json={"is_commander": True})
    assert r.status_code == 200
    body = r.json()
    assert body["is_commander"] is True
    assert body["is_considering"] is False


def test_setting_considering_clears_commander(client):
    client.patch("/api/decks/1/cards/1", json={"is_commander": True})
    r = client.patch("/api/decks/1/cards/1", json={"is_considering": True})
    assert r.status_code == 200
    body = r.json()
    assert body["is_considering"] is True
    assert body["is_commander"] is False


def test_setting_both_true_commander_wins(client):
    r = client.patch("/api/decks/1/cards/1", json={"is_commander": True, "is_considering": True})
    assert r.status_code == 200
    body = r.json()
    assert body["is_commander"] is True
    assert body["is_considering"] is False


def test_get_deck_cards_includes_is_considering(client):
    client.patch("/api/decks/1/cards/1", json={"is_considering": True})
    r = client.get("/api/decks/1/cards")
    assert r.status_code == 200
    card = next(c for c in r.json() if c["id"] == 1)
    assert card["is_considering"] is True


def test_add_card_to_deck_response_includes_is_considering(client):
    r = client.post("/api/decks/1/cards", json={"card_id": 2, "quantity": 1})
    assert r.status_code == 201
    assert r.json()["is_considering"] is False


def test_list_decks_card_count_excludes_considering(client):
    client.patch("/api/decks/1/cards/1", json={"is_considering": True})
    r = client.get("/api/decks")
    assert r.status_code == 200
    deck = next(d for d in r.json() if d["id"] == 1)
    assert deck["card_count"] == 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_deck_considering.py -v`
Expected: every test fails, most with `KeyError: 'is_considering'` or an assertion mismatch — the column and field don't exist yet.

- [ ] **Step 3: Add the schema migration**

In `main.py`, `migrate_database()` currently ends with the `version < 3` block:

```python
    if version < 3:
        cur.execute("ALTER TABLE cards ADD COLUMN power TEXT;")
        cur.execute("ALTER TABLE cards ADD COLUMN toughness TEXT;")
        cur.execute("UPDATE schema_version SET version = 3;")

    conn.commit()
    conn.close()
```

Add a `version < 4` block before the final `conn.commit()`:

```python
    if version < 3:
        cur.execute("ALTER TABLE cards ADD COLUMN power TEXT;")
        cur.execute("ALTER TABLE cards ADD COLUMN toughness TEXT;")
        cur.execute("UPDATE schema_version SET version = 3;")

    if version < 4:
        cur.execute("ALTER TABLE deck_cards ADD COLUMN is_considering INTEGER NOT NULL DEFAULT 0;")
        cur.execute("UPDATE schema_version SET version = 4;")

    conn.commit()
    conn.close()
```

- [ ] **Step 4: Update the test schema in `tests/conftest.py`**

The test DB in `conftest.py` is built directly from the `_SCHEMA` string, not by running `migrate_database()`, so it needs both the new column and the version bump applied directly. Currently:

```python
CREATE TABLE deck_cards (
    id INTEGER PRIMARY KEY,
    deck_id INTEGER NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
    card_id INTEGER NOT NULL REFERENCES cards(id),
    quantity INTEGER NOT NULL DEFAULT 1,
    is_commander INTEGER NOT NULL DEFAULT 0,
    UNIQUE(deck_id, card_id)
);
```

and later:

```python
INSERT INTO schema_version VALUES (3);
```

Change to:

```python
CREATE TABLE deck_cards (
    id INTEGER PRIMARY KEY,
    deck_id INTEGER NOT NULL REFERENCES decks(id) ON DELETE CASCADE,
    card_id INTEGER NOT NULL REFERENCES cards(id),
    quantity INTEGER NOT NULL DEFAULT 1,
    is_commander INTEGER NOT NULL DEFAULT 0,
    is_considering INTEGER NOT NULL DEFAULT 0,
    UNIQUE(deck_id, card_id)
);
```

and:

```python
INSERT INTO schema_version VALUES (4);
```

- [ ] **Step 5: Update `DeckCardUpdate` and `update_deck_card` in `app.py`**

Currently:

```python
class DeckCardUpdate(BaseModel):
    quantity: int | None = None
    is_commander: bool | None = None


@app.patch("/api/decks/{deck_id}/cards/{card_id}")
def update_deck_card(deck_id: int, card_id: int, body: DeckCardUpdate):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT quantity, is_commander FROM deck_cards WHERE deck_id = ? AND card_id = ?",
                    (deck_id, card_id))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Card not in deck")
        new_qty = body.quantity if body.quantity is not None else row["quantity"]
        new_cmd = int(body.is_commander) if body.is_commander is not None else row["is_commander"]
        cur.execute("""
            UPDATE deck_cards SET quantity = ?, is_commander = ?
            WHERE deck_id = ? AND card_id = ?
        """, (new_qty, new_cmd, deck_id, card_id))
        conn.commit()
    return {"deck_id": deck_id, "card_id": card_id, "quantity": new_qty, "is_commander": bool(new_cmd)}
```

Change to:

```python
class DeckCardUpdate(BaseModel):
    quantity: int | None = None
    is_commander: bool | None = None
    is_considering: bool | None = None


@app.patch("/api/decks/{deck_id}/cards/{card_id}")
def update_deck_card(deck_id: int, card_id: int, body: DeckCardUpdate):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT quantity, is_commander, is_considering FROM deck_cards WHERE deck_id = ? AND card_id = ?",
                    (deck_id, card_id))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Card not in deck")
        new_qty = body.quantity if body.quantity is not None else row["quantity"]
        new_cmd = int(body.is_commander) if body.is_commander is not None else row["is_commander"]
        new_considering = int(body.is_considering) if body.is_considering is not None else row["is_considering"]
        # Commander and Considering are mutually exclusive. Whichever flag was
        # just explicitly set true wins over the other; is_commander wins if
        # a single request sets both true.
        if body.is_commander:
            new_considering = 0
        elif body.is_considering:
            new_cmd = 0
        cur.execute("""
            UPDATE deck_cards SET quantity = ?, is_commander = ?, is_considering = ?
            WHERE deck_id = ? AND card_id = ?
        """, (new_qty, new_cmd, new_considering, deck_id, card_id))
        conn.commit()
    return {
        "deck_id": deck_id, "card_id": card_id, "quantity": new_qty,
        "is_commander": bool(new_cmd), "is_considering": bool(new_considering),
    }
```

- [ ] **Step 6: Update `get_deck_cards` in `app.py`**

Currently:

```python
        cur.execute(f"""
            SELECT {CARD_COLS_C}, dc.quantity, dc.is_commander
            FROM deck_cards dc
            JOIN cards c ON c.id = dc.card_id
            WHERE dc.deck_id = ?
            ORDER BY dc.is_commander DESC, c.name
        """, (deck_id,))
```

Change to:

```python
        cur.execute(f"""
            SELECT {CARD_COLS_C}, dc.quantity, dc.is_commander, dc.is_considering
            FROM deck_cards dc
            JOIN cards c ON c.id = dc.card_id
            WHERE dc.deck_id = ?
            ORDER BY dc.is_commander DESC, c.name
        """, (deck_id,))
```

- [ ] **Step 7: Update `add_card_to_deck` in `app.py`**

Currently:

```python
        cur.execute("SELECT quantity, is_commander FROM deck_cards WHERE deck_id = ? AND card_id = ?",
                    (deck_id, body.card_id))
        row = dict(cur.fetchone())
    return {"deck_id": deck_id, "card_id": body.card_id, **row}
```

Change to:

```python
        cur.execute("SELECT quantity, is_commander, is_considering FROM deck_cards WHERE deck_id = ? AND card_id = ?",
                    (deck_id, body.card_id))
        row = dict(cur.fetchone())
    return {"deck_id": deck_id, "card_id": body.card_id, **row}
```

- [ ] **Step 8: Update `list_decks` in `app.py`**

Currently:

```python
@app.get("/api/decks")
def list_decks():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT d.id, d.name, d.created_at,
                   COALESCE(SUM(dc.quantity), 0) AS card_count
            FROM decks d
            LEFT JOIN deck_cards dc ON dc.deck_id = d.id
            GROUP BY d.id
            ORDER BY d.name
        """)
        return [dict(r) for r in cur.fetchall()]
```

Change to:

```python
@app.get("/api/decks")
def list_decks():
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT d.id, d.name, d.created_at,
                   COALESCE(SUM(CASE WHEN dc.is_considering THEN 0 ELSE dc.quantity END), 0) AS card_count
            FROM decks d
            LEFT JOIN deck_cards dc ON dc.deck_id = d.id
            GROUP BY d.id
            ORDER BY d.name
        """)
        return [dict(r) for r in cur.fetchall()]
```

- [ ] **Step 9: Run the tests to verify they pass**

Run: `python -m pytest tests/test_deck_considering.py -v`
Expected: all 7 tests PASS.

- [ ] **Step 10: Run the full backend suite**

Run: `python -m pytest -q`
Expected: all tests pass (this change is additive — no existing behavior for non-considering cards changes).

- [ ] **Step 11: Commit**

```bash
git add main.py app.py tests/conftest.py tests/test_deck_considering.py
git commit -m "feat: add is_considering flag to deck_cards, mutually exclusive with commander"
```

---

### Task 2: Frontend — Considering toggle button and tile styling

**Files:**
- Modify: `static/app.js` — `buildDeckCardTile()`, `toggleCommander()`, add `toggleConsidering()`
- Modify: `static/style.css` — `.deck-cmd-btn`, add `.deck-actions`, `.deck-considering-btn`, `.deck-card-tile.is-considering`

**Interfaces:**
- Consumes: `is_considering` field from Task 1's API responses (`deckState.deckCards` items already carry it via `API.getDeckCards`); existing `API.updateDeckCard(deckId, cardId, updates)`.
- Produces: `toggleConsidering(cardId)`, callable the same way `toggleCommander(cardId)` is. Task 3 and Task 4 don't call this directly, but Task 3's manual verification needs it to create Considering cards to look at.

- [ ] **Step 1: Add the button markup and tile class to `buildDeckCardTile`**

Currently:

```js
function buildDeckCardTile(card) {
  const q = qty(card.id);
  const div = document.createElement('div');
  div.className = 'deck-card-tile' + (card.is_commander ? ' is-commander' : '');
  div.dataset.id = card.id;

  const imgHtml = card.image_uri
    ? `<img src="${API.imageUrl(card.image_uri)}" loading="lazy" alt="${esc(card.name)}">`
    : `<div class="card-img-placeholder">${esc(card.name)}</div>`;

  const ownedBadgeHtml = q > 0 ? OWNED_BADGE_HTML : '';

  div.innerHTML = `
    <div class="deck-card-img-wrap" data-owned-wrap-for="${card.id}">${ownedBadgeHtml}${imgHtml}</div>
    <div class="deck-card-info">
      <div class="deck-card-name">${esc(card.name)}</div>
      <div class="deck-card-row">
        <button class="qty-btn" data-action="dec" title="−">−</button>
        <span class="qty-label owned">${card.quantity}</span>
        <button class="qty-btn" data-action="inc" title="+">+</button>
        <button class="deck-cmd-btn${card.is_commander ? ' active' : ''}" title="Toggle commander">♛</button>
        <button class="deck-remove-btn" title="Remove">×</button>
      </div>
      ${tagChipsHtml(card.collection_tags, 'collection-tag')}
      ${tagChipsHtml(card.deck_tags, 'deck-tag')}
    </div>`;

  div.querySelector('[data-action="inc"]').addEventListener('click', e => { e.stopPropagation(); incDeckCard(card.id); });
  div.querySelector('[data-action="dec"]').addEventListener('click', e => { e.stopPropagation(); decDeckCard(card.id); });
  div.querySelector('.deck-cmd-btn').addEventListener('click', e => { e.stopPropagation(); toggleCommander(card.id); });
  div.querySelector('.deck-remove-btn').addEventListener('click', e => { e.stopPropagation(); removeDeckCard(card.id); });
  div.addEventListener('click', () => openModal(card, { deckId: deckState.currentDeckId }));

  return div;
}
```

Change to:

```js
function buildDeckCardTile(card) {
  const q = qty(card.id);
  const div = document.createElement('div');
  div.className = 'deck-card-tile'
    + (card.is_commander ? ' is-commander' : '')
    + (card.is_considering ? ' is-considering' : '');
  div.dataset.id = card.id;

  const imgHtml = card.image_uri
    ? `<img src="${API.imageUrl(card.image_uri)}" loading="lazy" alt="${esc(card.name)}">`
    : `<div class="card-img-placeholder">${esc(card.name)}</div>`;

  const ownedBadgeHtml = q > 0 ? OWNED_BADGE_HTML : '';

  // A commander can't be Considering, so the toggle is pointless on that tile.
  const consideringBtnHtml = card.is_commander ? '' : `
    <button class="deck-considering-btn${card.is_considering ? ' active' : ''}"
            title="${card.is_considering ? 'Move back to deck' : 'Move to Considering'}">?</button>`;

  div.innerHTML = `
    <div class="deck-card-img-wrap" data-owned-wrap-for="${card.id}">${ownedBadgeHtml}${imgHtml}</div>
    <div class="deck-card-info">
      <div class="deck-card-name">${esc(card.name)}</div>
      <div class="deck-card-row">
        <button class="qty-btn" data-action="dec" title="−">−</button>
        <span class="qty-label owned">${card.quantity}</span>
        <button class="qty-btn" data-action="inc" title="+">+</button>
        <div class="deck-actions">
          ${consideringBtnHtml}
          <button class="deck-cmd-btn${card.is_commander ? ' active' : ''}" title="Toggle commander">♛</button>
          <button class="deck-remove-btn" title="Remove">×</button>
        </div>
      </div>
      ${tagChipsHtml(card.collection_tags, 'collection-tag')}
      ${tagChipsHtml(card.deck_tags, 'deck-tag')}
    </div>`;

  div.querySelector('[data-action="inc"]').addEventListener('click', e => { e.stopPropagation(); incDeckCard(card.id); });
  div.querySelector('[data-action="dec"]').addEventListener('click', e => { e.stopPropagation(); decDeckCard(card.id); });
  div.querySelector('.deck-cmd-btn').addEventListener('click', e => { e.stopPropagation(); toggleCommander(card.id); });
  div.querySelector('.deck-remove-btn').addEventListener('click', e => { e.stopPropagation(); removeDeckCard(card.id); });
  const consideringBtn = div.querySelector('.deck-considering-btn');
  if (consideringBtn) consideringBtn.addEventListener('click', e => { e.stopPropagation(); toggleConsidering(card.id); });
  div.addEventListener('click', () => openModal(card, { deckId: deckState.currentDeckId }));

  return div;
}
```

- [ ] **Step 2: Add `toggleConsidering` and update `toggleCommander`**

Currently:

```js
async function toggleCommander(cardId) {
  const card = deckState.deckCards.find(c => c.id === cardId);
  if (!card) return;
  try {
    const res = await API.updateDeckCard(deckState.currentDeckId, cardId, { is_commander: !card.is_commander });
    card.is_commander = res.is_commander;
    renderDeckContent();
  } catch (e) { console.error(e); }
}
```

Change to (both functions sync `is_commander` AND `is_considering` from the response, since the backend may auto-clear the other flag, and both call `syncDeckCount()` since either toggle can change which cards count toward the total):

```js
async function toggleCommander(cardId) {
  const card = deckState.deckCards.find(c => c.id === cardId);
  if (!card) return;
  try {
    const res = await API.updateDeckCard(deckState.currentDeckId, cardId, { is_commander: !card.is_commander });
    card.is_commander = res.is_commander;
    card.is_considering = res.is_considering;
    syncDeckCount();
    renderDeckContent();
  } catch (e) { console.error(e); }
}

async function toggleConsidering(cardId) {
  const card = deckState.deckCards.find(c => c.id === cardId);
  if (!card) return;
  try {
    const res = await API.updateDeckCard(deckState.currentDeckId, cardId, { is_considering: !card.is_considering });
    card.is_commander = res.is_commander;
    card.is_considering = res.is_considering;
    syncDeckCount();
    renderDeckContent();
  } catch (e) { console.error(e); }
}
```

Place `toggleConsidering` directly after `toggleCommander` (before `syncDeckCount`, which both now call).

- [ ] **Step 3: Add/update CSS in `static/style.css`**

Currently:

```css
.deck-cmd-btn {
  background: none;
  border: 1px solid var(--border);
  border-radius: 3px;
  color: var(--muted);
  font-size: 11px;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: color 0.1s, border-color 0.1s;
  margin-left: auto;
}
.deck-cmd-btn:hover  { border-color: var(--accent); color: var(--accent); }
.deck-cmd-btn.active { border-color: var(--accent); color: var(--accent); background: rgba(200,155,60,0.1); }
```

Change to (the `margin-left: auto` moves to the new `.deck-actions` wrapper, since it's no longer always the first trailing element — the considering button can precede it):

```css
.deck-actions {
  display: flex;
  align-items: center;
  gap: 3px;
  margin-left: auto;
}

.deck-cmd-btn {
  background: none;
  border: 1px solid var(--border);
  border-radius: 3px;
  color: var(--muted);
  font-size: 11px;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: color 0.1s, border-color 0.1s;
}
.deck-cmd-btn:hover  { border-color: var(--accent); color: var(--accent); }
.deck-cmd-btn.active { border-color: var(--accent); color: var(--accent); background: rgba(200,155,60,0.1); }

.deck-considering-btn {
  background: none;
  border: 1px solid var(--border);
  border-radius: 3px;
  color: var(--muted);
  font-size: 11px;
  width: 20px;
  height: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: color 0.1s, border-color 0.1s;
}
.deck-considering-btn:hover  { border-color: var(--text); color: var(--text); }
.deck-considering-btn.active { border-color: var(--text); color: var(--text); background: rgba(255,255,255,0.08); }
```

Then find `.deck-card-tile.is-commander { border-color: var(--accent); }` and add a sibling rule directly after it:

```css
.deck-card-tile.is-considering { border-style: dashed; opacity: 0.7; }
```

- [ ] **Step 4: Manually verify in the browser**

Run: `uvicorn app:app --reload` (ensure `mtg.db` has imported card data — run `python importer.py` first if it's freshly initialized)

Open a deck with at least one non-commander card. Confirm:
1. Each non-commander tile shows a `?` button alongside the commander/remove buttons, right-aligned as a cluster.
2. The commander's tile shows no `?` button.
3. Clicking `?` toggles the tile to a dashed, slightly faded border and the button turns active-styled; clicking again reverts it.
4. Making a Considering card the commander (via the `♛` button) clears its Considering style automatically.

- [ ] **Step 5: Commit**

```bash
git add static/app.js static/style.css
git commit -m "feat: add Considering toggle button to deck card tiles"
```

---

### Task 3: Frontend — grid rendering (grouped-by-tag and ungrouped)

**Files:**
- Modify: `static/app.js` — `renderGroupedGrid()` (extract `renderGroupSection()`), `renderDeckGrid()`, `deckGroupCollapsed` declaration, the `deck-group-by` change handler, `selectDeck()`

**Interfaces:**
- Consumes: `card.is_considering` (Task 1's data, Task 2's toggle to create it), existing `groupCards()`, `applyFilters()`, `sortComparator()`.
- Produces: `renderGroupSection(container, group, buildTileFn, collapsedState)` — appends one collapsible group section to `container` without clearing it. `resetDeckGroupCollapsed()` — clears deck group-collapse state back to its Considering-collapsed default. Task 4 doesn't depend on these (text view has no collapse), but reuses the `mainCards`/`consideringCards` split pattern established here.

- [ ] **Step 1: Extract `renderGroupSection` out of `renderGroupedGrid`**

Currently:

```js
function renderGroupedGrid(container, groups, buildTileFn, collapsedState) {
  container.innerHTML = '';
  for (const group of groups) {
    const section = document.createElement('div');
    section.className = 'group-section';

    const isCollapsed = collapsedState.has(group.label);
    const header = document.createElement('div');
    header.className = 'group-header' + (isCollapsed ? ' collapsed' : '');
    header.innerHTML = `
      <span class="group-header-label">${esc(group.label)}</span>
      <span class="group-header-count">${group.cards.length}</span>
      <span class="group-header-chevron">▾</span>`;
    header.addEventListener('click', () => {
      if (collapsedState.has(group.label)) {
        collapsedState.delete(group.label);
      } else {
        collapsedState.add(group.label);
      }
      header.classList.toggle('collapsed');
      body.classList.toggle('collapsed');
    });

    const body = document.createElement('div');
    body.className = 'group-body' + (isCollapsed ? ' collapsed' : '');

    for (const card of group.cards) body.appendChild(buildTileFn(card));

    section.appendChild(header);
    section.appendChild(body);
    container.appendChild(section);
  }
}
```

Change to:

```js
function renderGroupSection(container, group, buildTileFn, collapsedState) {
  const section = document.createElement('div');
  section.className = 'group-section';

  const isCollapsed = collapsedState.has(group.label);
  const header = document.createElement('div');
  header.className = 'group-header' + (isCollapsed ? ' collapsed' : '');
  header.innerHTML = `
    <span class="group-header-label">${esc(group.label)}</span>
    <span class="group-header-count">${group.cards.length}</span>
    <span class="group-header-chevron">▾</span>`;
  header.addEventListener('click', () => {
    if (collapsedState.has(group.label)) {
      collapsedState.delete(group.label);
    } else {
      collapsedState.add(group.label);
    }
    header.classList.toggle('collapsed');
    body.classList.toggle('collapsed');
  });

  const body = document.createElement('div');
  body.className = 'group-body' + (isCollapsed ? ' collapsed' : '');

  for (const card of group.cards) body.appendChild(buildTileFn(card));

  section.appendChild(header);
  section.appendChild(body);
  container.appendChild(section);
}

function renderGroupedGrid(container, groups, buildTileFn, collapsedState) {
  container.innerHTML = '';
  for (const group of groups) renderGroupSection(container, group, buildTileFn, collapsedState);
}
```

This is a pure extraction — `renderGroupedGrid`'s signature and behavior are unchanged, so its two other call sites (Cards/Collection grid rendering) need no changes.

- [ ] **Step 2: Seed `deckGroupCollapsed` and add `resetDeckGroupCollapsed`**

Currently:

```js
const collectionGroupCollapsed = new Set();
const deckGroupCollapsed = new Set();
```

Change to:

```js
const collectionGroupCollapsed = new Set();
const deckGroupCollapsed = new Set(['Considering']);

function resetDeckGroupCollapsed() {
  deckGroupCollapsed.clear();
  deckGroupCollapsed.add('Considering');
}
```

- [ ] **Step 3: Use the reset helper on group-by change**

Currently:

```js
document.getElementById('deck-group-by').addEventListener('change', e => {
  deckState.groupBy = e.target.value;
  deckGroupCollapsed.clear();
  renderDeckContent();
});
```

Change to:

```js
document.getElementById('deck-group-by').addEventListener('change', e => {
  deckState.groupBy = e.target.value;
  resetDeckGroupCollapsed();
  renderDeckContent();
});
```

- [ ] **Step 4: Use the reset helper when switching decks**

In `selectDeck(id)`, currently:

```js
async function selectDeck(id) {
  closeAddPalette();                      // never carry the palette between decks
  deckState.currentDeckId = id;
  deckState.deckCards = [];
  deckState.filter = makeFilterModel();   // reset filters between decks
  deckState.query = '';                   // reset content search between decks
```

Change to:

```js
async function selectDeck(id) {
  closeAddPalette();                      // never carry the palette between decks
  deckState.currentDeckId = id;
  deckState.deckCards = [];
  deckState.filter = makeFilterModel();   // reset filters between decks
  deckState.query = '';                   // reset content search between decks
  resetDeckGroupCollapsed();              // Considering starts collapsed for every freshly loaded deck
```

- [ ] **Step 5: Split Considering out in `renderDeckGrid`**

Currently:

```js
function renderDeckGrid() {
  const el = document.getElementById('deck-grid-view');
  el.innerHTML = '';
  const filtered = applyFilters(deckState.deckCards, deckState.filter);
  if (!filtered.length) {
    el.innerHTML = '<div class="deck-empty-msg">No cards match — adjust filters or search to add some.</div>';
    return;
  }
  const cmp = sortComparator(deckState.filter);
  if (deckState.groupBy !== 'none') {
    const tagField = deckState.groupBy === 'deck-tag' ? 'deck_tags' : 'collection_tags';
    const groups = groupCards(filtered, tagField);
    for (const g of groups) g.cards.sort(cmp);
    renderGroupedGrid(el, groups, buildDeckCardTile, deckGroupCollapsed);
  } else {
    const sorted = [...filtered].sort((a, b) => {
      if (a.is_commander && !b.is_commander) return -1;   // commander pinned first
      if (!a.is_commander && b.is_commander) return 1;
      return cmp(a, b);
    });
    const frag = document.createDocumentFragment();
    for (const card of sorted) frag.appendChild(buildDeckCardTile(card));
    el.appendChild(frag);
  }
}
```

Change to:

```js
function renderDeckGrid() {
  const el = document.getElementById('deck-grid-view');
  el.innerHTML = '';
  const filtered = applyFilters(deckState.deckCards, deckState.filter);
  if (!filtered.length) {
    el.innerHTML = '<div class="deck-empty-msg">No cards match — adjust filters or search to add some.</div>';
    return;
  }
  const cmp = sortComparator(deckState.filter);
  const mainCards = filtered.filter(c => !c.is_considering);
  const consideringCards = filtered.filter(c => c.is_considering);

  if (deckState.groupBy !== 'none') {
    const tagField = deckState.groupBy === 'deck-tag' ? 'deck_tags' : 'collection_tags';
    const groups = groupCards(mainCards, tagField);
    for (const g of groups) g.cards.sort(cmp);
    if (consideringCards.length) {
      groups.push({ label: 'Considering', cards: [...consideringCards].sort(cmp) });
    }
    renderGroupedGrid(el, groups, buildDeckCardTile, deckGroupCollapsed);
  } else {
    const sorted = [...mainCards].sort((a, b) => {
      if (a.is_commander && !b.is_commander) return -1;   // commander pinned first
      if (!a.is_commander && b.is_commander) return 1;
      return cmp(a, b);
    });
    const frag = document.createDocumentFragment();
    for (const card of sorted) frag.appendChild(buildDeckCardTile(card));
    el.appendChild(frag);
    if (consideringCards.length) {
      renderGroupSection(
        el,
        { label: 'Considering', cards: [...consideringCards].sort(cmp) },
        buildDeckCardTile,
        deckGroupCollapsed
      );
    }
  }
}
```

- [ ] **Step 6: Manually verify in the browser**

Run: `uvicorn app:app --reload`

In a deck with several cards (use Task 2's toggle to mark 1-2 as Considering):
1. With grouping set to "none": the main cards render as before (commander pinned first); a collapsed "Considering" section appears below them with a header showing the count. Click the header — it expands to show the Considering tiles.
2. Switch grouping to "By collection tag" (or deck tag): Considering cards disappear from whatever tag group they'd otherwise land in; a "Considering" group appears as the last group (after "Untagged"), collapsed by default.
3. Switch to a different deck and back to grouped/considering mode: the Considering section starts collapsed again each time.
4. With no cards marked Considering, no "Considering" section/group appears at all in either mode.

- [ ] **Step 7: Commit**

```bash
git add static/app.js
git commit -m "feat: give deck grid views a dedicated, collapsed-by-default Considering section"
```

---

### Task 4: Frontend — text view section and total-count exclusion

**Files:**
- Modify: `static/app.js` — `renderDeckText()`, `renderDeckContent()`, `syncDeckCount()`

**Interfaces:**
- Consumes: `card.is_considering` (Task 1's data, Task 2's toggle).
- Produces: nothing consumed by later tasks — this is the last task in the plan.

- [ ] **Step 1: Add a Considering bucket to `renderDeckText`**

Currently:

```js
  const groups = {
    Commander:    [],
    Creature:     [],
    Instant:      [],
    Sorcery:      [],
    Enchantment:  [],
    Artifact:     [],
    Planeswalker: [],
    Land:         [],
    Other:        [],
  };

  for (const card of filtered) {
    if (card.is_commander) { groups.Commander.push(card); continue; }
    const t = card.type_line || '';
    if      (t.includes('Creature'))     groups.Creature.push(card);
    else if (t.includes('Instant'))      groups.Instant.push(card);
    else if (t.includes('Sorcery'))      groups.Sorcery.push(card);
    else if (t.includes('Enchantment'))  groups.Enchantment.push(card);
    else if (t.includes('Artifact'))     groups.Artifact.push(card);
    else if (t.includes('Planeswalker')) groups.Planeswalker.push(card);
    else if (t.includes('Land'))         groups.Land.push(card);
    else                                 groups.Other.push(card);
  }
```

Change to (note `Considering` is the last key, so `Object.entries` — which the rendering loop below iterates in insertion order — renders it last):

```js
  const groups = {
    Commander:    [],
    Creature:     [],
    Instant:      [],
    Sorcery:      [],
    Enchantment:  [],
    Artifact:     [],
    Planeswalker: [],
    Land:         [],
    Other:        [],
    Considering:  [],
  };

  for (const card of filtered) {
    if (card.is_commander) { groups.Commander.push(card); continue; }
    if (card.is_considering) { groups.Considering.push(card); continue; }
    const t = card.type_line || '';
    if      (t.includes('Creature'))     groups.Creature.push(card);
    else if (t.includes('Instant'))      groups.Instant.push(card);
    else if (t.includes('Sorcery'))      groups.Sorcery.push(card);
    else if (t.includes('Enchantment'))  groups.Enchantment.push(card);
    else if (t.includes('Artifact'))     groups.Artifact.push(card);
    else if (t.includes('Planeswalker')) groups.Planeswalker.push(card);
    else if (t.includes('Land'))         groups.Land.push(card);
    else                                 groups.Other.push(card);
  }
```

The rendering loop below this (`for (const [groupName, cards] of Object.entries(groups))`) needs no changes — it already skips empty buckets (`if (!cards.length) continue;`) and renders whatever's left with a heading and count, which is exactly what `Considering` needs too.

- [ ] **Step 2: Exclude Considering from the deck header total in `renderDeckContent`**

Currently:

```js
function renderDeckContent() {
  deckState.filter.text = deckState.query;   // content search box feeds the model
  const deck  = deckState.decks.find(d => d.id === deckState.currentDeckId);
  const total = deckState.deckCards.reduce((s, c) => s + c.quantity, 0);
  document.getElementById('deck-editor-name').textContent =
    deck ? `${deck.name} (${total})` : `(${total})`;
```

Change to:

```js
function renderDeckContent() {
  deckState.filter.text = deckState.query;   // content search box feeds the model
  const deck  = deckState.decks.find(d => d.id === deckState.currentDeckId);
  const total = deckState.deckCards
    .filter(c => !c.is_considering)
    .reduce((s, c) => s + c.quantity, 0);
  document.getElementById('deck-editor-name').textContent =
    deck ? `${deck.name} (${total})` : `(${total})`;
```

- [ ] **Step 3: Exclude Considering from `syncDeckCount`**

Currently:

```js
function syncDeckCount() {
  const deck = deckState.decks.find(d => d.id === deckState.currentDeckId);
  if (deck) deck.card_count = deckState.deckCards.reduce((s, c) => s + c.quantity, 0);
  renderDeckSwitchResults();
}
```

Change to:

```js
function syncDeckCount() {
  const deck = deckState.decks.find(d => d.id === deckState.currentDeckId);
  if (deck) {
    deck.card_count = deckState.deckCards
      .filter(c => !c.is_considering)
      .reduce((s, c) => s + c.quantity, 0);
  }
  renderDeckSwitchResults();
}
```

- [ ] **Step 4: Manually verify in the browser**

Run: `uvicorn app:app --reload`

In a deck with a mix of cards:
1. Note the header's `(N)` total. Toggle a card to Considering (via Task 2's `?` button) — the total decreases by that card's quantity immediately.
2. Switch the deck view to the text list. Confirm a "Considering" heading appears last, with the right count, always expanded (no collapse control, matching the other headings).
3. Open the deck-switcher palette (press `d` or the switch button) — the deck's shown card count matches the header total from step 1 (both exclude Considering).
4. Toggle the card back out of Considering — the total, the text-view heading, and the switcher count all revert.

- [ ] **Step 5: Commit**

```bash
git add static/app.js
git commit -m "feat: exclude Considering cards from deck totals; add text-view section"
```
