#!/usr/bin/env bash
set -euo pipefail

# launchd runs with a minimal PATH, so claude/pytest/uvicorn would not be found.
export PATH="$HOME/.local/bin:$HOME/.pyenv/shims:/opt/homebrew/bin:/usr/local/bin:$PATH"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# All backlog status transitions are committed onto the item's own branch inside
# its worktree — never onto main, and never left uncommitted in the user's own
# working tree. An existing item/* branch therefore *is* the claim, so its
# presence means this is a resume.
EXISTING_BRANCH="$(git for-each-ref --format='%(refname:short)' 'refs/heads/item/*' | head -n1)"

if [ -n "$EXISTING_BRANCH" ]; then
  # --- Resume: the claim is already committed on this branch. ---
  BRANCH="$EXISTING_BRANCH"
  WORKTREE_DIR="$REPO_ROOT/.claude/worktrees/$(basename "$BRANCH")"

  if [ ! -d "$WORKTREE_DIR" ]; then
    git worktree add "$WORKTREE_DIR" "$BRANCH"
  fi

  cd "$WORKTREE_DIR"

  # item/<id>-<slug> -> <id>
  ITEM_ID="${BRANCH#item/}"
  ITEM_ID="${ITEM_ID%%-*}"

  if ! ITEM_PATH="$(python3 scripts/backlog_cli.py find-by-id "$ITEM_ID")"; then
    echo "$(date): branch $BRANCH exists but no backlog item with id $ITEM_ID found in the worktree, exiting"
    exit 1
  fi
  echo "$(date): resuming $BRANCH on $ITEM_PATH"
else
  # --- Fresh claim. `select` is read-only, so running it against the main
  # checkout's backlog dir does not touch the user's working tree. ---
  if ! ITEM_PATH="$(python3 scripts/backlog_cli.py select)"; then
    echo "$(date): no backlog item ready, exiting"
    exit 0
  fi

  BRANCH="$(python3 scripts/backlog_cli.py branch-name "$ITEM_PATH")"
  WORKTREE_DIR="$REPO_ROOT/.claude/worktrees/$(basename "$BRANCH")"

  # Branch explicitly from main — this checkout may be on some other branch.
  git worktree add "$WORKTREE_DIR" -b "$BRANCH" main

  cd "$WORKTREE_DIR"

  # Claim the worktree's own copy of the item, then commit that status change so
  # the claim is durable and this run is resumable.
  ITEM_PATH="$WORKTREE_DIR/docs/superpowers/backlog/$(basename "$ITEM_PATH")"
  ITEM_ID="${BRANCH#item/}"
  ITEM_ID="${ITEM_ID%%-*}"
  python3 scripts/backlog_cli.py claim "$ITEM_PATH" >/dev/null
  git add "$ITEM_PATH"
  git commit -m "chore: claim item $ITEM_ID"
  echo "$(date): claimed item $ITEM_ID on $BRANCH"
fi

PROMPT="$(sed "s#{ITEM_PATH}#$ITEM_PATH#g" "$REPO_ROOT/scripts/stage2_prompt.txt")"

claude -p "$PROMPT" \
  --permission-mode acceptEdits \
  --settings "$REPO_ROOT/.claude/stage2.settings.json" \
  --output-format text
