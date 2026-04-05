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
  const res = await API.increment(cardId);
  state.collection[cardId] = res.quantity;
  refreshQtyInDOM(cardId);
}

async function decrement(cardId) {
  const res = await API.decrement(cardId);
  state.collection[cardId] = res.quantity;
  refreshQtyInDOM(cardId);
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
    case ' ': { e.preventDefault(); const c = focusedCard(); if (c) openModal(c); break; }
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

  function renderStrip() {
    strip.innerHTML = '';
    const visible = printings.slice(0, showing);
    visible.forEach((p, i) => {
      const thumb = document.createElement('div');
      thumb.className = 'art-thumb' + (p.image_uri === card.image_uri ? ' active' : '');
      thumb.title = `${p.set_name || ''} — ${p.artist || ''}`.trim().replace(/^—\s*/, '');
      thumb.innerHTML = `<img src="${API.imageUrl(p.image_uri)}" loading="lazy" alt="${esc(p.set_name || '')}">`;
      thumb.addEventListener('click', () => {
        document.getElementById('modal-main-img').src = API.imageUrl(p.image_uri);
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

  renderStrip();
}

function closeModal() {
  document.getElementById('modal-overlay').classList.add('hidden');
  document.body.style.overflow = '';
  state.modalCard = null;
  const tiles = document.querySelectorAll('#card-grid .card-tile');
  if (state.focusedIdx >= 0 && tiles[state.focusedIdx]) {
    tiles[state.focusedIdx].focus({ preventScroll: true });
  }
}

// ── Global keyboard handler ───────────────────────────────────────────────────

document.addEventListener('keydown', e => {
  const searchInput = document.getElementById('search-input');
  const modalOpen   = !document.getElementById('modal-overlay').classList.contains('hidden');

  if (modalOpen) {
    if (e.key === 'Escape') closeModal();
    if ((e.key === '+' || e.key === '=') && state.modalCard) {
      e.preventDefault(); increment(state.modalCard.id);
    }
    if (e.key === '-' && state.modalCard) {
      e.preventDefault(); decrement(state.modalCard.id);
    }
    return;
  }

  if (e.key === 'Escape') {
    searchInput.blur();
    return;
  }

  // '/' focuses search
  if (e.key === '/' && document.activeElement !== searchInput) {
    e.preventDefault();
    searchInput.focus();
    return;
  }

  // Space opens focused card (defaults to first card if none focused)
  if (e.key === ' ' && state.cards.length > 0) {
    e.preventDefault();
    if (state.focusedIdx < 0) setFocused(0);
    const c = focusedCard();
    if (c) { openModal(c); return; }
  }

  if (document.activeElement !== searchInput) {
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

function computeGrid() {
  const grid = document.getElementById('card-grid');
  if (!grid) return;

  const W = grid.clientWidth  - GRID_PAD_X;
  const H = grid.clientHeight - GRID_PAD_Y;
  if (W <= 0 || H <= 0) return;

  // How many columns fit at minimum card width?
  const N = Math.max(1, Math.floor((W + GRID_GAP) / (MIN_CARD_W + GRID_GAP)));

  // Actual card width when N columns share the full width
  const cardW = (W - GRID_GAP * (N - 1)) / N;

  // Row height = image portion (preserving card aspect ratio) + fixed info strip
  const cardH = Math.floor(cardW * CARD_ASPECT + INFO_H);

  grid.style.gridTemplateColumns = `repeat(${N}, 1fr)`;
  grid.style.gridAutoRows        = `${cardH}px`;
}

// ── Init ──────────────────────────────────────────────────────────────────────

async function init() {
  await loadCollection();
  setupInfiniteScroll();

  // Size the grid before first paint, then keep it in sync with window resizes
  computeGrid();
  new ResizeObserver(computeGrid).observe(document.getElementById('card-grid'));

  loadCards();
  document.getElementById('search-input').focus();
}

init();
