#!/usr/bin/env bash
set -euo pipefail

# launchd runs with a minimal PATH, so claude/pytest/uvicorn would not be found.
export PATH="$HOME/.local/bin:$HOME/.pyenv/shims:/opt/homebrew/bin:/usr/local/bin:$PATH"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Every backlog status transition is committed onto the item's own branch inside
# its worktree — never onto main, and never left uncommitted in the user's own
# working tree. So an item's live status lives on its branch, while main's copy
# only ever reads queued or changes-requested (or is gone, deleted on accept).

# item/<id>-<slug> -> <id>
id_from_branch() {
  local rest="${1#item/}"
  printf '%s\n' "${rest%%-*}"
}

# A branch's backlog dir holds every item as of the branch point, so find the
# branch's own item by id rather than taking the first file listed.
branch_item_path() {
  local branch="$1" want_id="$2" candidate base num
  while IFS= read -r candidate; do
    base="$(basename "$candidate")"
    num="${base%%-*}"
    case "$num" in ''|*[!0-9]*) continue ;; esac
    if [ "$((10#$num))" -eq "$want_id" ]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done < <(git ls-tree -r --name-only "$branch" -- docs/superpowers/backlog/)
  return 0
}

status_on_branch() {
  git show "$1:$2" 2>/dev/null | sed -n 's/^status: *//p' | head -n1 || true
}

status_on_main() {
  sed -n 's/^status: *//p' "$1" | head -n1 || true
}

assert_in_worktree() {
  local top
  top="$(git rev-parse --show-toplevel)"
  if [ "$top" != "$WORKTREE_DIR" ]; then
    echo "$(date): expected git toplevel $WORKTREE_DIR but got $top, aborting" >&2
    exit 1
  fi
}

# Print the worktree path currently holding branch $1, or nothing if that
# branch isn't checked out in any worktree.
worktree_path_for_branch() {
  git worktree list --porcelain | awk -v want="refs/heads/$1" '
    /^worktree / { path = substr($0, 10) }
    $0 == "branch " want { print path; exit }
  '
}

main() {
  # --- Resume scan. An item/* branch is only a resume target while its own copy
  # of its item file still says in-progress. A finished item's branch sticks
  # around until the human accepts it, and re-entering it forever would starve
  # every other item. ---
  BRANCH=""
  ITEM_ID=""
  RESUMING=0
  while IFS= read -r candidate_branch; do
    [ -n "$candidate_branch" ] || continue
    candidate_id="$(id_from_branch "$candidate_branch")"
    candidate_path="$(branch_item_path "$candidate_branch" "$candidate_id")"
    [ -n "$candidate_path" ] || continue
    candidate_status="$(status_on_branch "$candidate_branch" "$candidate_path")"
    if [ "$candidate_status" = "in-progress" ]; then
      BRANCH="$candidate_branch"
      ITEM_ID="$candidate_id"
      RESUMING=1
      break
    fi
    echo "$(date): $candidate_branch is '${candidate_status:-unknown}', not in-progress — not resuming it"
  done < <(git for-each-ref --format='%(refname:short)' 'refs/heads/item/*')

  if [ "$RESUMING" = "1" ]; then
    # --- Resume: the claim is already committed on this branch. ---
    WORKTREE_DIR="$REPO_ROOT/.claude/worktrees/$(basename "$BRANCH")"

    if [ ! -d "$WORKTREE_DIR" ]; then
      existing_wt="$(worktree_path_for_branch "$BRANCH")"
      if [ -n "$existing_wt" ]; then
        echo "$(date): $BRANCH is already checked out at $existing_wt (outside this script's own worktree convention) — exiting rather than fighting over it" >&2
        exit 1
      fi
      git worktree add "$WORKTREE_DIR" "$BRANCH"
    fi

    cd "$WORKTREE_DIR"
    assert_in_worktree

    if ! ITEM_PATH="$(python3 scripts/backlog_cli.py find-by-id "$ITEM_ID")"; then
      echo "$(date): branch $BRANCH exists but no backlog item with id $ITEM_ID found in the worktree, exiting"
      exit 1
    fi
    echo "$(date): resuming $BRANCH on $ITEM_PATH"
  else
    # --- Nothing in-progress to resume: ask select() what to work next. This is
    # also how a changes-requested item (whose status a human updated on main
    # during Stage 3 review) gets found again. `select` is read-only, so running
    # it against the main checkout does not touch the user's working tree. ---
    EXCLUDES=()
    REWORK=0

    while true; do
      if ! ITEM_PATH="$(python3 scripts/backlog_cli.py select ${EXCLUDES[@]+"${EXCLUDES[@]}"})"; then
        echo "$(date): no backlog item ready, exiting"
        exit 0
      fi

      ITEM_ID="$(sed -n 's/^id: *0*//p' "$ITEM_PATH" | head -n1)"
      EXISTING_BRANCH="$(git for-each-ref --format='%(refname:short)' "refs/heads/item/${ITEM_ID}-*" | head -n1)"
      if [ -n "$EXISTING_BRANCH" ]; then
        # A branch already exists for this id — always reuse it by id, even if
        # the item's title (and so its freshly-slugified branch name) changed
        # since the branch was first cut. Prevents a retitle during
        # changes-requested from abandoning the branch's prior work by cutting
        # a same-id sibling branch instead of reusing the real one.
        BRANCH="$EXISTING_BRANCH"
      else
        BRANCH="$(python3 scripts/backlog_cli.py branch-name "$ITEM_PATH")"
      fi
      REWORK=0

      if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
        # This item was implemented before. Main's copy still reads queued or
        # changes-requested either way, so the branch is what says which.
        branch_path="$(branch_item_path "$BRANCH" "$ITEM_ID")"
        branch_status=""
        [ -n "$branch_path" ] && branch_status="$(status_on_branch "$BRANCH" "$branch_path")"

        if [ "$branch_status" = "in-progress" ]; then
          : # Claimed but not finished (another item's branch won the resume scan
            # order); carry on with the branch's own copy, claim will be a no-op.
        elif [ "$(status_on_main "$ITEM_PATH")" = "changes-requested" ]; then
          REWORK=1
        else
          # Finished work waiting on the human in Stage 3 — not ours to touch.
          # Skip it so the rest of the backlog still gets worked.
          echo "$(date): item $ITEM_ID is '${branch_status:-unknown}' on $BRANCH and awaiting review — skipping it"
          EXCLUDES=(${EXCLUDES[@]+"${EXCLUDES[@]}"} --exclude-id "$ITEM_ID")
          continue
        fi
      fi
      break
    done

    WORKTREE_DIR="$REPO_ROOT/.claude/worktrees/$(basename "$BRANCH")"

    if [ ! -d "$WORKTREE_DIR" ]; then
      if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
        existing_wt="$(worktree_path_for_branch "$BRANCH")"
        if [ -n "$existing_wt" ]; then
          echo "$(date): $BRANCH is already checked out at $existing_wt (outside this script's own worktree convention) — exiting rather than fighting over it" >&2
          exit 1
        fi
        git worktree add "$WORKTREE_DIR" "$BRANCH"
      else
        # Branch explicitly from main — this checkout may be on some other branch.
        git worktree add "$WORKTREE_DIR" -b "$BRANCH" main
      fi
    fi

    WORKTREE_ITEM_PATH="$WORKTREE_DIR/docs/superpowers/backlog/$(basename "$ITEM_PATH")"

    # The human writes review feedback (and status: changes-requested) into main's
    # copy of the item, so the branch's copy is stale. Sync it in before claiming:
    # claim only rewrites frontmatter and preserves the body verbatim, so the
    # copied-in "## Review feedback" section survives the claim.
    if [ "$REWORK" = "1" ]; then
      cp "$ITEM_PATH" "$WORKTREE_ITEM_PATH"
    fi

    cd "$WORKTREE_DIR"
    assert_in_worktree

    python3 scripts/backlog_cli.py claim "$WORKTREE_ITEM_PATH" >/dev/null
    git add "$WORKTREE_ITEM_PATH"
    if [ "$REWORK" = "1" ]; then
      COMMIT_MSG="chore: resume item $ITEM_ID after review feedback"
      LOG_MSG="$(date): resuming item $ITEM_ID on $BRANCH after review feedback"
    else
      COMMIT_MSG="chore: claim item $ITEM_ID"
      LOG_MSG="$(date): claimed item $ITEM_ID on $BRANCH"
    fi
    # Skip an empty commit (would abort the run under set -e) if the branch's copy
    # of the item is already exactly what the claim would write.
    if git diff --cached --quiet -- "$WORKTREE_ITEM_PATH"; then
      echo "$(date): item $ITEM_ID already up to date on $BRANCH, nothing to commit"
    else
      git commit -m "$COMMIT_MSG"
    fi
    echo "$LOG_MSG"
    ITEM_PATH="$WORKTREE_ITEM_PATH"
  fi

  PROMPT="$(sed "s#{ITEM_PATH}#$ITEM_PATH#g" "$REPO_ROOT/scripts/stage2_prompt.txt")"

  claude -p "$PROMPT" \
    --permission-mode acceptEdits \
    --settings "$REPO_ROOT/.claude/stage2.settings.json" \
    --output-format text
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
