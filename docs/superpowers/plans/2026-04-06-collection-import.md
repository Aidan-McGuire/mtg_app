# Collection Bulk Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a bulk import modal to the collection view that accepts a pasted text list or a Moxfield CSV file, matching cards by name and adding quantities to the existing collection.

**Architecture:** New `POST /api/collection/import` backend endpoint reuses `parse_decklist` and `lookup_card_id` from the deck import. A new collection import modal in the frontend mirrors the deck import modal pattern, with a two-tab UI (Text / CSV) where CSV is parsed entirely in JS before posting.

**Tech Stack:** FastAPI (Python), vanilla JS, SQLite

---

## Files

| File | Change |
|------|--------|
| `app.py` | Add `CollectionImport` model + `POST /api/collection/import` endpoint |
| `static/index.html` | Add Import button to collection header + collection import modal HTML |
| `static/app.js` | Add `API.importCollection`, modal open/close functions, submit handler, CSV parser |
| `static/style.css` | Add tab styles (`.import-tabs`, `.import-tab-btn`, `.import-tab-panel`) and CSV file input styles |

---

### Task 1: Backend endpoint

**Files:**
- Modify: `app.py` (after the `decrement_collection` endpoint, before the Decks section)

- [ ] **Step 1: Add the `CollectionImport` model and endpoint**

In `app.py`, after the `decrement_collection` function (around line 220), add:

```python
class CollectionImport(BaseModel):
    list: str


@app.post("/api/collection/import")
def import_collection(body: CollectionImport):
    entries = parse_decklist(body.list)
    if not entries:
        raise HTTPException(400, "No valid card entries found")

    with get_db() as conn:
        cur = conn.cursor()
        not_found = []
        imported = 0
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
        conn.commit()

    return {"imported": imported, "not_found": not_found}
```

- [ ] **Step 2: Verify the server starts without errors**

```bash
uvicorn app:app --reload
```

Expected: server starts, no import errors.

- [ ] **Step 3: Smoke-test the endpoint**

```bash
curl -s -X POST http://localhost:8000/api/collection/import \
  -H 'Content-Type: application/json' \
  -d '{"list": "1x Lightning Bolt\n1 Counterspell"}' | python3 -m json.tool
```

Expected: JSON with `imported` (≥0) and `not_found` list. (Cards may not be in your DB — `not_found` is fine.)

- [ ] **Step 4: Test empty list returns 400**

```bash
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/api/collection/import \
  -H 'Content-Type: application/json' \
  -d '{"list": ""}'
```

Expected: `400`

- [ ] **Step 5: Commit**

```bash
git add app.py
git commit -m "feat: add POST /api/collection/import endpoint"
```

---

### Task 2: HTML — Import button + modal

**Files:**
- Modify: `static/index.html`

- [ ] **Step 1: Add Import button to the collection view header**

In `index.html`, replace the collection view `search-bar` div (lines 33–43):

```html
    <div id="view-collection" class="view">
      <div class="search-bar">
        <input type="text" id="collection-search"
          placeholder="Filter collection…  (press / to focus)"
          autocomplete="off" spellcheck="false">
        <span id="collection-count" class="collection-count"></span>
        <button id="import-collection-btn" class="action-btn">↑ Import</button>
        <span class="kbd-hints">
          <kbd>Space</kbd> detail &nbsp;
          <kbd>+</kbd> / <kbd>-</kbd> quantity
        </span>
      </div>
      <div id="collection-grid" class="card-grid"></div>
    </div>
```

- [ ] **Step 2: Add the collection import modal**

In `index.html`, after the closing `</div>` of `<!-- Import deck modal -->` (after line 113, before `<script>`), add:

```html
  <!-- Import collection modal -->
  <div id="col-import-overlay" class="modal-overlay hidden" role="dialog" aria-modal="true">
    <div class="modal import-modal">
      <button id="col-import-close" class="modal-close" aria-label="Close">✕</button>
      <div class="import-modal-title">Import Collection</div>
      <div class="import-modal-body">
        <div class="import-tabs">
          <button class="import-tab-btn active" data-tab="text">Text list</button>
          <button class="import-tab-btn" data-tab="csv">Moxfield CSV</button>
        </div>
        <div id="col-import-tab-text" class="import-tab-panel">
          <textarea id="col-import-list" class="import-textarea"
            placeholder="Paste card list here…&#10;&#10;1 Atraxa, Praetors' Voice&#10;4 Lightning Bolt&#10;&#10;Section headers and // comments are ignored."></textarea>
        </div>
        <div id="col-import-tab-csv" class="import-tab-panel hidden">
          <label class="csv-file-label">
            <span id="csv-file-name" class="csv-file-name">No file chosen</span>
            <input id="col-import-file" type="file" accept=".csv" class="csv-file-input">
            <span class="action-btn">Choose file</span>
          </label>
          <div id="csv-preview" class="csv-preview hidden"></div>
        </div>
        <div id="col-import-result" class="import-result hidden"></div>
        <div class="import-actions">
          <button id="col-import-submit" class="action-btn import-submit-btn">Import</button>
        </div>
      </div>
    </div>
  </div>
```

- [ ] **Step 3: Verify HTML renders without console errors**

Open the app in a browser and navigate to the Collection tab. Confirm the Import button is visible in the header. Open devtools — no errors expected.

- [ ] **Step 4: Commit**

```bash
git add static/index.html
git commit -m "feat: add collection import button and modal HTML"
```

---

### Task 3: CSS — Tab styles and CSV file input

**Files:**
- Modify: `static/style.css`

- [ ] **Step 1: Add tab and CSV styles**

In `style.css`, append after the existing `.import-submit-btn:disabled` rule (end of the import modal section):

```css
/* Import modal tabs */
.import-tabs {
  display: flex;
  gap: 4px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 4px;
}
.import-tab-btn {
  background: none;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--muted);
  font-size: 13px;
  padding: 6px 12px;
  cursor: pointer;
  margin-bottom: -1px;
  transition: color 0.1s, border-color 0.1s;
}
.import-tab-btn:hover  { color: var(--text); }
.import-tab-btn.active { color: var(--text); border-bottom-color: var(--accent); }

.import-tab-panel { display: flex; flex-direction: column; gap: 8px; }
.import-tab-panel.hidden { display: none; }

/* CSV file picker */
.csv-file-label {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}
.csv-file-input { display: none; }
.csv-file-name {
  flex: 1;
  font-size: 13px;
  color: var(--muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.csv-preview {
  font-size: 12px;
  color: var(--muted);
  padding: 6px 10px;
  background: var(--surface2);
  border-radius: 6px;
  border: 1px solid var(--border);
}
```

- [ ] **Step 2: Verify tabs render correctly**

Open the collection import modal in the browser. Check that "Text list" and "Moxfield CSV" tabs appear, the active tab has the accent underline, and switching tabs (to be wired in Task 4) will show/hide panels.

- [ ] **Step 3: Commit**

```bash
git add static/style.css
git commit -m "feat: add collection import tab and CSV input styles"
```

---

### Task 4: JS — Modal logic, CSV parser, submit handler

**Files:**
- Modify: `static/app.js`

- [ ] **Step 1: Add `API.importCollection` to the API object**

In `app.js`, find the `API` object and add after `async importDeck(name, list)`:

```javascript
  async importCollection(list) {
    const r = await fetch('/api/collection/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ list }),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail || 'Import failed');
    }
    return r.json();
  },
```

- [ ] **Step 2: Add the CSV parser function**

In `app.js`, in the collection view section (after `renderCollectionGrid` and its search listener), add:

```javascript
function parseMoxfieldCsv(text) {
  const lines = text.split('\n').map(l => l.trim()).filter(Boolean);
  if (!lines.length) return '';

  function parseCsvRow(line) {
    const fields = [];
    let cur = '', inQuote = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (ch === '"') {
        if (inQuote && line[i + 1] === '"') { cur += '"'; i++; }
        else inQuote = !inQuote;
      } else if (ch === ',' && !inQuote) {
        fields.push(cur); cur = '';
      } else {
        cur += ch;
      }
    }
    fields.push(cur);
    return fields;
  }

  const header = parseCsvRow(lines[0]).map(h => h.toLowerCase());
  const countIdx = header.indexOf('count');
  const nameIdx  = header.indexOf('name');
  if (countIdx === -1 || nameIdx === -1) return '';

  return lines.slice(1).map(line => {
    const fields = parseCsvRow(line);
    const count = parseInt(fields[countIdx], 10);
    const name  = fields[nameIdx] || '';
    return (count > 0 && name) ? `${count}x ${name}` : null;
  }).filter(Boolean).join('\n');
}
```

- [ ] **Step 3: Add the modal open/close functions and event wiring**

In `app.js`, after the `parseMoxfieldCsv` function, add:

```javascript
// ── Collection import modal ───────────────────────────────────────────────────

let colImportList = ''; // assembled list string (from text tab or parsed CSV)

function openColImportModal() {
  colImportList = '';
  document.getElementById('col-import-list').value = '';
  document.getElementById('col-import-file').value = '';
  document.getElementById('csv-file-name').textContent = 'No file chosen';
  document.getElementById('csv-preview').classList.add('hidden');
  document.getElementById('col-import-result').classList.add('hidden');
  document.getElementById('col-import-result').textContent = '';
  document.getElementById('col-import-submit').disabled = false;
  document.getElementById('col-import-submit').textContent = 'Import';
  // Reset to text tab
  document.querySelectorAll('#col-import-overlay .import-tab-btn').forEach(b => b.classList.remove('active'));
  document.querySelector('#col-import-overlay .import-tab-btn[data-tab="text"]').classList.add('active');
  document.getElementById('col-import-tab-text').classList.remove('hidden');
  document.getElementById('col-import-tab-csv').classList.add('hidden');
  document.getElementById('col-import-overlay').classList.remove('hidden');
  document.body.style.overflow = 'hidden';
  document.getElementById('col-import-list').focus();
}

function closeColImportModal() {
  document.getElementById('col-import-overlay').classList.add('hidden');
  document.body.style.overflow = '';
}

document.getElementById('import-collection-btn').addEventListener('click', openColImportModal);
document.getElementById('col-import-close').addEventListener('click', closeColImportModal);
document.getElementById('col-import-overlay').addEventListener('click', e => {
  if (e.target === document.getElementById('col-import-overlay')) closeColImportModal();
});

// Tab switching
document.querySelectorAll('#col-import-overlay .import-tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('#col-import-overlay .import-tab-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    const tab = btn.dataset.tab;
    document.getElementById('col-import-tab-text').classList.toggle('hidden', tab !== 'text');
    document.getElementById('col-import-tab-csv').classList.toggle('hidden', tab !== 'csv');
  });
});

// CSV file picker
document.getElementById('col-import-file').addEventListener('change', e => {
  const file = e.target.files[0];
  if (!file) return;
  document.getElementById('csv-file-name').textContent = file.name;
  const reader = new FileReader();
  reader.onload = ev => {
    colImportList = parseMoxfieldCsv(ev.target.result);
    const preview = document.getElementById('csv-preview');
    const lineCount = colImportList ? colImportList.split('\n').length : 0;
    if (lineCount > 0) {
      preview.textContent = `${lineCount} card entr${lineCount !== 1 ? 'ies' : 'y'} parsed`;
      preview.classList.remove('hidden');
    } else {
      preview.textContent = 'Could not parse CSV — check file format';
      preview.classList.remove('hidden');
    }
  };
  reader.readAsText(file);
});

// Submit
document.getElementById('col-import-submit').addEventListener('click', async () => {
  const activeTab = document.querySelector('#col-import-overlay .import-tab-btn.active').dataset.tab;
  const list = activeTab === 'text'
    ? document.getElementById('col-import-list').value.trim()
    : colImportList;

  const resultEl = document.getElementById('col-import-result');
  const btn = document.getElementById('col-import-submit');

  if (!list) {
    resultEl.className = 'import-result import-result-error';
    resultEl.textContent = activeTab === 'csv' ? 'No CSV file selected or file could not be parsed.' : 'List is empty.';
    resultEl.classList.remove('hidden');
    return;
  }

  btn.disabled = true;
  btn.textContent = 'Importing…';
  resultEl.classList.add('hidden');

  try {
    const res = await API.importCollection(list);
    const { imported, not_found } = res;

    await loadCollectionView();

    if (not_found.length === 0) {
      closeColImportModal();
    } else {
      resultEl.className = 'import-result import-result-warn';
      resultEl.innerHTML =
        `Imported ${imported} card${imported !== 1 ? 's' : ''}. ` +
        `<strong>${not_found.length} not found:</strong><br>` +
        not_found.map(n => esc(n)).join('<br>');
      resultEl.classList.remove('hidden');
      btn.disabled = false;
      btn.textContent = 'Done';
      btn.addEventListener('click', closeColImportModal, { once: true });
    }
  } catch (err) {
    resultEl.className = 'import-result import-result-error';
    resultEl.textContent = err.message || 'Import failed.';
    resultEl.classList.remove('hidden');
    btn.disabled = false;
    btn.textContent = 'Import';
  }
});
```

- [ ] **Step 4: Add Escape key handling for the new modal**

In `app.js`, find the Escape key handler in the global keydown listener. It currently has:

```javascript
  if (e.key === 'Escape') {
    if (!document.getElementById('import-overlay').classList.contains('hidden')) {
      closeImportModal(); return;
    }
```

Add a check for the collection import overlay directly after the existing `closeImportModal` check:

```javascript
  if (e.key === 'Escape') {
    if (!document.getElementById('import-overlay').classList.contains('hidden')) {
      closeImportModal(); return;
    }
    if (!document.getElementById('col-import-overlay').classList.contains('hidden')) {
      closeColImportModal(); return;
    }
```

- [ ] **Step 5: Manual end-to-end test — Text tab**

1. Navigate to Collection tab
2. Click "↑ Import"
3. Confirm modal opens on Text tab
4. Paste: `1 Lightning Bolt`
5. Click Import
6. Confirm result or not-found message appears
7. Confirm collection view reloads after close

- [ ] **Step 6: Manual end-to-end test — CSV tab**

1. Open modal, click "Moxfield CSV" tab
2. Choose the `moxfield_haves.csv` file from Downloads
3. Confirm the preview shows the correct number of card entries
4. Click Import
5. Confirm result summary (imported count + any not-found)
6. Confirm collection view reloads

- [ ] **Step 7: Commit**

```bash
git add static/app.js
git commit -m "feat: add collection import modal with text and CSV support"
```
