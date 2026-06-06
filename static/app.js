// ── API ───────────────────────────────────────────────────────────────────────

const API = {
  async searchCards(q = '', limit = 40, offset = 0) {
    const p = new URLSearchParams({ q, limit, offset });
    const r = await fetch(`/api/cards?${p}`);
    if (!r.ok) throw new Error('Search failed');
    return r.json();
  },
  async getCollection() {
    const r = await fetch('/api/collection');
    if (!r.ok) throw new Error('Failed to load collection');
    return r.json();
  },
  async increment(cardId) {
    const r = await fetch(`/api/collection/${cardId}/increment`, { method: 'POST' });
    if (!r.ok) throw new Error('Failed');
    return r.json();
  },
  async decrement(cardId) {
    const r = await fetch(`/api/collection/${cardId}/decrement`, { method: 'POST' });
    if (!r.ok) throw new Error('Failed');
    return r.json();
  },
  async listDecks() {
    const r = await fetch('/api/decks');
    if (!r.ok) throw new Error('Failed to load decks');
    return r.json();
  },
  async createDeck(name) {
    const r = await fetch('/api/decks', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    if (!r.ok) throw new Error('Failed to create deck');
    return r.json();
  },
  async renameDeck(id, name) {
    const r = await fetch(`/api/decks/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name }),
    });
    if (!r.ok) throw new Error('Failed to rename deck');
    return r.json();
  },
  async deleteDeck(id) {
    const r = await fetch(`/api/decks/${id}`, { method: 'DELETE' });
    if (!r.ok) throw new Error('Failed to delete deck');
  },
  async getDeckCards(id) {
    const r = await fetch(`/api/decks/${id}/cards`);
    if (!r.ok) throw new Error('Failed to load deck');
    return r.json();
  },
  async addCardToDeck(deckId, cardId, quantity = 1) {
    const r = await fetch(`/api/decks/${deckId}/cards`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ card_id: cardId, quantity }),
    });
    if (!r.ok) throw new Error('Failed to add card');
    return r.json();
  },
  async updateDeckCard(deckId, cardId, updates) {
    const r = await fetch(`/api/decks/${deckId}/cards/${cardId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    });
    if (!r.ok) throw new Error('Failed to update card');
    return r.json();
  },
  async removeCardFromDeck(deckId, cardId) {
    const r = await fetch(`/api/decks/${deckId}/cards/${cardId}`, { method: 'DELETE' });
    if (!r.ok) throw new Error('Failed to remove card');
  },
  async importDeck(name, list) {
    const r = await fetch('/api/decks/import', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, list }),
    });
    if (!r.ok) {
      const err = await r.json().catch(() => ({}));
      throw new Error(err.detail || 'Import failed');
    }
    return r.json();
  },
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
  imageUrl(uri) {
    return `/api/image?url=${encodeURIComponent(uri)}`;
  },
};

// ── State ─────────────────────────────────────────────────────────────────────

const state = {
  cards:      [],       // all loaded cards in order
  collection: {},       // card id → quantity
  focusedIdx: -1,
  query:      '',
  offset:     0,
  loading:    false,
  hasMore:    true,
  modalCard:  null,
};

const LIMIT = 40;

// ── Collection ────────────────────────────────────────────────────────────────

async function loadCollection() {
  const rows = await API.getCollection();
  state.collection = {};
  for (const r of rows) state.collection[r.id] = r.quantity;
}

function qty(cardId) {
  return state.collection[cardId] || 0;
}

async function increment(cardId) {
  const wasOwned = qty(cardId) > 0;
  const res = await API.increment(cardId);
  state.collection[cardId] = res.quantity;
  refreshQtyInDOM(cardId);
  if (collectionViewActive()) {
    if (!wasOwned) {
      await loadCollectionView(); // card newly added — re-fetch for full data
    } else {
      const card = collectionState.cards.find(c => c.id === cardId);
      if (card) { card.quantity = res.quantity; renderCollectionGrid(); }
    }
  }
}

async function decrement(cardId) {
  const res = await API.decrement(cardId);
  state.collection[cardId] = res.quantity;
  refreshQtyInDOM(cardId);
  if (collectionViewActive()) {
    if (res.quantity === 0) {
      collectionState.cards = collectionState.cards.filter(c => c.id !== cardId);
    } else {
      const card = collectionState.cards.find(c => c.id === cardId);
      if (card) card.quantity = res.quantity;
    }
    renderCollectionGrid();
  }
}

function collectionViewActive() {
  return document.getElementById('view-collection').classList.contains('active');
}

function refreshQtyInDOM(cardId) {
  const q = qty(cardId);
  // Update all qty labels for this card (tile + modal)
  document.querySelectorAll(`[data-qty-for="${cardId}"]`).forEach(el => {
    el.textContent = q;
    el.className = 'qty-label' + (q > 0 ? ' owned' : '');
  });
}

// ── Grid rendering ────────────────────────────────────────────────────────────

function esc(str) {
  if (!str) return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function tagChipsHtml(tags, type) {
  if (!tags || !tags.length) return '';
  return `<div class="tag-chips-row">${
    tags.map(t => `<span class="tag-chip ${type}" title="${esc(t)}">${esc(t)}</span>`).join('')
  }</div>`;
}

function buildCardTile(card) {
  const q = qty(card.id);
  const div = document.createElement('div');
  div.className = 'card-tile';
  div.dataset.id = card.id;
  div.tabIndex = -1;

  const imgHtml = card.image_uri
    ? `<img src="${API.imageUrl(card.image_uri)}" loading="lazy" alt="${esc(card.name)}">`
    : `<div class="card-img-placeholder">${esc(card.name)}</div>`;

  const meta = [card.mana_cost, card.cmc != null ? `${card.cmc} CMC` : null]
    .filter(Boolean).join(' · ');

  div.innerHTML = `
    <div class="card-img-wrap">${imgHtml}</div>
    <div class="card-info">
      <div class="card-name">${esc(card.name)}</div>
      <div class="card-meta">${esc(meta)}</div>
      <div class="qty-row">
        <button class="qty-btn" data-action="dec" title="Remove from collection (-)">−</button>
        <span class="qty-label${q > 0 ? ' owned' : ''}" data-qty-for="${card.id}">${q}</span>
        <button class="qty-btn" data-action="inc" title="Add to collection (+)">+</button>
      </div>
      ${tagChipsHtml(card.collection_tags, 'collection-tag')}
    </div>`;

  div.querySelector('[data-action="inc"]').addEventListener('click', e => {
    e.stopPropagation(); increment(card.id);
  });
  div.querySelector('[data-action="dec"]').addEventListener('click', e => {
    e.stopPropagation(); decrement(card.id);
  });
  div.addEventListener('click', () => openModal(card));

  return div;
}

function appendCards(cards) {
  const grid = document.getElementById('card-grid');
  const frag = document.createDocumentFragment();
  for (const card of cards) frag.appendChild(buildCardTile(card));
  grid.appendChild(frag);
}

function clearGrid() {
  const grid = document.getElementById('card-grid');
  grid.querySelectorAll('.card-tile, .grid-message').forEach(el => el.remove());
  state.focusedIdx = -1;
}

function setGridMessage(msg) {
  clearGrid();
  const grid = document.getElementById('card-grid');
  const div = document.createElement('div');
  div.className = 'grid-message';
  div.textContent = msg;
  grid.appendChild(div);
}

// ── Search / load ─────────────────────────────────────────────────────────────

let searchTimer = null;

function onSearchInput(e) {
  const q = e.target.value;
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    if (q === state.query) return;
    state.query  = q;
    state.offset = 0;
    state.hasMore = true;
    state.cards  = [];
    clearGrid();
    loadCards();
  }, 300);
}

async function loadCards() {
  if (state.loading || !state.hasMore) return;
  state.loading = true;

  if (state.offset === 0) setGridMessage('Loading…');

  try {
    const cards = await API.searchCards(state.query, LIMIT, state.offset);
    if (state.offset === 0) clearGrid();

    if (cards.length === 0 && state.offset === 0) {
      setGridMessage('No cards found.');
    } else {
      appendCards(cards);
      state.cards.push(...cards);
      state.offset += cards.length;
      state.hasMore = cards.length === LIMIT;
    }
  } catch (err) {
    setGridMessage('Error loading cards.');
    console.error(err);
  } finally {
    state.loading = false;
  }
}

// ── Infinite scroll ───────────────────────────────────────────────────────────

function setupInfiniteScroll() {
  const grid = document.getElementById('card-grid');
  grid.addEventListener('scroll', () => {
    if (grid.scrollTop + grid.clientHeight >= grid.scrollHeight - 300) {
      loadCards();
    }
  });
}

// ── Keyboard nav ──────────────────────────────────────────────────────────────

function columnCount() {
  const tiles = document.querySelectorAll('#card-grid .card-tile');
  if (tiles.length < 2) return 1;
  const top0 = tiles[0].getBoundingClientRect().top;
  let n = 0;
  for (const t of tiles) {
    if (t.getBoundingClientRect().top !== top0) break;
    n++;
  }
  return Math.max(1, n);
}

function setFocused(idx) {
  const tiles = document.querySelectorAll('#card-grid .card-tile');
  if (!tiles.length) return;
  if (state.focusedIdx >= 0 && tiles[state.focusedIdx]) {
    tiles[state.focusedIdx].classList.remove('focused');
  }
  state.focusedIdx = Math.max(0, Math.min(idx, tiles.length - 1));
  const tile = tiles[state.focusedIdx];
  if (tile) {
    tile.classList.add('focused');
    tile.focus({ preventScroll: true });
    tile.scrollIntoView({ block: 'nearest' });
    // Load more if within two rows of end
    if (state.focusedIdx >= state.cards.length - columnCount() * 2) loadCards();
  }
}

function focusedCard() {
  if (state.focusedIdx < 0 || state.focusedIdx >= state.cards.length) return null;
  return state.cards[state.focusedIdx];
}

function handleGridKey(e) {
  const tiles = document.querySelectorAll('#card-grid .card-tile');
  if (!tiles.length) return;
  const cols = columnCount();
  const cur  = state.focusedIdx;

  switch (e.key) {
    case 'ArrowRight': e.preventDefault(); setFocused(cur < 0 ? 0 : cur + 1);    break;
    case 'ArrowLeft':  e.preventDefault(); setFocused(cur < 0 ? 0 : cur - 1);    break;
    case 'ArrowDown':  e.preventDefault(); setFocused(cur < 0 ? 0 : cur + cols); break;
    case 'ArrowUp':    e.preventDefault(); setFocused(cur < 0 ? 0 : cur - cols); break;
    case 'Enter': { e.preventDefault(); const c = focusedCard(); if (c) openModal(c); break; }
    case '+': case '=': { e.preventDefault(); const c = focusedCard(); if (c) increment(c.id); break; }
    case '-':           { e.preventDefault(); const c = focusedCard(); if (c) decrement(c.id); break; }
  }
}

// ── Modal ─────────────────────────────────────────────────────────────────────

function openModal(card) {
  state.modalCard = card;
  const q = qty(card.id);

  const imgSrc = card.image_uri ? API.imageUrl(card.image_uri) : null;
  const imgHtml = imgSrc
    ? `<img id="modal-main-img" src="${imgSrc}" alt="${esc(card.name)}">`
    : `<div class="modal-img-placeholder">${esc(card.name)}</div>`;

  const contentEl = document.getElementById('modal-content');
  contentEl.innerHTML = `
    <div class="modal-left">
      <div class="modal-img" id="modal-img-wrap">${imgHtml}</div>
      <button id="modal-flip-btn" class="modal-flip-btn hidden" title="Flip card (F)">⟲ Back face</button>
      <div class="modal-art-strip" id="modal-art-strip">
        <span style="font-size:12px;color:var(--muted)">Loading art options…</span>
      </div>
    </div>
    <div class="modal-details">
      <div class="modal-name">${esc(card.name)}</div>
      <div class="modal-mana">${esc(card.mana_cost || '—')}</div>
      <div class="modal-type">${esc(card.type_line || '')}</div>
      <div class="modal-oracle">${esc(card.oracle_text || '')}</div>
      <div class="modal-collection">
        <button class="qty-btn" data-action="dec" title="Remove (-)">−</button>
        <span class="qty-label${q > 0 ? ' owned' : ''}" data-qty-for="${card.id}">${q}</span>
        <button class="qty-btn" data-action="inc" title="Add (+)">+</button>
        <span class="qty-owned-label">owned</span>
      </div>
    </div>`;

  contentEl.querySelector('[data-action="inc"]').addEventListener('click', () => increment(card.id));
  contentEl.querySelector('[data-action="dec"]').addEventListener('click', () => decrement(card.id));

  document.getElementById('modal-overlay').classList.remove('hidden');
  document.body.style.overflow = 'hidden';
  document.getElementById('modal-close').focus();

  // Fetch and render art options asynchronously
  loadPrintings(card);
}

async function loadPrintings(card) {
  const strip = document.getElementById('modal-art-strip');
  if (!strip) return;

  let printings;
  try {
    const r = await fetch(`/api/cards/${card.id}/printings`);
    printings = r.ok ? await r.json() : [];
  } catch {
    printings = [];
  }

  if (!strip.isConnected) return; // modal was closed

  if (!printings.length) {
    strip.innerHTML = '';
    return;
  }

  const PREVIEW = 3;
  let showing = PREVIEW;
  let activePrinting = printings.find(p => p.image_uri === card.image_uri) || printings[0];
  let showingBack = false;

  const flipBtn = document.getElementById('modal-flip-btn');

  function updateMainImage() {
    const mainImg = document.getElementById('modal-main-img');
    if (!mainImg) return;
    const uri = showingBack && activePrinting.back_image_uri
      ? activePrinting.back_image_uri
      : activePrinting.image_uri;
    mainImg.src = API.imageUrl(uri);
    if (flipBtn) {
      if (activePrinting.back_image_uri) {
        flipBtn.classList.remove('hidden');
        flipBtn.textContent = showingBack ? '⟲ Front face' : '⟲ Back face';
      } else {
        flipBtn.classList.add('hidden');
      }
    }
  }

  if (flipBtn) {
    flipBtn.onclick = () => {
      showingBack = !showingBack;
      updateMainImage();
    };
  }

  function renderStrip() {
    strip.innerHTML = '';
    const visible = printings.slice(0, showing);
    visible.forEach(p => {
      const thumb = document.createElement('div');
      thumb.className = 'art-thumb' + (p === activePrinting ? ' active' : '');
      thumb.title = `${p.set_name || ''} — ${p.artist || ''}`.trim().replace(/^—\s*/, '');
      thumb.innerHTML = `<img src="${API.imageUrl(p.image_uri)}" loading="lazy" alt="${esc(p.set_name || '')}">`;
      thumb.addEventListener('click', () => {
        activePrinting = p;
        showingBack = false;
        updateMainImage();
        strip.querySelectorAll('.art-thumb').forEach(t => t.classList.remove('active'));
        thumb.classList.add('active');
      });
      strip.appendChild(thumb);
    });

    if (printings.length > PREVIEW) {
      const btn = document.createElement('button');
      btn.className = 'art-show-all';
      if (showing <= PREVIEW) {
        btn.textContent = `+${printings.length - PREVIEW} more`;
        btn.addEventListener('click', () => { showing = printings.length; renderStrip(); });
      } else {
        btn.textContent = 'Show less';
        btn.addEventListener('click', () => { showing = PREVIEW; renderStrip(); });
      }
      strip.appendChild(btn);
    }
  }

  updateMainImage();
  renderStrip();
}

function closeModal() {
  document.getElementById('modal-overlay').classList.add('hidden');
  document.body.style.overflow = '';
  state.modalCard = null;
  if (document.getElementById('view-decks').classList.contains('active')) {
    document.getElementById('deck-search').focus();
  } else if (collectionViewActive()) {
    document.getElementById('collection-search').focus();
  } else {
    const tiles = document.querySelectorAll('#card-grid .card-tile');
    if (state.focusedIdx >= 0 && tiles[state.focusedIdx]) {
      tiles[state.focusedIdx].focus({ preventScroll: true });
    }
  }
}

// ── Global keyboard handler ───────────────────────────────────────────────────

document.addEventListener('keydown', e => {
  const searchInput      = document.getElementById('search-input');
  const deckSearch       = document.getElementById('deck-search');
  const collectionSearch = document.getElementById('collection-search');
  const modalOpen        = !document.getElementById('modal-overlay').classList.contains('hidden');
  const decksActive      = document.getElementById('view-decks').classList.contains('active');

  if (modalOpen) {
    if (e.key === 'Escape') closeModal();
    if ((e.key === '+' || e.key === '=') && state.modalCard) {
      e.preventDefault(); increment(state.modalCard.id);
    }
    if (e.key === '-' && state.modalCard) {
      e.preventDefault(); decrement(state.modalCard.id);
    }
    if (e.key === 'f' || e.key === 'F') {
      const flipBtn = document.getElementById('modal-flip-btn');
      if (flipBtn && !flipBtn.classList.contains('hidden')) {
        e.preventDefault(); flipBtn.click();
      }
    }
    return;
  }

  if (e.key === 'Escape') {
    if (!document.getElementById('import-overlay').classList.contains('hidden')) {
      closeImportModal(); return;
    }
    if (!document.getElementById('col-import-overlay').classList.contains('hidden')) {
      closeColImportModal(); return;
    }
    searchInput.blur();
    deckSearch.blur();
    return;
  }

  // '/' focuses the relevant search input
  if (e.key === '/') {
    if (decksActive && document.activeElement !== deckSearch) {
      e.preventDefault(); deckSearch.focus(); return;
    } else if (collectionViewActive() && document.activeElement !== collectionSearch) {
      e.preventDefault(); collectionSearch.focus(); return;
    } else if (!decksActive && !collectionViewActive() && document.activeElement !== searchInput) {
      e.preventDefault(); searchInput.focus(); return;
    }
  }

  // Enter opens focused card (defaults to first card if none focused)
  if (e.key === 'Enter' && state.cards.length > 0) {
    e.preventDefault();
    if (state.focusedIdx < 0) setFocused(0);
    const c = focusedCard();
    if (c) { openModal(c); return; }
  }

  if (!decksActive && document.activeElement !== searchInput) {
    handleGridKey(e);
  }
});

// ── Nav ───────────────────────────────────────────────────────────────────────

document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.view').forEach(v   => v.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(`view-${btn.dataset.view}`).classList.add('active');
    btn.classList.add('active');
    if (btn.dataset.view === 'decks')      loadDeckList();
    if (btn.dataset.view === 'collection') loadCollectionView();
  });
});

// ── Search input wiring ───────────────────────────────────────────────────────

document.getElementById('search-input').addEventListener('input', onSearchInput);

// Arrow down from search → move focus into grid
document.getElementById('search-input').addEventListener('keydown', e => {
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    document.getElementById('search-input').blur();
    setFocused(state.focusedIdx < 0 ? 0 : state.focusedIdx);
  }
});

// ── Modal close wiring ────────────────────────────────────────────────────────

document.getElementById('modal-close').addEventListener('click', closeModal);
document.getElementById('modal-overlay').addEventListener('click', e => {
  if (e.target === document.getElementById('modal-overlay')) closeModal();
});

// ── Grid sizing ───────────────────────────────────────────────────────────────

const CARD_ASPECT = 680 / 488; // height / width of a magic card
const GRID_GAP    = 12;
const GRID_PAD_X  = 32;  // 16px left + 16px right
const GRID_PAD_Y  = 32;  // 8px top + 24px bottom
const INFO_H      = 78;  // fixed height of .card-info section
const MIN_CARD_W  = 240; // minimum card width before adding another column

function computeGrid(gridEl) {
  if (!gridEl) return;

  const W = gridEl.clientWidth  - GRID_PAD_X;
  const H = gridEl.clientHeight - GRID_PAD_Y;
  if (W <= 0 || H <= 0) return;

  const N     = Math.max(1, Math.floor((W + GRID_GAP) / (MIN_CARD_W + GRID_GAP)));
  const cardW = (W - GRID_GAP * (N - 1)) / N;
  const cardH = Math.floor(cardW * CARD_ASPECT + INFO_H);

  gridEl.style.gridTemplateColumns = `repeat(${N}, 1fr)`;
  gridEl.style.gridAutoRows        = `${cardH}px`;
}

// ── Init ──────────────────────────────────────────────────────────────────────

async function init() {
  await loadCollection();
  setupInfiniteScroll();

  // Size both card grids before first paint, keep in sync with resizes
  const browserGrid    = document.getElementById('card-grid');
  const collectionGrid = document.getElementById('collection-grid');
  computeGrid(browserGrid);
  computeGrid(collectionGrid);
  new ResizeObserver(() => computeGrid(browserGrid)).observe(browserGrid);
  new ResizeObserver(() => computeGrid(collectionGrid)).observe(collectionGrid);

  loadCards();
  loadDeckList();
  document.getElementById('search-input').focus();
}

init();

// ── Collection view ───────────────────────────────────────────────────────────

const collectionState = {
  cards: [],   // full card objects with .quantity
  query: '',
};

async function loadCollectionView() {
  try {
    const rows = await API.getCollection();
    // Keep state.collection map in sync too
    state.collection = {};
    for (const r of rows) state.collection[r.id] = r.quantity;
    collectionState.cards = rows;
    renderCollectionGrid();
  } catch (e) {
    console.error(e);
  }
}

function renderCollectionGrid() {
  const grid = document.getElementById('collection-grid');
  const countEl = document.getElementById('collection-count');
  grid.innerHTML = '';

  const q = collectionState.query.toLowerCase();
  const filtered = q
    ? collectionState.cards.filter(c => c.name.toLowerCase().includes(q))
    : collectionState.cards;

  const totalCopies  = filtered.reduce((s, c) => s + c.quantity, 0);
  const uniqueCards  = filtered.length;
  countEl.textContent = filtered.length
    ? `${totalCopies} card${totalCopies !== 1 ? 's' : ''} · ${uniqueCards} unique`
    : '';

  if (!filtered.length) {
    const msg = document.createElement('div');
    msg.className = 'grid-message';
    msg.textContent = collectionState.query ? 'No matches.' : 'No cards in collection yet.';
    grid.appendChild(msg);
    return;
  }

  const frag = document.createDocumentFragment();
  for (const card of filtered) frag.appendChild(buildCardTile(card));
  grid.appendChild(frag);
}

document.getElementById('collection-search').addEventListener('input', e => {
  collectionState.query = e.target.value;
  renderCollectionGrid();
});

document.getElementById('collection-search').addEventListener('keydown', e => {
  if (e.key === 'Escape') { e.target.blur(); collectionState.query = ''; renderCollectionGrid(); }
});

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
  document.getElementById('col-import-submit').onclick = null;
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
    if (tab !== 'csv') document.getElementById('csv-preview').classList.add('hidden');
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
  reader.onerror = () => {
    const preview = document.getElementById('csv-preview');
    preview.textContent = 'Could not read file.';
    preview.classList.remove('hidden');
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

    // Refresh collection grid before showing result — imported cards should appear even on partial success
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
      btn.onclick = closeColImportModal;
    }
  } catch (err) {
    resultEl.className = 'import-result import-result-error';
    resultEl.textContent = err.message || 'Import failed.';
    resultEl.classList.remove('hidden');
    btn.disabled = false;
    btn.textContent = 'Import';
  }
});

// ── Deck state ────────────────────────────────────────────────────────────────

const deckState = {
  decks:          [],
  currentDeckId:  null,
  deckCards:      [],
  deckView:       'grid',
  searchResults:  [],
  searchFocusIdx: -1,
  addingCards:    new Set(), // card IDs with an in-flight add request
};

// ── Deck list ─────────────────────────────────────────────────────────────────

async function loadDeckList() {
  try {
    deckState.decks = await API.listDecks();
    renderDeckList();
  } catch (e) {
    console.error(e);
  }
}

function renderDeckList() {
  const el = document.getElementById('deck-list');
  el.innerHTML = '';
  if (!deckState.decks.length) {
    const msg = document.createElement('div');
    msg.className = 'deck-list-empty';
    msg.textContent = 'No decks yet.';
    el.appendChild(msg);
    return;
  }
  for (const deck of deckState.decks) {
    const item = document.createElement('div');
    item.className = 'deck-list-item' + (deck.id === deckState.currentDeckId ? ' active' : '');
    item.dataset.id = deck.id;
    item.innerHTML = `
      <span class="deck-list-name">${esc(deck.name)}</span>
      <span class="deck-list-count">${deck.card_count}</span>`;
    item.addEventListener('click', () => selectDeck(deck.id));
    el.appendChild(item);
  }
}

async function selectDeck(id) {
  deckState.currentDeckId = id;
  deckState.deckCards = [];
  renderDeckList();
  try {
    deckState.deckCards = await API.getDeckCards(id);
    showDeckEditor();
  } catch (e) {
    console.error(e);
  }
}

function showDeckEditor() {
  document.getElementById('deck-empty').classList.add('hidden');
  document.getElementById('deck-editor').classList.remove('hidden');
  renderDeckContent();
}

// ── Deck editor rendering ─────────────────────────────────────────────────────

function renderDeckContent() {
  const deck  = deckState.decks.find(d => d.id === deckState.currentDeckId);
  const total = deckState.deckCards.reduce((s, c) => s + c.quantity, 0);
  document.getElementById('deck-editor-name').textContent =
    deck ? `${deck.name} (${total})` : `(${total})`;

  if (deckState.deckView === 'grid') {
    renderDeckGrid();
    document.getElementById('deck-grid-view').classList.remove('hidden');
    document.getElementById('deck-text-view').classList.add('hidden');
  } else {
    renderDeckText();
    document.getElementById('deck-text-view').classList.remove('hidden');
    document.getElementById('deck-grid-view').classList.add('hidden');
  }
}

function renderDeckGrid() {
  const el = document.getElementById('deck-grid-view');
  el.innerHTML = '';
  if (!deckState.deckCards.length) {
    el.innerHTML = '<div class="deck-empty-msg">No cards yet — search to add some.</div>';
    return;
  }
  const sorted = [...deckState.deckCards].sort((a, b) => {
    if (a.is_commander && !b.is_commander) return -1;
    if (!a.is_commander && b.is_commander) return 1;
    return a.name.localeCompare(b.name);
  });
  const frag = document.createDocumentFragment();
  for (const card of sorted) frag.appendChild(buildDeckCardTile(card));
  el.appendChild(frag);
}

function buildDeckCardTile(card) {
  const div = document.createElement('div');
  div.className = 'deck-card-tile' + (card.is_commander ? ' is-commander' : '');
  div.dataset.id = card.id;

  const imgHtml = card.image_uri
    ? `<img src="${API.imageUrl(card.image_uri)}" loading="lazy" alt="${esc(card.name)}">`
    : `<div class="card-img-placeholder">${esc(card.name)}</div>`;

  div.innerHTML = `
    <div class="deck-card-img-wrap">${imgHtml}</div>
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
  div.addEventListener('click', () => openModal(card));

  return div;
}

function renderDeckText() {
  const el = document.getElementById('deck-text-view');
  el.innerHTML = '';
  if (!deckState.deckCards.length) {
    el.innerHTML = '<div class="deck-empty-msg">No cards yet — search to add some.</div>';
    return;
  }

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

  for (const card of deckState.deckCards) {
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

  for (const [groupName, cards] of Object.entries(groups)) {
    if (!cards.length) continue;
    cards.sort((a, b) => a.name.localeCompare(b.name));
    const count = cards.reduce((s, c) => s + c.quantity, 0);
    const section = document.createElement('div');
    section.className = 'deck-text-section';
    section.innerHTML = `<div class="deck-text-group">${esc(groupName)} (${count})</div>`;
    for (const card of cards) {
      const row = document.createElement('div');
      row.className = 'deck-text-row';
      row.innerHTML = `
        <span class="deck-text-qty">${card.quantity}x</span>
        <span class="deck-text-name">${esc(card.name)}</span>
        <span class="deck-text-mana">${esc(card.mana_cost || '')}</span>`;
      row.addEventListener('click', () => openModal(card));
      section.appendChild(row);
    }
    el.appendChild(section);
  }
}

// ── Deck card mutations ───────────────────────────────────────────────────────

async function incDeckCard(cardId) {
  const card = deckState.deckCards.find(c => c.id === cardId);
  if (!card) return;
  try {
    const res = await API.updateDeckCard(deckState.currentDeckId, cardId, { quantity: card.quantity + 1 });
    card.quantity = res.quantity;
    syncDeckCount();
    renderDeckContent();
  } catch (e) { console.error(e); }
}

async function decDeckCard(cardId) {
  const card = deckState.deckCards.find(c => c.id === cardId);
  if (!card) return;
  if (card.quantity <= 1) { removeDeckCard(cardId); return; }
  try {
    const res = await API.updateDeckCard(deckState.currentDeckId, cardId, { quantity: card.quantity - 1 });
    card.quantity = res.quantity;
    syncDeckCount();
    renderDeckContent();
  } catch (e) { console.error(e); }
}

async function removeDeckCard(cardId) {
  try {
    await API.removeCardFromDeck(deckState.currentDeckId, cardId);
    deckState.deckCards = deckState.deckCards.filter(c => c.id !== cardId);
    syncDeckCount();
    renderDeckContent();
  } catch (e) { console.error(e); }
}

async function toggleCommander(cardId) {
  const card = deckState.deckCards.find(c => c.id === cardId);
  if (!card) return;
  try {
    const res = await API.updateDeckCard(deckState.currentDeckId, cardId, { is_commander: !card.is_commander });
    card.is_commander = res.is_commander;
    renderDeckContent();
  } catch (e) { console.error(e); }
}

function syncDeckCount() {
  const deck = deckState.decks.find(d => d.id === deckState.currentDeckId);
  if (deck) deck.card_count = deckState.deckCards.reduce((s, c) => s + c.quantity, 0);
  renderDeckList();
}

// ── Deck search ───────────────────────────────────────────────────────────────

let deckSearchTimer = null;

function onDeckSearchInput(e) {
  const q = e.target.value.trim();
  clearTimeout(deckSearchTimer);
  deckSearchTimer = setTimeout(() => runDeckSearch(q), 250);
}

async function runDeckSearch(q) {
  if (!q) { deckState.searchResults = []; renderDeckSearchResults(); return; }
  try {
    deckState.searchResults = await API.searchCards(q, 20, 0);
    deckState.searchFocusIdx = -1;
    renderDeckSearchResults();
  } catch (e) { console.error(e); }
}

function renderDeckSearchResults() {
  const el = document.getElementById('deck-search-results');
  el.innerHTML = '';
  for (let i = 0; i < deckState.searchResults.length; i++) {
    const card = deckState.searchResults[i];
    const row = document.createElement('div');
    row.className = 'deck-search-row';
    row.dataset.idx = i;
    row.innerHTML = `
      <span class="dsearch-name">${esc(card.name)}</span>
      <span class="dsearch-type">${esc(card.type_line || '')}</span>
      <button class="dsearch-add-btn" title="Add to deck">+</button>`;
    row.querySelector('.dsearch-add-btn').addEventListener('click', e => { e.stopPropagation(); addCardToDeck(card.id, card); });
    row.addEventListener('click', () => addCardToDeck(card.id, card));
    el.appendChild(row);
  }
}

async function addCardToDeck(cardId, cardData) {
  if (!deckState.currentDeckId) return;
  const existing = deckState.deckCards.find(c => c.id === cardId);
  if (existing) {
    incDeckCard(cardId);
  } else {
    if (deckState.addingCards.has(cardId)) return;
    deckState.addingCards.add(cardId);
    try {
      const res = await API.addCardToDeck(deckState.currentDeckId, cardId);
      deckState.deckCards.push({ ...cardData, quantity: res.quantity, is_commander: false });
      syncDeckCount();
      renderDeckContent();
    } catch (e) { console.error(e); }
    finally { deckState.addingCards.delete(cardId); }
  }
}

function setDeckSearchFocus() {
  const rows = document.querySelectorAll('.deck-search-row');
  rows.forEach((r, i) => r.classList.toggle('focused', i === deckState.searchFocusIdx));
  if (rows[deckState.searchFocusIdx]) rows[deckState.searchFocusIdx].scrollIntoView({ block: 'nearest' });
}

// ── Deck controls wiring ──────────────────────────────────────────────────────

document.getElementById('new-deck-btn').addEventListener('click', async () => {
  const name = prompt('Deck name:');
  if (!name || !name.trim()) return;
  try {
    const deck = await API.createDeck(name.trim());
    deckState.decks.push({ ...deck, card_count: 0 });
    deckState.decks.sort((a, b) => a.name.localeCompare(b.name));
    renderDeckList();
    selectDeck(deck.id);
  } catch (e) { alert('Failed to create deck.'); }
});

document.getElementById('deck-rename-btn').addEventListener('click', async () => {
  const deck = deckState.decks.find(d => d.id === deckState.currentDeckId);
  if (!deck) return;
  const name = prompt('New name:', deck.name);
  if (!name || !name.trim() || name.trim() === deck.name) return;
  try {
    await API.renameDeck(deck.id, name.trim());
    deck.name = name.trim();
    renderDeckList();
    renderDeckContent();
  } catch (e) { alert('Failed to rename deck.'); }
});

document.getElementById('deck-delete-btn').addEventListener('click', async () => {
  const deck = deckState.decks.find(d => d.id === deckState.currentDeckId);
  if (!deck) return;
  if (!confirm(`Delete "${deck.name}"?`)) return;
  try {
    await API.deleteDeck(deck.id);
    deckState.decks = deckState.decks.filter(d => d.id !== deck.id);
    deckState.currentDeckId = null;
    deckState.deckCards = [];
    renderDeckList();
    document.getElementById('deck-editor').classList.add('hidden');
    document.getElementById('deck-empty').classList.remove('hidden');
  } catch (e) { alert('Failed to delete deck.'); }
});

document.querySelectorAll('.vtoggle-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.vtoggle-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    deckState.deckView = btn.dataset.dview;
    renderDeckContent();
  });
});

// ── Import modal ──────────────────────────────────────────────────────────────

function openImportModal() {
  document.getElementById('import-name').value = '';
  document.getElementById('import-list').value = '';
  document.getElementById('import-result').classList.add('hidden');
  document.getElementById('import-result').textContent = '';
  document.getElementById('import-submit').disabled = false;
  document.getElementById('import-submit').textContent = 'Import';
  document.getElementById('import-overlay').classList.remove('hidden');
  document.body.style.overflow = 'hidden';
  document.getElementById('import-name').focus();
}

function closeImportModal() {
  document.getElementById('import-overlay').classList.add('hidden');
  document.body.style.overflow = '';
}

document.getElementById('import-deck-btn').addEventListener('click', openImportModal);
document.getElementById('import-close').addEventListener('click', closeImportModal);
document.getElementById('import-overlay').addEventListener('click', e => {
  if (e.target === document.getElementById('import-overlay')) closeImportModal();
});

document.getElementById('import-submit').addEventListener('click', async () => {
  const name = document.getElementById('import-name').value.trim();
  const list = document.getElementById('import-list').value.trim();
  const resultEl = document.getElementById('import-result');
  const btn = document.getElementById('import-submit');

  if (!name) { document.getElementById('import-name').focus(); return; }
  if (!list)  { document.getElementById('import-list').focus(); return; }

  btn.disabled = true;
  btn.textContent = 'Importing…';
  resultEl.classList.add('hidden');

  try {
    const res = await API.importDeck(name, list);
    const { deck, imported, not_found } = res;

    deckState.decks.push({ ...deck, card_count: imported });
    deckState.decks.sort((a, b) => a.name.localeCompare(b.name));
    renderDeckList();

    if (not_found.length === 0) {
      closeImportModal();
    } else {
      resultEl.className = 'import-result import-result-warn';
      resultEl.innerHTML =
        `Imported ${imported} card${imported !== 1 ? 's' : ''}. ` +
        `<strong>${not_found.length} not found:</strong><br>` +
        not_found.map(n => esc(n)).join('<br>');
      resultEl.classList.remove('hidden');
      btn.disabled = false;
      btn.textContent = 'Done';
      btn.addEventListener('click', closeImportModal, { once: true });
    }

    selectDeck(deck.id);
  } catch (err) {
    resultEl.className = 'import-result import-result-error';
    resultEl.textContent = err.message || 'Import failed.';
    resultEl.classList.remove('hidden');
    btn.disabled = false;
    btn.textContent = 'Import';
  }
});

document.getElementById('deck-search').addEventListener('input', onDeckSearchInput);
document.getElementById('deck-search').addEventListener('keydown', e => {
  const results = deckState.searchResults;
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    deckState.searchFocusIdx = Math.min(deckState.searchFocusIdx + 1, results.length - 1);
    setDeckSearchFocus();
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    deckState.searchFocusIdx = Math.max(deckState.searchFocusIdx - 1, -1);
    if (deckState.searchFocusIdx < 0) document.getElementById('deck-search').focus();
    else setDeckSearchFocus();
  } else if ((e.key === 'Enter' || e.key === '+') && deckState.searchFocusIdx >= 0) {
    e.preventDefault();
    const card = results[deckState.searchFocusIdx];
    if (card) addCardToDeck(card.id, card);
  } else if (e.key === 'Escape') {
    e.preventDefault();
    document.getElementById('deck-search').blur();
    deckState.searchResults = [];
    renderDeckSearchResults();
  }
});
