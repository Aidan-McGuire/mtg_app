# Group header count next to name Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In every collapsible group header (Deck Grid, Deck Text, Collection page grouped grid), the card count sits immediately next to the group name instead of flush against the header's right edge.

**Architecture:** Pure CSS change to the one shared `.group-header-*` styling used by `renderGroupSection` across all three grouped views.

**Tech Stack:** Plain CSS, no build step.

## Global Constraints

- No backend or JS changes — this is CSS-only.
- Follow the approved design spec at `docs/superpowers/specs/2026-08-02-group-header-count-placement-design.md` exactly if anything is ambiguous.

---

### Task 1: Reposition the group header count

**Files:**
- Modify: `static/style.css:1169-1186` (`.group-header-label`, `.group-header-chevron`)

**Interfaces:** None — pure CSS, no JS/HTML changes, no new classes or selectors introduced.

- [ ] **Step 1: Move `flex: 1` off the label, onto the chevron as `margin-left: auto`**

In `static/style.css`, replace:

```css
.group-header-label {
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--accent);
  flex: 1;
}
.group-header-count {
  font-size: 11px;
  color: var(--muted);
}
.group-header-chevron {
  font-size: 10px;
  color: var(--muted);
  transition: transform 0.15s;
}
```

with:

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
.group-header-chevron {
  font-size: 10px;
  color: var(--muted);
  transition: transform 0.15s;
  margin-left: auto;
}
```

(Only `flex: 1;` is removed from `.group-header-label`, and `margin-left: auto;` is added to `.group-header-chevron`. `.group-header-count` and the `.group-header.collapsed .group-header-chevron` rule right after it are untouched.)

- [ ] **Step 2: Manual verification**

Run `uvicorn app:app --reload` from the repo root, open `http://localhost:8000`.

- Deck page, Grid view, Group-by "Card type" or a tag mode: confirm each group header shows the count immediately next to the name (small gap, not flush-right), and the chevron is still pinned to the header's right edge.
- Click a header to collapse/expand it: confirm the chevron still rotates and the collapse/expand behavior (including the collapsed-groups-sort-to-bottom behavior from the previous feature) is unaffected.
- Repeat in Text view and on the Collection page's grouped grid.

- [ ] **Step 3: Commit**

```bash
git add static/style.css
git commit -m "style: move group header count next to the group name"
```
