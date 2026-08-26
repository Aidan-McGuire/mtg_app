# Stage 2 Tooling Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the 5 known gaps in the Stage 2 async-backlog driver (`scripts/run_stage2.sh`): no test coverage for its state machine, a retitle-during-rework bug that abandons branch work, an unhandled `git worktree add` conflict, a dead code path, an unscoped commit, and a silent skip in the resume scan — without changing the documented protocol in `docs/superpowers/specs/2026-08-20-async-backlog-workflow-design.md`.

**Architecture:** `run_stage2.sh` is currently a flat procedural script (helper functions + top-level imperative code that runs the instant the file is executed). Task 1 makes it sourceable — wraps the procedural body in a `main()` function called only when the script is executed directly — with no behavior change, which is what makes both (a) direct unit tests of individual bash functions and (b) a real subprocess-driven integration-test harness possible. Every other task is additive on top of that: new integration tests exercise the full state machine against scratch git repos with a stubbed `claude` binary, and each bug/nit fix ships together with the test that proves it.

**Tech Stack:** Bash (`scripts/run_stage2.sh`), Python (`scripts/backlog_lib.py`, `scripts/backlog_cli.py`), pytest with `subprocess` for integration tests against real scratch git repos.

**Spec:** `docs/superpowers/backlog/017-stage2-tooling-hardening.md`

## Global Constraints

- No changes to the documented Stage 1/2/3 protocol in
  `docs/superpowers/specs/2026-08-20-async-backlog-workflow-design.md` —
  every fix here is an implementation-correctness fix, not a protocol change.
- No schema changes to backlog item frontmatter.
- Every test must run against a real scratch git repo under `tmp_path`, not
  a mock of git — this script's entire job is git plumbing, so a mocked git
  would test nothing real.
- macOS's `/tmp` and `/var` are symlinks to `/private/tmp` and `/private/var`
  — `git rev-parse --show-toplevel` resolves them, so `pytest`'s `tmp_path`
  must be `.resolve()`d before use, or `assert_in_worktree`'s toplevel check
  spuriously fails inside tests (this is a test-fixture concern only; the
  real deployment path, the user's actual repo, is never under `/tmp`).
- The real `claude` CLI lives at `$HOME/.local/bin/claude`, which is the
  *first* directory in `run_stage2.sh`'s own hardcoded `PATH` export — so a
  test's fake `claude` stub is only reachable if the test also points `HOME`
  at an empty scratch directory (not overriding `PATH` alone).

---

### Task 1: Make `run_stage2.sh` sourceable; build the integration-test harness

**Files:**
- Modify: `scripts/run_stage2.sh` (wrap the procedural body in `main()`, add an execute-only guard)
- Create: `tests/test_run_stage2.py` (fixture + first integration test)

**Interfaces:**
- Produces: `stage2_repo` pytest fixture (in `tests/test_run_stage2.py`), reused by Tasks 3-6. It exposes `.path` (scratch repo root, a resolved `Path`), `.claude_log` (`Path` to the fake claude invocation log), `.run()` (runs `scripts/run_stage2.sh` in the scratch repo, returns a `subprocess.CompletedProcess`), `.git(*args)` (runs `git` in the scratch repo, returns a `CompletedProcess`), `.write_item(id, title, priority=, status=, branch=, body=)` (writes a backlog item file, returns its `Path`).
- Produces: `main()` function in `run_stage2.sh`, callable interface for Task 7's direct function tests (source the script, then call e.g. `id_from_branch`, `assert_in_worktree` directly — sourcing no longer runs the whole state machine).

- [ ] **Step 1: Wrap the procedural body of `run_stage2.sh` in `main()`**

Open `scripts/run_stage2.sh`. Everything from the line `# --- Resume scan. An item/* branch is only a resume target...` through the end of the file (the final `claude -p "$PROMPT" \ ... --output-format text` block) is currently top-level procedural code. Indent every line of that block by 2 spaces and wrap it as the body of a new `main()` function, i.e. transform:

```bash
# --- Resume scan. An item/* branch is only a resume target while its own copy
# of its item file still says in-progress. A finished item's branch sticks
# around until the human accepts it, and re-entering it forever would starve
# every other item. ---
BRANCH=""
ITEM_ID=""
RESUMING=0
...
claude -p "$PROMPT" \
  --permission-mode acceptEdits \
  --settings "$REPO_ROOT/.claude/stage2.settings.json" \
  --output-format text
```

into:

```bash
main() {
  # --- Resume scan. An item/* branch is only a resume target while its own copy
  # of its item file still says in-progress. A finished item's branch sticks
  # around until the human accepts it, and re-entering it forever would starve
  # every other item. ---
  BRANCH=""
  ITEM_ID=""
  RESUMING=0
  ...
  claude -p "$PROMPT" \
    --permission-mode acceptEdits \
    --settings "$REPO_ROOT/.claude/stage2.settings.json" \
    --output-format text
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
```

Leave the shebang, `set -euo pipefail`, the `PATH` export, `REPO_ROOT`/`cd`, and all the helper function definitions (`id_from_branch`, `branch_item_path`, `status_on_branch`, `status_on_main`, `assert_in_worktree`) exactly where they are, at the top level — they must stay callable both when the script is executed directly and when it's sourced.

- [ ] **Step 2: Verify the script still runs identically when executed directly**

Run:
```bash
cd /tmp && rm -rf stage2_smoke && mkdir stage2_smoke && cd stage2_smoke
git init -q -b main && git config user.email t@t.com && git config user.name T
mkdir -p scripts docs/superpowers/backlog .claude
cp /Users/mcg/projects/mtg_app/.claude/worktrees/17-harden-stage-2-backlog-tooling-run-stage2-sh-state-machine/scripts/{run_stage2.sh,backlog_lib.py,backlog_cli.py,stage2_prompt.txt} scripts/
echo '{}' > .claude/stage2.settings.json
git add -A && git commit -q -m init
bash scripts/run_stage2.sh; echo "exit=$?"
```
Expected: `no backlog item ready, exiting` printed and `exit=0` (no items exist yet in this smoke repo — this just proves `main` still executes on direct invocation after the refactor). Clean up: `cd /tmp && rm -rf stage2_smoke`.

- [ ] **Step 3: Write the integration-test harness and first test**

Create `tests/test_run_stage2.py`:

```python
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
STAGE2_FILES = ("run_stage2.sh", "backlog_lib.py", "backlog_cli.py", "stage2_prompt.txt")


def _git(repo, *args, check=True):
    return subprocess.run(
        ["git", *args], cwd=repo, check=check, capture_output=True, text=True
    )


class Stage2Repo:
    def __init__(self, path, claude_log, env):
        self.path = path
        self.claude_log = claude_log
        self._env = env

    def run(self):
        return subprocess.run(
            ["bash", "scripts/run_stage2.sh"],
            cwd=self.path, env=self._env, capture_output=True, text=True,
        )

    def git(self, *args, check=True):
        return _git(self.path, *args, check=check)

    def write_item(self, id, title, priority="medium", status="queued", branch="", body="## Problem\n"):
        slug = title.lower().replace(" ", "-")
        backlog_dir = self.path / "docs" / "superpowers" / "backlog"
        backlog_dir.mkdir(parents=True, exist_ok=True)
        item_path = backlog_dir / f"{id:03d}-{slug}.md"
        item_path.write_text(
            f"---\nid: {id:03d}\ntitle: {title}\npriority: {priority}\n"
            f"status: {status}\nbranch: {branch}\ncreated: 2026-08-26\n---\n\n{body}"
        )
        return item_path


@pytest.fixture
def stage2_repo(tmp_path):
    """A real scratch git repo wired to run the real scripts/run_stage2.sh
    under test, with a stubbed `claude` binary standing in for the real CLI."""
    repo = (tmp_path / "repo").resolve()
    fakehome = (tmp_path / "fakehome").resolve()
    claude_log = (tmp_path / "claude.log").resolve()
    fakebin = (tmp_path / "fakebin").resolve()

    repo.mkdir()
    fakehome.mkdir()
    fakebin.mkdir()

    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")

    scripts_dir = repo / "scripts"
    scripts_dir.mkdir()
    for name in STAGE2_FILES:
        shutil.copy2(REPO_SCRIPTS / name, scripts_dir / name)

    claude_dir = repo / ".claude"
    claude_dir.mkdir()
    (claude_dir / "stage2.settings.json").write_text("{}")

    claude_stub = fakebin / "claude"
    claude_stub.write_text(
        "#!/usr/bin/env bash\n"
        f'echo "claude invoked: $*" >> "{claude_log}"\n'
        "exit 0\n"
    )
    claude_stub.chmod(0o755)

    (repo / "README.md").write_text("scratch repo for run_stage2.sh tests\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")

    env = {
        **os.environ,
        "HOME": str(fakehome),
        "PATH": f"{fakebin}:{os.environ['PATH']}",
    }
    return Stage2Repo(repo, claude_log, env)


def test_fresh_claim_of_highest_priority_queued_item(stage2_repo):
    stage2_repo.write_item(1, "Sample Item", priority="high", status="queued")
    stage2_repo.git("add", "-A")
    stage2_repo.git("commit", "-q", "-m", "add item 1")

    result = stage2_repo.run()

    assert result.returncode == 0, result.stderr
    assert stage2_repo.claude_log.exists()
    assert "claude invoked" in stage2_repo.claude_log.read_text()

    branches = stage2_repo.git("branch", "--list", "item/1-sample-item").stdout
    assert "item/1-sample-item" in branches

    on_branch = stage2_repo.git(
        "show", "item/1-sample-item:docs/superpowers/backlog/001-sample-item.md"
    ).stdout
    assert "status: in-progress" in on_branch

    on_main = (stage2_repo.path / "docs/superpowers/backlog/001-sample-item.md").read_text()
    assert "status: queued" in on_main
```

- [ ] **Step 4: Run it to verify it passes**

Run: `pytest tests/test_run_stage2.py -v`
Expected: PASS. If it fails on a path-mismatch (`expected git toplevel ... but got ...`), double check `tmp_path` subdirectories are `.resolve()`d — see the Global Constraints note on macOS `/tmp`/`/var` symlinks.

- [ ] **Step 5: Commit**

```bash
git add scripts/run_stage2.sh tests/test_run_stage2.py
git commit -m "test: add sourceable main() + integration harness for run_stage2.sh"
```

---

### Task 2: Unit tests for the pure helper functions

**Files:**
- Create: `tests/test_run_stage2_helpers.py`

**Interfaces:**
- Consumes: `run_stage2.sh`'s `id_from_branch` and `status_on_main` functions (already defined at top level, now sourceable per Task 1).

- [ ] **Step 1: Write the tests**

Create `tests/test_run_stage2_helpers.py`:

```python
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_stage2.sh"


def _source_and_call(func_call, cwd):
    """Source run_stage2.sh (defines functions only, per Task 1's guard) then
    run one function call, returning its captured stdout."""
    result = subprocess.run(
        ["bash", "-c", f'source "{SCRIPT}" && {func_call}'],
        cwd=cwd, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_id_from_branch_strips_prefix_and_slug(tmp_path):
    out = _source_and_call("id_from_branch 'item/16-collection-deck-import'", tmp_path)
    assert out == "16"


def test_id_from_branch_single_digit(tmp_path):
    out = _source_and_call("id_from_branch 'item/1-sample-item'", tmp_path)
    assert out == "1"


def test_status_on_main_reads_status_field(tmp_path):
    item = tmp_path / "item.md"
    item.write_text("---\nid: 001\ntitle: X\npriority: low\nstatus: changes-requested\nbranch: \ncreated: 2026-08-26\n---\n\nBody\n")
    out = _source_and_call(f"status_on_main '{item}'", tmp_path)
    assert out == "changes-requested"


def test_status_on_main_missing_file_prints_nothing(tmp_path):
    out = _source_and_call(f"status_on_main '{tmp_path}/does-not-exist.md'", tmp_path)
    assert out == ""
```

Note: `source "$SCRIPT"` runs the script's top-level code (shebang line is a no-op when sourced, `set -euo pipefail` applies to the sourcing shell, the `PATH` export runs harmlessly, and `REPO_ROOT`/`cd` resolve relative to `run_stage2.sh`'s own real location — i.e. the actual repo — which is fine since these two functions don't touch `$REPO_ROOT` or git state at all). `main` is never called because these invocations use `bash -c '...'` (not passing `run_stage2.sh` as `$0`), so `"${BASH_SOURCE[0]}" == "${0}"` is false.

- [ ] **Step 2: Run it to verify it passes**

Run: `pytest tests/test_run_stage2_helpers.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/test_run_stage2_helpers.py
git commit -m "test: unit-test run_stage2.sh's pure helper functions"
```

---

### Task 3: Integration tests for resume, skip-and-continue, and nothing-to-do

**Files:**
- Modify: `tests/test_run_stage2.py` (append tests, reuse `stage2_repo` fixture)

**Interfaces:**
- Consumes: `stage2_repo` fixture from Task 1.

- [ ] **Step 1: Write the tests**

Append to `tests/test_run_stage2.py`:

```python
def test_nothing_actionable_exits_zero_with_no_side_effects(stage2_repo):
    stage2_repo.write_item(1, "Accepted Already", priority="high", status="accepted")
    stage2_repo.git("add", "-A")
    stage2_repo.git("commit", "-q", "-m", "add accepted item")

    result = stage2_repo.run()

    assert result.returncode == 0, result.stderr
    assert not stage2_repo.claude_log.exists()
    assert stage2_repo.git("branch", "--list", "item/*").stdout.strip() == ""


def test_resumes_in_progress_branch_instead_of_selecting_a_new_item(stage2_repo):
    # First firing claims item 1.
    stage2_repo.write_item(1, "First Item", priority="high", status="queued")
    stage2_repo.git("add", "-A")
    stage2_repo.git("commit", "-q", "-m", "add item 1")
    first = stage2_repo.run()
    assert first.returncode == 0, first.stderr

    # A second, higher-priority item appears on main before the first firing's
    # work is finished — the resume scan must still win over item 2's select.
    stage2_repo.write_item(2, "Second Item", priority="high", status="queued")
    stage2_repo.git("add", "-A")
    stage2_repo.git("commit", "-q", "-m", "add item 2")

    stage2_repo.claude_log.unlink()
    second = stage2_repo.run()
    assert second.returncode == 0, second.stderr
    assert "claude invoked" in stage2_repo.claude_log.read_text()

    # Item 2 was never touched.
    assert stage2_repo.git("branch", "--list", "item/2-*").stdout.strip() == ""
    on_branch_1 = stage2_repo.git(
        "show", "item/1-first-item:docs/superpowers/backlog/001-first-item.md"
    ).stdout
    assert "status: in-progress" in on_branch_1


def test_finished_branch_awaiting_review_is_skipped_for_next_queued_item(stage2_repo):
    # Simulate a finished-and-pushed item 1 (in-review on its branch, main
    # still says queued) sitting untouched, and a queued item 2.
    stage2_repo.write_item(1, "Finished Item", priority="high", status="queued")
    stage2_repo.git("add", "-A")
    stage2_repo.git("commit", "-q", "-m", "add item 1")
    stage2_repo.run()  # claims item 1, branch item/1-finished-item now in-progress

    stage2_repo.git("checkout", "-q", "item/1-finished-item")
    item_on_branch = stage2_repo.path / "docs/superpowers/backlog/001-finished-item.md"
    item_on_branch.write_text(
        item_on_branch.read_text().replace("status: in-progress", "status: in-review")
    )
    stage2_repo.git("add", "-A")
    stage2_repo.git("commit", "-q", "-m", "mark in-review")
    stage2_repo.git("checkout", "-q", "main")

    stage2_repo.write_item(2, "Second Item", priority="medium", status="queued")
    stage2_repo.git("add", "-A")
    stage2_repo.git("commit", "-q", "-m", "add item 2")

    stage2_repo.claude_log.unlink()
    result = stage2_repo.run()

    assert result.returncode == 0, result.stderr
    assert "item 1 is 'in-review'" in result.stdout or "awaiting review" in result.stdout
    on_branch_2 = stage2_repo.git(
        "show", "item/2-second-item:docs/superpowers/backlog/002-second-item.md"
    ).stdout
    assert "status: in-progress" in on_branch_2
```

- [ ] **Step 2: Run them to verify they pass**

Run: `pytest tests/test_run_stage2.py -v`
Expected: PASS for all 4 tests now in the file (the Task 1 test plus these 3).

- [ ] **Step 3: Commit**

```bash
git add tests/test_run_stage2.py
git commit -m "test: cover resume, skip-awaiting-review, and nothing-actionable paths"
```

---

### Task 4: Fix retitle-during-changes-requested abandoning the branch

**Files:**
- Modify: `scripts/run_stage2.sh` (the non-resume/select branch of `main()`)
- Modify: `tests/test_run_stage2.py` (append the reproduction test)

**Interfaces:** none beyond what Task 1 established.

- [ ] **Step 1: Write a failing test reproducing the bug**

Append to `tests/test_run_stage2.py`:

```python
def test_retitle_during_changes_requested_reuses_existing_branch(stage2_repo):
    stage2_repo.write_item(1, "Old Title", priority="high", status="queued")
    stage2_repo.git("add", "-A")
    stage2_repo.git("commit", "-q", "-m", "add item 1")
    stage2_repo.run()  # claims item 1 -> branch item/1-old-title

    # Simulate finished work on the branch: an extra file marking "real" work,
    # then mark in-review (as a completed Stage 2 run would).
    stage2_repo.git("checkout", "-q", "item/1-old-title")
    (stage2_repo.path / "WORK_DONE.txt").write_text("implementation happened here\n")
    stage2_repo.git("add", "-A")
    stage2_repo.git("commit", "-q", "-m", "did the actual work")
    item_on_branch = stage2_repo.path / "docs/superpowers/backlog/001-old-title.md"
    item_on_branch.write_text(
        item_on_branch.read_text().replace("status: in-progress", "status: in-review")
    )
    stage2_repo.git("add", "-A")
    stage2_repo.git("commit", "-q", "-m", "mark in-review")
    stage2_repo.git("checkout", "-q", "main")

    # Human retitles the item and requests changes, both on main.
    item_on_main = stage2_repo.path / "docs/superpowers/backlog/001-old-title.md"
    item_on_main.write_text(
        item_on_main.read_text()
        .replace("title: Old Title", "title: New Title")
        .replace("status: queued", "status: changes-requested")
    )
    stage2_repo.git("add", "-A")
    stage2_repo.git("commit", "-q", "-m", "retitle + request changes")

    stage2_repo.claude_log.unlink()
    result = stage2_repo.run()

    assert result.returncode == 0, result.stderr
    # No sibling branch was created for the new title.
    assert stage2_repo.git("branch", "--list", "item/1-new-title").stdout.strip() == ""
    # The original branch was reused and still has the prior work on it.
    assert stage2_repo.git(
        "show", "item/1-old-title:WORK_DONE.txt"
    ).stdout == "implementation happened here\n"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/test_run_stage2.py::test_retitle_during_changes_requested_reuses_existing_branch -v`
Expected: FAIL — today's code recomputes the branch name from the new title (`item/1-new-title`), doesn't find that ref, and cuts a fresh branch from `main`, so `git branch --list item/1-new-title` is non-empty and/or the `git show item/1-old-title:WORK_DONE.txt` assertion errors (branch still exists but wasn't the one claimed this run — actually the old branch still exists untouched, but a *second* branch item/1-new-title now also exists, which the first assertion catches).

- [ ] **Step 3: Fix it**

In `scripts/run_stage2.sh`, inside `main()`'s non-resume branch, find:

```bash
    BRANCH="$(python3 scripts/backlog_cli.py branch-name "$ITEM_PATH")"
    ITEM_ID="$(id_from_branch "$BRANCH")"
    REWORK=0
```

Replace with:

```bash
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
```

- [ ] **Step 4: Run the test again to verify it passes**

Run: `pytest tests/test_run_stage2.py::test_retitle_during_changes_requested_reuses_existing_branch -v`
Expected: PASS.

- [ ] **Step 5: Run the full `test_run_stage2.py` file to check for regressions**

Run: `pytest tests/test_run_stage2.py -v`
Expected: PASS for all tests (the id-prefix lookup is a superset of the old exact-name lookup for the fresh-claim and resume cases already covered).

- [ ] **Step 6: Commit**

```bash
git add scripts/run_stage2.sh tests/test_run_stage2.py
git commit -m "fix: reuse existing branch by id when reworking a retitled item"
```

---

### Task 5: Fix unhandled `git worktree add` conflict

**Files:**
- Modify: `scripts/run_stage2.sh` (add a shared helper + guard both `git worktree add` call sites)
- Modify: `tests/test_run_stage2.py` (append the reproduction test)

**Interfaces:**
- Produces: `worktree_path_for_branch()` helper function in `run_stage2.sh`, alongside the other top-level helpers.

- [ ] **Step 1: Write a failing test reproducing the bug**

Append to `tests/test_run_stage2.py`:

```python
def test_worktree_already_checked_out_elsewhere_fails_clearly(stage2_repo):
    stage2_repo.write_item(1, "Old Title", priority="high", status="queued")
    stage2_repo.git("add", "-A")
    stage2_repo.git("commit", "-q", "-m", "add item 1")
    stage2_repo.run()  # creates branch item/1-old-title + its own worktree

    # Simulate: the script's own worktree was removed, and a human checked
    # the same branch out in a second worktree (e.g. to test it manually).
    stage2_repo.git(
        "worktree", "remove", "--force",
        str(stage2_repo.path / ".claude" / "worktrees" / "1-old-title"),
    )
    human_worktree = stage2_repo.path.parent / "human-testing"
    stage2_repo.git("worktree", "add", str(human_worktree), "item/1-old-title")

    stage2_repo.claude_log.unlink()
    result = stage2_repo.run()

    assert result.returncode != 0
    assert "item/1-old-title" in (result.stdout + result.stderr)
    assert str(human_worktree) in (result.stdout + result.stderr)
    # No stray worktree was created at the conventional path.
    assert not (stage2_repo.path / ".claude" / "worktrees" / "1-old-title").exists()
    # main is untouched.
    assert stage2_repo.git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() != "item/1-old-title"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pytest tests/test_run_stage2.py::test_worktree_already_checked_out_elsewhere_fails_clearly -v`
Expected: FAIL — today the raw `git worktree add` failure propagates as an uncaught non-zero exit under `set -e`, but the assertions on the specific log message text (`"item/1-old-title"` / the human worktree path both appearing together in a clear message) won't match git's raw stderr format, and depending on git's exact error wording this may fail one of the content assertions even though `returncode != 0` already holds. (If it happens to pass on `returncode` alone, the message-content assertions are still meaningful once Step 3 lands — keep them.)

- [ ] **Step 3: Fix it**

In `scripts/run_stage2.sh`, add a new helper next to `assert_in_worktree` (top level, before `main()`):

```bash
# Print the worktree path currently holding branch $1, or nothing if that
# branch isn't checked out in any worktree.
worktree_path_for_branch() {
  git worktree list --porcelain | awk -v want="refs/heads/$1" '
    /^worktree / { path = substr($0, 10) }
    $0 == "branch " want { print path; exit }
  '
}
```

Then in `main()`'s resume branch, find:

```bash
  if [ ! -d "$WORKTREE_DIR" ]; then
    git worktree add "$WORKTREE_DIR" "$BRANCH"
  fi
```

Replace with:

```bash
  if [ ! -d "$WORKTREE_DIR" ]; then
    existing_wt="$(worktree_path_for_branch "$BRANCH")"
    if [ -n "$existing_wt" ]; then
      echo "$(date): $BRANCH is already checked out at $existing_wt (outside this script's own worktree convention) — exiting rather than fighting over it" >&2
      exit 1
    fi
    git worktree add "$WORKTREE_DIR" "$BRANCH"
  fi
```

And in `main()`'s non-resume branch, find:

```bash
  if [ ! -d "$WORKTREE_DIR" ]; then
    if git show-ref --verify --quiet "refs/heads/$BRANCH"; then
      git worktree add "$WORKTREE_DIR" "$BRANCH"
    else
      # Branch explicitly from main — this checkout may be on some other branch.
      git worktree add "$WORKTREE_DIR" -b "$BRANCH" main
    fi
  fi
```

Replace with:

```bash
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
```

- [ ] **Step 4: Run the test again to verify it passes**

Run: `pytest tests/test_run_stage2.py::test_worktree_already_checked_out_elsewhere_fails_clearly -v`
Expected: PASS.

- [ ] **Step 5: Run the full `test_run_stage2.py` file to check for regressions**

Run: `pytest tests/test_run_stage2.py -v`
Expected: PASS for all tests.

- [ ] **Step 6: Commit**

```bash
git add scripts/run_stage2.sh tests/test_run_stage2.py
git commit -m "fix: exit clearly instead of crashing when a branch's worktree is claimed elsewhere"
```

---

### Task 6: Nits — dead code, unscoped commit, silent resume-scan skip

**Files:**
- Modify: `scripts/run_stage2.sh`
- Modify: `tests/test_run_stage2.py` (append 2 new tests; one existing assertion updated)

**Interfaces:** none beyond what Task 1 established.

- [ ] **Step 1: Remove the dead in-progress branch in the select loop**

In `scripts/run_stage2.sh`, inside `main()`'s non-resume branch, find:

```bash
      if [ "$branch_status" = "in-progress" ]; then
        : # Claimed but not finished (another item's branch won the resume scan
          # order); carry on with the branch's own copy, claim will be a no-op.
      elif [ "$(status_on_main "$ITEM_PATH")" = "changes-requested" ]; then
        REWORK=1
      else
```

Replace with:

```bash
      if [ "$(status_on_main "$ITEM_PATH")" = "changes-requested" ]; then
        REWORK=1
      else
```

This branch was unreachable: the resume scan earlier in `main()` already checks every `item/*` branch for `status: in-progress` and jumps straight to the resume path the moment it finds one, so by the time execution reaches this point, no `item/*` branch can be `in-progress`. `branch_status` is still computed just above this (needed for the `else` branch's log message) — leave that computation as-is.

- [ ] **Step 2: Scope the claim/resume commit to the item file**

In `scripts/run_stage2.sh`, inside `main()`, find:

```bash
  if git diff --cached --quiet -- "$WORKTREE_ITEM_PATH"; then
    echo "$(date): item $ITEM_ID already up to date on $BRANCH, nothing to commit"
  else
    git commit -m "$COMMIT_MSG"
  fi
```

Replace with:

```bash
  if git diff --cached --quiet -- "$WORKTREE_ITEM_PATH"; then
    echo "$(date): item $ITEM_ID already up to date on $BRANCH, nothing to commit"
  else
    git commit -m "$COMMIT_MSG" -- "$WORKTREE_ITEM_PATH"
  fi
```

- [ ] **Step 3: Log the resume scan's silent skip**

In `scripts/run_stage2.sh`, find:

```bash
while IFS= read -r candidate_branch; do
  [ -n "$candidate_branch" ] || continue
  candidate_id="$(id_from_branch "$candidate_branch")"
  candidate_path="$(branch_item_path "$candidate_branch" "$candidate_id")"
  [ -n "$candidate_path" ] || continue
  candidate_status="$(status_on_branch "$candidate_branch" "$candidate_path")"
```

Replace with:

```bash
while IFS= read -r candidate_branch; do
  [ -n "$candidate_branch" ] || continue
  candidate_id="$(id_from_branch "$candidate_branch")"
  candidate_path="$(branch_item_path "$candidate_branch" "$candidate_id")"
  if [ -z "$candidate_path" ]; then
    echo "$(date): $candidate_branch has no matching backlog item file for id $candidate_id — not resuming it"
    continue
  fi
  candidate_status="$(status_on_branch "$candidate_branch" "$candidate_path")"
```

(Note: this `while` loop reading from the resume-scan's `git for-each-ref` pipe currently sits at the top level of the file, *before* the `main()` wrapper added in Task 1 — Task 1's Step 1 already moved it inside `main()` along with the rest of the procedural body, so by the time this task runs, this loop is indented one level inside `main()`. Apply this edit wherever the loop now lives.)

- [ ] **Step 4: Write tests for the unscoped-commit fix and the resume-scan logging fix**

Append to `tests/test_run_stage2.py`:

```python
def test_claim_commit_does_not_sweep_in_unrelated_staged_changes(stage2_repo):
    # The commit this test targets only happens on the claim/rework path, not
    # the resume path (resuming an already in-progress branch doesn't commit
    # anything) — so drive this through a changes-requested rework, whose
    # worktree from the original claim is still sitting on disk untouched.
    stage2_repo.write_item(1, "Old Title", priority="high", status="queued")
    stage2_repo.git("add", "-A")
    stage2_repo.git("commit", "-q", "-m", "add item 1")
    stage2_repo.run()  # claims item 1 -> branch + worktree item/1-old-title

    stage2_repo.git("checkout", "-q", "item/1-old-title")
    item_on_branch = stage2_repo.path / "docs/superpowers/backlog/001-old-title.md"
    item_on_branch.write_text(
        item_on_branch.read_text().replace("status: in-progress", "status: in-review")
    )
    stage2_repo.git("add", "-A")
    stage2_repo.git("commit", "-q", "-m", "mark in-review")
    stage2_repo.git("checkout", "-q", "main")

    item_on_main = stage2_repo.path / "docs/superpowers/backlog/001-old-title.md"
    item_on_main.write_text(item_on_main.read_text().replace("status: queued", "status: changes-requested"))
    stage2_repo.git("add", "-A")
    stage2_repo.git("commit", "-q", "-m", "request changes")

    # Stray staged file left in the original worktree (still on disk — nothing
    # removes it between a claim and a later rework of the same item).
    worktree = stage2_repo.path / ".claude" / "worktrees" / "1-old-title"
    (worktree / "EXTRA.txt").write_text("unrelated staged content\n")
    subprocess.run(["git", "add", "EXTRA.txt"], cwd=worktree, check=True)

    stage2_repo.claude_log.unlink()
    result = stage2_repo.run()

    assert result.returncode == 0, result.stderr
    # EXTRA.txt is still staged, uncommitted — the rework commit didn't touch it.
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=worktree, capture_output=True, text=True, check=True
    ).stdout
    assert "EXTRA.txt" in status


def test_resume_scan_logs_branch_with_no_matching_item_file(stage2_repo):
    stage2_repo.write_item(1, "Real Item", priority="high", status="queued")
    stage2_repo.git("add", "-A")
    stage2_repo.git("commit", "-q", "-m", "add item 1")

    # An orphan item/* branch with no matching backlog item file at all.
    stage2_repo.git("checkout", "-q", "-b", "item/99-orphan")
    stage2_repo.git("checkout", "-q", "main")

    result = stage2_repo.run()

    assert result.returncode == 0, result.stderr
    assert "item/99-orphan" in result.stdout
    assert "not resuming it" in result.stdout
    # It still went on to claim the real item.
    on_branch = stage2_repo.git(
        "show", "item/1-real-item:docs/superpowers/backlog/001-real-item.md"
    ).stdout
    assert "status: in-progress" in on_branch
```

- [ ] **Step 5: Run the new tests to verify they pass**

Run: `pytest tests/test_run_stage2.py -v`
Expected: PASS for all tests in the file.

- [ ] **Step 6: Static check for the removed dead code**

Run: `grep -n "Claimed but not finished" scripts/run_stage2.sh; echo "exit=$?"`
Expected: no match, `exit=1` (grep's not-found exit code) — confirms the dead branch and its stale comment are gone.

- [ ] **Step 7: Commit**

```bash
git add scripts/run_stage2.sh tests/test_run_stage2.py
git commit -m "fix: remove dead code path, scope claim commit, log resume-scan skips"
```

---

### Task 7: `assert_in_worktree` also checks `HEAD`

**Files:**
- Modify: `scripts/run_stage2.sh` (`assert_in_worktree` function)
- Modify: `tests/test_run_stage2_helpers.py` (append tests)

**Interfaces:** none beyond what Task 1 established.

- [ ] **Step 1: Write failing tests**

Append to `tests/test_run_stage2_helpers.py`:

```python
import subprocess as sp


def _init_scratch_repo(tmp_path):
    repo = (tmp_path / "repo").resolve()
    repo.mkdir()
    sp.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    sp.run(["git", "config", "user.email", "t@t.com"], cwd=repo, check=True)
    sp.run(["git", "config", "user.name", "T"], cwd=repo, check=True)
    (repo / "f.txt").write_text("x\n")
    sp.run(["git", "add", "-A"], cwd=repo, check=True)
    sp.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)
    sp.run(["git", "checkout", "-q", "-b", "item/1-foo"], cwd=repo, check=True)
    return repo


def test_assert_in_worktree_passes_when_toplevel_and_head_match(tmp_path):
    repo = _init_scratch_repo(tmp_path)
    result = sp.run(
        ["bash", "-c", f'source "{SCRIPT}" && WORKTREE_DIR="{repo}" BRANCH="item/1-foo" assert_in_worktree'],
        cwd=repo, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr


def test_assert_in_worktree_fails_when_head_does_not_match_expected_branch(tmp_path):
    repo = _init_scratch_repo(tmp_path)
    result = sp.run(
        ["bash", "-c", f'source "{SCRIPT}" && WORKTREE_DIR="{repo}" BRANCH="item/1-different" assert_in_worktree'],
        cwd=repo, capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "item/1-different" in result.stderr
```

- [ ] **Step 2: Run them to verify the second one fails**

Run: `pytest tests/test_run_stage2_helpers.py -v`
Expected: `test_assert_in_worktree_passes_when_toplevel_and_head_match` PASSES already (today's `assert_in_worktree` only checks toplevel, which does match here). `test_assert_in_worktree_fails_when_head_does_not_match_expected_branch` FAILS — today's function has no `HEAD` check at all, so it returns 0 even though `HEAD` (`item/1-foo`) doesn't match the asserted `BRANCH` (`item/1-different`).

- [ ] **Step 3: Fix it**

In `scripts/run_stage2.sh`, find:

```bash
assert_in_worktree() {
  local top
  top="$(git rev-parse --show-toplevel)"
  if [ "$top" != "$WORKTREE_DIR" ]; then
    echo "$(date): expected git toplevel $WORKTREE_DIR but got $top, aborting" >&2
    exit 1
  fi
}
```

Replace with:

```bash
assert_in_worktree() {
  local top head
  top="$(git rev-parse --show-toplevel)"
  if [ "$top" != "$WORKTREE_DIR" ]; then
    echo "$(date): expected git toplevel $WORKTREE_DIR but got $top, aborting" >&2
    exit 1
  fi
  head="$(git rev-parse --abbrev-ref HEAD)"
  if [ "$head" != "$BRANCH" ]; then
    echo "$(date): expected HEAD on branch $BRANCH but got $head, aborting" >&2
    exit 1
  fi
}
```

- [ ] **Step 4: Run the tests again to verify they pass**

Run: `pytest tests/test_run_stage2_helpers.py -v`
Expected: PASS for both.

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `pytest -v`
Expected: PASS for every test (`run_stage2.sh`'s own call sites always set `WORKTREE_DIR` and `BRANCH` correctly before calling `assert_in_worktree`, so the new `HEAD` check is a no-op for every existing passing path).

- [ ] **Step 6: Commit**

```bash
git add scripts/run_stage2.sh tests/test_run_stage2_helpers.py
git commit -m "fix: assert_in_worktree also verifies HEAD is on the expected branch"
```
