---
id: 020
title: Deck-page indicator for cards fully allocated to other built decks
priority: medium
status: in-progress
branch: item/20-deck-page-indicator-for-cards-fully-allocated-to-other-built-decks
created: 2026-08-26
---

## Problem

Once decks can be marked "built" (item 018), a card you own can end up
entirely committed to *other* built decks, leaving none actually free for
the deck you're currently working on. There's currently no way to see
this while browsing a deck: neither on cards already added to the current
deck (which might not really be backed by a free copy once other decks
claim the collection), nor while searching to add new cards (where you
might add a copy of something with none actually available).

**Depends on item 018** (the `decks.built` column) — implement 018 first.

Show a distinct visual indicator, separate from the existing green
"owned" checkmark, in both places:
1. Cards already in the currently-open deck (grid tile and text row).
2. The "Add cards" search results for the currently-open deck.

A card qualifies when: it's owned (`quantity > 0`) AND every owned copy is
allocated to built decks *other than the one currently open* (Considering
cards don't count as allocated, matching item 018/019's rule). Note this
condition is deck-relative — always excluding the deck currently being
viewed — so the same card can show the indicator while viewing Deck B but
not while viewing Deck A, if Deck A itself holds the copies.

## Approach

Rather than modifying `/api/cards` (the shared search endpoint used by the
main card browser too, with multiple FTS/LIKE query branches — not worth
the risk for a deck-specific concern), add one new lightweight endpoint
and fetch it once per deck, the same way `state.collection` is fetched
once and used as a plain client-side lookup everywhere.

- `app.py`: add
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
  Returns a JSON object mapping `card_id -> quantity allocated to other
  built decks`. A card with no such allocation simply isn't a key in the
  map (frontend treats a missing key as 0).
- `static/app.js`:
  - `API`: add `getDeckAllocations(deckId)` following the existing fetch
    wrapper pattern (`GET /api/decks/${deckId}/allocations`, parse JSON).
  - `deckState`: add `allocatedElsewhere: {}` to the state object
    (~line 1841 area, alongside `filter`/`groupBy`).
  - `selectDeck(id)` (~line 1943): fetch and store
    `deckState.allocatedElsewhere = await API.getDeckAllocations(id);`
    alongside the existing `deckState.deckCards = await
    API.getDeckCards(id);` fetch, so it's refreshed on every deck switch.
  - Add a helper:
    ```js
    function isLockedElsewhere(cardId) {
      const owned = qty(cardId);
      if (owned <= 0) return false;
      return owned <= (deckState.allocatedElsewhere[cardId] || 0);
    }
    ```
  - `buildDeckCardTile` (~line 2130) and `buildDeckTextRow` (~line 2179):
    when `isLockedElsewhere(card.id)` is true, add a distinct badge/class
    — e.g. a small warning glyph or an `.locked-elsewhere` class on the
    tile/row, styled distinctly from the existing green `OWNED_BADGE_HTML`
    checkmark (different color, e.g. an amber/warning tone — don't reuse
    the owned-green so the two meanings stay visually distinguishable).
    This is additive to the existing owned badge, not a replacement — a
    card can be both "owned" (green check) and "locked elsewhere" (new
    marker) at the same time.
  - `renderDeckSearchResults` (~line 2531): for each result row, when
    `isLockedElsewhere(card.id)` is true, append a small warning
    indicator to the row (e.g. a `<span class="dsearch-locked"
    title="All owned copies are in other built decks">⚠</span>`) — this
    row currently has no owned-quantity display at all, so this is a new
    addition, not a variant of an existing badge.
- `static/style.css`: add the new badge/class styling (amber/warning tone,
  distinct from the existing `--accent` green used for owned indicators —
  check if the stylesheet already defines a warning color variable; if
  not, a plain fixed color like `#c98a2b`-ish amber is fine, matching the
  existing accent hue family used elsewhere for warnings if any exist).

## Acceptance criteria

- [ ] Opening a deck fetches its allocation map once (visible via one
      `GET /api/decks/{id}/allocations` request per deck switch, not per
      card).
- [ ] A card already in the open deck, owned but with all copies
      allocated to *other* built decks, shows the new indicator.
- [ ] The same card does NOT show the indicator while viewing a deck that
      itself holds the allocating copies (deck-relative exclusion works).
- [ ] The "Add cards" search results show the same indicator for a
      matching card, distinct from (and combinable with) the existing "in
      deck: N" text already shown there.
- [ ] A card allocated only to Considering sections elsewhere is not
      treated as locked (matches item 018/019's Considering-doesn't-count
      rule).
- [ ] A card allocated to non-built decks doesn't trigger the indicator.
- [ ] The indicator is visually distinct from the existing green owned
      checkmark/qty-label styling, and both can appear together.
