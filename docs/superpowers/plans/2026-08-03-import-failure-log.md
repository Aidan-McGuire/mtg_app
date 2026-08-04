# Import Failure Log Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every card name that fails to match during a collection or deck import is durably recorded (not just returned once in the HTTP response), reviewable later on a new "Import History" page, and dismissible once handled.

**Architecture:** New `import_failures` table (schema v5). Both `import_collection` and `import_deck` in `app.py` write to it via a shared helper wherever they currently do `not_found.append(name)`. Two new endpoints (`GET /api/import-failures`, `POST /api/import-failures/{id}/resolve`) expose it. A new frontend nav page renders and manages it. See spec at `docs/superpowers/specs/2026-08-03-import-failure-log-design.md`.

**Tech Stack:** FastAPI + sqlite3 (backend), vanilla JS + plain CSS (frontend), pytest + FastAPI TestClient (backend tests). No JS test runner exists in this repo — frontend verification is manual in the browser, matching prior plans (e.g. `docs/superpowers/plans/2026-08-01-owned-card-badge.md`).

## Global Constraints

- `import_failures.deck_id` is NULL for collection-import failures, set for deck-import failures, with `ON DELETE CASCADE` so deleting a deck cleans up its own failure rows.
- No dedup: every failed match inserts a new row, even if the same card name failed before.
- `GET /api/import-failures` defaults to outstanding-only (`resolved_at IS NULL`) when the `resolved` query param is omitted. `resolved=true` returns resolved-only. `resolved=all` returns everything.
- Resolving is manual only — no automatic resolution when a later import succeeds for a previously-failed name.
- The existing one-time `not_found` response/UI panel on both import flows is unchanged; this feature is additive, not a replacement.
- Out of scope: no "retry" action that re-attempts the add from the history page.

---

### Task 1: Schema — `import_failures` table

**Files:**
- Modify: `main.py` — `migrate_database()` (currently `main.py:85-123`)
- Modify: `tests/conftest.py` — `_SCHEMA` string (currently `tests/conftest.py:5-60`)

**Interfaces:**
- Consumes: nothing new.
- Produces: table `import_failures(id, source, deck_id, card_name, requested_qty, created_at, resolved_at)`, used by Task 2 (writes) and Task 3 (reads/updates).

This task has no directly observable behavior on its own (no code reads or writes the table yet), so per existing repo convention there's no dedicated migration test — `main.py`'s other version bumps (`v2`–`v4`, lines 93–120) have none either; they're only exercised indirectly through `tests/conftest.py`'s static schema, which is what this task updates. Verification is: the full test suite still passes after the schema change.

- [ ] **Step 1: Add the v5 migration block**

Open `main.py`. Find the `if version < 4:` block (currently lines 118-120):

```python
    if version < 4:
        cur.execute("ALTER TABLE deck_cards ADD COLUMN is_considering INTEGER NOT NULL DEFAULT 0;")
        cur.execute("UPDATE schema_version SET version = 4;")

    conn.commit()
    conn.close()
```

Insert a new block right after it, still before `conn.commit()`:

```python
    if version < 4:
        cur.execute("ALTER TABLE deck_cards ADD COLUMN is_considering INTEGER NOT NULL DEFAULT 0;")
        cur.execute("UPDATE schema_version SET version = 4;")

    if version < 5:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS import_failures (
                id INTEGER PRIMARY KEY,
                source TEXT NOT NULL,
                deck_id INTEGER REFERENCES decks(id) ON DELETE CASCADE,
                card_name TEXT NOT NULL,
                requested_qty INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                resolved_at TEXT
            );
        """)
        cur.execute("UPDATE schema_version SET version = 5;")

    conn.commit()
    conn.close()
```

- [ ] **Step 2: Mirror the table in the test schema**

Open `tests/conftest.py`. In the `_SCHEMA` string, add the table definition after the `deck_card_tags` table (currently ends at line 53) and before `INSERT INTO schema_version VALUES (4);` (currently line 54):

```python
CREATE TABLE import_failures (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    deck_id INTEGER REFERENCES decks(id) ON DELETE CASCADE,
    card_name TEXT NOT NULL,
    requested_qty INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at TEXT
);
INSERT INTO schema_version VALUES (5);
```

Replace the old `INSERT INTO schema_version VALUES (4);` line with `INSERT INTO schema_version VALUES (5);` (don't leave both — there must be exactly one `schema_version` row).

- [ ] **Step 3: Run the full test suite to confirm nothing broke**

Run: `pytest tests/ -v`
Expected: all existing tests PASS (this step only changes schema shape, not behavior — a failure here means the `_SCHEMA` string has a syntax error or a stray duplicate `schema_version` insert).

- [ ] **Step 4: Commit**

```bash
git add main.py tests/conftest.py
git commit -m "feat: add import_failures table (schema v5)"
```

---

### Task 2: Backend — record failures during import

**Files:**
- Modify: `app.py` — add helper near `lookup_card_id` (currently `app.py:210-233`); modify `import_collection` (currently `app.py:480-502`) and `import_deck` (currently `app.py:591-621`)
- Test: `tests/test_import_failures.py` (new file)

**Interfaces:**
- Consumes: `lookup_card_id(cur, name) -> int | None` (existing, `app.py:210`), the `cur`/`conn` pattern from `get_db()` (existing, `app.py:177-182`), `import_failures` table (Task 1).
- Produces: `_record_import_failure(cur, source, deck_id, card_name, requested_qty) -> None`, called by both import endpoints. No other task depends on its internals, only on the rows it produces.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_import_failures.py`:

```python
import sqlite3


def test_failed_collection_import_records_failure(client, db_path):
    r = client.post("/api/collection/import", json={"list": "1x Totally Fake Card Name"})
    assert r.status_code == 200
    assert "Totally Fake Card Name" in r.json()["not_found"]

    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT source, deck_id, card_name, requested_qty, resolved_at FROM import_failures"
    ).fetchone()
    conn.close()
    assert row == ("collection", None, "Totally Fake Card Name", 1, None)


def test_failed_deck_import_records_failure(client, db_path):
    r = client.post("/api/decks/import", json={
        "name": "New Deck", "list": "2x Another Fake Card"
    })
    assert r.status_code == 201
    body = r.json()
    deck_id = body["deck"]["id"]
    assert "Another Fake Card" in body["not_found"]

    conn = sqlite3.connect(str(db_path))
    row = conn.execute(
        "SELECT source, deck_id, card_name, requested_qty, resolved_at FROM import_failures"
    ).fetchone()
    conn.close()
    assert row == ("deck", deck_id, "Another Fake Card", 2, None)


def test_successful_import_records_no_failure(client, db_path):
    r = client.post("/api/collection/import", json={"list": "1x Lightning Bolt"})
    assert r.status_code == 200
    assert r.json()["not_found"] == []

    conn = sqlite3.connect(str(db_path))
    count = conn.execute("SELECT COUNT(*) FROM import_failures").fetchone()[0]
    conn.close()
    assert count == 0
```

(`db_path` and `client` are existing fixtures from `tests/conftest.py`; `Lightning Bolt` is one of the two stub cards `_SCHEMA` always seeds, id 1.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_import_failures.py -v`
Expected: FAIL — `import_failures` table exists (from Task 1) but nothing inserts into it yet, so the row-fetch assertions fail (`row` is `None`, or `count` isn't 0 in a way that's actually meaningful — the third test should already pass since nothing writes to the table at all yet; the first two must fail).

- [ ] **Step 3: Add the `_record_import_failure` helper**

Open `app.py`. After `lookup_card_id` (ends at line 232 with `return row["id"] if row else None`), add:

```python
def _record_import_failure(cur, source: str, deck_id: int | None, card_name: str, requested_qty: int) -> None:
    cur.execute("""
        INSERT INTO import_failures (source, deck_id, card_name, requested_qty)
        VALUES (?, ?, ?, ?)
    """, (source, deck_id, card_name, requested_qty))
```

- [ ] **Step 4: Call it from `import_collection`**

Find (currently `app.py:490-499`):

```python
        for qty, name in entries:
            card_id = lookup_card_id(cur, name)
            if card_id:
                cur.execute("""
                    INSERT INTO collection (card_id, quantity) VALUES (?, ?)
                    ON CONFLICT(card_id) DO UPDATE SET quantity = quantity + excluded.quantity
                """, (card_id, qty))
                imported += qty
            else:
                not_found.append(name)
```

Change the `else` branch to:

```python
            else:
                not_found.append(name)
                _record_import_failure(cur, "collection", None, name, qty)
```

- [ ] **Step 5: Call it from `import_deck`**

Find (currently `app.py:604-613`):

```python
        for qty, name in entries:
            card_id = lookup_card_id(cur, name)
            if card_id:
                cur.execute("""
                    INSERT INTO deck_cards (deck_id, card_id, quantity) VALUES (?, ?, ?)
                    ON CONFLICT(deck_id, card_id) DO UPDATE SET quantity = quantity + excluded.quantity
                """, (deck_id, card_id, qty))
                imported += qty
            else:
                not_found.append(name)
```

Change the `else` branch to:

```python
            else:
                not_found.append(name)
                _record_import_failure(cur, "deck", deck_id, name, qty)
```

(`deck_id` is already in scope from `cur.lastrowid` earlier in the function, line 600.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_import_failures.py -v`
Expected: PASS — all three tests green. Also run `pytest tests/ -v` to confirm no regressions in the existing collection/deck import tests.

- [ ] **Step 7: Commit**

```bash
git add app.py tests/test_import_failures.py
git commit -m "feat: record failed import matches to import_failures table"
```

---

### Task 3: Backend — list and resolve endpoints

**Files:**
- Modify: `app.py` — new section after `import_deck` (currently ends `app.py:621`, before the `# Deck cards` section comment at `app.py:624`)
- Test: `tests/test_import_failures.py` (extend from Task 2)

**Interfaces:**
- Consumes: `import_failures` table (Task 1 schema, Task 2 writes), `get_db()` (existing).
- Produces: `GET /api/import-failures?resolved=<false|true|all>` returning a list of `{id, source, deck_id, deck_name, card_name, requested_qty, created_at, resolved_at}`; `POST /api/import-failures/{id}/resolve` returning the updated row or 404. Task 4 (frontend) consumes both by these exact paths and shapes.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_import_failures.py`:

```python
def _seed_failure(db_path, source="collection", deck_id=None, card_name="Ghost Card", qty=1, resolved=False):
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "INSERT INTO import_failures (source, deck_id, card_name, requested_qty, resolved_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (source, deck_id, card_name, qty, "2026-08-03T00:00:00" if resolved else None),
    )
    conn.commit()
    failure_id = conn.execute("SELECT id FROM import_failures WHERE card_name = ?", (card_name,)).fetchone()[0]
    conn.close()
    return failure_id


def test_get_import_failures_defaults_to_outstanding(client, db_path):
    _seed_failure(db_path, card_name="Outstanding One", resolved=False)
    _seed_failure(db_path, card_name="Resolved One", resolved=True)

    r = client.get("/api/import-failures")
    assert r.status_code == 200
    names = [f["card_name"] for f in r.json()]
    assert names == ["Outstanding One"]


def test_get_import_failures_resolved_true(client, db_path):
    _seed_failure(db_path, card_name="Outstanding One", resolved=False)
    _seed_failure(db_path, card_name="Resolved One", resolved=True)

    r = client.get("/api/import-failures?resolved=true")
    names = [f["card_name"] for f in r.json()]
    assert names == ["Resolved One"]


def test_get_import_failures_resolved_all(client, db_path):
    _seed_failure(db_path, card_name="Outstanding One", resolved=False)
    _seed_failure(db_path, card_name="Resolved One", resolved=True)

    r = client.get("/api/import-failures?resolved=all")
    names = sorted(f["card_name"] for f in r.json())
    assert names == ["Outstanding One", "Resolved One"]


def test_get_import_failures_includes_deck_name(client, db_path):
    # deck id 1 ("Test Deck") already exists per the base _SCHEMA seed data
    _seed_failure(db_path, source="deck", deck_id=1, card_name="Deck Miss")

    r = client.get("/api/import-failures")
    row = next(f for f in r.json() if f["card_name"] == "Deck Miss")
    assert row["deck_id"] == 1
    assert row["deck_name"] == "Test Deck"


def test_resolve_import_failure(client, db_path):
    failure_id = _seed_failure(db_path, card_name="To Resolve")

    r = client.post(f"/api/import-failures/{failure_id}/resolve")
    assert r.status_code == 200
    assert r.json()["resolved_at"] is not None

    remaining = client.get("/api/import-failures").json()
    assert all(f["id"] != failure_id for f in remaining)


def test_resolve_nonexistent_import_failure_404(client):
    r = client.post("/api/import-failures/9999/resolve")
    assert r.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_import_failures.py -v`
Expected: FAIL on all the new tests — the endpoints don't exist yet (404s from FastAPI's default not-found, or connection errors depending on TestClient behavior for unmatched routes).

- [ ] **Step 3: Add the endpoints**

Open `app.py`. After `import_deck` (ends at line 621) and before the `# Deck cards` section comment (line 624), add:

```python
# ---------------------------------------------------------------------------
# Import failures
# ---------------------------------------------------------------------------

@app.get("/api/import-failures")
def list_import_failures(resolved: str = Query("false")):
    with get_db() as conn:
        cur = conn.cursor()
        where = ""
        if resolved == "false":
            where = "WHERE f.resolved_at IS NULL"
        elif resolved == "true":
            where = "WHERE f.resolved_at IS NOT NULL"
        elif resolved != "all":
            raise HTTPException(400, "resolved must be 'false', 'true', or 'all'")

        cur.execute(f"""
            SELECT f.id, f.source, f.deck_id, d.name AS deck_name,
                   f.card_name, f.requested_qty, f.created_at, f.resolved_at
            FROM import_failures f
            LEFT JOIN decks d ON d.id = f.deck_id
            {where}
            ORDER BY f.created_at DESC, f.id DESC
        """)
        return [dict(r) for r in cur.fetchall()]


@app.post("/api/import-failures/{failure_id}/resolve")
def resolve_import_failure(failure_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM import_failures WHERE id = ?", (failure_id,))
        if not cur.fetchone():
            raise HTTPException(404, "Import failure not found")
        cur.execute(
            "UPDATE import_failures SET resolved_at = datetime('now') WHERE id = ?",
            (failure_id,)
        )
        conn.commit()
        cur.execute("""
            SELECT f.id, f.source, f.deck_id, d.name AS deck_name,
                   f.card_name, f.requested_qty, f.created_at, f.resolved_at
            FROM import_failures f
            LEFT JOIN decks d ON d.id = f.deck_id
            WHERE f.id = ?
        """, (failure_id,))
        return dict(cur.fetchone())
```

`Query` and `HTTPException` are already imported at the top of `app.py` (`app.py:8`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_import_failures.py -v`
Expected: PASS — all tests from Task 2 and Task 3 green. Also run `pytest tests/ -v` for a full regression check.

- [ ] **Step 5: Commit**

```bash
git add app.py tests/test_import_failures.py
git commit -m "feat: add GET/resolve endpoints for import_failures"
```

---

### Task 4: Frontend — Import History page

**Files:**
- Modify: `static/index.html` — nav (`static/index.html:11-16`), add new view container after `view-decks` closes (currently `static/index.html:96`)
- Modify: `static/app.js` — `API` object (add methods after `importCollection`, currently `static/app.js:91-102`), nav click wiring (currently `static/app.js:1269-1284`), new render function
- Modify: `static/style.css` — new rules for the history table/rows

**Interfaces:**
- Consumes: `GET /api/import-failures?resolved=...` and `POST /api/import-failures/{id}/resolve` (Task 3), existing `esc()` helper (used throughout `app.js` for HTML-escaping text), existing `.nav-btn` / `.view` / `.action-btn` CSS classes.
- Produces: nothing consumed by later tasks — this is the last task.

This is one cohesive task: the nav entry, the view container, the fetch/render logic, and the resolve wiring all have to land together to be meaningfully testable in the browser.

- [ ] **Step 1: Add the nav button and view container**

Open `static/index.html`. In the `<nav>` block (currently lines 11-16):

```html
    <nav id="nav">
      <span class="nav-title">MTG</span>
      <button class="nav-btn" data-view="browser">Cards</button>
      <button class="nav-btn active" data-view="collection">Collection</button>
      <button class="nav-btn" data-view="decks">Decks</button>
    </nav>
```

Add a fourth button:

```html
    <nav id="nav">
      <span class="nav-title">MTG</span>
      <button class="nav-btn" data-view="browser">Cards</button>
      <button class="nav-btn active" data-view="collection">Collection</button>
      <button class="nav-btn" data-view="decks">Decks</button>
      <button class="nav-btn" data-view="history">Import History</button>
    </nav>
```

Then, right after `view-decks` closes (currently line 96, immediately before the `<!-- Add-card palette (decks page) -->` comment on line 98), add the new view container:

```html
    <div id="view-history" class="view">
      <div class="search-bar">
        <span class="import-history-title">Import History</span>
        <label class="import-history-toggle">
          <input type="checkbox" id="history-show-resolved">
          Show resolved
        </label>
      </div>
      <div id="import-history-list"></div>
    </div>
```

- [ ] **Step 2: Add API methods**

Open `static/app.js`. After `importCollection` (currently lines 91-102, ending `return r.json(); },`), add:

```js
  async getImportFailures(resolved = 'false') {
    const r = await fetch(`/api/import-failures?resolved=${resolved}`);
    if (!r.ok) throw new Error('Failed to load import history');
    return r.json();
  },
  async resolveImportFailure(id) {
    const r = await fetch(`/api/import-failures/${id}/resolve`, { method: 'POST' });
    if (!r.ok) throw new Error('Failed to resolve');
    return r.json();
  },
```

- [ ] **Step 3: Write the render function**

Still in `static/app.js`, add a new function near `loadCollectionView` (currently `static/app.js:1499-1518`) — place it directly after that function:

```js
async function loadImportHistoryView() {
  const showResolved = document.getElementById('history-show-resolved').checked;
  const listEl = document.getElementById('import-history-list');
  try {
    const rows = await API.getImportFailures(showResolved ? 'true' : 'false');
    listEl.innerHTML = '';
    if (rows.length === 0) {
      listEl.innerHTML = `<div class="import-history-empty">${showResolved ? 'No resolved entries.' : 'No outstanding import failures.'}</div>`;
      return;
    }
    for (const f of rows) {
      const row = document.createElement('div');
      row.className = 'import-history-row';
      const sourceLabel = f.source === 'deck' ? `Deck: ${esc(f.deck_name || 'Unknown')}` : 'Collection';
      row.innerHTML = `
        <span class="import-history-source">${esc(sourceLabel)}</span>
        <span class="import-history-name">${esc(f.card_name)}</span>
        <span class="import-history-qty">×${f.requested_qty}</span>
        <span class="import-history-date">${esc(f.created_at)}</span>
        ${showResolved ? '' : '<button class="action-btn import-history-resolve-btn">Resolve</button>'}
      `;
      if (!showResolved) {
        row.querySelector('.import-history-resolve-btn').addEventListener('click', async () => {
          await API.resolveImportFailure(f.id);
          loadImportHistoryView();
        });
      }
      listEl.appendChild(row);
    }
  } catch (e) {
    console.error(e);
    listEl.innerHTML = '<div class="import-history-empty">Failed to load import history.</div>';
  }
}
```

(`esc()` is the existing HTML-escaping helper used throughout `app.js`, e.g. in `buildCardTile`.)

- [ ] **Step 4: Wire up nav click and the show-resolved toggle**

Still in `static/app.js`, find the nav click handler (currently lines 1269-1284):

```js
document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.view').forEach(v   => v.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(`view-${btn.dataset.view}`).classList.add('active');
    btn.classList.add('active');
    if (btn.dataset.view !== 'decks') { closeAddPalette(); closeDeckSwitchPalette(); }
    if (btn.dataset.view === 'decks') {
      loadDeckList().then(() => {
        const stillOnDecks = document.getElementById('view-decks').classList.contains('active');
        if (stillOnDecks && !deckState.currentDeckId) openDeckSwitchPalette();
      });
    }
    if (btn.dataset.view === 'collection') loadCollectionView();
  });
});
```

Add a branch for `history`:

```js
document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.view').forEach(v   => v.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(`view-${btn.dataset.view}`).classList.add('active');
    btn.classList.add('active');
    if (btn.dataset.view !== 'decks') { closeAddPalette(); closeDeckSwitchPalette(); }
    if (btn.dataset.view === 'decks') {
      loadDeckList().then(() => {
        const stillOnDecks = document.getElementById('view-decks').classList.contains('active');
        if (stillOnDecks && !deckState.currentDeckId) openDeckSwitchPalette();
      });
    }
    if (btn.dataset.view === 'collection') loadCollectionView();
    if (btn.dataset.view === 'history') loadImportHistoryView();
  });
});
```

Right after that block, add the toggle's own listener:

```js
document.getElementById('history-show-resolved').addEventListener('change', loadImportHistoryView);
```

- [ ] **Step 5: Add CSS**

Open `static/style.css`. Add at the end of the file:

```css
/* ── Import History ─────────────────────────────────────────────────────── */

.import-history-title {
  font-weight: 600;
}

.import-history-toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-left: auto;
  font-size: 0.9em;
  cursor: pointer;
}

.import-history-empty {
  padding: 24px;
  opacity: 0.7;
  text-align: center;
}

.import-history-row {
  display: grid;
  grid-template-columns: 120px 1fr 60px 180px auto;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
}

.import-history-source {
  opacity: 0.8;
  font-size: 0.9em;
}

.import-history-qty {
  opacity: 0.8;
}

.import-history-date {
  opacity: 0.6;
  font-size: 0.85em;
}
```

- [ ] **Step 6: Manual verification in the browser**

No JS test runner exists in this repo (consistent with the owned-card-badge plan). Start the app (`uvicorn app:app --reload`) and verify:
- A new "Import History" nav button appears and switches to an empty state initially (or whatever's already in the table from Task 2/3's tests, if run against the same dev DB — use a scratch DB copy if you want a clean slate, same approach used during the original bug investigation).
- Running a collection import with a misspelled card name shows it on the Import History page after switching there.
- Running a deck import with a misspelled card name shows it with the correct deck name in the "Deck: X" source label.
- Clicking "Resolve" removes the row from the default (outstanding) view.
- Checking "Show resolved" reveals it again, without a Resolve button.
- Unchecking "Show resolved" returns to the outstanding-only view.

- [ ] **Step 7: Commit**

```bash
git add static/index.html static/app.js static/style.css
git commit -m "feat: add Import History page for reviewing/resolving failed import matches"
```
