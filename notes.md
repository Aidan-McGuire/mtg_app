# Notes
## Feature backlog


All raw ideas refined into `docs/superpowers/backlog/`: commander-in-tag-groups
(001), wider preview panel (002), larger grouped-view tiles/headers (003),
deck category visibility checkboxes (004, amended to drop its land-default
logic in favor of 005), type-based hide-lands toggle (005), auto-refresh
card DB on server startup (006), collection type grouping (007), deck grid
view hide-preview + bump tile size (008), deck list view two-column grid +
column-aware nav (009), deck removal scoping + list-view/keyboard removal
parity (010), deck grid tile size reverted to match collection (011),
deck considering-toggle in list view + keyboard shortcut (012), owned
indicator on deck text view (013), deck filter for unowned cards (014),
grid-view categories span full width (015), collection/deck import never
guesses on ambiguous name match (016), Stage 2 tooling hardening (017),
deck built flag (018), collection filter hiding fully-allocated cards
(019), deck-page indicator for cards allocated to other built decks (020),
deck text view tri-state owned/locked status color (021), deck text view
font size bump (022), preferred printing selectable on detail modal (023),
commander toggle in deck list view (024), deck action buttons bake in their
keyboard shortcut hints (025), deck modal read-only owned count (026), Enter
opens the deck modal (027), deck content-search keyboard flow (028), apply
deck tag to focused card via keyboard (029), group headers keyboard-operable
(030), deck mana curve in list-view preview panel (031).



## Issues
1. Keyboard navigation needs work on all pages
  - works decently well on 'Cards' page, needs refinement
  - Ultimately need to be able to navigate the app without using a mouse at all
2. `colors` field is empty for double-faced/transform cards because the importer only reads the top-level Scryfall `colors` field, not `card_faces[*].colors` — affects the Exact Colors filter (and would affect anything else that reads `colors`) for ~895 cards. Fix: update `importer.py` to fall back to the union of face colors, then re-run `python importer.py` to backfill.
3. (REFINED → `docs/superpowers/backlog/016-fix-ambiguous-import-match.md`) Collection import can attach quantity to the wrong `oracle_id` when multiple Scryfall entries share a printed name — found via `Clearwater Pathway // Clearwater Pathway` (a non-playable Scryfall `art_series` print) holding 4 tracked copies separately from the real `Clearwater Pathway // Murkwater Pathway` land's 2. Manually merged this one instance (now 6 on the real land) on 2026-08-03, but the underlying name-matching bug in collection import wasn't fixed — other name collisions could still misattribute quantity.
4. (DONE) cdv (card detail view) not showing images — root cause: Scryfall's non-playable `art_series` layout (art-only crossover prints) was being imported like a real card, with placeholder `type_line`/`mana_cost` and, for some, no `image_uri` at all. Fixed by skipping `art_series` in `importer.py` and deleting the 2,194 already-imported art_series rows from the DB (`8026c5f`).
5. (DONE) Failed collection/deck import matches were silent — only shown once in a transient results panel, never persisted. This is how "Kalakscion, Hunger Tyrant" (imported before it existed in the card DB) and "Biophagus"/"Summon: Leviathan" (name typos) went unnoticed; found by re-running the same import against a scratch DB copy and manually added on 2026-08-04. Fixed by adding an `import_failures` table + an "Import History" page (outstanding/resolved failures, dismissible) — see `docs/superpowers/specs/2026-08-03-import-failure-log-design.md` and `docs/superpowers/plans/2026-08-03-import-failure-log.md`. Note: this does **not** fix issue #3 above — that's silent *misattribution* to the wrong `oracle_id` on a successful match, a different bug class from a failed match being silently dropped.
6. (DONE) `lookup_card_id` used exact string matching with no normalization, so two real cases from the new Import History page (#5) failed even though the card existed: a curly apostrophe (`’`, e.g. from pasting a list out of Notes/Word) never matched a name's straight ASCII apostrophe, and a bare `{123}` collector-number suffix (as opposed to the already-handled `(SET) 123` form) stayed glued onto the name. Fixed by normalizing smart quotes to straight ones and stripping a trailing `{N}` suffix in `lookup_card_id`/`_ENTRY_RE` (`c599039`).
7. (REFINED → `docs/superpowers/backlog/017-stage2-tooling-hardening.md`) Async backlog workflow tooling (`scripts/backlog_lib.py`, `scripts/backlog_cli.py`, `scripts/run_stage2.sh`, `.claude/stage2.settings.json`; see `docs/superpowers/specs/2026-08-20-async-backlog-workflow-design.md`) shipped with these known, low-severity gaps, deliberately deferred rather than fixed in the initial build:
   - `run_stage2.sh` has zero automated test coverage (only the Python CLI/library are unit tested) — the state-machine logic (resume-vs-fresh-claim-vs-rework detection) only has manual sandbox-run evidence from the build session.
   - Retitling a backlog item's `title` field while it's in `changes-requested` review silently starts a *new* branch from `main` on the next run (since the branch name is re-derived from the title) instead of reusing the branch with the prior work — abandoning that work without any error.
   - `git worktree add` aborts the whole run if a human has the item's branch checked out in a second worktree (e.g. while testing it in Stage 3) and the script's own worktree was removed in the meantime.
   - A few minor robustness/logging nits: an unreachable code path with a stale comment in `run_stage2.sh`'s selection loop; the `git commit` for a claim/resume isn't scoped to just the item file (would sweep in any other staged changes in that worktree); `assert_in_worktree` checks the worktree's location but not that its `HEAD` is actually on the expected branch; a branch whose item file can't be found during the resume scan is skipped silently (no log line) rather than logged like the equivalent case in the select loop.