# Async Backlog Workflow

## Purpose

Split feature work into three decoupled stages so implementation can happen
unattended, in the background, across multiple days, without losing progress
or requiring the user to be present:

1. **Backlog development** — human + Claude refine raw ideas into
   implementation-ready specs.
2. **Implementation** — a daily scheduled task autonomously implements one
   ready item at a time, with no human input, resuming automatically across
   daily usage-limit interruptions.
3. **Test** — the user reviews, tests, accepts, or requests changes on
   finished work at their own pace.

## Stage 1 — Backlog Development

Raw ideas continue to live in `notes.md` under "Next features" / "Issues" as
today. An idea graduates into a **backlog item** only once it's refined
enough that a fresh session with zero conversation history could implement it
without asking anyone anything — no ambiguity, no open design questions.

Backlog items live in `docs/superpowers/backlog/`, one file per item, named
`NNN-slug.md` (NNN = zero-padded id, unique, monotonically increasing).

Frontmatter:

```yaml
---
id: 007
title: Commander gets own section on deck page
priority: medium   # high | medium | low
status: queued     # queued | in-progress | changes-requested | in-review | accepted
branch:            # set once claimed, e.g. item/007-deck-page-commander-section
created: 2026-08-20
---
```

Body: problem statement, approach, acceptance criteria — the same bar as a
normal `docs/superpowers/specs/*-design.md`, just scoped to one backlog item
and stored in this separate directory so Stage 2 tooling can scan it
mechanically by status/priority.

Once an item is created here, remove (or strike through) the corresponding
line in `notes.md` so the raw list only ever holds not-yet-refined ideas.

## Stage 2 — Implementation (autonomous)

A **daily scheduled task** (cron-style, via a scheduled cloud agent) fires
once a day and runs the protocol below. The same protocol can also be
triggered **on demand**, mid-conversation, when the user explicitly asks for
the next item to be picked up — most commonly right after accepting or
requesting changes on an item in Stage 3, so they can immediately get another
item moving the same day instead of waiting for tomorrow's scheduled firing.
An on-demand run isn't a fresh, context-less session the way a scheduled
firing is, but it still follows the identical protocol (select/claim/
plan/build/finish, one item) so behavior stays consistent regardless of what
triggered it.

Each firing follows this fixed protocol:

1. **Select.** Scan `docs/superpowers/backlog/*.md`.
   - If any item has `status: in-progress`, resume that one.
   - Otherwise, among `status: queued` and `status: changes-requested` items,
     pick the highest-priority one (changes-requested is treated as bumped to
     `high` regardless of its stored priority, so review feedback loops close
     quickly). Tiebreak by lowest `id`.
   - If nothing is queued, in-progress, or has changes requested: exit
     immediately. No commits, no branch, no notification.
2. **Claim.** Set the item's `status: in-progress`. Create (or re-enter, if
   resuming) an isolated `git worktree` on branch `item/<id>-<slug>`. Work
   only happens in this worktree — the user's own working tree/session is
   never touched, so this can safely run even if the user is mid-edit
   elsewhere.
3. **Plan.** If no implementation plan exists yet for this item, run the
   `writing-plans` skill against the item's spec to produce a plan under
   `docs/superpowers/plans/`. If resuming, read the existing plan and the
   branch's existing commits to determine what's left.
4. **Build.** Execute the plan (TDD, following this repo's existing
   conventions — test in the browser for UI changes, etc.), committing
   incrementally as each step completes. Incremental commits mean an
   interruption mid-run (including hitting a daily usage limit) leaves real,
   resumable progress rather than losing work.
5. **Finish.**
   - Full completion (plan done, tests passing): set `status: in-review`,
     push the branch to origin, send a push notification that the item is
     ready for review.
   - Partial/failed completion: leave `status: in-progress` with whatever is
     committed. The next daily firing resumes at step 1 automatically —
     hitting a usage limit requires no special handling, since the next
     scheduled firing naturally retries once the limit resets.
6. Exactly **one item per firing**, then stop — regardless of remaining
   budget for that run.

## Stage 3 — Test (human-paced)

Any item with `status: in-review` has a pushed branch waiting on the user, on
whatever cadence they choose to check in:

- **Test**: check out the branch/worktree, exercise the change in the running
  app.
- **Accept**: merge to `main`, push (existing push-after-merge habit), delete
  the branch/worktree, and delete the backlog item file (git history retains
  it; nothing further to track).
- **Request changes**: append a `## Review feedback` section to the item's
  file with what needs to change, set `status: changes-requested`. The next
  Stage 2 firing picks it up ahead of untouched queued work (see Stage 2,
  step 1) and continues on the *same* branch rather than restarting.

After either accepting or requesting changes, the user may ask, in the same
conversation, to pick up the next item right away rather than waiting for
tomorrow's scheduled firing. This runs the Stage 2 protocol on demand: if
changes were just requested, that same item (now bumped to high priority) is
the natural next pick; otherwise it's whatever the normal select step
resolves to.

## Out of scope

- No changes to how Stage 1 refinement itself happens (still ordinary
  brainstorming); this spec only defines the artifact it produces.
- No specific interval/backoff logic for usage-limit failures beyond "try
  again at the next scheduled daily firing" — the scheduler's normal cadence
  already provides this.
- No automated Stage 3 gate (e.g. auto-merge on green CI) — acceptance is
  always a manual, human decision.
