---
id: 017
title: Harden Stage 2 backlog tooling (run_stage2.sh state machine)
priority: low
status: queued
branch:
created: 2026-08-26
---

## Problem

`scripts/run_stage2.sh` (the async backlog workflow's Stage 2 driver —
see `docs/superpowers/specs/2026-08-20-async-backlog-workflow-design.md`)
and its supporting `scripts/backlog_lib.py` shipped with several known,
low-severity gaps that were deliberately deferred at build time (recorded
in `notes.md` Issues #7). None have caused a real incident yet, but they
should be closed before the workflow runs unattended for longer stretches.
This item bundles all of them since they're small and touch the same
files:

1. **No automated test coverage for `run_stage2.sh` itself.** Only
   `backlog_lib.py`/`backlog_cli.py` are unit tested; the shell
   state-machine logic (resume-vs-fresh-claim-vs-rework detection) only
   has manual sandbox-run evidence from the original build session.
2. **Retitling an item during `changes-requested` silently abandons its
   branch's work.** `branch_name()` in `scripts/backlog_lib.py` derives
   the branch name from `item.id` + `slugify(item.title)`. If a human
   edits an item's `title` while it's `changes-requested` on `main`, the
   next `run_stage2.sh` firing computes a *different* branch name via
   `backlog_cli.py branch-name`, finds no existing ref for that new name
   (`git show-ref --verify --quiet "refs/heads/$BRANCH"` in
   `run_stage2.sh` fails), and falls into the fresh-branch path
   (`git worktree add "$WORKTREE_DIR" -b "$BRANCH" main`) — silently
   starting over from `main` instead of reusing the branch that already
   has the prior implementation work, with no error or warning.
3. **`git worktree add` aborts the whole run if a human has the item's
   branch checked out in a second worktree.** Both worktree-creation call
   sites in `run_stage2.sh` (the resume path and the fresh-claim/rework
   path) call `git worktree add "$WORKTREE_DIR" "$BRANCH"` unconditionally
   when `$WORKTREE_DIR` doesn't already exist locally. If a human is
   testing that branch in a separate worktree (normal Stage 3 flow) and
   this script's own worktree directory was removed in the meantime, `git
   worktree add` fails outright (git refuses to check out a branch that's
   already checked out elsewhere) and, under `set -euo pipefail`, the
   whole script aborts with a raw git error instead of a clear message.
4. **Minor robustness/logging nits**, all in `scripts/run_stage2.sh`:
   - The "was this item's branch already `in-progress`?" check inside the
     select loop's `if git show-ref --verify --quiet "refs/heads/$BRANCH";
     then ...` block is unreachable dead code: the resume scan that runs
     earlier in the script already checks *every* `item/*` branch for
     `status: in-progress` and, per its own logic, sets `RESUMING=1` and
     jumps straight to the resume path the moment it finds one — so by the
     time execution reaches the select loop, no `item/*` branch can be
     `in-progress`. The branch's stale comment ("Claimed but not finished
     (another item's branch won the resume scan order)") describes a
     scenario the resume scan's own logic already rules out.
   - The `git commit -m "$COMMIT_MSG"` for a claim/resume has no pathspec,
     so it commits *everything* currently staged in the worktree, not just
     the item file this script explicitly `git add`ed — even though the
     preceding `git diff --cached --quiet -- "$WORKTREE_ITEM_PATH"` check
     is correctly scoped to that one file.
   - `assert_in_worktree()` checks only that `git rev-parse
     --show-toplevel` matches `$WORKTREE_DIR`; it never checks that the
     worktree's current `HEAD` is actually on `$BRANCH`.
   - In the resume scan loop, when `branch_item_path` can't find a
     candidate branch's item file (`candidate_path` empty), the loop does
     `continue` with no log line — unlike every other skip case in that
     same loop and its select-loop counterpart, which all `echo` a
     `$(date): ...` line explaining the skip.

## Approach

All changes are in `scripts/run_stage2.sh` and `scripts/backlog_lib.py`
(item 2 only); no schema or protocol changes to the spec itself.

1. **Test coverage**: add a test suite for `run_stage2.sh`'s state
   machine (resume vs. fresh-claim vs. rework vs. skip-and-continue),
   using a throwaway git repo/worktree fixture per test case (create
   commits/branches with the needed `status:`/`title:` combinations, run
   the script or its relevant logic against it, assert the resulting
   branch/worktree/commit state). Match whatever test framework/style
   `backlog_lib.py`'s existing tests already use, if any exist — check for
   a `tests/` directory or `test_backlog_lib.py` before choosing a new
   one.
2. **Retitle-during-rework**: make branch identity independent of `title`.
   Simplest fix: when `changes-requested` and a branch already exists for
   this item's `id` (search `refs/heads/item/<id>-*` rather than the exact
   slugified name), reuse that branch regardless of what the current title
   slugifies to, rather than deriving the expected branch name purely from
   the live title. This likely means changing the select loop in
   `run_stage2.sh` (and/or `backlog_cli.py branch-name`) to look up an
   existing branch by numeric id prefix before falling back to
   `branch_name()`'s fresh-name computation.
3. **Worktree-add conflict**: before calling `git worktree add` in either
   call site, detect whether the target branch is already checked out
   elsewhere (`git worktree list --porcelain` shows a `branch` line per
   worktree; or catch `git worktree add`'s failure) and, if so, log a
   clear message identifying the branch/path and exit non-zero (Stage 2
   already treats "nothing to do" and hard failures distinctly via its
   exit codes — follow that convention) rather than surfacing a raw git
   error under `set -e`.
4. **Nits**:
   - Delete the dead `if [ "$branch_status" = "in-progress" ]; then : ...`
     branch and its stale comment from the select loop, since the resume
     scan already makes it unreachable — leave the `elif`/`else` logic
     otherwise intact.
   - Scope the claim/resume commit to the item file:
     `git commit -m "$COMMIT_MSG" -- "$WORKTREE_ITEM_PATH"`.
   - Extend `assert_in_worktree()` to also check
     `git rev-parse --abbrev-ref HEAD` equals the expected branch name,
     failing the same way it already does for a toplevel mismatch.
   - Add an `echo "$(date): ..."` line before the silent `continue` in the
     resume scan when `candidate_path` is empty, matching the phrasing
     style of the loop's existing `not resuming it` log line.

## Acceptance criteria

- [ ] A test suite exercises `run_stage2.sh`'s resume / fresh-claim /
      rework / skip-and-continue paths against constructed git fixtures
      and passes.
- [ ] Retitling a `changes-requested` item on `main` and then running
      Stage 2 reuses the item's existing branch (verified by its prior
      commits still being present on the resulting branch), not a fresh
      branch from `main`.
- [ ] Simulating a branch checked out in a second worktree and then
      running Stage 2 against that item exits with a clear logged error
      instead of an unhandled git failure, and does not corrupt any other
      worktree/branch state.
- [ ] The dead in-progress branch/comment is removed from the select loop
      with no behavior change to the surrounding logic.
- [ ] The claim/resume commit only ever contains the item file, verified
      by inspecting the resulting commit's changed files in a test run
      that has an extra unrelated staged file present.
- [ ] `assert_in_worktree` fails loudly if `HEAD` isn't the expected
      branch, verified by a test that checks out a different branch inside
      the worktree before calling it.
- [ ] The resume scan logs a line for every branch it skips, including the
      item-file-not-found case.
