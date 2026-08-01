// ── API ───────────────────────────────────────────────────────────────────────

const API = {
  async searchCards(q = '', limit = 40, offset = 0, extra = {}) {
    const p = new URLSearchParams({ q, limit, offset, ...extra });
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
  async getCollectionCardTags(cardId) {
    const r = await fetch(`/api/collection/${cardId}/tags`);
    return r.ok ? r.json() : [];
  },
  async addCollectionTag(cardId, tag) {
    const r = await fetch(`/api/collection/${cardId}/tags`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tag }),
    });
    if (!r.ok) throw new Error('Failed to add tag');
    return r.json();
  },
  async removeCollectionTag(cardId, tag) {
    await fetch(`/api/collection/${cardId}/tags/${encodeURIComponent(tag)}`, { method: 'DELETE' });
  },
  async getDeckCardTags(deckId, cardId) {
    const r = await fetch(`/api/decks/${deckId}/cards/${cardId}/tags`);
    return r.ok ? r.json() : [];
  },
  async addDeckTag(deckId, cardId, tag) {
    const r = await fetch(`/api/decks/${deckId}/cards/${cardId}/tags`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ tag }),
    });
    if (!r.ok) throw new Error('Failed to add tag');
    return r.json();
  },
  async removeDeckTag(deckId, cardId, tag) {
    await fetch(`/api/decks/${deckId}/cards/${cardId}/tags/${encodeURIComponent(tag)}`, { method: 'DELETE' });
  },
  async listCollectionTags() {
    const r = await fetch('/api/collection/tags');
    return r.ok ? r.json() : [];
  },
  async listDeckTags(deckId) {
    const r = await fetch(`/api/decks/${deckId}/tags`);
    return r.ok ? r.json() : [];
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
  filter:     null,   // filter/sort model, initialized in init()
};

const LIMIT = 40;

// ── Filter / Sort module ───────────────────────────────────────────────────────

const COLOR_LETTERS = ['W', 'U', 'B', 'R', 'G'];
const TYPE_OPTIONS = ['Creature', 'Instant', 'Sorcery', 'Enchantment',
                      'Artifact', 'Planeswalker', 'Land', 'Battle'];
const SORT_OPTIONS_BASE = [
  { value: 'name', label: 'Name' },
  { value: 'cmc',  label: 'Mana value' },
  { value: 'type', label: 'Type' },
  { value: 'power', label: 'Power' },
  { value: 'toughness', label: 'Toughness' },
];
const SORT_OPTION_QUANTITY = { value: 'quantity', label: 'Quantity' };

function makeFilterModel(overrides = {}) {
  return {
    text: '', colors: new Set(), colorlessOnly: false,
    types: new Set(), cmcMin: null, cmcMax: null, tags: new Set(),
    sort: 'name', dir: 'asc', ...overrides,
  };
}

function typeRank(typeLine) {
  const tl = typeLine || '';
  const i = TYPE_OPTIONS.findIndex(t => tl.includes(t));
  return i === -1 ? TYPE_OPTIONS.length : i;
}

function ptNum(v) {
  const n = parseFloat(v);
  return Number.isFinite(n) && /^[0-9]/.test(String(v)) ? n : null;
}

function sortComparator(model) {
  const dir = model.dir === 'desc' ? -1 : 1;
  const byName = (a, b) => a.name.localeCompare(b.name);
  return (a, b) => {
    let r;
    switch (model.sort) {
      case 'cmc':      r = (a.cmc ?? 0) - (b.cmc ?? 0); break;
      case 'quantity': r = (a.quantity ?? 0) - (b.quantity ?? 0); break;
      case 'type':     r = typeRank(a.type_line) - typeRank(b.type_line); break;
      case 'power':
      case 'toughness': {
        const av = ptNum(a[model.sort]), bv = ptNum(b[model.sort]);
        if (av === null && bv === null) return byName(a, b);
        if (av === null) return 1;    // missing/non-numeric always last
        if (bv === null) return -1;
        r = av - bv;
        break;
      }
      default: return byName(a, b) * dir;   // name
    }
    return r !== 0 ? r * dir : byName(a, b);
  };
}

function applyFilters(cards, model) {
  return cards.filter(c => {
    if (model.text) {
      const t = model.text.toLowerCase();
      if (!c.name.toLowerCase().includes(t) &&
          !(c.oracle_text || '').toLowerCase().includes(t) &&
          !(c.type_line || '').toLowerCase().includes(t)) return false;
    }
    if (model.colorlessOnly) {
      if ((c.color_identity || '') !== '') return false;
    } else if (model.colors.size) {
      for (const ch of (c.color_identity || '')) {
        if (!model.colors.has(ch)) return false;   // subset; '' passes
      }
    }
    if (model.types.size) {
      const tl = c.type_line || '';
      if (![...model.types].some(ty => tl.includes(ty))) return false;
    }
    if (model.cmcMin != null && (c.cmc ?? 0) < model.cmcMin) return false;
    if (model.cmcMax != null && (c.cmc ?? 0) > model.cmcMax) return false;
    if (model.tags.size) {
      const tags = [...(c.collection_tags || []), ...(c.deck_tags || [])];
      if (![...model.tags].some(tg => tags.includes(tg))) return false;
    }
    return true;
  });
}

function activeFilterCount(model) {
  let n = 0;
  if (model.text) n++;
  if (model.colorlessOnly || model.colors.size) n++;
  if (model.types.size) n++;
  if (model.cmcMin != null || model.cmcMax != null) n++;
  if (model.tags.size) n++;
  return n;
}

function modelToParams(model) {
  const p = {};
  if (model.text) p.text = model.text;
  if (model.colorlessOnly) p.colorless = '1';
  else if (model.colors.size) p.colors = [...model.colors].join(',');
  if (model.types.size) p.types = [...model.types].join(',');
  if (model.cmcMin != null) p.cmc_min = model.cmcMin;
  if (model.cmcMax != null) p.cmc_max = model.cmcMax;
  if (model.sort) p.sort = model.sort;
  if (model.dir) p.dir = model.dir;
  return p;
}

/**
 * Render a filter/sort control bar into `container`.
 * config: { model, facets:Set<'colors'|'types'|'cmc'|'tags'>,
 *           sortOptions:[{value,label}], tagOptions:[], onChange:fn }
 */
function buildFilterControls(container, config) {
  const { model, facets, sortOptions, tagOptions = [], onChange } = config;
  container.innerHTML = '';
  container.className = 'filter-bar';

  // Sort select + direction toggle
  const sortSel = document.createElement('select');
  sortSel.className = 'sort-select';
  for (const opt of sortOptions) {
    const o = document.createElement('option');
    o.value = opt.value; o.textContent = `Sort: ${opt.label}`;
    if (opt.value === model.sort) o.selected = true;
    sortSel.appendChild(o);
  }
  sortSel.addEventListener('change', () => { model.sort = sortSel.value; onChange(); });

  const dirBtn = document.createElement('button');
  dirBtn.className = 'dir-btn action-btn';
  dirBtn.textContent = model.dir === 'desc' ? '↓' : '↑';
  dirBtn.title = 'Toggle sort direction';
  dirBtn.addEventListener('click', () => {
    model.dir = model.dir === 'desc' ? 'asc' : 'desc';
    dirBtn.textContent = model.dir === 'desc' ? '↓' : '↑';
    onChange();
  });

  // Filters disclosure
  const filterBtn = document.createElement('button');
  filterBtn.className = 'filters-btn action-btn';
  const badge = document.createElement('span');
  badge.className = 'filter-badge';
  const refreshBadge = () => {
    const n = activeFilterCount(model);
    badge.textContent = n ? String(n) : '';
    badge.classList.toggle('hidden', n === 0);
  };
  filterBtn.textContent = 'Filters ';
  filterBtn.appendChild(badge);

  const panel = document.createElement('div');
  panel.className = 'filter-panel hidden';
  filterBtn.addEventListener('click', () => panel.classList.toggle('hidden'));

  // Colors
  if (facets.has('colors')) {
    const grp = document.createElement('div');
    grp.className = 'filter-group';
    grp.innerHTML = '<span class="filter-group-label">Colors</span>';
    // Declare clBtn before the loop so the loop's click handlers can reference it.
    const clBtn = document.createElement('button');
    clBtn.className = 'color-btn color-C' + (model.colorlessOnly ? ' active' : '');
    clBtn.textContent = 'C';
    clBtn.title = 'Colorless only';
    for (const letter of COLOR_LETTERS) {
      const b = document.createElement('button');
      b.className = 'color-btn color-' + letter +
        (model.colors.has(letter) ? ' active' : '');
      b.textContent = letter;
      b.dataset.color = letter;
      b.addEventListener('click', () => {
        if (model.colors.has(letter)) model.colors.delete(letter);
        else { model.colors.add(letter); model.colorlessOnly = false; }
        b.classList.toggle('active');
        clBtn.classList.toggle('active', model.colorlessOnly);
        refreshBadge(); onChange();
      });
      grp.appendChild(b);
    }
    clBtn.addEventListener('click', () => {
      model.colorlessOnly = !model.colorlessOnly;
      if (model.colorlessOnly) model.colors.clear();
      grp.querySelectorAll('.color-btn').forEach(x =>
        x.classList.toggle('active',
          x === clBtn ? model.colorlessOnly : model.colors.has(x.dataset.color)));
      refreshBadge(); onChange();
    });
    grp.appendChild(clBtn);
    panel.appendChild(grp);
  }

  // Types
  if (facets.has('types')) {
    const grp = document.createElement('div');
    grp.className = 'filter-group';
    grp.innerHTML = '<span class="filter-group-label">Types</span>';
    for (const ty of TYPE_OPTIONS) {
      const lab = document.createElement('label');
      lab.className = 'check-pill';
      const cb = document.createElement('input');
      cb.type = 'checkbox'; cb.checked = model.types.has(ty);
      cb.addEventListener('change', () => {
        if (cb.checked) model.types.add(ty); else model.types.delete(ty);
        refreshBadge(); onChange();
      });
      lab.appendChild(cb);
      lab.appendChild(document.createTextNode(ty));
      grp.appendChild(lab);
    }
    panel.appendChild(grp);
  }

  // CMC range
  if (facets.has('cmc')) {
    const grp = document.createElement('div');
    grp.className = 'filter-group';
    grp.innerHTML = '<span class="filter-group-label">Mana value</span>';
    const mk = (key, ph) => {
      const inp = document.createElement('input');
      inp.type = 'number'; inp.min = '0'; inp.className = 'cmc-input';
      inp.placeholder = ph;
      if (model[key] != null) inp.value = model[key];
      inp.addEventListener('input', () => {
        model[key] = inp.value === '' ? null : parseFloat(inp.value);
        refreshBadge(); onChange();
      });
      return inp;
    };
    grp.appendChild(mk('cmcMin', 'min'));
    grp.appendChild(document.createTextNode('–'));
    grp.appendChild(mk('cmcMax', 'max'));
    panel.appendChild(grp);
  }

  // Tags
  if (facets.has('tags') && tagOptions.length) {
    const grp = document.createElement('div');
    grp.className = 'filter-group';
    grp.innerHTML = '<span class="filter-group-label">Tags</span>';
    for (const tag of tagOptions) {
      const lab = document.createElement('label');
      lab.className = 'check-pill';
      const cb = document.createElement('input');
      cb.type = 'checkbox'; cb.checked = model.tags.has(tag);
      cb.addEventListener('change', () => {
        if (cb.checked) model.tags.add(tag); else model.tags.delete(tag);
        refreshBadge(); onChange();
      });
      lab.appendChild(cb);
      lab.appendChild(document.createTextNode(tag));
      grp.appendChild(lab);
    }
    panel.appendChild(grp);
  }

  // Clear
  const clearBtn = document.createElement('button');
  clearBtn.className = 'clear-filters-btn action-btn';
  clearBtn.textContent = 'Clear';
  clearBtn.addEventListener('click', () => {
    // Text search is owned by the page's search box, so Clear preserves it.
    const keepText = model.text;
    Object.assign(model, makeFilterModel({ sort: model.sort, dir: model.dir, text: keepText }));
    buildFilterControls(container, config);  // re-render to reset control state
    onChange();
  });
  panel.appendChild(clearBtn);

  refreshBadge();
  container.appendChild(sortSel);
  container.appendChild(dirBtn);
  container.appendChild(filterBtn);
  container.appendChild(panel);
}

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

function reloadCards() {
  state.offset = 0;
  state.hasMore = true;
  state.cards = [];
  clearGrid();
  loadCards();
}

function onSearchInput(e) {
  const q = e.target.value;
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    if (q === state.query) return;
    state.query = q;
    reloadCards();
  }, 300);
}

async function loadCards() {
  if (state.loading || !state.hasMore) return;
  state.loading = true;

  if (state.offset === 0) setGridMessage('Loading…');

  try {
    const extra = state.filter ? modelToParams(state.filter) : {};
    const cards = await API.searchCards(state.query, LIMIT, state.offset, extra);
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

function openModal(card, deckContext = null) {
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
      <div id="modal-tags-section"></div>
      <div id="modal-decks-section"></div>
    </div>`;

  contentEl.querySelector('[data-action="inc"]').addEventListener('click', () => increment(card.id));
  contentEl.querySelector('[data-action="dec"]').addEventListener('click', () => decrement(card.id));

  document.getElementById('modal-overlay').classList.remove('hidden');
  document.body.style.overflow = 'hidden';
  document.getElementById('modal-close').focus();

  // Fetch and render art options asynchronously
  loadPrintings(card);
  loadModalTags(card, deckContext);
  loadModalDecks(card);
}

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

function buildTagEditor({ label, chipClass, tags, suggestions, onAdd, onRemove }) {
  const wrapper = document.createElement('div');
  wrapper.className = 'modal-tags-section';

  let currentTags = [...tags];

  function render() {
    wrapper.innerHTML = `
      <div class="modal-tags-label">${esc(label)}</div>
      <div class="modal-tags-chips">
        ${currentTags.map(t => `
          <span class="modal-tag-chip ${chipClass}" data-tag="${esc(t)}">
            ${esc(t)}
            <button class="modal-tag-remove" title="Remove">×</button>
          </span>`).join('')}
        <input class="modal-tag-input" list="tag-suggestions-${chipClass}"
          placeholder="Add tag…" autocomplete="off">
        <datalist id="tag-suggestions-${chipClass}">
          ${suggestions.map(s => `<option value="${esc(s)}">`).join('')}
        </datalist>
      </div>`;

    wrapper.querySelectorAll('.modal-tag-remove').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const tag = btn.closest('[data-tag]').dataset.tag;
        currentTags = await onRemove(tag);
        render();
      });
    });

    const input = wrapper.querySelector('.modal-tag-input');
    input.addEventListener('keydown', async (e) => {
      if (e.key === 'Enter' || e.key === ',') {
        e.preventDefault();
        const val = input.value.trim().toLowerCase().replace(/,/g, '');
        if (!val || currentTags.includes(val)) return;
        currentTags = await onAdd(val);
        render();
      }
    });
  }

  render();
  return wrapper;
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

async function loadModalTags(card, deckContext) {
  const section = document.getElementById('modal-tags-section');
  if (!section) return;

  const inCollection = qty(card.id) > 0;

  const [collTags, deckTags] = await Promise.all([
    inCollection ? API.getCollectionCardTags(card.id) : Promise.resolve([]),
    deckContext ? API.getDeckCardTags(deckContext.deckId, card.id) : Promise.resolve([]),
  ]);

  const [allCollTags, allDeckTags] = await Promise.all([
    inCollection ? API.listCollectionTags() : Promise.resolve([]),
    deckContext ? API.listDeckTags(deckContext.deckId) : Promise.resolve([]),
  ]);

  if (!section.isConnected) return;
  section.innerHTML = '';

  let trackedCollTags = [...collTags];
  if (inCollection) {
    section.appendChild(buildTagEditor({
      label: 'Collection tags',
      chipClass: 'collection-tag',
      tags: collTags,
      suggestions: allCollTags,
      onAdd: async (tag) => {
        const updated = await API.addCollectionTag(card.id, tag);
        trackedCollTags = updated;
        syncCollectionTagsOnCard(card.id, updated);
        return updated;
      },
      onRemove: async (tag) => {
        await API.removeCollectionTag(card.id, tag);
        trackedCollTags = trackedCollTags.filter(t => t !== tag);
        syncCollectionTagsOnCard(card.id, trackedCollTags);
        return trackedCollTags;
      },
    }));
  }

  if (deckContext) {
    let trackedDeckTags = [...deckTags];
    section.appendChild(buildTagEditor({
      label: 'Deck tags',
      chipClass: 'deck-tag',
      tags: deckTags,
      suggestions: allDeckTags,
      onAdd: async (tag) => {
        const updated = await API.addDeckTag(deckContext.deckId, card.id, tag);
        trackedDeckTags = updated;
        syncDeckTagsOnCard(card.id, updated);
        return updated;
      },
      onRemove: async (tag) => {
        await API.removeDeckTag(deckContext.deckId, card.id, tag);
        trackedDeckTags = trackedDeckTags.filter(t => t !== tag);
        syncDeckTagsOnCard(card.id, trackedDeckTags);
        return trackedDeckTags;
      },
    }));
  }
}

function syncCollectionTagsOnCard(cardId, tags) {
  const card = collectionState.cards.find(c => c.id === cardId);
  if (card) { card.collection_tags = tags; renderCollectionGrid(); }
}

function syncDeckTagsOnCard(cardId, tags) {
  const card = deckState.deckCards.find(c => c.id === cardId);
  if (card) { card.deck_tags = tags; renderDeckContent(); }
}

function closeModal() {
  document.getElementById('modal-overlay').classList.add('hidden');
  document.body.style.overflow = '';
  state.modalCard = null;
  if (document.getElementById('view-decks').classList.contains('active')) {
    if (addPaletteOpen()) document.getElementById('deck-search').focus();
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
    // Don't fire card shortcuts while typing in a field (e.g. the deck/tag inputs).
    if (e.target && e.target.matches && e.target.matches('input, textarea, select')) return;
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
    const openPanel = document.querySelector('.filter-panel:not(.hidden)');
    if (openPanel) { openPanel.classList.add('hidden'); return; }
    if (!document.getElementById('import-overlay').classList.contains('hidden')) {
      closeImportModal(); return;
    }
    if (!document.getElementById('col-import-overlay').classList.contains('hidden')) {
      closeColImportModal(); return;
    }
    if (addPaletteOpen()) { closeAddPalette(); return; }
    searchInput.blur();
    deckSearch.blur();
    return;
  }

  // '/' opens the add palette (decks) or focuses the relevant search input
  if (e.key === '/') {
    const typingInField = !!document.activeElement &&
      document.activeElement.matches('input, textarea');
    if (decksActive && !typingInField) {
      e.preventDefault(); openAddPalette(); return;
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

// Close any open filter panel when clicking outside a filter bar.
document.addEventListener('click', e => {
  if (!e.target.closest('.filter-bar')) {
    document.querySelectorAll('.filter-panel:not(.hidden)').forEach(p => p.classList.add('hidden'));
  }
});

// ── Nav ───────────────────────────────────────────────────────────────────────

document.querySelectorAll('.nav-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.view').forEach(v   => v.classList.remove('active'));
    document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(`view-${btn.dataset.view}`).classList.add('active');
    btn.classList.add('active');
    if (btn.dataset.view !== 'decks')      closeAddPalette();
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

  state.filter = makeFilterModel();
  buildFilterControls(document.getElementById('browser-filter-controls'), {
    model: state.filter,
    facets: new Set(['colors', 'types', 'cmc']),
    sortOptions: SORT_OPTIONS_BASE,
    onChange: reloadCards,
  });

  loadCards();
  loadDeckList();
  document.getElementById('search-input').focus();
}

init();

// ── Collection view ───────────────────────────────────────────────────────────

const collectionState = {
  cards: [],   // full card objects with .quantity
  query: '',
  groupBy: 'none',   // 'none' | 'collection-tag'
  filter: makeFilterModel(),
};

const collectionGroupCollapsed = new Set();
const deckGroupCollapsed = new Set();

/**
 * Groups an array of card objects by a tag field.
 * Returns [{label, cards}, ...] sorted alphabetically, "Untagged" last.
 * A card with N tags appears in N groups.
 */
function groupCards(cards, tagField) {
  const map = new Map();
  for (const card of cards) {
    const tags = card[tagField] || [];
    if (!tags.length) {
      if (!map.has('Untagged')) map.set('Untagged', []);
      map.get('Untagged').push(card);
    } else {
      for (const tag of tags) {
        if (!map.has(tag)) map.set(tag, []);
        map.get(tag).push(card);
      }
    }
  }
  const groups = [];
  for (const [label, groupCards] of map) {
    if (label !== 'Untagged') groups.push({ label, cards: groupCards });
  }
  groups.sort((a, b) => a.label.localeCompare(b.label));
  if (map.has('Untagged')) groups.push({ label: 'Untagged', cards: map.get('Untagged') });
  return groups;
}

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

async function loadCollectionView() {
  try {
    const rows = await API.getCollection();
    // Keep state.collection map in sync too
    state.collection = {};
    for (const r of rows) state.collection[r.id] = r.quantity;
    collectionState.cards = rows;
    const tagOptions = await API.listCollectionTags();
    buildFilterControls(document.getElementById('collection-filter-controls'), {
      model: collectionState.filter,
      facets: new Set(['colors', 'types', 'cmc', 'tags']),
      sortOptions: [...SORT_OPTIONS_BASE, SORT_OPTION_QUANTITY],
      tagOptions,
      onChange: renderCollectionGrid,
    });
    renderCollectionGrid();
  } catch (e) {
    console.error(e);
  }
}

function renderCollectionGrid() {
  const grid = document.getElementById('collection-grid');
  const countEl = document.getElementById('collection-count');
  grid.innerHTML = '';

  collectionState.filter.text = collectionState.query;   // name/text box feeds the model
  const filtered = applyFilters(collectionState.cards, collectionState.filter);
  const cmp = sortComparator(collectionState.filter);

  const totalCopies = filtered.reduce((s, c) => s + c.quantity, 0);
  countEl.textContent = filtered.length
    ? `${totalCopies} card${totalCopies !== 1 ? 's' : ''} · ${filtered.length} unique`
    : '';

  if (!filtered.length) {
    const msg = document.createElement('div');
    msg.className = 'grid-message';
    msg.textContent = (collectionState.query || activeFilterCount(collectionState.filter))
      ? 'No matches.' : 'No cards in collection yet.';
    grid.appendChild(msg);
    return;
  }

  if (collectionState.groupBy !== 'none') {
    const groups = groupCards(filtered, 'collection_tags');
    for (const g of groups) g.cards.sort(cmp);
    renderGroupedGrid(grid, groups, buildCardTile, collectionGroupCollapsed);
  } else {
    const frag = document.createDocumentFragment();
    for (const card of [...filtered].sort(cmp)) frag.appendChild(buildCardTile(card));
    grid.appendChild(frag);
  }
}

document.getElementById('collection-search').addEventListener('input', e => {
  collectionState.query = e.target.value;
  renderCollectionGrid();
});

document.getElementById('collection-search').addEventListener('keydown', e => {
  if (e.key === 'Escape') { e.target.blur(); collectionState.query = ''; renderCollectionGrid(); }
});

document.getElementById('deck-content-search').addEventListener('input', e => {
  deckState.query = e.target.value;
  renderDeckContent();
});

document.getElementById('deck-content-search').addEventListener('keydown', e => {
  if (e.key === 'Escape') { e.target.blur(); deckState.query = ''; renderDeckContent(); }
});

document.getElementById('collection-group-by').addEventListener('change', e => {
  collectionState.groupBy = e.target.value;
  collectionGroupCollapsed.clear();
  renderCollectionGrid();
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
  groupBy:        'none',   // 'none' | 'collection-tag' | 'deck-tag'
  filter:         makeFilterModel(),
  query:          '',       // deck content search box (name/text/type)
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
  closeAddPalette();                      // never carry the palette between decks
  deckState.currentDeckId = id;
  deckState.deckCards = [];
  deckState.filter = makeFilterModel();   // reset filters between decks
  deckState.query = '';                   // reset content search between decks
  const searchInput = document.getElementById('deck-content-search');
  if (searchInput) searchInput.value = '';
  renderDeckList();
  try {
    deckState.deckCards = await API.getDeckCards(id);
    const [collTags, deckTags] = await Promise.all([
      API.listCollectionTags(),
      API.listDeckTags(id),
    ]);
    buildFilterControls(document.getElementById('deck-filter-controls'), {
      model: deckState.filter,
      facets: new Set(['colors', 'types', 'cmc', 'tags']),
      sortOptions: [...SORT_OPTIONS_BASE, SORT_OPTION_QUANTITY],
      tagOptions: [...new Set([...collTags, ...deckTags])].sort(),
      onChange: renderDeckContent,
    });
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
  deckState.filter.text = deckState.query;   // content search box feeds the model
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
  div.addEventListener('click', () => openModal(card, { deckId: deckState.currentDeckId }));

  return div;
}

function renderDeckText() {
  const el = document.getElementById('deck-text-view');
  el.innerHTML = '';
  const filtered = applyFilters(deckState.deckCards, deckState.filter);
  if (!filtered.length) {
    el.innerHTML = deckState.deckCards.length
      ? '<div class="deck-empty-msg">No cards match — adjust filters.</div>'
      : '<div class="deck-empty-msg">No cards yet — search to add some.</div>';
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
      row.addEventListener('click', () => openModal(card, { deckId: deckState.currentDeckId }));
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

// ── parseAddQuery ──
/**
 * Splits a leading "xN " quantity off an add-card query.
 *   "x20 swamp" -> { quantity: 20, name: "swamp" }
 *   "swamp"     -> { quantity: 1,  name: "swamp" }
 *   "20 swamp"  -> { quantity: 1,  name: "20 swamp" }  (bare number is not a quantity)
 * The leading "x" is required so card names that start with digits
 * ("1996 World Champion") are searched literally.
 */
function parseAddQuery(raw) {
  const q = (raw || '').trim();
  const m = /^x(\d+)\s+(.+)$/i.exec(q);
  if (!m) return { quantity: 1, name: q };
  const qty = Math.min(Math.max(parseInt(m[1], 10) || 1, 1), 999);
  return { quantity: qty, name: m[2].trim() };
}
// ── end parseAddQuery ──

// ── Add-card palette ──────────────────────────────────────────────────────────

function addPaletteOpen() {
  const p = document.getElementById('deck-add-palette');
  return !!p && !p.classList.contains('hidden');
}

function openAddPalette() {
  if (!deckState.currentDeckId) return;
  const palette = document.getElementById('deck-add-palette');
  const input   = document.getElementById('deck-search');
  if (!palette || !input) return;
  palette.classList.remove('hidden');
  input.focus();
  input.select();
}

function closeAddPalette() {
  const palette = document.getElementById('deck-add-palette');
  const input   = document.getElementById('deck-search');
  const note    = document.getElementById('deck-add-note');
  if (palette) palette.classList.add('hidden');
  if (input) { input.blur(); input.value = ''; }
  if (note) { note.textContent = ''; note.classList.remove('error'); }
  deckState.searchResults  = [];
  deckState.searchFocusIdx = -1;
  renderDeckSearchResults();
  updateQtyBadge();
}

let addNoteTimer = null;

function showAddNote(msg, isError) {
  const note = document.getElementById('deck-add-note');
  if (!note) return;
  note.textContent = msg;
  note.classList.toggle('error', !!isError);
  if (addNoteTimer) clearTimeout(addNoteTimer);
  addNoteTimer = setTimeout(() => {
    note.textContent = '';
    note.classList.remove('error');
  }, 2000);
}

function updateQtyBadge() {
  const badge = document.getElementById('deck-add-qty');
  const input = document.getElementById('deck-search');
  if (!badge || !input) return;
  const { quantity } = parseAddQuery(input.value);
  badge.textContent = quantity > 1 ? `×${quantity}` : '';
  badge.classList.toggle('hidden', quantity <= 1);
}

/** Clear the query after an add, leaving the palette open for the next card. */
function resetPaletteQuery() {
  const input = document.getElementById('deck-search');
  if (input) { input.value = ''; input.focus(); }
  deckState.searchResults  = [];
  deckState.searchFocusIdx = -1;
  renderDeckSearchResults();
  updateQtyBadge();
}

// ── Deck search ───────────────────────────────────────────────────────────────

let deckSearchTimer = null;

function onDeckSearchInput(e) {
  const { name } = parseAddQuery(e.target.value);
  updateQtyBadge();
  clearTimeout(deckSearchTimer);
  deckSearchTimer = setTimeout(() => runDeckSearch(name), 250);
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
  if (!el) return;
  el.innerHTML = '';
  for (let i = 0; i < deckState.searchResults.length; i++) {
    const card = deckState.searchResults[i];
    const inDeck = deckState.deckCards.find(c => c.id === card.id);
    const row = document.createElement('div');
    row.className = 'deck-search-row';
    row.dataset.idx = i;
    row.innerHTML = `
      <span class="dsearch-name">${esc(card.name)}</span>
      <span class="dsearch-type">${esc(card.type_line || '')}</span>
      <span class="dsearch-indeck">${inDeck ? `in deck: ${inDeck.quantity}` : ''}</span>
      <button class="dsearch-add-btn" title="Add to deck">+</button>`;
    row.querySelector('.dsearch-add-btn').addEventListener('click', e => { e.stopPropagation(); addFromPalette(card); });
    row.addEventListener('click', () => addFromPalette(card));
    el.appendChild(row);
  }
}

/**
 * Adds `quantity` copies of a card to the current deck in one request.
 * The backend upserts additively, so this works for new and existing cards
 * alike. Returns true on success.
 */
async function addCardToDeck(cardId, cardData, quantity = 1) {
  if (!deckState.currentDeckId) return false;
  if (deckState.addingCards.has(cardId)) return false;
  deckState.addingCards.add(cardId);
  try {
    const res = await API.addCardToDeck(deckState.currentDeckId, cardId, quantity);
    const existing = deckState.deckCards.find(c => c.id === cardId);
    if (existing) {
      existing.quantity = res.quantity;
    } else {
      deckState.deckCards.push({ ...cardData, quantity: res.quantity, is_commander: false, collection_tags: [], deck_tags: [] });
    }
    syncDeckCount();
    renderDeckContent();
    return true;
  } catch (e) {
    console.error(e);
    return false;
  } finally {
    deckState.addingCards.delete(cardId);
  }
}

/** Add from the palette: reads the quantity prefix, notes the result, resets. */
async function addFromPalette(card) {
  const input = document.getElementById('deck-search');
  const { quantity } = parseAddQuery(input ? input.value : '');
  const ok = await addCardToDeck(card.id, card, quantity);
  if (!ok) { showAddNote(`Could not add ${card.name}`, true); return; }
  showAddNote(quantity > 1 ? `Added ${quantity}× ${card.name}` : `Added ${card.name}`);
  resetPaletteQuery();
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

document.getElementById('deck-group-by').addEventListener('change', e => {
  deckState.groupBy = e.target.value;
  deckGroupCollapsed.clear();
  renderDeckContent();
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
    if (card) addFromPalette(card);
  } else if (e.key === 'Escape') {
    e.preventDefault();
    closeAddPalette();
  }
});

document.getElementById('deck-add-btn').addEventListener('click', openAddPalette);

document.addEventListener('mousedown', e => {
  if (!addPaletteOpen()) return;
  const palette = document.getElementById('deck-add-palette');
  const btn     = document.getElementById('deck-add-btn');
  if (palette && palette.contains(e.target)) return;
  if (btn && btn.contains(e.target)) return;   // let the opener's own click through
  closeAddPalette();
});
