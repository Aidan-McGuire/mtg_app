# Deck Action Button Mnemonics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bake the Considering/Remove keyboard-shortcut hints into the buttons' own permanent labels so hovering/focusing a deck tile or list row no longer reflows sibling buttons.

**Architecture:** Presentation-only change in `static/app.js` (two builder functions: `buildDeckCardTile`, `buildDeckTextRow`) and `static/style.css`. No backend, no state/behavior changes — click handlers and keyboard shortcut logic are untouched.

**Tech Stack:** Vanilla JS, CSS. No JS test framework in this repo; verify via code reading + `node --check` syntax validation + manual reasoning about acceptance criteria. Also run `python3 -m pytest` for backend regression safety (unrelated to this change but required by process).

**Spec:** `docs/superpowers/backlog/025-deck-action-button-mnemonics.md`

## Global Constraints

- Considering button: content becomes "`<u>C</u>onsidering`" (was bare `?`), no adjacent kbd hint.
- Considering button CSS: switch from fixed 18×18 icon box to auto-width pill with small horizontal padding, font-size ~10-11px, keep existing hover/active color rules.
- Remove button: glyph becomes `⌫` (was `×`), no adjacent kbd hint. No size change — stays fixed 18×18 icon box.
- Delete `.deck-kbd-hint` CSS rules entirely (`static/style.css:958-960`).
- Remove all four `<kbd class="deck-kbd-hint">` usages in `static/app.js` (2 in `buildDeckCardTile`, 2 in `buildDeckTextRow`).
- Commander button (♛) untouched.
- Click handlers, keyboard shortcuts (`c`, `Backspace`), and all other behavior must work exactly as before — this is presentation-only.

---

### Task 1: Update `buildDeckCardTile` and `buildDeckTextRow` markup in `static/app.js`

**Files:**
- Modify: `static/app.js:2204-2222` (`buildDeckCardTile`)
- Modify: `static/app.js:2252-2265` (`buildDeckTextRow`)

**Interfaces:**
- No new functions. `consideringBtn`/`removeDeckCard`/`toggleConsidering` event wiring (lines ~2229-2234, ~2266-2268) stays as-is; only the HTML string literals producing `consideringBtnHtml` and the remove/kbd markup change.

- [ ] **Step 1: Edit `buildDeckCardTile`'s `consideringBtnHtml` (around line 2204-2208)**

Replace:
```js
  const consideringBtnHtml = card.is_commander ? '' : `
    <button class="deck-considering-btn${card.is_considering ? ' active' : ''}"
            title="${card.is_considering ? 'Move back to deck' : 'Move to Considering'}">?</button>
    <kbd class="deck-kbd-hint" title="Toggle Considering">c</kbd>`;
```
with:
```js
  const consideringBtnHtml = card.is_commander ? '' : `
    <button class="deck-considering-btn${card.is_considering ? ' active' : ''}"
            title="${card.is_considering ? 'Move back to deck' : 'Move to Considering'}"><u>C</u>onsidering</button>`;
```

- [ ] **Step 2: Edit `buildDeckCardTile`'s remove button block (around line 2220-2222)**

Replace:
```js
          <button class="deck-cmd-btn${card.is_commander ? ' active' : ''}" title="Toggle commander">♛</button>
          <kbd class="deck-kbd-hint" title="Remove focused card">⌫</kbd>
          <button class="deck-remove-btn" title="Remove">×</button>
```
with:
```js
          <button class="deck-cmd-btn${card.is_commander ? ' active' : ''}" title="Toggle commander">♛</button>
          <button class="deck-remove-btn" title="Remove">⌫</button>
```

- [ ] **Step 3: Edit `buildDeckTextRow`'s `consideringBtnHtml` (around line 2252-2256)**

Same replacement pattern as Step 1, applied to the copy inside `buildDeckTextRow`.

- [ ] **Step 4: Edit `buildDeckTextRow`'s remove button block (around line 2263-2265)**

Replace:
```js
    ${consideringBtnHtml}
    <kbd class="deck-kbd-hint" title="Remove focused card">⌫</kbd>
    <button class="deck-remove-btn" title="Remove">×</button>`;
```
with:
```js
    ${consideringBtnHtml}
    <button class="deck-remove-btn" title="Remove">⌫</button>`;
```

- [ ] **Step 5: Verify no `deck-kbd-hint` references remain in app.js**

Run: `grep -n "deck-kbd-hint" static/app.js`
Expected: no output.

- [ ] **Step 6: Syntax-check the file**

Run: `/opt/homebrew/bin/node --check static/app.js` (fall back to `node --check static/app.js` if the homebrew path doesn't exist, but avoid `/usr/local`'s node)
Expected: exits 0, no output.

- [ ] **Step 7: Commit**

```bash
git add static/app.js
git commit -m "feat(deck): bake keyboard-shortcut hints into button labels"
```

---

### Task 2: Update `static/style.css` — Considering button pill styling and hint rule removal

**Files:**
- Modify: `static/style.css:874-889` (`.deck-considering-btn` rules)
- Modify: `static/style.css:958-960` (delete `.deck-kbd-hint` rules)

- [ ] **Step 1: Change `.deck-considering-btn` from fixed icon box to auto-width pill**

Replace:
```css
.deck-considering-btn {
  background: none;
  border: 1px solid var(--border);
  border-radius: 3px;
  color: var(--muted);
  font-size: 10px;
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: color 0.1s, border-color 0.1s;
}
```
with:
```css
.deck-considering-btn {
  background: none;
  border: 1px solid var(--border);
  border-radius: 3px;
  color: var(--muted);
  font-size: 10px;
  height: 18px;
  padding: 0 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  white-space: nowrap;
  transition: color 0.1s, border-color 0.1s;
}
```
(Leave the adjacent `:hover`/`.active` rules at lines 888-889 untouched — they don't reference width/height.)

- [ ] **Step 2: Delete the now-unused `.deck-kbd-hint` rules**

Delete lines 955-960 (the comment block and the two rules):
```css
/* Backspace-removal hint: hidden by default, shown only on the focused
   grid tile / list row (setDeckFocus toggles `.focused` on hover/arrow-nav
   without rebuilding the tile, so visibility here is purely CSS-driven). */
.deck-kbd-hint { display: none; }
.deck-card-tile.focused .deck-kbd-hint,
.deck-text-row.focused .deck-kbd-hint { display: inline-block; }
```

- [ ] **Step 3: Verify no `deck-kbd-hint` references remain anywhere**

Run: `grep -rn "deck-kbd-hint" static/`
Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add static/style.css
git commit -m "style(deck): considering btn becomes auto-width pill, drop kbd-hint CSS"
```

---

### Task 3: Final verification

- [ ] **Step 1: Confirm zero remaining references repo-wide**

Run: `grep -rn "deck-kbd-hint" .` (excluding `.git/`)
Expected: no output (backlog item markdown mentioning the class name in prose is fine to keep, but check there's no stray leftover in code).

- [ ] **Step 2: Run backend test suite**

Run: `python3 -m pytest`
Expected: all tests pass (this change touches no backend code, so this is a regression check).

- [ ] **Step 3: Manual code-reading check against acceptance criteria**

Re-read the diff for `buildDeckCardTile`/`buildDeckTextRow` and confirm:
- Considering button text is `<u>C</u>onsidering` in both functions, click handler (`toggleConsidering`) still wired via `.deck-considering-btn` selector.
- Remove button glyph is `⌫` in both functions, click handler (`removeDeckCard`) still wired via `.deck-remove-btn` selector.
- No `<kbd class="deck-kbd-hint">` anywhere.
- Nothing added/removed conditionally based on `.focused` state on these buttons — only the tile/row-level `.focused` class (pre-existing, untouched) still drives outline/background highlighting.

- [ ] **Step 4: Commit if any fixups were needed**

If Step 3 surfaced no issues, no commit needed here.
