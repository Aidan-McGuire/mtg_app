#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if ! ITEM_PATH="$(python3 scripts/backlog_cli.py select)"; then
  echo "$(date): no backlog item ready, exiting"
  exit 0
fi

BRANCH="$(python3 scripts/backlog_cli.py claim "$ITEM_PATH")"
WORKTREE_DIR="$REPO_ROOT/.claude/worktrees/$(basename "$BRANCH")"

if [ ! -d "$WORKTREE_DIR" ]; then
  if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
    git worktree add "$WORKTREE_DIR" "$BRANCH"
  else
    git worktree add "$WORKTREE_DIR" -b "$BRANCH"
  fi
fi

PROMPT="$(sed "s#{ITEM_PATH}#$ITEM_PATH#g" "$REPO_ROOT/scripts/stage2_prompt.txt")"

cd "$WORKTREE_DIR"
claude -p "$PROMPT" \
  --permission-mode default \
  --settings "$REPO_ROOT/.claude/stage2.settings.json" \
  --output-format text
