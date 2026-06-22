# Modal "In decks" Section Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show, in the card detail modal, a list of decks the card belongs to, with each deck name clickable to navigate to that deck.

**Architecture:** A new read-only FastAPI endpoint returns the decks containing a card. The frontend modal loads it asynchronously (mirroring the existing printings/tags loaders) and renders deck names as links; clicking one closes the modal and navigates to the decks view via the existing `selectDeck` path. Hidden entirely when the card is in no decks.

**Tech Stack:** FastAPI + SQLite (`app.py`), vanilla JS (`static/app.js`), CSS (`static/style.css`), pytest with `fastapi.testclient`.

## Global Constraints

- Cards are deduplicated by `oracle_id`; deck membership lives in `deck_cards (deck_id, card_id, quantity, is_commander)`, unique on `(deck_id, card_id)`.
- Scryfall requests (not relevant here) require `User-Agent`/`Accept` headers — no external calls in this feature.
- Tests run with: `python -m pytest tests/ -v` from the repo root.

---

### Task 1: Backend endpoint `GET /api/cards/{card_id}/decks`

**Files:**
- Modify: `app.py` (add a new route; place it immediately after the `get_printings` route ending near line 327, before `get_card` at line 329)
- Test: `tests/test_card_decks.py` (create)

**Interfaces:**
- Consumes: existing `get_db()` context manager in `app.py`; conftest fixtures `client`, `db_path`.
- Produces: `GET /api/cards/{card_id}/decks` → `200` with JSON array `[{"id": int, "name": str}, …]`, ordered by deck name, one entry per deck. Returns `[]` when the card is in no decks. Returns `404 {"detail": "Card not found"}` when the card id does not exist.

- [ ] **Step 1: Write the failing test**

Create `tests/test_card_decks.py`. The base `db_path` fixture (see `tests/conftest.py`) seeds card id 1 (Lightning Bolt) into deck 1 ("Test Deck"), and card id 2 (Forest) into no deck.

```python
def test_card_in_one_deck(client):
    r = client.get("/api/cards/1/decks")
    assert r.status_code == 200
    assert r.json() == [{"id": 1, "name": "Test Deck"}]


def test_card_in_no_decks(client):
    r = client.get("/api/cards/2/decks")
    assert r.status_code == 200
    assert r.json() == []


def test_card_in_multiple_decks_sorted_distinct(client, db_path):
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    # Two more decks; "Aggro" sorts before "Test Deck", "Zoo" after.
    conn.execute("INSERT INTO decks (id, name) VALUES (2, 'Zoo')")
    conn.execute("INSERT INTO decks (id, name) VALUES (3, 'Aggro')")
    conn.execute("INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (2, 1, 2)")
    conn.execute("INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (3, 1, 1)")
    conn.commit()
    conn.close()
    r = client.get("/api/cards/1/decks")
    assert r.status_code == 200
    assert r.json() == [
        {"id": 3, "name": "Aggro"},
        {"id": 1, "name": "Test Deck"},
        {"id": 2, "name": "Zoo"},
    ]


def test_card_not_found(client):
    r = client.get("/api/cards/9999/decks")
    assert r.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_card_decks.py -v`
Expected: FAIL — all four tests return 404 or wrong body because the route does not exist yet (FastAPI matches `/api/cards/{card_id}` and the trailing `/decks` 404s).

- [ ] **Step 3: Write minimal implementation**

In `app.py`, add this route immediately after the `get_printings` function (just before `@app.get("/api/cards/{card_id}")`):

```python
@app.get("/api/cards/{card_id}/decks")
def get_card_decks(card_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM cards WHERE id = ?", (card_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Card not found")
        cur.execute("""
            SELECT DISTINCT d.id, d.name
            FROM deck_cards dc
            JOIN decks d ON d.id = dc.deck_id
            WHERE dc.card_id = ?
            ORDER BY d.name
        """, (card_id,))
        return [dict(r) for r in cur.fetchall()]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_card_decks.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Run the full suite to confirm nothing broke**

Run: `python -m pytest tests/ -v`
Expected: PASS (all tests).

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_card_decks.py
git commit -m "feat: add GET /api/cards/{card_id}/decks endpoint"
```

---

### Task 2: Frontend "In decks" modal section

**Files:**
- Modify: `static/app.js` (add section div in `openModal`'s template near line 718; add a `loadModalDecks` call near line 730; add the `loadModalDecks` function)
- Modify: `static/style.css` (add styles for the decks section + deck link)

**Interfaces:**
- Consumes: the `GET /api/cards/{card_id}/decks` endpoint from Task 1; existing globals `esc()`, `selectDeck(id)`, `loadDeckList()`, and the modal-close helper.
- Produces: `loadModalDecks(card)` — async, renders into `#modal-decks-section`; no return value.

**Note on closing the modal:** find the existing close routine in `static/app.js` (search for where `modal-overlay` gets `classList.add('hidden')` and `document.body.style.overflow` is restored — typically a `closeModal()` function). Use that exact function name in Step 3 below. If it is inlined rather than a named function, call the same statements it uses.

- [ ] **Step 1: Confirm the modal-close mechanism**

Run: `grep -nE "closeModal|modal-overlay'?\)?\.classList\.add\('hidden'\)|body\.style\.overflow" static/app.js`
Expected: identifies the function/lines that hide the overlay and restore `document.body.style.overflow`. Note the function name (assume `closeModal()` below; substitute if different).

- [ ] **Step 2: Add the section container to the modal template**

In `static/app.js`, in `openModal`, locate (near line 718):

```javascript
      <div id="modal-tags-section"></div>
    </div>`;
```

Change it to:

```javascript
      <div id="modal-tags-section"></div>
      <div id="modal-decks-section"></div>
    </div>`;
```

- [ ] **Step 3: Call the loader from openModal**

In `static/app.js`, locate (near line 730):

```javascript
  loadPrintings(card);
  loadModalTags(card, deckContext);
}
```

Change it to:

```javascript
  loadPrintings(card);
  loadModalTags(card, deckContext);
  loadModalDecks(card);
}
```

- [ ] **Step 4: Implement `loadModalDecks`**

In `static/app.js`, add this function immediately after `openModal` (before `buildTagEditor`). Replace `closeModal()` with the actual close routine confirmed in Step 1 if its name differs.

```javascript
async function loadModalDecks(card) {
  const section = document.getElementById('modal-decks-section');
  if (!section) return;

  let decks;
  try {
    const r = await fetch(`/api/cards/${card.id}/decks`);
    decks = r.ok ? await r.json() : [];
  } catch {
    decks = [];
  }

  if (!section.isConnected) return; // modal was closed

  if (!decks.length) {
    section.innerHTML = '';            // hidden entirely when card is in no decks
    return;
  }

  section.innerHTML = `
    <div class="modal-tags-label">In decks</div>
    <div class="modal-decks-list">
      ${decks.map(d => `<button class="modal-deck-link" data-deck-id="${d.id}">${esc(d.name)}</button>`).join('')}
    </div>`;

  section.querySelectorAll('.modal-deck-link').forEach(btn => {
    btn.addEventListener('click', () => {
      const deckId = Number(btn.dataset.deckId);
      closeModal();
      document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
      document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
      document.getElementById('view-decks').classList.add('active');
      document.querySelector('.nav-btn[data-view="decks"]').classList.add('active');
      loadDeckList();
      selectDeck(deckId);
    });
  });
}
```

- [ ] **Step 5: Add styles**

In `static/style.css`, add (near the other `.modal-tags-*` rules; reuse `.modal-tags-label` which already exists, so only add the list + link):

```css
.modal-decks-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 4px;
}
.modal-deck-link {
  background: none;
  border: none;
  padding: 0;
  color: var(--accent, #6ea8fe);
  font: inherit;
  cursor: pointer;
  text-decoration: underline;
}
.modal-deck-link:hover {
  filter: brightness(1.2);
}
```

- [ ] **Step 6: Manual verification in the running app**

Start the server: `uvicorn app:app --reload`
- Open a card known to be in a deck → modal shows "In decks" with the deck name(s).
- Click a deck name → modal closes, app switches to the Decks view, and that deck opens.
- Open a card in no decks → no "In decks" section appears.

- [ ] **Step 7: Commit**

```bash
git add static/app.js static/style.css
git commit -m "feat: show 'In decks' section in card detail modal"
```

---

## Self-Review Notes

- **Spec coverage:** endpoint (Task 1) ✓; modal section + names-only clickable links (Task 2) ✓; hide-when-empty (Task 2 Step 4) ✓; navigation via existing `selectDeck` path (Task 2 Step 4) ✓; CSS (Task 2 Step 5) ✓; tests for multiple/zero/sorted/distinct (Task 1) ✓.
- **Placeholders:** none — all code shown in full. The only deliberate variable is the modal-close function name, resolved by Task 2 Step 1 before use.
- **Type consistency:** endpoint returns `{id, name}`; frontend reads `d.id` and `d.name` — consistent.
