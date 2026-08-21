# Backlog

Refined, implementation-ready work items for the async backlog workflow.
Full protocol: `docs/superpowers/specs/2026-08-20-async-backlog-workflow-design.md`.

Each item is one `NNN-slug.md` file (NNN = zero-padded id). Frontmatter:

- `id` — unique integer, matches the NNN filename prefix
- `title` — short name
- `priority` — `high` | `medium` | `low`
- `status` — `queued` | `in-progress` | `changes-requested` | `in-review` | `accepted`
- `branch` — set automatically once claimed (`item/<id>-<slug>`); leave empty when creating an item
- `created` — ISO date

Body: problem statement, approach, acceptance criteria — refined until a
fresh session with zero context could implement it without asking anyone
anything. Copy `TEMPLATE.md` to start a new item, using the next unused id.
