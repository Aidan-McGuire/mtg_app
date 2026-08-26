---
id: 016
title: Collection/deck import never guesses on an ambiguous name match
priority: high
status: in-progress
branch: item/16-collection-deck-import-never-guesses-on-an-ambiguous-name-match
created: 2026-08-26
---

## Problem

`lookup_card_id(cur, name)` in `app.py` (used by both `import_collection`
and `import_deck`) has 3 match tiers, each ending in `... LIMIT 1`:

1. Exact name match (`WHERE name = ? COLLATE NOCASE`)
2. MDFC slash-normalized match (`"A / B"` → `"A // B"`)
3. Front-face-only match (`WHERE name LIKE ? COLLATE NOCASE`, i.e.
   `"<name> //%"`)

If a tier's query matches **more than one** row, `LIMIT 1` silently keeps
whichever row SQLite happens to return first (no `ORDER BY`, so this is
effectively arbitrary and not guaranteed stable) instead of surfacing the
ambiguity. This previously misattributed collection quantity: a decklist
entry "Clearwater Pathway" (front-face-only, tier 3) could match either
the real `Clearwater Pathway // Murkwater Pathway` land or an unrelated
`Clearwater Pathway // Clearwater Pathway` `art_series` print that had
been imported as its own row before `art_series` printings were excluded
from the importer (see `notes.md` Issues #4). That specific collision is
gone now that `art_series` is filtered at import time, but the underlying
"silently pick one of several matches" behavior in `lookup_card_id` is
still live and can misattribute quantity for any other future name
collision across tiers 1–3.

## Approach

Change `lookup_card_id` in `app.py` so that whenever a tier's query would
match more than one row, it treats that name as **unresolved** rather than
guessing — exactly like a genuinely unmatched name already is:

- For each of the 3 tiers, drop `LIMIT 1` and instead fetch up to 2 rows
  (`LIMIT 2` is enough to detect ">1 match" cheaply without scanning
  everything) with `cur.execute(...); rows = cur.fetchall()`.
- If `len(rows) == 1`: return that row's `id` (current behavior for the
  unambiguous case).
- If `len(rows) > 1`: do **not** fall through to the next tier and do
  **not** return a row — return `None` immediately, the same value already
  returned when nothing matches at all.
- If `len(rows) == 0`: fall through to the next tier (current behavior).

No caller changes are needed: `import_collection` and `import_deck` both
already do `if card_id: ... else: not_found.append(name);
_record_import_failure(cur, ...)` — since ambiguous now returns `None`
exactly like "not found" does, ambiguous matches automatically flow into
the existing `not_found` list and the existing Import History page
(`import_failures` table) without any new code path. This keeps the fix
scoped to `lookup_card_id` alone.

Explicitly out of scope: distinguishing "ambiguous" from "genuinely not
found" in the `import_failures` table (e.g. a `reason` column) — both
surface identically today as an unresolved name for the human to look up
manually, which is sufficient to stop the silent misattribution. A richer
distinction can be a future item if it turns out to matter in practice.

## Acceptance criteria

- [x] `lookup_card_id` never returns a row's id when its matching tier
      found more than one candidate row.
- [x] A name that matches exactly one row at any tier still resolves
      exactly as it does today (no behavior change for the common case).
- [x] A name whose tier-1 (or tier-2, or tier-3) query matches 2+ rows
      results in that decklist entry appearing in `not_found` /
      `import_failures`, not a silently-chosen match.
- [x] Existing single-match import behavior (collection import, deck
      import) is unchanged for every currently-passing case — verify
      against the current test suite for import behavior, if one exists,
      plus a manual test importing a decklist with a name known to match
      more than one card (construct one via a scratch DB if no natural
      collision currently exists in the live dataset).
