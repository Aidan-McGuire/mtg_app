# Deck Built Flag Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `built` boolean flag to decks — a toggle button in the deck editor header, a badge in the deck-switcher list — as the prerequisite for items 019 (collection filter) and 020 (deck-page indicator), both of which need to know which decks' cards are "spoken for."

**Architecture:** One new `decks.built` column (migration v6→v7, following the exact pattern of the existing `is_considering`/`cards_last_refreshed` migrations). The existing `PATCH /api/decks/{deck_id}` endpoint (currently rename-only via a required-`name` `DeckRename` model) becomes a general deck-update endpoint with both `name` and `built` optional, mirroring how `PATCH /api/decks/{deck_id}/cards/{card_id}` already handles `quantity`/`is_commander`/`is_considering` together. The frontend adds one new button, reusing the existing accent-highlight `.active` convention already used by Hide Lands/Unowned Only, and syncs the button's state from `renderDeckContent()` (the existing function that already refreshes deck-header text on every deck render) so it stays correct across deck switches.

**Tech Stack:** Python (FastAPI, sqlite3), vanilla JS/HTML/CSS, pytest.

**Spec:** `docs/superpowers/backlog/018-deck-built-flag.md`

## Global Constraints

- No changes to `initialize_database()`'s `CREATE TABLE decks` statement — like every other column added to this schema since v1 (`power`, `toughness`, `is_considering`, `cards_last_refreshed`), `built` is added purely via a migration, even though a fresh install runs `migrate_database()` immediately after `initialize_database()`.
- The existing rename-only call site (`API.renameDeck`, sending only `{name}`) must keep working unchanged — `built` always falls back to the deck's current value when omitted from a PATCH body.
- Reuse the existing accent-highlight colors (`border-color: var(--accent); color: var(--accent); background: rgba(200,155,60,0.1);`) already used by `.hide-lands-btn.active` / `.unowned-only-btn.active` — no new color.

---

### Task 1: Migration — add `decks.built`

**Files:**
- Modify: `main.py` (`migrate_database()`, currently ends at the `version < 6` block around line 135-137)
- Test: `tests/test_migrate.py`

**Interfaces:**
- Produces: `decks.built INTEGER NOT NULL DEFAULT 0` column, available to every later task.

- [ ] **Step 1: Write the failing migration test**

Append to `tests/test_migrate.py`:

```python
def _make_v6_db(tmp_path):
    p = tmp_path / "mig_v6.db"
    conn = sqlite3.connect(str(p))
    conn.execute("CREATE TABLE schema_version (version INTEGER NOT NULL, cards_last_refreshed TEXT);")
    conn.execute("INSERT INTO schema_version VALUES (6, NULL);")
    conn.execute("""
        CREATE TABLE decks (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    conn.execute("INSERT INTO decks (name) VALUES ('Existing Deck');")
    conn.commit()
    conn.close()
    return p


def test_migration_adds_built_column_defaulting_to_zero(tmp_path, monkeypatch):
    db = _make_v6_db(tmp_path)
    monkeypatch.setattr(main_module, "DB_PATH", db)

    main_module.migrate_database()

    conn = sqlite3.connect(str(db))
    cols = [r[1] for r in conn.execute("PRAGMA table_info(decks)")]
    version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    built = conn.execute("SELECT built FROM decks WHERE name = 'Existing Deck'").fetchone()[0]
    conn.close()

    assert "built" in cols
    assert version == 7
    assert built == 0


def test_migration_v6_to_v7_is_idempotent(tmp_path, monkeypatch):
    db = _make_v6_db(tmp_path)
    monkeypatch.setattr(main_module, "DB_PATH", db)

    main_module.migrate_database()
    main_module.migrate_database()  # must not error, must not re-add the column

    conn = sqlite3.connect(str(db))
    version = conn.execute("SELECT version FROM schema_version").fetchone()[0]
    conn.close()

    assert version == 7
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/test_migrate.py -v`
Expected: FAIL on both new tests — `main_module.migrate_database()` doesn't know about a `built` column yet, so `PRAGMA table_info(decks)` won't include it and `version` stays `6`.

- [ ] **Step 3: Add the migration**

In `main.py`, immediately after the existing `if version < 6:` block (which ends with `cur.execute("UPDATE schema_version SET version = 6;")`), add:

```python
    if version < 7:
        cur.execute("ALTER TABLE decks ADD COLUMN built INTEGER NOT NULL DEFAULT 0;")
        cur.execute("UPDATE schema_version SET version = 7;")
```

- [ ] **Step 4: Run the tests again to verify they pass**

Run: `pytest tests/test_migrate.py -v`
Expected: PASS for all tests in the file.

- [ ] **Step 5: Re-initialize this worktree's local dev DB**

Run: `rm -f mtg.db mtg.db-shm mtg.db-wal && python3 main.py` — this worktree's `mtg.db` is gitignored/local-only; regenerating it picks up the new column for the rest of this plan's manual testing.

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_migrate.py
git commit -m "feat: add decks.built column via migration"
```

---

### Task 2: Backend — `built` in `list_decks` and the deck-update endpoint

**Files:**
- Modify: `app.py` (`DeckRename` model, `list_decks`, `rename_deck`)
- Test: `tests/test_deck_built.py` (new)

**Interfaces:**
- Consumes: `decks.built` column from Task 1.
- Produces: `GET /api/decks` rows now include `built` (bool); `PATCH /api/decks/{deck_id}` accepts an optional `built` field alongside the existing optional-in-effect `name` field, consumed by Task 3's frontend toggle.

- [ ] **Step 1: Write failing tests**

Create `tests/test_deck_built.py` (the base seeded DB already has deck id 1 "Test Deck", per `tests/conftest.py`):

```python
def test_list_decks_includes_built_field_default_false(client):
    r = client.get("/api/decks")
    assert r.status_code == 200
    deck = next(d for d in r.json() if d["id"] == 1)
    assert deck["built"] is False


def test_patch_deck_sets_built_true(client):
    r = client.patch("/api/decks/1", json={"built": True})
    assert r.status_code == 200
    assert r.json()["built"] is True

    r2 = client.get("/api/decks")
    deck = next(d for d in r2.json() if d["id"] == 1)
    assert deck["built"] is True


def test_patch_deck_built_true_then_false(client):
    client.patch("/api/decks/1", json={"built": True})
    r = client.patch("/api/decks/1", json={"built": False})
    assert r.status_code == 200
    assert r.json()["built"] is False


def test_patch_deck_name_only_does_not_reset_built(client):
    client.patch("/api/decks/1", json={"built": True})
    r = client.patch("/api/decks/1", json={"name": "Renamed Deck"})
    assert r.status_code == 200
    assert r.json()["name"] == "Renamed Deck"
    assert r.json()["built"] is True


def test_patch_deck_built_only_does_not_reset_name(client):
    r = client.patch("/api/decks/1", json={"built": True})
    assert r.status_code == 200
    assert r.json()["name"] == "Test Deck"


def test_patch_nonexistent_deck_404(client):
    r = client.patch("/api/decks/9999", json={"built": True})
    assert r.status_code == 404
```

- [ ] **Step 2: Run them to verify they fail**

Run: `pytest tests/test_deck_built.py -v`
Expected: FAIL — `list_decks` doesn't select `built` yet (`KeyError`/`None` instead of `False`), and `rename_deck` only accepts `name` (a `built`-only body fails Pydantic validation on the current required-`name` `DeckRename` model).

- [ ] **Step 3: Implement**

In `app.py`, replace:

```python
class DeckRename(BaseModel):
    name: str
```

with:

```python
class DeckUpdate(BaseModel):
    name: str | None = None
    built: bool | None = None
```

Replace `list_decks`'s query:

```python
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

with (add `d.built` to the `SELECT`, cast it to `bool` per row since SQLite stores it as an int):

```python
        cur.execute("""
            SELECT d.id, d.name, d.created_at, d.built,
                   COALESCE(SUM(CASE WHEN dc.is_considering THEN 0 ELSE dc.quantity END), 0) AS card_count
            FROM decks d
            LEFT JOIN deck_cards dc ON dc.deck_id = d.id
            GROUP BY d.id
            ORDER BY d.name
        """)
        rows = [dict(r) for r in cur.fetchall()]
        for row in rows:
            row["built"] = bool(row["built"])
        return rows
```

Replace `rename_deck`:

```python
@app.patch("/api/decks/{deck_id}")
def rename_deck(deck_id: int, body: DeckRename):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("UPDATE decks SET name = ? WHERE id = ?", (body.name.strip(), deck_id))
        if cur.rowcount == 0:
            raise HTTPException(404, "Deck not found")
        conn.commit()
    return {"id": deck_id, "name": body.name.strip()}
```

with:

```python
@app.patch("/api/decks/{deck_id}")
def update_deck(deck_id: int, body: DeckUpdate):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT name, built FROM decks WHERE id = ?", (deck_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Deck not found")
        new_name = body.name.strip() if body.name is not None else row["name"]
        new_built = int(body.built) if body.built is not None else row["built"]
        cur.execute("UPDATE decks SET name = ?, built = ? WHERE id = ?", (new_name, new_built, deck_id))
        conn.commit()
    return {"id": deck_id, "name": new_name, "built": bool(new_built)}
```

- [ ] **Step 4: Run the tests again to verify they pass**

Run: `pytest tests/test_deck_built.py -v`
Expected: PASS for all 6 tests.

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `pytest -v`
Expected: PASS for everything — no other code references `DeckRename` by name (grep to confirm: `grep -rn "DeckRename" app.py` should show no remaining references after the rename), and the rename-only frontend call site sends `{name}`, which `DeckUpdate` still accepts (with `built` falling back to the current value).

- [ ] **Step 6: Commit**

```bash
git add app.py tests/test_deck_built.py
git commit -m "feat: expose and update decks.built via the API"
```

---

### Task 3: Frontend — toggle button, switcher badge, active-state sync

**Files:**
- Modify: `static/index.html` (deck editor header)
- Modify: `static/app.js` (`API`, `renderDeckSwitchResults`, `renderDeckContent`, new click handler)
- Modify: `static/style.css` (button active state, badge)

**Interfaces:**
- Consumes: `PATCH /api/decks/{deck_id}` (now accepts `built`) and `GET /api/decks` (now returns `built`) from Task 2.

- [ ] **Step 1: Add the button to the deck editor header**

In `static/index.html`, find:

```html
                <button id="deck-add-btn" class="action-btn" title="Add cards  (/)">+ Add</button>
                <button id="deck-rename-btn" class="action-btn">Rename</button>
                <button id="deck-delete-btn" class="action-btn action-btn-danger">Delete</button>
```

Replace with:

```html
                <button id="deck-add-btn" class="action-btn" title="Add cards  (/)">+ Add</button>
                <button id="deck-built-btn" class="action-btn">Built</button>
                <button id="deck-rename-btn" class="action-btn">Rename</button>
                <button id="deck-delete-btn" class="action-btn action-btn-danger">Delete</button>
```

- [ ] **Step 2: Add the active-state CSS**

In `static/style.css`, find:

```css
.hide-lands-btn.active { border-color: var(--accent); color: var(--accent); background: rgba(200,155,60,0.1); }
.unowned-only-btn.active { border-color: var(--accent); color: var(--accent); background: rgba(200,155,60,0.1); }
```

Add a third line immediately after:

```css
#deck-built-btn.active { border-color: var(--accent); color: var(--accent); background: rgba(200,155,60,0.1); }
```

Then find the deck-switcher list rules (`.deck-list-name { ... }` / `.deck-list-count { ... }`, around line 478-490) and add, right after `.deck-list-count`'s rule:

```css
.deck-list-built-badge { color: var(--accent); margin-left: 4px; font-size: 11px; }
```

- [ ] **Step 3: Add `API.updateDeck` alongside the existing `renameDeck`**

In `static/app.js`, find the existing `renameDeck` method on the `API` object:

```js
  async renameDeck(id, name) {
    const r = await fetch(`/api/decks/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    if (!r.ok) throw new Error('Failed to rename deck');
    return r.json();
  },
```

Add a new method right after it:

```js
  async setDeckBuilt(id, built) {
    const r = await fetch(`/api/decks/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ built }),
    });
    if (!r.ok) throw new Error('Failed to update deck');
    return r.json();
  },
```

- [ ] **Step 4: Show the switcher-list badge**

In `static/app.js`, in `renderDeckSwitchResults()`, find:

```js
    item.innerHTML = `
      <span class="deck-list-name">${esc(deck.name)}</span>
      <span class="deck-list-count">${deck.card_count}</span>`;
```

Replace with:

```js
    item.innerHTML = `
      <span class="deck-list-name">${esc(deck.name)}</span>
      <span class="deck-list-count">${deck.card_count}</span>
      ${deck.built ? '<span class="deck-list-built-badge" title="Built">✓</span>' : ''}`;
```

- [ ] **Step 5: Sync the button's active state from `renderDeckContent()`**

In `static/app.js`, in `renderDeckContent()`, find:

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

Replace with (add the sync line right after the existing `textContent` assignment):

```js
function renderDeckContent() {
  deckState.filter.text = deckState.query;   // content search box feeds the model
  const deck  = deckState.decks.find(d => d.id === deckState.currentDeckId);
  const total = deckState.deckCards
    .filter(c => !c.is_considering)
    .reduce((s, c) => s + c.quantity, 0);
  document.getElementById('deck-editor-name').textContent =
    deck ? `${deck.name} (${total})` : `(${total})`;
  document.getElementById('deck-built-btn').classList.toggle('active', !!(deck && deck.built));
```

This runs on every deck render (deck switch, card add/remove, etc.), so the button always reflects whichever deck is currently open — not just the deck that was open when it was last clicked.

- [ ] **Step 6: Add the click handler**

In `static/app.js`, find the existing `deck-rename-btn` click handler:

```js
document.getElementById('deck-rename-btn').addEventListener('click', async () => {
```

Add a new handler immediately before it:

```js
document.getElementById('deck-built-btn').addEventListener('click', async () => {
  const deck = deckState.decks.find(d => d.id === deckState.currentDeckId);
  if (!deck) return;
  try {
    const res = await API.setDeckBuilt(deck.id, !deck.built);
    deck.built = res.built;
    renderDeckSwitchResults();
    renderDeckContent();
  } catch (e) { alert('Failed to update deck.'); }
});

```

- [ ] **Step 7: Manual verification**

Run: `uvicorn app:app --reload` (in this worktree, using its own local `mtg.db` from Task 1 Step 5) and in a browser:
- Open a deck, click "Built" — the button should get the accent highlight immediately, and the deck-switcher list (press `d`) should show a ✓ badge next to that deck's name.
- Click "Built" again — highlight and badge both disappear.
- Switch to a different (not-built) deck, then back to the built one — the button's highlight should correctly reflect each deck's own state, not carry over from whichever was clicked last.
- Rename the built deck — it should stay built after the rename.

- [ ] **Step 8: Commit**

```bash
git add static/index.html static/app.js static/style.css
git commit -m "feat: add Built toggle to deck header and switcher-list badge"
```

---

### Task 4: Check off acceptance criteria and finish

**Files:**
- Modify: `docs/superpowers/backlog/018-deck-built-flag.md`

- [ ] **Step 1: Verify each acceptance criterion against the finished work, then check it off**

Re-read `docs/superpowers/backlog/018-deck-built-flag.md`'s "Acceptance criteria" section and mark each `- [ ]` as `- [x]` only once you've genuinely confirmed it (Tasks 1-3's tests and manual verification already cover all of them: persistence, highlight convention, switcher badge, rename not resetting `built`, and default `built = 0` for existing decks via the migration test).

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/backlog/018-deck-built-flag.md
git commit -m "docs(backlog): check off item 018 acceptance criteria"
```

- [ ] **Step 3: Run the full test suite one last time**

Run: `pytest -v`
Expected: PASS for everything.
