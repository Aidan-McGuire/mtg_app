# Deck tags on the Text view

## Problem

Notes.md, Deck Page item #3: "display deck tags for each card on list
view." Grid view already shows both collection and deck tag chips on each
card tile via the existing `tagChipsHtml(tags, type)` helper and
`.tag-chip.collection-tag`/`.tag-chip.deck-tag` styling. Text view
(`buildDeckTextRow`) shows nothing — just quantity, name, and mana cost.

Scope: deck tags only, matching the notes.md wording — collection tags on
Text view is a separate, not-yet-requested change.

## Behavior

Deck tag chips render inline, at the end of the same row (qty · name ·
mana · chips), reusing the exact same chip markup/styling Grid view and
the modal already use. A card with no deck tags renders exactly as it
does today — no layout change, no empty space reserved.

## Implementation

`static/app.js`, `buildDeckTextRow`: append `tagChipsHtml(card.deck_tags,
'deck-tag')` to the row's `innerHTML`, after the mana-cost span. No new
function — reuses the existing helper as-is.

`static/style.css`: `tagChipsHtml` wraps its chips in a `.tag-chips-row`
div (built for a below-content block context elsewhere — Grid tile,
modal). To make its chips act as direct inline flex items of
`.deck-text-row` instead, add a scoped override:

```css
.deck-text-row .tag-chips-row {
  display: contents;
}
```

`display: contents` removes the wrapper from the box model entirely —
only its `.tag-chip` children remain as layout participants, becoming
ordinary flex items of `.deck-text-row` (picking up its existing 8px
`gap`, same as the qty/name/mana spacing, rather than the wrapper's own
tighter 3px chip-to-chip gap).

Also add `flex-wrap: wrap` to `.deck-text-row` (currently `nowrap`) as a
safety net — with several deck tags on one card, the row wraps onto a
second line instead of overflowing horizontally off-screen. No visual
change for rows that already fit on one line.

## Out of Scope

- Collection tags on Text view.
- Any change to Grid view, the modal, or how tags are added/removed.
- Any change to `tagChipsHtml` itself.

## Testing

No JS test applies (pure markup/CSS). Manual verification in a running
browser: a deck with at least one card carrying multiple deck tags —
confirm the chips render inline after the mana cost, confirm an untagged
card's row is unchanged, and confirm a card with enough tags to not fit
on one line wraps cleanly rather than overflowing.
