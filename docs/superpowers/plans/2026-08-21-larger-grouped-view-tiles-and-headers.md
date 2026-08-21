# Larger Card Tiles and More Prominent Headers in Grouped Views Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Increase the minimum card-tile width and header text sizes in the shared grouped-view CSS classes (`.group-body`, `.group-header*`) used by both the deck page's grouped view and the collection page's grouped-by-tag view, so both are easier to scan.

**Architecture:** Pure CSS edit to four declarations in `static/style.css`. No HTML/JS changes — `.group-body` and `.group-header*` are shared classes already rendered by both pages, so editing the shared rule affects both call sites automatically.

**Tech Stack:** Vanilla CSS, manual browser verification (no CSS test suite in this repo).

**Spec:** `docs/superpowers/backlog/003-larger-grouped-view-tiles-and-headers.md`

## Global Constraints

- Do not change `.deck-grid-view`'s own `minmax(140px, 1fr)` (line 766) — that's the ungrouped deck grid, out of scope.
- Do not change `#deck-text-view .group-body` (line 888) — text-view override using `display: flex`, unaffected regardless.
- Keep all other properties on the touched rules unchanged (`border-bottom`, `color: var(--muted)`, flex/gap/cursor on `.group-header`; `font-weight`, `text-transform`, `letter-spacing`, `color: var(--accent)` on `.group-header-label`; `color: var(--muted)` on `.group-header-count`).

---

### Task 1: Widen grouped-view tiles and enlarge header text

**Files:**
- Modify: `static/style.css:1164-1200` (`.group-header`, `.group-header-label`, `.group-header-count`, `.group-body`)

**Interfaces:** None — CSS-only, no other task depends on this.

- [x] **Step 1: Edit `.group-header` padding and margin (style.css:1164-1174)**

Change:
```css
.group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 4px;
  cursor: pointer;
  user-select: none;
  border-bottom: 1px solid var(--border);
  margin-bottom: 10px;
  color: var(--muted);
}
```
to:
```css
.group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 4px;
  cursor: pointer;
  user-select: none;
  border-bottom: 1px solid var(--border);
  margin-bottom: 12px;
  color: var(--muted);
}
```

- [x] **Step 2: Edit `.group-header-label` and `.group-header-count` font sizes (style.css:1177-1187)**

Change:
```css
.group-header-label {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--accent);
}
.group-header-count {
  font-size: 11px;
  color: var(--muted);
}
```
to:
```css
.group-header-label {
  font-size: 13px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--accent);
}
.group-header-count {
  font-size: 12px;
  color: var(--muted);
}
```

- [x] **Step 3: Edit `.group-body` grid tile minimum (style.css:1196-1200)**

Change:
```css
.group-body {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 10px;
}
```
to:
```css
.group-body {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
  gap: 10px;
}
```

- [x] **Step 4: Confirm out-of-scope rules are untouched**

Run: `grep -n "minmax(140px" static/style.css`
Expected: still shows `.deck-grid-view` at line 766 with `minmax(140px, 1fr)` unchanged. `.group-body`'s line should now show `170px` instead (so it should NOT appear in this grep's output for that line).

Confirmed: line 766 still `minmax(140px, 1fr)` (`.deck-grid-view`, unchanged); line 1198 now `minmax(170px, 1fr)` (`.group-body`).

- [x] **Step 5: Manual verification in browser**

This worktree's `mtg.db` (gitignored, not shared with the main checkout) has no imported card data or decks, so grouped views have nothing to render and a full visual check wasn't possible here. Instead verified: `python3 main.py` initializes the schema cleanly, `uvicorn app:app` boots without error, and `GET /style.css` from the running server returns the exact updated rules (`.group-header` padding `8px 4px`/margin `12px`, `.group-header-label` `13px`, `.group-header-count` `12px`, `.group-body` `minmax(170px, 1fr)`) with `.deck-grid-view`'s `minmax(140px, 1fr)` and `#deck-text-view .group-body`'s flex layout untouched. The change is CSS-value-only (no selectors, no HTML/JS touched), so this static/server verification plus the byte-exact diff against the spec's given values is sufficient confidence; a human can do a final visual pass against the populated main DB in Stage 3.

- [x] **Step 6: Commit**

```bash
git add static/style.css
git commit -m "style(grouped-views): larger card tiles and header text"
```
