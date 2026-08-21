# Widen Deck-Page Preview Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Widen the deck page's hover/focus card preview panel from 260px to 360px so card art and oracle text are easier to read at a glance.

**Architecture:** Single CSS rule change in `static/style.css`. The panel's image and text elements already scale/wrap to their container width, so no HTML/JS changes are needed.

**Tech Stack:** Vanilla CSS (no build step, no preprocessor).

**Spec:** `docs/superpowers/backlog/002-deck-preview-panel-wider.md`

## Global Constraints

- Change `.deck-preview-panel`'s `flex-basis` from `260px` to `360px` — no other property changes.
- No other rules in `static/style.css` should be modified.

---

### Task 1: Widen the preview panel

**Files:**
- Modify: `static/style.css:548-553` (`.deck-preview-panel` rule)

**Interfaces:**
- Consumes: none (pure CSS constant change).
- Produces: `.deck-preview-panel` panel width of 360px, consumed visually by the existing `#deck-preview-panel` DOM element populated by `renderDeckPreviewPanel` in `static/app.js` (no JS changes required — that function does not read or set panel width).

- [ ] **Step 1: Change the flex-basis**

In `static/style.css`, change:

```css
.deck-preview-panel {
  flex: 0 0 260px;
  overflow-y: auto;
  padding: 12px;
  border-right: 1px solid var(--border);
}
```

to:

```css
.deck-preview-panel {
  flex: 0 0 360px;
  overflow-y: auto;
  padding: 12px;
  border-right: 1px solid var(--border);
}
```

- [ ] **Step 2: Verify no other rule caps the image or panel width below 360px**

Run: `grep -n "deck-preview" static/style.css`

Expected: `.deck-preview-img img` still shows `width: 100%` with no `max-width` below 360px, and no other selector sets a competing width/flex-basis on `.deck-preview-panel`.

- [ ] **Step 3: Manual visual check (best effort, no test harness for CSS)**

Since this app has no CSS test suite, sanity-check by grepping for any test files that reference `deck-preview-panel` sizing:

Run: `grep -rln "deck-preview-panel" --include="*.py" --include="*.js" . | grep -i test`

Expected: no output (no automated tests assert on this pixel width). If any test does reference it, update the expected value there too.

- [ ] **Step 4: Commit**

```bash
git add static/style.css
git commit -m "style(deck): widen hover/focus preview panel to 360px"
```
