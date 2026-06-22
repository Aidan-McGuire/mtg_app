# Modal "Add to deck" Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a type-ahead "Add to deck" control to the card detail modal that adds the card (one copy) to an existing deck and refreshes the "In decks" list.

**Architecture:** Frontend-only. The existing `POST /api/decks/{deck_id}/cards` endpoint (upsert/increment) is reused via `API.addCardToDeck`. The current `loadModalDecks(card)` is restructured: a behavior-preserving refactor first extracts the "In decks" rendering into `renderInDecksList`, then a second task adds an always-visible type-ahead control (native `<input list=datalist>`, matching the modal's tag inputs) that resolves typed text to a deck, adds the card, refreshes the list, and shows a transient note.

**Tech Stack:** Vanilla JS (`static/app.js`), CSS (`static/style.css`). No backend or Python test changes. JS has no automated test harness — verification is `node --check` + manual click-through.

## Global Constraints

- **No backend changes.** Reuse `API.addCardToDeck(deckId, cardId, quantity = 1)` → `POST /api/decks/{deck_id}/cards` with body `{card_id, quantity}`; it upserts (`quantity = quantity + excluded.quantity`).
- **Existing decks only.** A typed name that matches no deck must show an inline hint and make no API call. No deck creation.
- **Each add adds quantity 1.** No quantity selector. Re-adding increments via the backend upsert.
- Deck names rendered into HTML must be escaped with the existing `esc()` helper.
- Use the native ARM node for syntax checks: `/opt/homebrew/bin/node --check static/app.js` (NOT `/usr/local`, which is a dead Intel binary).
- `API.listDecks()` returns `[{id, name, created_at, card_count}, …]`.
- Guard renders with `element.isConnected` after any `await` (the modal may have closed).

---

### Task 1: Refactor — extract `renderInDecksList` (no behavior change)

**Files:**
- Modify: `static/app.js` (the `loadModalDecks` function, currently at lines 735-772)

**Interfaces:**
- Consumes: existing globals `esc`, `closeModal`, `loadDeckList`, `selectDeck`, and the `#modal-decks-section` element created by `openModal`.
- Produces:
  - `renderInDecksList(decks)` — renders the "In decks" sub-list into `#modal-in-decks`; `decks` is `[{id:int, name:str}, …]`; empty array clears the container. No return value.
  - `loadModalDecks(card)` — unchanged signature; now builds a `#modal-in-decks` container inside `#modal-decks-section` and delegates rendering to `renderInDecksList`.

This task must NOT change what the user sees: a card in no decks shows nothing; a card in decks shows the same "In decks" list with the same click-to-navigate behavior.

- [ ] **Step 1: Replace `loadModalDecks` with the refactored version**

In `static/app.js`, replace the entire current `loadModalDecks` function (lines 735-772) with:

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

  section.innerHTML = `<div id="modal-in-decks"></div>`;
  renderInDecksList(decks);
}

function renderInDecksList(decks) {
  const list = document.getElementById('modal-in-decks');
  if (!list) return;

  if (!decks.length) {
    list.innerHTML = '';   // hidden entirely when card is in no decks
    return;
  }

  list.innerHTML = `
    <div class="modal-tags-label">In decks</div>
    <div class="modal-decks-list">
      ${decks.map(d => `<button class="modal-deck-link" data-deck-id="${d.id}">${esc(d.name)}</button>`).join('')}
    </div>`;

  list.querySelectorAll('.modal-deck-link').forEach(btn => {
    btn.addEventListener('click', async () => {
      const deckId = Number(btn.dataset.deckId);
      closeModal();
      document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
      document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
      document.getElementById('view-decks').classList.add('active');
      document.querySelector('.nav-btn[data-view="decks"]').classList.add('active');
      await loadDeckList();
      selectDeck(deckId);
    });
  });
}
```

- [ ] **Step 2: Syntax check**

Run: `/opt/homebrew/bin/node --check static/app.js`
Expected: no output, exit 0.

- [ ] **Step 3: Manual verification (record result in report)**

Start the server if not running (`uvicorn app:app --reload`). In the browser:
- Open a card that is in at least one deck → modal shows the "In decks" list; clicking a deck name closes the modal and opens that deck (unchanged).
- Open a card in no decks → no "In decks" content appears.

If you cannot run a browser, state that explicitly and rely on the syntax check + a careful re-read confirming the rendered HTML and event wiring are identical to the pre-refactor version.

- [ ] **Step 4: Commit**

```bash
git add static/app.js
git commit -m "refactor: extract renderInDecksList from loadModalDecks"
```

---

### Task 2: Add the type-ahead "Add to deck" control

**Files:**
- Modify: `static/app.js` (the `loadModalDecks` function from Task 1)
- Modify: `static/style.css` (append new styles)

**Interfaces:**
- Consumes: `renderInDecksList(decks)` and the `#modal-in-decks` container from Task 1; `API.listDecks()`, `API.addCardToDeck(deckId, cardId)`, `esc`.
- Produces: an always-visible "Add to deck" control inside `#modal-decks-section`; no new exported functions (the add handler and note logic are local to `loadModalDecks`).

- [ ] **Step 1: Replace `loadModalDecks` to fetch all decks and render the add control**

In `static/app.js`, replace the `loadModalDecks` function (the version from Task 1) with this version. `renderInDecksList` stays exactly as written in Task 1 — do not change it.

```javascript
async function loadModalDecks(card) {
  const section = document.getElementById('modal-decks-section');
  if (!section) return;

  let cardDecks = [];
  let allDecks = [];
  try {
    [cardDecks, allDecks] = await Promise.all([
      fetch(`/api/cards/${card.id}/decks`).then(r => (r.ok ? r.json() : [])),
      API.listDecks().catch(() => []),
    ]);
  } catch {
    cardDecks = [];
    allDecks = [];
  }

  if (!section.isConnected) return; // modal was closed

  section.innerHTML = `
    <div class="modal-add-deck">
      <div class="modal-tags-label">Add to deck</div>
      <div class="modal-add-deck-row">
        <input id="modal-add-deck-input" class="modal-add-deck-input"
          list="modal-deck-suggestions" placeholder="Search decks…" autocomplete="off">
        <datalist id="modal-deck-suggestions">
          ${allDecks.map(d => `<option value="${esc(d.name)}">`).join('')}
        </datalist>
      </div>
      <div id="modal-add-deck-note" class="modal-add-deck-note"></div>
    </div>
    <div id="modal-in-decks"></div>`;

  renderInDecksList(cardDecks);

  const input = document.getElementById('modal-add-deck-input');
  const note = document.getElementById('modal-add-deck-note');
  let noteTimer = null;

  function showNote(msg, isError) {
    note.textContent = msg;
    note.classList.toggle('error', !!isError);
    if (noteTimer) clearTimeout(noteTimer);
    noteTimer = setTimeout(() => {
      if (note.isConnected) { note.textContent = ''; note.classList.remove('error'); }
    }, 2000);
  }

  input.addEventListener('keydown', async (e) => {
    if (e.key !== 'Enter') return;
    e.preventDefault();
    const value = input.value.trim();
    if (!value) return;

    const deck = allDecks.find(d => d.name.toLowerCase() === value.toLowerCase());
    if (!deck) {
      showNote(`No deck named "${value}"`, true);
      return;
    }

    try {
      await API.addCardToDeck(deck.id, card.id);
    } catch {
      showNote(`Could not add to ${deck.name}`, true);
      return;
    }

    if (!input.isConnected) return; // modal closed during request
    input.value = '';

    let refreshed = [];
    try {
      const r = await fetch(`/api/cards/${card.id}/decks`);
      refreshed = r.ok ? await r.json() : [];
    } catch {
      refreshed = [];
    }
    if (!section.isConnected) return;
    renderInDecksList(refreshed);
    showNote(`Added to ${deck.name}`, false);
  });
}
```

- [ ] **Step 2: Append styles**

In `static/style.css`, append:

```css
.modal-add-deck {
  margin-top: 8px;
}
.modal-add-deck-row {
  margin-top: 4px;
}
.modal-add-deck-input {
  width: 100%;
  box-sizing: border-box;
  padding: 4px 8px;
  font: inherit;
}
.modal-add-deck-note {
  margin-top: 4px;
  min-height: 1em;
  font-size: 12px;
  color: var(--muted, #888);
}
.modal-add-deck-note.error {
  color: #d9534f;
}
```

- [ ] **Step 3: Syntax check**

Run: `/opt/homebrew/bin/node --check static/app.js`
Expected: no output, exit 0.

- [ ] **Step 4: Manual verification (record result in report)**

Start the server (`uvicorn app:app --reload`). In the browser, open a card's modal:
- The "Add to deck" input is visible for any card, including one in zero decks.
- Type an existing deck name (suggestions appear from the datalist), press Enter → note shows "Added to <deck>", the "In decks" list updates to include that deck.
- Press Enter again on the same deck → still works; open the deck in the deck view and confirm the quantity incremented.
- Type a name that matches no deck, press Enter → inline hint "No deck named …", and the deck is NOT added (the "In decks" list does not change).

If you cannot run a browser, state that explicitly and rely on the syntax check plus a careful re-read confirming: the datalist is populated from `allDecks`, the Enter handler resolves case-insensitively, the no-match path makes no API call, and `renderInDecksList` is called with refreshed data after a successful add.

- [ ] **Step 5: Commit**

```bash
git add static/app.js static/style.css
git commit -m "feat: add 'Add to deck' type-ahead control to card detail modal"
```

---

## Self-Review Notes

- **Spec coverage:** always-visible add control (Task 2) ✓; native `<input list=datalist>` type-ahead matching tag inputs (Task 2) ✓; case-insensitive exact-match resolution (Task 2 Step 1) ✓; existing-decks-only + inline hint, no API call on no match (Task 2 Step 1) ✓; quantity 1 / increment via backend (Task 2, `API.addCardToDeck` default) ✓; refresh "In decks" + transient note on success (Task 2 Step 1) ✓; error note on failure (Task 2 Step 1) ✓; `renderInDecksList` helper reused on refresh (Task 1) ✓; `esc()` on deck names in both list and datalist ✓; CSS for headings/row/note incl. error variant (Task 2 Step 2) ✓.
- **Placeholders:** none — full code shown for both tasks. No automated JS tests exist; verification is `node --check` + manual, stated honestly.
- **Type consistency:** `renderInDecksList(decks)` defined in Task 1 and called in Task 2 with the same shape `[{id, name}, …]`. `allDecks` items use `.id`/`.name` consistent with `API.listDecks()`. `API.addCardToDeck(deckId, cardId)` matches the existing client signature.
